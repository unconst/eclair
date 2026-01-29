"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ECLAIR - IMAGE-TO-VIDEO VALIDATOR                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  MECHANISM OVERVIEW                                                          ║
║  ──────────────────                                                          ║
║  Miners run image-to-video (I2V) generators and commit their chute slugs to  ║
║  chain. Validators sample clips from a Hippius S3 bucket, extract the first  ║
║  frame, generate a description via GPT-4o, and challenge miners to generate  ║
║  video from the frame+prompt. Scoring uses GPT-4o forced-choice comparison.  ║
║  Winner takes all based on highest win rate vs original clips.               ║
║                                                                              ║
║  DATA FLOW                                                                   ║
║  ─────────────────                                                           ║
║  1. Download random video from Hippius "lot-of-videos" bucket                ║
║  2. Extract 5s clip and first frame                                          ║
║  3. Generate prompt via GPT-4o description                                   ║
║  4. Query each miner's I2V model (or placeholder)                            ║
║  5. Score each miner vs original using GPT-4o forced choice                  ║
║  6. Upload sample (all videos + metadata) to "video-samples" bucket          ║
║  7. Calculate win rates from samples, set weights (winner takes all)         ║
║                                                                              ║
║  MINER ENDPOINTS                                                             ║
║  ───────────────                                                             ║
║  Miners commit JSON to chain: {"generator_chute": "<chute_slug>"}            ║
║                                                                              ║
║  SCORING CRITERIA                                                            ║
║  ─────────────────                                                           ║
║  GPT-4o forced choice: which video (original vs generated) looks more real?  ║
║  Win = 1 if generated video chosen as more real. Winner takes all weights.   ║
║                                                                              ║
║  STORAGE                                                                     ║
║  ───────                                                                     ║
║  - Source videos: Hippius S3 "lot-of-videos" bucket                          ║
║  - Training samples: Hippius S3 "video-samples" bucket                       ║
║    Each sample includes: original clip, miner videos, metadata.json          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import random
import asyncio
import base64
import subprocess
import aiohttp
import bittensor as bt
from minio import Minio
from openai import AsyncOpenAI
from typing import Dict, List, Any
from datetime import datetime


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              CONFIGURATION                                 ║
# ╚════════════════════════════════════════════════════════════════════════════╝

NETUID = 120
EPOCH_LEN = 30  # Set weights every 30 blocks (~6 minutes)
REQUEST_TIMEOUT = 300
SCORING_SLEEP = 60  # Time between sample generation rounds
MIN_SAMPLES_TO_CHALLENGE = 12
EPSILON_BEAT = 0.05

CHUTES_API_URL = os.environ.get("CHUTES_API_URL", "https://api.chutes.ai")
CHUTES_API_KEY = os.environ.get("CHUTES_API_KEY")

WALLET_NAME = os.environ.get("WALLET_NAME", "default")
HOTKEY_NAME = os.environ.get("HOTKEY_NAME", "default")
NETWORK = os.environ.get("NETWORK", "finney")

# Hippius S3 configuration
HIPPIUS_SEED_PHRASE = os.environ.get(
    "HIPPIUS_SEED_PHRASE",
    "race hungry company town transfer review horn base flip joke hour moral",
)
SOURCE_BUCKET = os.environ.get("HIPPIUS_SOURCE_BUCKET", "lot-of-videos")
SAMPLES_BUCKET = os.environ.get("HIPPIUS_SAMPLES_BUCKET", "video-samples")

# OpenAI configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Video generation placeholder model
PLACEHOLDER_I2V_ENDPOINT = "https://chutes-wan-2-2-i2v-14b-fast.chutes.ai/generate"

# Video processing settings
MIN_VIDEO_SIZE = 1_000_000  # 1MB minimum
MAX_VIDEO_SIZE = 200_000_000  # 200MB maximum
CLIP_DURATION = 5  # seconds

