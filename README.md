<p align="center">
  <img src="eclair.png" alt="Eclair">
</p>

# Eclair

**Image-to-Video Generation Subnet with GPT-4o Evaluation**

Miners run image-to-video (I2V) generators. Validators sample real video clips, extract the first frame, generate a description via GPT-4o, and challenge miners to generate video from the frame + prompt. Scoring uses GPT-4o forced-choice comparison: which video looks more real? Winner takes all weights.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SAMPLE GENERATION LOOP                          │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Download random video from Hippius "lot-of-videos" bucket           │
│  2. Extract 5s clip and first frame                                     │
│  3. Generate prompt via GPT-4o description                              │
│  4. Query each miner's I2V model                                        │
│  5. Score each miner vs original using GPT-4o forced choice             │
│  6. Upload sample to "video-samples" bucket with full metadata          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         WEIGHT SETTING LOOP                             │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Read all samples from "video-samples" bucket                        │
│  2. Calculate win rates per miner (wins / total)                        │
│  3. Apply winner-take-all with epsilon beat rule                        │
│  4. Set weights on chain (leader gets 1.0, others get 0.0)              │
└─────────────────────────────────────────────────────────────────────────┘
```

## For Validators

### Quick Start (Docker)

```bash
# 1. Clone the repo
git clone https://github.com/your-org/eclair.git
cd eclair

# 2. Create .env from example
cp env.example .env
# Edit .env with your API keys and wallet info

# 3. Run
docker compose up -d
```

### Manual Installation

```bash
# Requires Python 3.12+, ffmpeg
pip install uv
uv pip install -e .

# Run
eclair
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CHUTES_API_KEY` | Yes | Chutes API key for I2V generation |
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4o evaluation |
| `HIPPIUS_SEED_PHRASE` | Yes | Hippius subaccount seed phrase |
| `WALLET_NAME` | No | Bittensor wallet name (default: `default`) |
| `HOTKEY_NAME` | No | Bittensor hotkey name (default: `default`) |
| `NETWORK` | No | Bittensor network (default: `finney`) |

## For Miners

Miners commit their I2V chute slug to chain. The validator will call your chute with:

```json
{
  "prompt": "A person walks through a park...",
  "image": "<base64 encoded first frame>",
  "fps": 16,
  "frames": 81,
  "resolution": "480p",
  "fast": true
}
```

Your chute should return the generated video as `video/mp4`.

### Commitment Format

Commit JSON to chain:
```json
{"generator_chute": "your-chute-slug"}
```

## Scoring

- **Metric**: GPT-4o forced choice - which video (original vs generated) looks more real?
- **Win**: Generated video chosen as more real than the original clip
- **Score**: Win rate = wins / total samples
- **Weights**: Winner-take-all (leader must beat all predecessors by epsilon)

## Storage

All samples are stored in Hippius S3 for reproducibility:

```
s3://video-samples/
  └── 2024-01-29_12-34-56/
      ├── original_clip.mp4
      ├── first_frame.png
      ├── miner_5FHneW46.mp4
      ├── miner_8Abc1234.mp4
      └── metadata.json
```

Each `metadata.json` contains:
- Source video info (bucket, key, clip timing)
- GPT-4o generated prompt
- Per-miner evaluation results (wins, confidence, reasoning, artifacts)
- All hotkeys and chute slugs

## License

MIT
