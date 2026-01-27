"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     SIGMA ZERO - CENTRAL BANKER AGENT VALIDATOR              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  MECHANISM OVERVIEW                                                          ║
║  ──────────────────                                                          ║
║  Miners submit Docker containers that output portfolio allocations across    ║
║  assets (BTC, ETH, XAU). Validators run these containers, score allocations  ║
║  against realized price movements, and elect a single "leader" who receives  ║
║  all weight for the epoch.                                                   ║
║                                                                              ║
║  VALIDATION FLOW                                                             ║
║  ───────────────                                                             ║
║                                                                              ║
║    ┌─────────────────────────────────────────────────────────────────────┐   ║
║    │  EPOCH N (current_block)                                            │   ║
║    │                                                                     │   ║
║    │  1. RUNNER: Execute miner containers in parallel                    │   ║
║    │     • Read committed docker images from chain                       │   ║
║    │     • Run each via Basilica (affinetes)                             │   ║
║    │     • Collect portfolio allocations {asset: weight}                 │   ║
║    │     • Store in HISTORY[current_block]                               │   ║
║    │                                                                     │   ║
║    │  2. SCORER: Evaluate allocations from EPOCH N-LAG                   │   ║
║    │     • Fetch realized prices for lag window                          │   ║
║    │     • Score each allocation: |Σ(weight × log_return)|               │   ║
║    │     • Lower score = better (closer to market-neutral)               │   ║
║    │     • Update pairwise statistics (Welford's algorithm)              │   ║
║    │     • Select leader via statistical dominance                       │   ║
║    │     • Set weights: leader=1.0, others=0.0                           │   ║
║    └─────────────────────────────────────────────────────────────────────┘   ║
║                                                                              ║
║  LEADER SELECTION (Condorcet-style)                                          ║
║  ──────────────────────────────────                                          ║
║  A miner "beats" another if statistically better (99% confidence).           ║
║  Leader = miner not beaten by anyone. Ties broken by earliest commit.        ║
║                                                                              ║
║      beats(i,j) = True if:                                                   ║
║          • n >= 24 observations                                              ║
║          • mean(score_i - score_j) + 2.33*SE < 0                             ║
║                                                                              ║
║  This creates a tournament where only statistically dominant miners win.     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import math
import asyncio
import aiohttp
import affinetes as af
import bittensor as bt
from typing import Dict, List
from datetime import datetime, timedelta


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              CONFIGURATION                                 ║
# ╚════════════════════════════════════════════════════════════════════════════╝

NETUID = 120                                      # Subnet identifier
LAG = 2                                           # Epochs to wait before scoring (prevents lookahead)
EPOCH_LEN = 2                                     # Blocks per epoch
ASSETS = ["BTC/USD", "ETH/USD", "XAU/USD"]        # Assets miners allocate across
TWELVE_API_KEY = os.environ.get("TWELVE_DATA_API_KEY")
TWELVE_BASE_URL = "https://api.twelvedata.com/time_series"
CHUTES_API_KEY = os.environ.get("CHUTES_API_KEY")

# Wallet/Network configuration (from environment)
WALLET_NAME = os.environ.get("WALLET_NAME", "default")
HOTKEY_NAME = os.environ.get("HOTKEY_NAME", "default")
NETWORK = os.environ.get("NETWORK", "finney")

# In-memory state: {block: {miners, allocations, scores, stats, leader}}
HISTORY = {}


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
# ║                              PRICE DATA                                    ║
# ╚════════════════════════════════════════════════════════════════════════════╝

async def fetch_prices(session: aiohttp.ClientSession, symbol: str, start: datetime, end: datetime) -> List[float]:
    """
    Fetch minute-level close prices from Twelve Data API.
    
    Returns: List of prices in chronological order (oldest first).
    """
    if not TWELVE_API_KEY: raise RuntimeError("Missing TWELVE_DATA_API_KEY.")
    params = {"symbol": symbol, "interval": "1min", "start_date": start.isoformat(), 
              "end_date": end.isoformat(), "apikey": TWELVE_API_KEY, "format": "JSON", "outputsize": 5000}
    async with session.get(TWELVE_BASE_URL, params=params, timeout=30) as resp:
        resp.raise_for_status()
        data = await resp.json()
        if data.get("status") == "error": raise RuntimeError(f"Twelve Data error: {data.get('message')}")
        values = data.get("values")
        if not values: raise RuntimeError(f"No data for {symbol}")
        return [float(v["close"]) for v in reversed(values)]


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              SCORING                                       ║
# ╠────────────────────────────────────────────────────────────────────────────╣
# ║  Score = |portfolio return| = |Σ weight_i × log(price_1/price_0)|          ║
# ║                                                                            ║
# ║  Lower is better: a score of 0 means perfectly market-neutral              ║
# ║  (gains and losses across assets cancel out).                              ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def score_allocation(allocation: Dict[str, float], prices: Dict[str, List[float]]) -> float:
    """
    Score a portfolio allocation against realized price movements.
    
    Args:
        allocation: {asset: weight} where weights should sum to ~1
        prices: {asset: [price_t0, price_t1, ...]} time series
    
    Returns:
        Absolute portfolio return (lower = more market-neutral = better)
    """
    r = {}
    for a, ps in prices.items():
        if len(ps) < 2 or ps[0] <= 0 or ps[1] <= 0: return float("inf")
        r[a] = math.log(ps[1] / ps[0])  # Log return for numerical stability
    return abs(sum(allocation.get(a, 0.0) * r[a] for a in ASSETS))


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              CONTAINER EXECUTION                           ║
# ╠────────────────────────────────────────────────────────────────────────────╣
# ║  Miners commit Docker image URLs to chain. Validators run these images     ║
# ║  via Basilica (affinetes) in sandboxed pods to get allocations.            ║
# ║                                                                            ║
# ║  Container interface:                                                      ║
# ║    Actor.get_allocation(assets: List[str]) -> Dict[str, float]             ║
# ╚════════════════════════════════════════════════════════════════════════════╝

async def run_container(hotkey: str, image: str) -> Dict[str, float]:
    """
    Execute a miner's container and retrieve their portfolio allocation.
    
    Falls back to equal-weight allocation on any failure.
    """
    env = None
    try:
        env = af.load_env(
            mode="basilica",
            image=image,
            env_vars={"CHUTES_API_KEY": CHUTES_API_KEY, "ASSETS": ",".join(ASSETS)}
        )
        result = await env.get_allocation(assets=ASSETS, _timeout=30)
        return result
    except Exception as e:
        log(f"Container failed for {hotkey[:6]}: {e}", "error")
    finally:
        if env: await env.cleanup()
    return {a: 1/len(ASSETS) for a in ASSETS}  # Default: equal weight


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              RUNNER                                        ║
# ╠────────────────────────────────────────────────────────────────────────────╣
# ║  Parallel execution of all miner containers for the current epoch.         ║
# ║                                                                            ║
# ║  1. Read revealed commitments (docker image URLs) from chain               ║
# ║  2. Spawn async tasks to run each container                                ║
# ║  3. Collect allocations into HISTORY[block]                                ║
# ╚════════════════════════════════════════════════════════════════════════════╝

async def runner(subtensor: bt.AsyncSubtensor, block: int, max_concurrent: int = 16) -> Dict[str, Dict]:
    """
    Run all miner containers in parallel and collect their allocations.
    
    Stores results in HISTORY[block] for later scoring.
    """
    commits = await subtensor.get_all_revealed_commitments(NETUID, block=block)
    if not commits: return {}
    
    # Initialize state for this block
    HISTORY[block] = {'miners': {}, 'allocations': {}, 'scores': {}, 'stats': {}, 'leader': None}
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_miner(hotkey, commit_data):
        async with semaphore:
            commit_block, docker_image = commit_data[-1]
            HISTORY[block]['miners'][hotkey] = {'block': commit_block, 'image': docker_image}
            allocation = await run_container(hotkey, docker_image)
            HISTORY[block]['allocations'][hotkey] = allocation
            return hotkey, allocation
    
    # Execute all containers concurrently (limited by semaphore)
    tasks = [process_miner(hk, cd) for hk, cd in commits.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    log(f"[{block}] Ran {len([r for r in results if not isinstance(r, Exception)])} miner containers", 'info')
    return HISTORY[block]['allocations']


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              SCORER                                        ║
# ╠────────────────────────────────────────────────────────────────────────────╣
# ║  Evaluates miners from a PAST epoch (lag_block) using realized prices.     ║
# ║                                                                            ║
# ║  SCORING PIPELINE:                                                         ║
# ║    1. Fetch prices for the evaluation window                               ║
# ║    2. Score each miner's allocation                                        ║
# ║    3. Update pairwise comparison statistics                                ║
# ║    4. Select leader via statistical dominance                              ║
# ║    5. Set weights on chain (winner-take-all)                               ║
# ╚════════════════════════════════════════════════════════════════════════════╝

async def scorer(subtensor: bt.AsyncSubtensor, wallet: bt.Wallet, current_block: int, lag_block: int) -> str | None:
    """
    Score miners from lag_block, determine leader, and set weights.
    
    Returns: Leader hotkey or None if no valid candidates.
    """
    if lag_block not in HISTORY or not HISTORY[lag_block].get('miners'):
        log(f"[{lag_block}] No state for lag block", 'info')
        return None
    
    log(f"[{lag_block}] Found {len(HISTORY[lag_block]['miners'])} miners", 'info')
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: Fetch realized prices for the scoring window
    # ──────────────────────────────────────────────────────────────────────────
    start_time = await subtensor.get_timestamp(lag_block) - timedelta(minutes=10)
    end_time = await subtensor.get_timestamp(current_block)
    async with aiohttp.ClientSession() as session:
        price_tasks = {sym: fetch_prices(session, sym, start_time, end_time) for sym in ASSETS}
        results = await asyncio.gather(*price_tasks.values())
        prices = dict(zip(price_tasks.keys(), results))
    HISTORY[lag_block]['prices'] = prices
    log(f"[{lag_block}] Fetched prices: {[len(p) for p in prices.values()]}", 'info')
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: Score each miner's allocation
    # ──────────────────────────────────────────────────────────────────────────
    for hotkey in HISTORY[lag_block]['miners']:
        HISTORY[lag_block]['scores'][hotkey] = score_allocation(HISTORY[lag_block]['allocations'][hotkey], prices)
    log(f"[{lag_block}] Scored {len(HISTORY[lag_block]['scores'])} miners", 'info')
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: Update pairwise statistics using Welford's online algorithm
    #
    # For each pair (i, j), we track:
    #   n    = number of observations
    #   mean = running mean of (score_i - score_j)
    #   M2   = sum of squared deviations (for variance)
    #
    # This allows computing confidence intervals for "i beats j".
    # ──────────────────────────────────────────────────────────────────────────
    pairwise = {}
    for blk in HISTORY:
        if blk > lag_block: break
        scores_i = HISTORY[lag_block]["scores"]
        for mi, si in scores_i.items():
            for mj, sj in scores_i.items():
                if mi == mj: continue
                d = si - sj  # Difference: negative means i is better
                key = (mi, mj)
                e = pairwise.get(key, {"n": 0, "mean": 0.0, "M2": 0.0})
                # Welford's update
                e["n"] += 1
                delta = d - e["mean"]
                e["mean"] += delta / e["n"]
                e["M2"] += delta * (d - e["mean"])
                pairwise[key] = e
    HISTORY[lag_block]["stats"] = pairwise
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: Leader selection via statistical dominance
    #
    # beats(i, j) returns True if miner i statistically beats miner j:
    #   - Need at least 24 observations for statistical validity
    #   - One-tailed test at 99% confidence (z = 2.33)
    #   - i beats j if: mean(score_i - score_j) + 2.33*SE < 0
    #     (i.e., i's scores are significantly lower = better)
    #
    # Leader = any miner NOT beaten by anyone else (Condorcet winner)
    # Tie-breaker: earliest commit block (first-mover advantage)
    # ──────────────────────────────────────────────────────────────────────────
    def beats(i: str, j: str) -> bool:
        """Returns True if miner i statistically dominates miner j (99% confidence)."""
        e = pairwise.get((i, j))
        if not e or e["n"] < 24: return False          # Not enough data
        var = e["M2"] / max(1, e["n"] - 1)             # Sample variance
        se = math.sqrt(var / e["n"])                   # Standard error of mean
        return e["mean"] + 2.33 * se < 0               # Upper bound of 99% CI < 0
    
    log(f"[{lag_block}] Finding leader via statistical dominance", 'info')
    candidates = []
    for hk in HISTORY[lag_block]['miners']:
        # Find anyone who beats this miner
        dominated_by = [o for o in HISTORY[lag_block]['miners'] if o != hk and beats(o, hk)]
        if dominated_by:
            log(f"[{lag_block}] {hk[:6]} beaten by {dominated_by[0][:6]}", 'info')
        else:
            candidates.append(hk)
    
    if not candidates: 
        log(f"[{lag_block}] No undominated candidates", 'warn')
        return None
    
    # Tie-breaker: earliest commit wins
    commit_blocks = {hk: d['block'] for hk, d in HISTORY[lag_block]['miners'].items()}
    leader = min(candidates, key=lambda hk: commit_blocks[hk])
    HISTORY[lag_block]["leader"] = leader
    log(f"[{lag_block}] Leader: {leader[:6]} (commit block {commit_blocks[leader]})", 'success')
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5: Set weights on chain (winner-take-all)
    # ──────────────────────────────────────────────────────────────────────────
    metagraph = await subtensor.metagraph(NETUID)
    uids, weights = [], []
    for uid, hotkey in enumerate(metagraph.hotkeys):
        if hotkey in HISTORY[lag_block]['miners']:
            uids.append(uid)
            weights.append(1.0 if hotkey == leader else 0.0)
    
    if uids:
        await subtensor.set_weights(wallet=wallet, netuid=NETUID, uids=uids, weights=weights, wait_for_inclusion=True)
        log(f"[{lag_block}] Set weights for {len(uids)} miners (leader gets 100%)", 'success')
    
    return leader


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                              MAIN LOOP                                     ║
# ╠────────────────────────────────────────────────────────────────────────────╣
# ║  Each epoch:                                                               ║
# ║    1. Wait for epoch boundary (block % EPOCH_LEN == 0)                     ║
# ║    2. Run containers for current block (collect allocations)               ║
# ║    3. Score lag_block allocations and set weights                          ║
# ║                                                                            ║
# ║  The LAG ensures miners can't see prices before committing allocations.    ║
# ╚════════════════════════════════════════════════════════════════════════════╝

async def step(subtensor: bt.AsyncSubtensor, wallet: bt.Wallet):
    """Execute one validation step: run containers, score past epoch, set weights."""
    current_block = await subtensor.get_current_block()
    
    # Wait for epoch boundary
    if current_block % EPOCH_LEN != 0:
        remaining = EPOCH_LEN - (current_block % EPOCH_LEN)
        await asyncio.sleep(12 * remaining)  # ~12 seconds per block
        return
    
    lag_block = current_block - (LAG * EPOCH_LEN)
    log_header(f'Epoch: {current_block // EPOCH_LEN} (scoring lag block: {lag_block})')
    
    # Phase 1: Collect allocations for current epoch
    await runner(subtensor, current_block)
    
    # Phase 2: Score allocations from LAG epochs ago and set weights
    await scorer(subtensor, wallet, current_block, lag_block)


async def main():
    """Initialize connections and run the validator loop forever."""
    subtensor = bt.AsyncSubtensor(network=NETWORK)
    wallet = bt.Wallet(name=WALLET_NAME, hotkey=HOTKEY_NAME)
    log(f"Starting validator: wallet={WALLET_NAME}/{HOTKEY_NAME} network={NETWORK}", "start")
    while True:
        await step(subtensor, wallet)


if __name__ == "__main__":
    asyncio.run(main())
