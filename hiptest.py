import base64
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Track recently used videos to avoid repeats
HISTORY_FILE = Path("/tmp/.hiptest_history.json")
MAX_HISTORY = 50

# Output bucket for training samples
SAMPLES_BUCKET = "video-samples"


def load_history() -> list[str]:
    """Load list of recently used video keys."""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_history(history: list[str]) -> None:
    """Save list of recently used video keys."""
    HISTORY_FILE.write_text(json.dumps(history[-MAX_HISTORY:]))


def ensure_bucket_exists(client, bucket_name: str) -> None:
    """Create bucket if it doesn't exist."""
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        print(f"   Created bucket: {bucket_name}")
    else:
        print(f"   Bucket exists: {bucket_name}")


def upload_sample(
    client,
    sample_id: str,
    files: dict[str, str],
    metadata: dict,
) -> str:
    """
    Upload a complete sample to the video-samples bucket.
    
    Args:
        client: Minio client
        sample_id: Unique identifier for this sample (e.g., "2024-01-29_12-34-56")
        files: Dict mapping filename to local path (e.g., {"original_clip.mp4": "/tmp/clip.mp4"})
        metadata: Dict with all sample metadata
    
    Returns:
        The S3 prefix where files were uploaded
    """
    prefix = f"{sample_id}"
    
    # Upload each file
    for filename, local_path in files.items():
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            object_name = f"{prefix}/{filename}"
            client.fput_object(SAMPLES_BUCKET, object_name, local_path)
            size_kb = os.path.getsize(local_path) / 1024
            print(f"   Uploaded: {object_name} ({size_kb:.1f} KB)")
    
    # Upload metadata as JSON
    metadata_json = json.dumps(metadata, indent=2)
    metadata_path = "/tmp/metadata.json"
    with open(metadata_path, "w") as f:
        f.write(metadata_json)
    
    object_name = f"{prefix}/metadata.json"
    client.fput_object(SAMPLES_BUCKET, object_name, metadata_path)
    print(f"   Uploaded: {object_name}")
    
    return prefix


def extract_frames(video_path: str, output_dir: str, max_frames: int = 6) -> list[str]:
    """Extract frames from a video for GPT-4o analysis."""
    os.makedirs(output_dir, exist_ok=True)
    for f in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, f))
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vf", "fps=2", "-frames:v", str(max_frames),
         "-q:v", "2", f"{output_dir}/frame_%02d.jpg"],
        capture_output=True,
    )
    return sorted([os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".jpg")])


def frames_to_base64(frame_paths: list[str]) -> list[dict]:
    """Convert frame files to base64 image content for OpenAI."""
    content = []
    for path in frame_paths:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    return content


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def forced_choice_comparison(client, frames_original: list[dict], frames_generated: list[dict], prompt: str) -> dict:
    """
    Force GPT to choose which video looks MORE REAL and matches the prompt better.
    Randomizes presentation order to avoid position bias, returns normalized result.
    """
    # Randomize order to prevent position bias
    swap = random.choice([True, False])
    
    if swap:
        first_frames, second_frames = frames_generated, frames_original
    else:
        first_frames, second_frames = frames_original, frames_generated

    content = [{"type": "text", "text": f"""You are a video authenticity judge. One video is REAL footage, one is AI-GENERATED from the real video's first frame.

The AI was given this prompt to generate video from the first frame:
"{prompt}"

VIDEO 1 - frames in sequence:"""}] + first_frames + [{"type": "text", "text": """

VIDEO 2 - frames in sequence:"""}] + second_frames + [{"type": "text", "text": """

Judge which video looks MORE REAL based on:
- Temporal consistency (do objects/faces stay stable across frames?)
- Motion naturalness (realistic movement vs warping/morphing?)
- Fine details (hands, text, edges - sharp or blurry/distorted?)
- Lighting consistency across frames
- How well it matches the prompt description

YOU MUST CHOOSE ONE. No ties. Pick the video that looks more like real footage.

Respond with ONLY this JSON:
{"winner": 1 or 2, "confidence": 50-100, "video1_artifacts": ["artifacts in video 1"], "video2_artifacts": ["artifacts in video 2"], "reasoning": "one sentence why winner looks more real"}"""}]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=300,
    )
    
    text = response.choices[0].message.content.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    
    try:
        result = json.loads(text)
        winner_num = result.get("winner")
        
        # Normalize: determine if original or generated won
        if swap:
            # Video 1 = generated, Video 2 = original
            original_won = winner_num == 2
            original_artifacts = result.get("video2_artifacts", [])
            generated_artifacts = result.get("video1_artifacts", [])
        else:
            # Video 1 = original, Video 2 = generated
            original_won = winner_num == 1
            original_artifacts = result.get("video1_artifacts", [])
            generated_artifacts = result.get("video2_artifacts", [])
        
        return {
            "original_won": original_won,
            "generated_won": not original_won,
            "confidence": result.get("confidence", 50),
            "original_artifacts": original_artifacts,
            "generated_artifacts": generated_artifacts,
            "reasoning": result.get("reasoning", ""),
            "presentation_order": f"{'generated' if swap else 'original'} shown first",
        }
    except json.JSONDecodeError:
        return {"original_won": True, "generated_won": False, "confidence": 0, "reasoning": f"Parse error: {text[:100]}"}


