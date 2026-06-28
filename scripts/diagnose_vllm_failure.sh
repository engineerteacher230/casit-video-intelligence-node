#!/usr/bin/env bash

LOG=~/casit-data/outputs/logs/vllm_start.log

echo "---- REAL VLLM PROCESS ----"
pgrep -af "vllm serve" || echo "vLLM serve process yok"

echo
echo "---- PORT 8000 ----"
ss -ltnp | grep 8000 || echo "8000 portunda çalışan yok"

echo
echo "---- GPU ----"
nvidia-smi

echo
echo "---- IMPORTANT ERRORS ----"
grep -nEi "error|runtimeerror|traceback|cuda|out of memory|oom|killed|failed|exception|no space|permission|driver" "$LOG" | tail -120

echo
echo "---- LAST 200 LOG LINES ----"
tail -200 "$LOG"
