# LMCache adapter — KV cache management layer for local inference

A concrete binding of the **`model_cache`** and **`inference_optimization`** extension points
using [LMCache](https://github.com/LMCache/LMCache) — a high-performance KV cache management
layer for LLM inference. Reduces Time-To-First-Token (TTFT), improves throughput, and lowers
GPU cost by caching KV caches across GPU, CPU, disk, and remote storage.

**Author:** LMCache team / CMU + Princeton.<br>
**Repo:** [github.com/LMCache/LMCache](https://github.com/LMCache/LMCache)<br>
**Docs:** [docs.lmcache.ai](https://docs.lmcache.ai)

---

## What is LMCache

LMCache is a **KV cache management layer** that sits between the LLM inference engine
(vLLM, SGLang) and the hardware. It caches the KV (Key-Value) cache — the intermediate
representations that the transformer generates during prefill — so that future requests
with overlapping prefix context skip recomputation.

### Why this matters

In transformer inference, every request goes through two phases:

1. **Prefill** — the model processes the full input prompt in parallel. This is compute-bound
   and dominates TTFT.
2. **Decode** — the model generates tokens one at a time. This is memory-bound.

Without KV caching, every request repeats prefill for the **entire prompt**, even when most
of it is identical to a previous request (e.g., system prompt, conversation history, task
instructions). LMCache eliminates this redundancy.

### Cache hierarchy

| Tier | Storage | Latency | Capacity | Persistence |
|------|---------|---------|----------|-------------|
| L1 | GPU VRAM | ~0 µs | Smallest | Volatile (per-process) |
| L2 | CPU RAM | ~10 µs | Medium | Volatile (per-process) |
| L3 | Local disk (NVMe/SSD) | ~100 µs | Large | Persistent across restarts |
| L4 | Remote storage (NFS, S3) | ~ms | Largest | Persistent, shareable |

LMCache automatically manages data movement across tiers — hot KV caches stay on GPU,
warm ones on CPU/disk, cold ones on remote storage.

---

## How it fits in the simplicio-loop architecture

### Extension point bindings

| Extension point | Without LMCache | With LMCache |
|----------------|-----------------|--------------|
| `model_cache` | No caching — full prefill every turn | KV cache retained across turns; overlapping prefixes skip prefill |
| `inference_optimization` | None (local inference is slow, GPU-bound) | Automatic tiered caching for faster TTFT and higher throughput |
| Step 3d (model routing) | Route to model, pay full prefill cost each time | Route to model, cache hit reduces or eliminates prefill |

### Step 3d — Model routing

During **Step 3d** (model routing), the orchestrator decides which model to use for a task.
LMCache integrates at this point by:

1. **Checking cache state** — does the KV cache exist for the current prefix
   (system prompt + conversation history)?
2. **Estimating cache benefit** — if the prefix overlaps heavily with a previous request,
   routing to a cached model is cheaper (lower TTFT, less GPU time)
3. **Preferring L2/L3 models** — local models (Llama, Mistral, Qwen, etc.) benefit most
   from KV caching; API models route through their own provider infrastructure

```text
┌─────────────────────────────────────────────────┐
│ Step 3d: Model Routing                          │
│                                                 │
│  Work item ──→ Check LMCache for cached prefix  │
│                   │                             │
│                   ├─ Cache hit (≥80% overlap)   │
│                   │   └─→ Route to cached model │
│                   │       TTFT: ~100ms (decode  │
│                   │       only, no prefill)     │
│                   │                             │
│                   ├─ Partial hit (40-80%)       │
│                   │   └─→ Route to fastest      │
│                   │       local model; partial  │
│                   │       prefill only for      │
│                   │       new prefix            │
│                   │                             │
│                   └─ Cache miss                 │
│                       └─→ Route normally;       │
│                           full prefill cost     │
│                           but results cached    │
│                           for next request      │
└─────────────────────────────────────────────────┘
```

### Token economy integration

The `token_economy` extension point benefits directly from LMCache:

| Metric | Without LMCache | With LMCache (average) |
|--------|-----------------|------------------------|
| TTFT | ~2–5s (4K prompt, local GPU) | ~100–500ms (cache hit) |
| GPU memory per request | Full KV cache per sequence | Partial (shared prefixes) |
| Throughput (req/s) | Baseline | 1.5–5× improvement |
| GPU $ per inference | Baseline | **30–60% reduction** on cache-hit requests |

The key insight: **every token that was pre-filled once and cached costs zero GPU compute
on subsequent requests.** In the simplicio-loop pattern — where the orchestrator runs many
iterations with similar system prompts, task descriptions, and conversation context — the
cache hit rate is naturally high.

---

## Model tiers: who benefits most

LMCache is most impactful for **L2 and L3 models** (local inference models in the
simplicio-loop tier system):

| Tier | Models | LMCache benefit | Why |
|------|--------|----------------|------|
| **L1** | GPT-4o, Claude Opus, Gemini Ultra | **None** (API-only) | Inference runs on provider infrastructure; no local KV cache control |
| **L2** | Llama 3 70B, Qwen 2.5 72B, DeepSeek V3 | **High** | Large models on local GPUs; prefilling 70B parameters is expensive — caching saves the most |
| **L3** | Llama 3.1 8B, Mistral 7B, Qwen 2.5 7B, Phi-4 | **Very high** | Small models run on consumer GPUs; caching makes them feel instant even with long context |
| **L4** | Embedding models, classifiers | **N/A** | These don't use autoregressive KV caches |

> **Rule of thumb**: The larger the model and the longer the prompt, the bigger the LMCache
> savings. A 70B model with a 32K token system prompt that repeats across every iteration
> will save ~$0.05–0.15 *per iteration* on GPU compute.

---

## Installation

### Python package

```bash
pip install lmcache
```

Requires Python 3.10+, CUDA 12.1+ (or ROCm 5.7+). Works with vLLM ≥0.6.0 and SGLang.

### With vLLM

LMCache provides a vLLM plugin that patches into the vLLM engine:

```bash
pip install lmcache[vllm]
```

### With SGLang

```bash
pip install lmcache[sglang]
```

### Verify installation

```bash
python -c "import lmcache; print(lmcache.__version__)"
```

---

## Configuration

LMCache is configured via the `LMCACHE_CONFIG` environment variable, pointing to a YAML or
JSON file, or via inline configuration passed to the inference engine.

### Minimal config (GPU-only cache)

```yaml
# lmcache-minimal.yaml
chunk_size: 4096          # KV cache chunk size in tokens
local_device: "cuda"      # Primary cache device: cuda, cpu, disk
max_local_cache_size: 8   # Max GPU cache size in GB
```

### Full config (multi-tier, shared storage)

```yaml
# lmcache-full.yaml
chunk_size: 4096

# Local caching
local_device: "cpu"        # Primary cache device
max_local_cache_size: 64   # Max CPU RAM cache in GB

# GPU cache (fastest tier)
gpu:
  enabled: true
  max_size: 4              # GB of GPU VRAM for KV cache
  reserved_memory: 1.0     # GB reserved for model weights

# Disk cache (NVMe preferred)
disk:
  enabled: true
  path: "/tmp/lmcache"     # Cache directory
  max_size: 200            # GB on disk
  compression: "zstd"      # Optional: zstd, lz4, none

# Remote storage (share across machines/processes)
remote:
  enabled: false
  protocol: "redis"        # redis, nfs, s3
  # Redis example:
  # host: "127.0.0.1"
  # port: 6379
  # prefix: "lmcache:"
  # NFS/S3 example:
  # path: "/mnt/shared/lmcache"

# Eviction policy
eviction: "lru"            # lru, lfu, fifo
```

### Export the config

```bash
export LMCACHE_CONFIG=/path/to/lmcache.yaml
```

---

## How to use

### 1. With vLLM (plugin mode)

LMCache integrates as a vLLM plugin. Start the vLLM server with LMCache enabled:

```bash
# Using the lmcache wrapper (recommended)
lmcache serve \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --gpu-memory-utilization 0.8 \
  --max-model-len 32768

# Or directly with vLLM, setting env vars
LMCACHE_CONFIG=lmcache.yaml \
CUDA_VISIBLE_DEVICES=0 \
vllm serve meta-llama/Llama-3.1-8B-Instruct \
  --gpu-memory-utilization 0.8 \
  --max-model-len 32768 \
  --enable-lmcache
```

### 2. With SGLang

```bash
# SGLang runtime with LMCache
LMCACHE_CONFIG=lmcache.yaml \
python -m sglang.launch_server \
  --model-path meta-llama/Llama-3.1-8B-Instruct \
  --enable-lmcache
```

### 3. `lmcache serve` standalone command

The `lmcache serve` CLI wraps vLLM automatically with LMCache configured:

```bash
# Start with defaults
lmcache serve --model meta-llama/Llama-3.1-8B-Instruct

# With config file
LMCACHE_CONFIG=lmcache-full.yaml lmcache serve \
  --model meta-llama/Llama-3.1-8B-Instruct
```

### 4. Query the inference endpoint (standard OpenAI-compatible API)

```bash
# First request — full prefill, cached for future
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [
      {"role": "system", "content": "You are a helpful coding assistant."},
      {"role": "user", "content": "Write a Python function to sort a list."}
    ]
  }'

# Second request — overlapping system prompt → partial cache hit
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [
      {"role": "system", "content": "You are a helpful coding assistant."},
      {"role": "user", "content": "Now add type hints."}
    ]
  }'
# → The system prompt KV cache is reused; only the new user message is prefilled
```

### 5. Check cache statistics

```bash
# LMCache exposes metrics via its admin endpoint (if enabled)
curl -s http://localhost:8000/lmcache/stats | jq .

# Example output:
# {
#   "cache_hits": 47,
#   "cache_misses": 12,
#   "hit_rate": 0.7966,
#   "gpu_cache_usage_gb": 2.3,
#   "cpu_cache_usage_gb": 14.1,
#   "disk_cache_usage_gb": 56.8,
#   "tokens_saved": 18432000,  # tokens that didn't need prefilling
#   "estimated_gpu_time_saved_sec": 368.64
# }
```

---

## Multi-agent: shared cache across concurrent workers

LMCache supports a **multi-process (MP)** architecture where concurrent agents share KV cache
via remote storage (Redis, NFS, S3). This is critical when the simplicio-loop orchestrator
spawns parallel workers (e.g., multi-agent review, parallel PR generation).

### Architecture

```text
┌─────────────────────────────────────────────────────┐
│                  LMCache remote store                │
│                  (Redis / NFS / S3)                  │
│                                                      │
│   KV cache for: system prompt, shared context       │
└────┬────────────┬────────────┬────────────┬─────────┘
     │            │            │            │
     ▼            ▼            ▼            ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Worker 1│ │ Worker 2│ │ Worker 3│ │ Worker 4│
│ (review)│ │ (code)  │ │ (test)  │ │ (docs)  │
└─────────┘ └─────────┘ └─────────┘ └─────────┘
     │            │            │            │
  Shared system prompt KV cache is computed ONCE
  and reused by ALL workers. Each worker pays
  prefill only for its unique task instruction.
```

### Redis backend config for shared cache

```yaml
# lmcache-multiagent.yaml
chunk_size: 4096
local_device: "cpu"
max_local_cache_size: 32

gpu:
  enabled: true
  max_size: 2

disk:
  enabled: true
  path: "/tmp/lmcache"
  max_size: 100

remote:
  enabled: true
  protocol: "redis"
  host: "127.0.0.1"
  port: 6379
  prefix: "lmcache:simplicio:"
  timeout_ms: 5000
```

### Running workers with shared cache

```bash
# Start Redis (if not already running)
redis-server --daemonize yes

# Worker 1 (code generation)
LMCACHE_CONFIG=lmcache-multiagent.yaml CUDA_VISIBLE_DEVICES=0 \
  lmcache serve --model meta-llama/Llama-3.1-8B-Instruct --port 8001 &

# Worker 2 (review)
LMCACHE_CONFIG=lmcache-multiagent.yaml CUDA_VISIBLE_DEVICES=1 \
  lmcache serve --model meta-llama/Llama-3.1-8B-Instruct --port 8002 &

# Worker 3 (test generation)
LMCACHE_CONFIG=lmcache-multiagent.yaml CUDA_VISIBLE_DEVICES=2 \
  lmcache serve --model meta-llama/Llama-3.1-8B-Instruct --port 8003 &
```

Each worker shares the same remote Redis backend. When Worker 1 prefills the system prompt,
Workers 2 and 3 get a cache hit on the same prefix — no redundant prefill.

---

## Integration in simplicio-loop Step 3d

### Adapter protocol

```bash
# 1. Check if LMCache is available
python -c "import lmcache; print('lmcache:ready')" 2>/dev/null \
  || echo "lmcache:absent — install: pip install lmcache"

# 2. Query cache stats for model routing decision
LMCACHE_URL="${LMCACHE_URL:-http://localhost:8000}"
cache_stats=$(curl -s "$LMCACHE_URL/lmcache/stats" 2>/dev/null || echo "{}")
hit_rate=$(echo "$cache_stats" | python3 -c "
import sys, json
data = json.load(sys.stdin)
rate = data.get('hit_rate', 0)
print(f'{rate:.0%}')
" 2>/dev/null || echo "N/A")

# 3. Decision: route to cached model if hit rate > 50%
if [ "$hit_rate" != "N/A" ] && [ "$(echo "$hit_rate > 0.5" | bc -l 2>/dev/null)" = "1" ]; then
  echo "ROUTE: cached model (hit rate: $hit_rate)"
else
  echo "ROUTE: any available model (cold cache)"
fi

# 4. If using a local L2/L3 model with LMCache, append to model config
MODEL_CONFIG=$(cat <<JSON
{
  "model": "meta-llama/Llama-3.1-8B-Instruct",
  "tier": "L3",
  "lmcache": {
    "enabled": true,
    "config": "$HOME/.simplicio/orchestrator/lmcache.yaml",
    "endpoint": "$LMCACHE_URL",
    "cache_hit_rate": "$hit_rate",
    "estimated_ttft_ms": {
      "cache_hit": 150,
      "cache_miss": 2000
    }
  }
}
JSON
)
```

### Token economy report integration

Append LMCache savings to the token economy report:

```json
{
  "lmcache": {
    "enabled": true,
    "tokens_saved": 18432000,
    "gpu_time_saved_sec": 368.64,
    "estimated_cost_saved_usd": 0.37,
    "cache_hit_rate": 0.80,
    "config": "$HOME/.simplicio/orchestrator/lmcache.yaml"
  }
}
```

---

## Token economy: detailed breakdown

The simplicio-loop architecture runs many iterations with highly overlapping context.
Here's how LMCache drives savings:

### Typical loop workload (30 iterations)

| Component | Per iteration (w/o cache) | Per iteration (w/ cache) | Savings |
|-----------|---------------------------|--------------------------|---------|
| System prompt prefill (8K tokens) | ~1.5s GPU | **~0s** (cached after first iteration) | 100% |
| Conversation history (4K tokens) | ~0.8s GPU | **~0s** (cached from previous turn) | 100% |
| Task instruction (1K tokens) | ~0.2s GPU | ~0.2s (new content each turn) | 0% |
| New task prefix (variable) | ~0.5s GPU | ~0.5s (unique per task) | 0% |
| **Total GPU time** | **~3.0s** | **~0.7s** | **~77%** |
| **Total GPU cost** (A100 @ $3.50/hr) | **~$0.0029** | **~$0.0007** | **~77%** |

### Savings over 100 iterations (typical daily run)

| Metric | Without LMCache | With LMCache |
|--------|-----------------|--------------|
| Total GPU time | ~300s | ~70s |
| Total GPU cost | ~$0.29 | ~$0.07 |
| Wall clock time | ~8.3 min | ~2.0 min |
| TTFT (avg) | ~2s | ~400ms |

### When savings are largest

- **Long system prompts** (>4K tokens): The repeated prefix dominates prefill cost
- **Many iterations on the same task**: Cache accumulates across the loop
- **Multi-turn conversations**: Each turn adds to the cached prefix
- **Concurrent workers**: Multi-process sharing amplifies savings linearly with worker count

---

## Prerequisites

| Requirement | Minimum version | Verification |
|-------------|----------------|--------------|
| Python | 3.10+ | `python --version` |
| CUDA | 12.1+ | `nvcc --version` |
| vLLM | 0.6.0+ | `pip show vllm \| grep Version` |
| SGLang | (optional) | `pip show sglang \| grep Version` |
| GPU VRAM | 8GB+ (for L3 models) | `nvidia-smi --query-gpu=memory.total --format=csv,noheader` |
| RAM | 32GB+ (for CPU cache tier) | |
| NVMe SSD | Recommended for disk cache tier | |
| Redis | 6.0+ (for remote cache) | `redis-server --version` |

### Installation checklist

```bash
# 1. Install LMCache
pip install lmcache

# 2. Install vLLM (if not present)
pip install vLLM

# 3. Verify CUDA
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}'); print(f'Device count: {torch.cuda.device_count()}')"

# 4. Create config
mkdir -p ~/.simplicio/orchestrator
cat > ~/.simplicio/orchestrator/lmcache.yaml << 'EOF'
chunk_size: 4096
local_device: "cuda"
max_local_cache_size: 4
EOF

# 5. Export config
export LMCACHE_CONFIG="$HOME/.simplicio/orchestrator/lmcache.yaml"

# 6. Start inference server
lmcache serve --model meta-llama/Llama-3.1-8B-Instruct &
```

### `.gitignore` recommendation

```
# LMCache disk cache directory (if using disk tier)
/tmp/lmcache/

# Config files may contain local paths — keep in .env or secrets
*.lmcache.yaml
```

---

## Testing (no GPU needed)

LMCache can be tested in CPU-only mode for development:

```yaml
# lmcache-test.yaml
chunk_size: 4096
local_device: "cpu"
max_local_cache_size: 4
```

```bash
# Dry-run config validation
python -c "
import lmcache
cfg = lmcache.config.load_yaml('lmcache-test.yaml')
assert cfg is not None
print('PASS: config valid')
"

# Test import + basic API
python -c "
import lmcache
print(f'LMCache version: {lmcache.__version__}')
print(f'Available backends: cuda={lmcache.has_cuda()}, cpu={lmcache.has_cpu()}, disk={lmcache.has_disk()}')
"
```

---

## References

| Resource | URL |
|----------|-----|
| GitHub repo | [github.com/LMCache/LMCache](https://github.com/LMCache/LMCache) |
| Documentation | [docs.lmcache.ai](https://docs.lmcache.ai) |
| LMCache paper (NSDI 2025) | [arxiv.org/abs/2405.16451](https://arxiv.org/abs/2405.16451) |
| vLLM integration guide | [docs.lmcache.ai/latest/integration/vllm](https://docs.lmcache.ai/latest/integration/vllm) |
| SGLang integration guide | [docs.lmcache.ai/latest/integration/sglang](https://docs.lmcache.ai/latest/integration/sglang) |
| Redis backend setup | [docs.lmcache.ai/latest/backends/redis](https://docs.lmcache.ai/latest/backends/redis) |
| CMU research group | [lmcache.ai](https://lmcache.ai) |

---

## Appendix: Architecture diagram

```text
┌─────────────────────────────────────────────────────────────┐
│                      simplicio-loop                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Step 3d: Model Routing                   │   │
│  │                                                     │   │
│  │  Work item ──→ Tier selection ──→ LMCache check     │   │
│  │                        │              │             │   │
│  │                   L1: API         L2/L3: Local      │   │
│  │                   (no cache)      (with LMCache)    │   │
│  └───────────────────────┬─────────────────────────────┘   │
│                          │                                 │
└──────────────────────────┼─────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    LMCache Layer                            │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  L1: GPU │  │  L2: CPU │  │ L3: Disk │  │ L4: Remote│   │
│  │  VRAM    │  │  RAM     │  │ (NVMe)   │  │ (Redis)  │   │
│  │  ~0 µs   │  │  ~10 µs  │  │ ~100 µs  │  │  ~ms     │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │             │             │         │
│       └──────────────┴─────────────┴─────────────┘         │
│                      │                                     │
│              Automatic tier promotion                      │
│           (hot data → GPU, warm → RAM/disk)                │
└──────────────────────┼─────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 Inference Engine                            │
│  (vLLM / SGLang with LMCache backend)                      │
│                                                             │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐        │
│  │ Prefill    │    │ Decode     │    │ Cache      │        │
│  │ (skipped   │───→│ (fast,     │───→│ Update     │        │
│  │  on hit)   │    │  memory-   │    │ (store new │        │
│  │            │    │  bound)    │    │  KV)       │        │
│  └────────────┘    └────────────┘    └────────────┘        │
└─────────────────────────────────────────────────────────────┘
```
