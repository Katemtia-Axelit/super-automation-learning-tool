#!/usr/bin/env bash
# Phase 1 import self-test (NO server start, NO port 5000)
# Steps:
#  1) create .venv if missing
#  2) pip install requirements-web.txt (offline-tolerant: ignore if fails)
#  3) run scripts/phase1_smoke.py via venv python
cd "/d/Axelit/.工作/trae/超级自动化学习工具"

PY="C:/Users/wn/AppData/Local/Programs/Python/Python312/python.exe"
VENV=".venv"
if [ ! -d "$VENV" ]; then
  echo "[setup] Creating .venv (one-time) ..."
  "$PY" -m venv "$VENV" || { echo "[FAIL] venv create"; exit 1; }
fi
# shellcheck disable=SC1091
source "$VENV/Scripts/activate"
python -m pip install -q -r requirements-web.txt -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -5 || true

export PYTHONPATH="$PWD"
echo ""
echo "[import test] running phase1_smoke.py ..."
python scripts/phase1_smoke.py