# Track recently used videos to avoid repeats (in-memory)
USED_VIDEOS: List[str] = []
MAX_VIDEO_HISTORY = 50


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              LOGGING UTILITIES                             ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def log(msg: str, level: str = "info"):
    """Pretty-print timestamped log messages with color-coded prefixes."""
    ts = datetime.now().strftime("%H:%M:%S")
    prefixes = {
        "info": f"\033[90m{ts}\033[0m \033[36m▸\033[0m",
        "success": f"\033[90m{ts}\033[0m \033[32m✓\033[0m",
        "error": f"\033[90m{ts}\033[0m \033[31m✗\033[0m",
        "warn": f"\033[90m{ts}\033[0m \033[33m⚠\033[0m",
        "start": f"\033[90m{ts}\033[0m \033[33m→\033[0m",
    }
    print(f"{prefixes.get(level, f'\033[90m{ts}\033[0m  ')} {msg}")


def log_header(title: str):
    """Print a bold section header."""
    print(f"\n\033[1m{'─' * 60}\033[0m\n\033[1m{title}\033[0m\n\033[1m{'─' * 60}\033[0m\n")


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              HIPPIUS S3 UTILITIES                          ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def create_minio_client() -> Minio:
    """Create a Minio client for Hippius S3."""
    access_key = base64.b64encode(HIPPIUS_SEED_PHRASE.encode("utf-8")).decode("utf-8")
    return Minio(
        "s3.hippius.com",
        access_key=access_key,
        secret_key=HIPPIUS_SEED_PHRASE,
        secure=True,
        region="decentralized",
    )


async def ensure_bucket_exists(minio_client: Minio, bucket_name: str) -> None:
    """Create bucket if it doesn't exist."""
    exists = await asyncio.to_thread(minio_client.bucket_exists, bucket_name)
    if not exists:
        await asyncio.to_thread(minio_client.make_bucket, bucket_name)
        log(f"Created bucket: {bucket_name}", "success")


async def upload_sample(
    minio_client: Minio,
    sample_id: str,
    files: Dict[str, str],
    metadata: Dict[str, Any],
) -> str:
    """Upload a complete sample to the video-samples bucket."""
    prefix = sample_id
    
    # Upload each file
    for filename, local_path in files.items():
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            object_name = f"{prefix}/{filename}"
            await asyncio.to_thread(
                minio_client.fput_object, SAMPLES_BUCKET, object_name, local_path
            )
            size_kb = os.path.getsize(local_path) / 1024
            log(f"Uploaded: {object_name} ({size_kb:.1f} KB)", "info")
    
    # Upload metadata as JSON
    metadata_json = json.dumps(metadata, indent=2)
    metadata_path = f"/tmp/metadata_{sample_id}.json"
    with open(metadata_path, "w") as f:
        f.write(metadata_json)
    
    object_name = f"{prefix}/metadata.json"
    await asyncio.to_thread(
        minio_client.fput_object, SAMPLES_BUCKET, object_name, metadata_path
    )
    log(f"Uploaded: {object_name}", "info")
    
    # Cleanup temp metadata file
    os.remove(metadata_path)
    
    return prefix


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              VIDEO PROCESSING                              ║
# ╚════════════════════════════════════════════════════════════════════════════╝

async def extract_frames(video_path: str, output_dir: str, max_frames: int = 6) -> List[str]:
    """Extract frames from a video for GPT-4o analysis."""
    os.makedirs(output_dir, exist_ok=True)
    # Clear existing frames
    for f in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, f))
    
    await asyncio.to_thread(
        subprocess.run,
        ["ffmpeg", "-y", "-i", video_path, "-vf", "fps=2", "-frames:v", str(max_frames),
         "-q:v", "2", f"{output_dir}/frame_%02d.jpg"],
        capture_output=True,
    )
    return sorted([os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".jpg")])


def frames_to_base64(frame_paths: List[str]) -> List[Dict[str, Any]]:
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


