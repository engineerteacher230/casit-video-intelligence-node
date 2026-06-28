#!/usr/bin/env bash

echo "---- CURRENT DIRECTORY ----"
pwd

echo
echo "---- VLLM PROCESS ----"
ps aux | grep vllm | grep -v grep || echo "vLLM process yok"

echo
echo "---- PORT 8000 ----"
ss -ltnp | grep 8000 || echo "8000 portunda çalışan yok"

echo
echo "---- MODEL API ----"
curl -s http://127.0.0.1:8000/v1/models || echo "API cevap vermiyor"

echo
echo
echo "---- LOG SONU ----"
tail -40 ~/casit-data/outputs/logs/vllm_start.log 2>/dev/null || echo "Log dosyası yok"