def get_description(client, frames: list[dict]) -> str:
    """Get video description optimized for I2V generation."""
    content = [{"type": "text", "text": """Describe this video for an image-to-video AI model. Focus on:
- Subject appearance and position
- Camera movement (static, pan, zoom)
- Motion and action
- Lighting and style

Be concise. 2-3 sentences max."""}] + frames

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()


def main() -> None:
    start_time = time.time()
    
    try:
        from minio import Minio
        import requests
        from openai import OpenAI
    except ImportError:
        print("Install deps: uv pip install minio requests openai", file=sys.stderr)
        sys.exit(1)

    # Auth setup
    seed_phrase = os.environ.get(
        "HIPPIUS_SEED_PHRASE",
        "race hungry company town transfer review horn base flip joke hour moral",
    )
    bucket = os.environ.get("HIPPIUS_BUCKET", "lot-of-videos")
    chutes_api_key = os.environ.get("CHUTES_API_KEY")
    openai_api_key = os.environ.get("OPENAI_API_KEY")

    if not chutes_api_key:
        print("CHUTES_API_KEY env var required", file=sys.stderr)
        sys.exit(1)
    if not openai_api_key:
        print("OPENAI_API_KEY env var required", file=sys.stderr)
        sys.exit(1)

    access_key = base64.b64encode(seed_phrase.encode("utf-8")).decode("utf-8")
    minio_client = Minio(
        "s3.hippius.com",
        access_key=access_key,
        secret_key=seed_phrase,
        secure=True,
        region="decentralized",
    )
    openai_client = OpenAI(api_key=openai_api_key)

    # Generate unique sample ID for this run
    sample_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Ensure output bucket exists
    print(f"0. Ensuring output bucket '{SAMPLES_BUCKET}' exists...")
    ensure_bucket_exists(minio_client, SAMPLES_BUCKET)

    # 1. List all videos and pick a random NEW one
    print("1. Listing videos in bucket...")
    all_objects = list(minio_client.list_objects(bucket, recursive=True))
    
    # Filter: .mp4 files, non-zero size, reasonable size (< 200MB to avoid long downloads)
    MIN_SIZE = 1_000_000  # 1MB minimum
    MAX_SIZE = 200_000_000  # 200MB maximum
    video_objects = [
        obj for obj in all_objects 
        if obj.object_name.endswith(".mp4") 
        and MIN_SIZE < obj.size < MAX_SIZE
    ]
    
    if not video_objects:
        print("No suitable videos found in bucket", file=sys.stderr)
        sys.exit(1)
    
    # Load history and filter out recently used videos
    history = load_history()
    available = [obj for obj in video_objects if obj.object_name not in history]
    
    # If all videos used, reset history but keep last few
    if not available:
        print("   All videos used, resetting history...")
        history = history[-5:]  # Keep last 5 to avoid immediate repeat
        available = [obj for obj in video_objects if obj.object_name not in history]
    
    # Pick random video
    chosen = random.choice(available)
    test_key = chosen.object_name
    file_size_mb = chosen.size / 1_000_000
    
    # Update history
    history.append(test_key)
    save_history(history)
    
    print(f"   Selected: {test_key}")
    print(f"   Size: {file_size_mb:.1f} MB (from {len(video_objects)} videos, {len(available)} unused)")

    # Paths
    video_path = "/tmp/test_video.mp4"
    frame_path = "/tmp/first_frame.png"
    original_frames_dir = "/tmp/original_frames"
    generated_frames_dir = "/tmp/generated_frames"
    generated_path = "/tmp/generated_video.mp4"
    stitched_path = "/tmp/stitched_video.mp4"
    clip_path = "/tmp/original_clip.mp4"

    # 2. Download video from Hippius
    print(f"2. Downloading video...")
    dl_start = time.time()
    minio_client.fget_object(bucket, test_key, video_path)
    dl_time = time.time() - dl_start
    print(f"   Downloaded {os.path.getsize(video_path):,} bytes in {dl_time:.1f}s")

    # 3. Get video duration and extract a random 5-second clip
    duration = get_video_duration(video_path)
    if duration < 5:
        print(f"   Video too short ({duration:.1f}s), skipping...", file=sys.stderr)
        sys.exit(1)
    
    # Random start time (not at the very beginning or end)
    max_start = max(0, duration - 8)
    start_offset = random.uniform(min(2, max_start), max_start) if max_start > 2 else 0
    
    print(f"3. Extracting 5s clip from {start_offset:.1f}s (video is {duration:.1f}s)...")
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start_offset), "-i", video_path, 
         "-t", "5", "-c:v", "libx264", "-crf", "23", "-an", clip_path],
        capture_output=True,
    )

    # 4. Extract first frame for I2V input
    print("4. Extracting first frame for I2V...")
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start_offset), "-i", video_path, 
         "-vframes", "1", "-q:v", "2", frame_path],
        capture_output=True,
    )

    # 5. Extract frames from original clip
    print("5. Extracting frames from original clip...")
    original_frames = extract_frames(clip_path, original_frames_dir, max_frames=6)
    original_frames_b64 = frames_to_base64(original_frames)
    
    if len(original_frames) < 3:
        print(f"   Not enough frames extracted ({len(original_frames)}), skipping...", file=sys.stderr)
        sys.exit(1)
    print(f"   Extracted {len(original_frames)} frames")

    # 6. Get video description
    print("6. Getting video description from GPT-4o...")
    desc_start = time.time()
    description = get_description(openai_client, original_frames_b64)
    desc_time = time.time() - desc_start
    print(f"   Description ({desc_time:.1f}s): {description[:80]}...")

    # 7. Generate video with Chutes I2V
    print("7. Calling Chutes I2V (this may take ~30-60s)...")
    gen_start = time.time()
    with open(frame_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    response = requests.post(
        "https://chutes-wan-2-2-i2v-14b-fast.chutes.ai/generate",
        headers={
            "Authorization": f"Bearer {chutes_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "prompt": description,
            "image": image_b64,
            "fps": 16,
            "frames": 81,
            "resolution": "480p",
            "fast": True,
        },
        timeout=300,
    )
    gen_time = time.time() - gen_start

    if response.status_code != 200:
        print(f"   Error: {response.status_code} - {response.text}", file=sys.stderr)
        sys.exit(1)

    with open(generated_path, "wb") as f:
        f.write(response.content)
    print(f"   Generated video: {len(response.content):,} bytes in {gen_time:.1f}s")

    # 8. Extract frames from generated
    print("8. Extracting frames from generated video...")
    generated_frames = extract_frames(generated_path, generated_frames_dir, max_frames=6)
    generated_frames_b64 = frames_to_base64(generated_frames)

    # 9. SINGLE forced-choice comparison (randomized order)
    print("9. Forced choice comparison (order randomized)...")
    cmp_start = time.time()
    comparison = forced_choice_comparison(
        openai_client, 
        original_frames_b64,
        generated_frames_b64,
        prompt=description
    )
    cmp_time = time.time() - cmp_start
    print(f"   Comparison complete in {cmp_time:.1f}s")

    # 10. Stitch videos side-by-side
    print("10. Stitching videos side-by-side...")
    subprocess.run(
        ["ffmpeg", "-y", "-i", clip_path, "-i", generated_path,
         "-filter_complex", 
         "[0:v]scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2[left];"
         "[1:v]scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2[right];"
         "[left][right]hstack=inputs=2",
         "-c:v", "libx264", "-crf", "23", "-an", stitched_path],
        capture_output=True,
    )
    stitched_size = os.path.getsize(stitched_path) if os.path.exists(stitched_path) else 0
    print(f"    Stitched video: {stitched_size:,} bytes")

    # 11. Build metadata and upload sample to Hippius
    total_time = time.time() - start_time
    generated_wins = comparison.get("generated_won", False)
    confidence = comparison.get("confidence", 0)
    
    # Get file sizes for metadata
    clip_size = os.path.getsize(clip_path) if os.path.exists(clip_path) else 0
    generated_size = os.path.getsize(generated_path) if os.path.exists(generated_path) else 0
    frame_size = os.path.getsize(frame_path) if os.path.exists(frame_path) else 0
    
    metadata = {
        "sample_id": sample_id,
        "created_at": datetime.now().isoformat(),
        
        # Source video information
        "source": {
            "bucket": bucket,
            "key": test_key,
            "full_duration_seconds": duration,
            "clip_start_seconds": start_offset,
            "clip_end_seconds": start_offset + 5,
            "clip_duration_seconds": 5,
        },
        
        # Description generation (GPT-4o)
        "description": {
            "model": "gpt-4o",
            "prompt_used": "Describe this video for an image-to-video AI model...",
            "output": description,
            "generation_time_seconds": desc_time,
        },
        
        # Video generation (Chutes I2V)
        "generation": {
            "model": "Wan-2.2-I2V-14B-Fast",
            "model_endpoint": "https://chutes-wan-2-2-i2v-14b-fast.chutes.ai/generate",
            "input_prompt": description,
            "parameters": {
                "fps": 16,
                "frames": 81,
                "resolution": "480p",
                "fast": True,
            },
            "generation_time_seconds": gen_time,
        },
        
        # Evaluation (GPT-4o forced choice)
        "evaluation": {
            "model": "gpt-4o",
            "method": "forced_choice_comparison",
            "presentation_order": comparison.get("presentation_order", "unknown"),
            "winner": "generated" if generated_wins else "original",
            "generated_wins": generated_wins,
            "confidence": confidence,
            "reasoning": comparison.get("reasoning", ""),
            "original_artifacts": comparison.get("original_artifacts", []),
            "generated_artifacts": comparison.get("generated_artifacts", []),
            "comparison_time_seconds": cmp_time,
        },
        
        # Training signal (easy access for ML)
        "training_signal": {
            "label": 1 if generated_wins else 0,  # 1 = generated won, 0 = original won
            "generated_wins": generated_wins,
            "confidence": confidence,
            "is_positive_example": generated_wins,  # True if generated fooled detector
        },
        
        # Files included in this sample
        "files": {
            "original_clip": {
                "filename": "original_clip.mp4",
                "description": "5-second clip from source video",
                "size_bytes": clip_size,
            },
            "generated_video": {
                "filename": "generated_video.mp4",
                "description": "AI-generated video from first frame + prompt",
                "size_bytes": generated_size,
            },
            "first_frame": {
                "filename": "first_frame.png",
                "description": "Input image for I2V generation",
                "size_bytes": frame_size,
            },
            "stitched_comparison": {
                "filename": "stitched_comparison.mp4",
                "description": "Side-by-side comparison (original left, generated right)",
                "size_bytes": stitched_size,
            },
            "metadata": {
                "filename": "metadata.json",
                "description": "This file - all sample metadata",
            },
        },
        
        # Timing breakdown
        "timing": {
            "total_seconds": total_time,
            "download_seconds": dl_time,
            "description_seconds": desc_time,
            "generation_seconds": gen_time,
            "comparison_seconds": cmp_time,
        },
        
        # Models used (summary)
        "models": {
            "description_model": "gpt-4o",
            "generation_model": "Wan-2.2-I2V-14B-Fast",
            "evaluation_model": "gpt-4o",
        },
    }
    
    print("11. Uploading sample to Hippius...")
    upload_start = time.time()
    sample_prefix = upload_sample(
        minio_client,
        sample_id,
        files={
            "original_clip.mp4": clip_path,
            "generated_video.mp4": generated_path,
            "first_frame.png": frame_path,
            "stitched_comparison.mp4": stitched_path,
        },
        metadata=metadata,
    )
    upload_time = time.time() - upload_start
    print(f"   Sample uploaded to s3://{SAMPLES_BUCKET}/{sample_prefix}/ in {upload_time:.1f}s")
    
    # 12. Print results
    print("\n" + "=" * 70)
    print("FORCED CHOICE RESULT")
    print("=" * 70)
    print(f"\nSample ID: {sample_id}")
    print(f"Video: {test_key}")
    print(f"Clip: {start_offset:.1f}s - {start_offset + 5:.1f}s of {duration:.1f}s")
    print(f"Prompt: {description}")
    print(f"\nPresentation: {comparison.get('presentation_order', 'unknown')} (randomized)")
    print(f"Winner: {'GENERATED' if generated_wins else 'ORIGINAL'}")
    print(f"Confidence: {confidence}%")
    print(f"Reasoning: {comparison.get('reasoning', 'N/A')}")
    print(f"\nOriginal artifacts: {comparison.get('original_artifacts', [])}")
    print(f"Generated artifacts: {comparison.get('generated_artifacts', [])}")
    
    print(f"\n" + "=" * 70)
    print("TRAINING SIGNAL")
    print("=" * 70)
    print(f"  sample_id = \"{sample_id}\"")
    print(f"  video_key = \"{test_key}\"")
    print(f"  generated_wins = {generated_wins}")
    print(f"  confidence = {confidence}")
    print(f"  Result: {'✓ POSITIVE EXAMPLE (generated fooled detector)' if generated_wins else '✗ NEGATIVE EXAMPLE (original won)'}")
    print(f"\n  Total time: {total_time:.1f}s (download: {dl_time:.1f}s, generate: {gen_time:.1f}s, compare: {cmp_time:.1f}s, upload: {upload_time:.1f}s)")
    print(f"  Saved to: s3://{SAMPLES_BUCKET}/{sample_prefix}/")
    print("=" * 70)

    # 13. Play stitched video
    if stitched_size > 0:
        print("\n13. Playing stitched video (original left, generated right)...")
        subprocess.run(["open", stitched_path])


if __name__ == "__main__":
    main()