async def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = await asyncio.to_thread(
        subprocess.run,
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


async def extract_clip(video_path: str, output_path: str, start_offset: float, duration: float) -> None:
    """Extract a clip from a video using ffmpeg."""
    await asyncio.to_thread(
        subprocess.run,
        ["ffmpeg", "-y", "-ss", str(start_offset), "-i", video_path,
         "-t", str(duration), "-c:v", "libx264", "-crf", "23", "-an", output_path],
        capture_output=True,
    )


async def extract_first_frame(video_path: str, output_path: str, start_offset: float = 0) -> None:
    """Extract the first frame from a video."""
    await asyncio.to_thread(
        subprocess.run,
        ["ffmpeg", "-y", "-ss", str(start_offset), "-i", video_path,
         "-vframes", "1", "-q:v", "2", output_path],
        capture_output=True,
    )


async def stitch_videos_side_by_side(left_path: str, right_path: str, output_path: str) -> None:
    """Stitch two videos side-by-side for comparison."""
    await asyncio.to_thread(
        subprocess.run,
        ["ffmpeg", "-y", "-i", left_path, "-i", right_path,
         "-filter_complex",
         "[0:v]scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2[left];"
         "[1:v]scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2[right];"
         "[left][right]hstack=inputs=2",
         "-c:v", "libx264", "-crf", "23", "-an", output_path],
        capture_output=True,
    )


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              GPT-4O EVALUATION                             ║
# ╚════════════════════════════════════════════════════════════════════════════╝

async def get_description_async(openai_client: AsyncOpenAI, frames: List[Dict[str, Any]]) -> str:
    """Get video description optimized for I2V generation using GPT-4o."""
    content = [{"type": "text", "text": """Describe this video for an image-to-video AI model. Focus on:
- Subject appearance and position
- Camera movement (static, pan, zoom)
- Motion and action
- Lighting and style

Be concise. 2-3 sentences max."""}] + frames

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()


async def forced_choice_comparison_async(
    openai_client: AsyncOpenAI,
    frames_original: List[Dict[str, Any]],
    frames_generated: List[Dict[str, Any]],
    prompt: str,
) -> Dict[str, Any]:
    """
    Force GPT to choose which video looks MORE REAL.
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

    response = await openai_client.chat.completions.create(
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
        return {
            "original_won": True,
            "generated_won": False,
            "confidence": 0,
            "original_artifacts": [],
            "generated_artifacts": [],
            "reasoning": f"Parse error: {text[:100]}",
            "presentation_order": "unknown",
        }


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              CHAIN UTILITIES                               ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def _parse_commit(commit_value: str) -> Dict[str, Any]:
    """Parse a miner's chain commitment to extract their chute slug."""
    if not commit_value:
        return {}
    try:
        parsed = json.loads(commit_value)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {"generator_chute": str(commit_value).strip()}


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              SAMPLE GENERATION                             ║
# ╚════════════════════════════════════════════════════════════════════════════╝

async def pick_random_video(minio_client: Minio) -> str | None:
    """Pick a random video from the source bucket, avoiding recently used ones."""
    global USED_VIDEOS
    
    # List all videos in source bucket
    objects = await asyncio.to_thread(
        lambda: list(minio_client.list_objects(SOURCE_BUCKET, recursive=True))
    )
    
    # Filter for suitable videos
    video_objects = [
        obj for obj in objects
        if obj.object_name.endswith(".mp4")
        and MIN_VIDEO_SIZE < obj.size < MAX_VIDEO_SIZE
    ]
    
    if not video_objects:
        log("No suitable videos found in source bucket", "warn")
        return None
    
    # Filter out recently used videos
    available = [obj for obj in video_objects if obj.object_name not in USED_VIDEOS]
    
    # Reset history if all videos used
    if not available:
        log("All videos used, resetting history...", "info")
        USED_VIDEOS = USED_VIDEOS[-5:]
        available = [obj for obj in video_objects if obj.object_name not in USED_VIDEOS]
    
    # Pick random video
    chosen = random.choice(available)
    USED_VIDEOS.append(chosen.object_name)
    if len(USED_VIDEOS) > MAX_VIDEO_HISTORY:
        USED_VIDEOS = USED_VIDEOS[-MAX_VIDEO_HISTORY:]
    
    return chosen.object_name


async def generate_video_placeholder(
    session: aiohttp.ClientSession,
    image_b64: str,
    prompt: str,
) -> bytes | None:
    """Generate a video using the placeholder I2V model (Wan-2.2-I2V-14B-Fast)."""
    try:
        async with session.post(
            PLACEHOLDER_I2V_ENDPOINT,
            headers={
                "Authorization": f"Bearer {CHUTES_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "image": image_b64,
                "fps": 16,
                "frames": 81,
                "resolution": "480p",
                "fast": True,
            },
            timeout=aiohttp.ClientTimeout(total=300),
        ) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                log(f"I2V generation failed: {resp.status}", "warn")
                return None
    except Exception as e:
        log(f"I2V generation error: {e}", "warn")
        return None


async def generate_samples_continuously(
    subtensor: bt.AsyncSubtensor,
    minio_client: Minio,
    openai_client: AsyncOpenAI,
):
    """Continuously generate samples: download video, query miners, score, upload to Hippius."""
    import time
    
    # Ensure output bucket exists
    await ensure_bucket_exists(minio_client, SAMPLES_BUCKET)
    log(f"Sample generation loop starting (interval={SCORING_SLEEP}s)", "start")
    
    round_num = 0
    while True:
        round_num += 1
        round_start = time.time()
        try:
            log_header(f"Sample Generation Round #{round_num}")
            
            # 1. Get miners from chain
            current_block = await subtensor.get_current_block()
            commits = await subtensor.get_all_revealed_commitments(NETUID, block=current_block)
            
            if not commits:
                log("No miner commitments found", "warn")
                await asyncio.sleep(SCORING_SLEEP)
                continue
            
            miners = {}
            for hotkey, commit_data in commits.items():
                commit_block, commit_value = commit_data[-1]
                parsed = _parse_commit(commit_value)
                chute = parsed.get("generator_chute")
                if not chute:
                    continue
                miners[hotkey] = {"slug": chute, "block": commit_block}
            
            if not miners:
                log("No valid miner chutes found", "warn")
                await asyncio.sleep(SCORING_SLEEP)
                continue
            
            log(f"Found {len(miners)} miners with chutes", "info")
            
            # 2. Download random video from Hippius
            video_key = await pick_random_video(minio_client)
            if not video_key:
                await asyncio.sleep(SCORING_SLEEP)
                continue
            
            log(f"Selected video: {video_key}", "info")
            
            sample_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            video_path = f"/tmp/source_video_{sample_id}.mp4"
            clip_path = f"/tmp/original_clip_{sample_id}.mp4"
            frame_path = f"/tmp/first_frame_{sample_id}.png"
            original_frames_dir = f"/tmp/original_frames_{sample_id}"
            
            await asyncio.to_thread(
                minio_client.fget_object, SOURCE_BUCKET, video_key, video_path
            )
            log(f"Downloaded video: {os.path.getsize(video_path):,} bytes", "info")
            
            # 3. Get video duration and extract clip
            duration = await get_video_duration(video_path)
            if duration < CLIP_DURATION:
                log(f"Video too short ({duration:.1f}s), skipping", "warn")
                os.remove(video_path)
                await asyncio.sleep(SCORING_SLEEP)
                continue
            
            max_start = max(0, duration - CLIP_DURATION - 3)
            start_offset = random.uniform(min(2, max_start), max_start) if max_start > 2 else 0
            
            await extract_clip(video_path, clip_path, start_offset, CLIP_DURATION)
            await extract_first_frame(video_path, frame_path, start_offset)
            log(f"Extracted {CLIP_DURATION}s clip from {start_offset:.1f}s", "info")
            
            # 4. Extract frames and get description via GPT-4o
            original_frames = await extract_frames(clip_path, original_frames_dir, max_frames=6)
            if len(original_frames) < 3:
                log("Not enough frames extracted, skipping", "warn")
                os.remove(video_path)
                await asyncio.sleep(SCORING_SLEEP)
                continue
            
            original_frames_b64 = frames_to_base64(original_frames)
            description = await get_description_async(openai_client, original_frames_b64)
            log(f"Description: {description[:80]}...", "info")
            
            # 5. Generate video for each miner (placeholder: same video for all)
            # In the future, each miner's chute would be called here
            with open(frame_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
            
            async with aiohttp.ClientSession() as session:
                # Generate one video (placeholder for all miners)
                log("Generating video via placeholder I2V model...", "info")
                generated_video_bytes = await generate_video_placeholder(session, image_b64, description)
                
                if not generated_video_bytes:
                    log("Failed to generate video, skipping sample", "warn")
                    os.remove(video_path)
                    await asyncio.sleep(SCORING_SLEEP)
                    continue
            
            # 6. Score each miner's video against original
            miner_results = {}
            files_to_upload = {
                "original_clip.mp4": clip_path,
                "first_frame.png": frame_path,
            }
            
            for hotkey, miner_info in miners.items():
                hotkey_short = hotkey[:8]
                miner_video_path = f"/tmp/miner_{hotkey_short}_{sample_id}.mp4"
                miner_frames_dir = f"/tmp/miner_frames_{hotkey_short}_{sample_id}"
                
                # Save the generated video (same for all miners in placeholder mode)
                with open(miner_video_path, "wb") as f:
                    f.write(generated_video_bytes)
                
                # Extract frames from generated video
                generated_frames = await extract_frames(miner_video_path, miner_frames_dir, max_frames=6)
                generated_frames_b64 = frames_to_base64(generated_frames)
                
                # Score via GPT-4o forced choice
                comparison = await forced_choice_comparison_async(
                    openai_client,
                    original_frames_b64,
                    generated_frames_b64,
                    description,
                )
                
                video_filename = f"miner_{hotkey_short}.mp4"
                files_to_upload[video_filename] = miner_video_path
                
                miner_results[hotkey] = {
                    "hotkey": hotkey,
                    "slug": miner_info["slug"],
                    "video_filename": video_filename,
                    "evaluation": {
                        "generated_wins": comparison["generated_won"],
                        "confidence": comparison["confidence"],
                        "reasoning": comparison["reasoning"],
                        "original_artifacts": comparison["original_artifacts"],
                        "generated_artifacts": comparison["generated_artifacts"],
                        "presentation_order": comparison["presentation_order"],
                    },
                }
                
                result_str = "WIN" if comparison["generated_won"] else "LOSE"
                log(f"Miner {hotkey_short} ({miner_info['slug']}): {result_str} (conf={comparison['confidence']}%)", 
                    "success" if comparison["generated_won"] else "info")
                
                # Cleanup miner frames dir
                for f in os.listdir(miner_frames_dir):
                    os.remove(os.path.join(miner_frames_dir, f))
                os.rmdir(miner_frames_dir)
            
            # 7. Build metadata
            metadata = {
                "sample_id": sample_id,
                "created_at": datetime.now().isoformat(),
                "source": {
                    "bucket": SOURCE_BUCKET,
                    "key": video_key,
                    "full_duration_seconds": duration,
                    "clip_start_seconds": start_offset,
                    "clip_duration_seconds": CLIP_DURATION,
                },
                "prompt": {
                    "model": "gpt-4o",
                    "text": description,
                },
                "generation": {
                    "model": "Wan-2.2-I2V-14B-Fast",
                    "endpoint": PLACEHOLDER_I2V_ENDPOINT,
                    "parameters": {
                        "fps": 16,
                        "frames": 81,
                        "resolution": "480p",
                        "fast": True,
                    },
                },
                "miners": miner_results,
                "files": list(files_to_upload.keys()) + ["metadata.json"],
            }
            
            # 8. Upload sample to Hippius
            log("Uploading sample to Hippius...", "info")
            await upload_sample(minio_client, sample_id, files_to_upload, metadata)
            
            # Cleanup temp files
            os.remove(video_path)
            os.remove(clip_path)
            os.remove(frame_path)
            for f in os.listdir(original_frames_dir):
                os.remove(os.path.join(original_frames_dir, f))
            os.rmdir(original_frames_dir)
            for filename, path in files_to_upload.items():
                if filename.startswith("miner_") and os.path.exists(path):
                    os.remove(path)
            
            # Summary
            round_duration = time.time() - round_start
            wins = sum(1 for m in miner_results.values() if m["evaluation"]["generated_wins"])
            log(f"Round #{round_num} complete: {wins}/{len(miner_results)} wins, {round_duration:.1f}s total", "success")
            log(f"Sample {sample_id} uploaded to s3://{SAMPLES_BUCKET}/{sample_id}/", "success")
            
        except Exception as e:
            log(f"Sample generation error: {e}", "error")
            import traceback
            traceback.print_exc()
        
        log(f"Sleeping {SCORING_SLEEP}s before next round...", "info")
        await asyncio.sleep(SCORING_SLEEP)


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              SCORE CALCULATION                             ║
# ╚════════════════════════════════════════════════════════════════════════════╝

async def calculate_scores_from_samples(minio_client: Minio) -> Dict[str, Dict[str, Any]]:
    """
    Read all samples from the Hippius bucket and calculate win rates per miner.
    
    Returns:
        Dict mapping hotkey to {"wins": int, "total": int, "win_rate": float, "slug": str}
    """
    scores: Dict[str, Dict[str, Any]] = {}
    
    try:
        # List all objects in samples bucket
        objects = await asyncio.to_thread(
            lambda: list(minio_client.list_objects(SAMPLES_BUCKET, recursive=True))
        )
        
        # Find all metadata.json files
        metadata_files = [obj for obj in objects if obj.object_name.endswith("metadata.json")]
        log(f"Found {len(metadata_files)} samples in bucket", "info")
        
        for obj in metadata_files:
            try:
                # Download and parse metadata
                response = await asyncio.to_thread(
                    minio_client.get_object, SAMPLES_BUCKET, obj.object_name
                )
                metadata_bytes = response.read()
                response.close()
                response.release_conn()
                
                metadata = json.loads(metadata_bytes.decode("utf-8"))
                
                # Process each miner's result
                miners_data = metadata.get("miners", {})
                for hotkey, miner_info in miners_data.items():
                    if hotkey not in scores:
                        scores[hotkey] = {
                            "wins": 0,
                            "total": 0,
                            "slug": miner_info.get("slug", "unknown"),
                        }
                    
                    scores[hotkey]["total"] += 1
                    if miner_info.get("evaluation", {}).get("generated_wins", False):
                        scores[hotkey]["wins"] += 1
                    
                    # Update slug if we have a newer one
                    if miner_info.get("slug"):
                        scores[hotkey]["slug"] = miner_info["slug"]
                        
            except Exception as e:
                log(f"Error reading sample {obj.object_name}: {e}", "warn")
                continue
        
        # Calculate win rates
        for hotkey, data in scores.items():
            if data["total"] > 0:
                data["win_rate"] = data["wins"] / data["total"]
            else:
                data["win_rate"] = 0.0
        
    except Exception as e:
        log(f"Error calculating scores from samples: {e}", "error")
    
    return scores


async def run_epoch(subtensor: bt.AsyncSubtensor, wallet: bt.Wallet, minio_client: Minio, block: int):
    """Set weights based on miner performance from samples bucket."""
    
    # Get miners from chain
    commits = await subtensor.get_all_revealed_commitments(NETUID, block=block)
    if not commits:
        log(f"[{block}] No miner commitments found", "warn")
        return

    miners = {}
    for hotkey, commit_data in commits.items():
        commit_block, commit_value = commit_data[-1]
        parsed = _parse_commit(commit_value)
        chute = parsed.get("generator_chute")
        if not chute:
            continue
        miners[hotkey] = {"chute": chute, "block": commit_block}

    if not miners:
        log(f"[{block}] No valid generator chutes in commitments", "warn")
        return

    # Calculate scores from samples bucket
    scores = await calculate_scores_from_samples(minio_client)
    
    # Log current scores
    for hotkey in miners:
        if hotkey in scores:
            s = scores[hotkey]
            log(f"  {hotkey[:8]}: {s['wins']}/{s['total']} wins ({s['win_rate']:.1%})", "info")
        else:
            log(f"  {hotkey[:8]}: no samples yet", "info")

    # Winner-take-all with "beat predecessors by epsilon" rule.
    # A miner can only beat earlier committers if they have enough samples.
    ordered = sorted(miners.keys(), key=lambda hk: miners[hk]["block"])
    
    def get_total(hk: str) -> int:
        return scores.get(hk, {}).get("total", 0)
    
    def get_win_rate(hk: str) -> float:
        return scores.get(hk, {}).get("win_rate", 0.0)
    
    leader = None
    for candidate in ordered:
        if get_total(candidate) < MIN_SAMPLES_TO_CHALLENGE:
            continue
        candidate_rate = get_win_rate(candidate)
        beats_all = True
        for prior in ordered:
            if miners[prior]["block"] >= miners[candidate]["block"]:
                break
            if get_total(prior) == 0:
                continue
            prior_rate = get_win_rate(prior)
            if candidate_rate < prior_rate + EPSILON_BEAT:
                beats_all = False
                break
        if beats_all:
            leader = candidate
            break

    if leader is None:
        eligible = [hk for hk in ordered if get_total(hk) > 0]
        leader = max(eligible, key=get_win_rate) if eligible else ordered[0]
    
    leader_rate = get_win_rate(leader)
    log(f"[{block}] Winner: {leader[:8]} win_rate={leader_rate:.1%}", "success")

    # Set weights on chain
    metagraph = await subtensor.metagraph(NETUID)
    uids, weights = [], []
    for uid, hotkey in enumerate(metagraph.hotkeys):
        if hotkey in miners:
            uids.append(uid)
            weights.append(1.0 if hotkey == leader else 0.0)
    if uids:
        await subtensor.set_weights(wallet=wallet, netuid=NETUID, uids=uids, weights=weights, wait_for_inclusion=True)
        log(f"[{block}] Set weights for {len(uids)} miners (winner takes all)", "success")


async def step(subtensor: bt.AsyncSubtensor, wallet: bt.Wallet, minio_client: Minio):
    """Wait for epoch boundary and run weight setting."""
    current_block = await subtensor.get_current_block()
    if current_block % EPOCH_LEN != 0:
        remaining = EPOCH_LEN - (current_block % EPOCH_LEN)
        wait_time = 12 * remaining
        log(f"Block {current_block}: waiting {remaining} blocks (~{wait_time}s) until epoch", "info")
        await asyncio.sleep(wait_time)
        return

    log_header(f"Eclair Epoch #{current_block // EPOCH_LEN} (block {current_block})")
    await run_epoch(subtensor, wallet, minio_client, current_block)


async def main():
    """Main entry point for the validator."""
    log_header("Eclair Validator Starting")
    
    # Check required environment variables
    if not CHUTES_API_KEY:
        log("CHUTES_API_KEY environment variable required", "error")
        return
    if not OPENAI_API_KEY:
        log("OPENAI_API_KEY environment variable required", "error")
        return
    
    # Initialize clients
    log("Initializing clients...", "info")
    subtensor = bt.AsyncSubtensor(network=NETWORK)
    wallet = bt.Wallet(name=WALLET_NAME, hotkey=HOTKEY_NAME)
    minio_client = create_minio_client()
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    # Log configuration
    log(f"Wallet: {WALLET_NAME}/{HOTKEY_NAME}", "info")
    log(f"Network: {NETWORK}", "info")
    log(f"NetUID: {NETUID}", "info")
    log(f"Epoch length: {EPOCH_LEN} blocks (~{EPOCH_LEN * 12}s)", "info")
    log(f"Sample interval: {SCORING_SLEEP}s", "info")
    log(f"Source bucket: s3://{SOURCE_BUCKET}", "info")
    log(f"Samples bucket: s3://{SAMPLES_BUCKET}", "info")
    log(f"Min samples to challenge: {MIN_SAMPLES_TO_CHALLENGE}", "info")
    log(f"Epsilon beat: {EPSILON_BEAT}", "info")
    
    log("Starting sample generation loop in background...", "start")
    asyncio.create_task(generate_samples_continuously(subtensor, minio_client, openai_client))
    
    log("Starting weight setting loop...", "start")
    while True:
        await step(subtensor, wallet, minio_client)


def main_sync():
    """Synchronous entry point for CLI."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
