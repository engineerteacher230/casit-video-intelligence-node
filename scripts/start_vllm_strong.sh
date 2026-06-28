#!/usr/bin/env bash

cd ~/casit/projects/casit-video-intelligence-node || exit 1
source .venv-vllm/bin/activate

mkdir -p ~/casit-data/outputs/logs

export HF_HOME=~/casit-data/models/huggingface
export TRANSFORMERS_CACHE=~/casit-data/models/huggingface

vllm serve Qwen/Qwen2.5-VL-3B-Instruct \
  --served-model-name casit-vlm-strong \
  --trust-remote-code \
  --host 127.0.0.1 \
  --port 8000 \
  --dtype half \
  --max-model-len 2048 \
  --gpu-memory-utilization 0.65 \
  --limit-mm-per-prompt '{"image": 1}' \
  --max-num-seqs 1 \
  --max-num-batched-tokens 2048 \
  --enforce-eager \
  --cpu-offload-gb 8 \
  2>&1 | tee ~/casit-data/outputs/logs/vllm_start.log
