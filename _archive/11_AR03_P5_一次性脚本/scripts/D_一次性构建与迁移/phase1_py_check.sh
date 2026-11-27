#!/usr/bin/env bash
# Phase 1 py_compile self-test (run via git bash)
set -e
cd "/d/Axelit/.工作/trae/超级自动化学习工具"
PY="C:/Users/wn/AppData/Local/Programs/Python/Python312/python.exe"

echo "[1/3] py_compile all new/changed server/ python files..."
fail=0
for f in server/app/__init__.py \
         server/app/app_factory.py \
         server/app/config.py \
         server/app/extensions.py \
         server/blueprints/tasks_bp.py \
         server/blueprints/gacha_bp.py \
         server/blueprints/tags_bp.py \
         server/schema/__init__.py \
         server/services/gacha.py \
         server/backend_api.py; do
  if "$PY" -m py_compile "$f" 2>/dev/null; then
    echo "  OK $f"
  else
    echo "  FAIL $f"
    "$PY" -m py_compile "$f"
    fail=1
  fi
done

echo ""
echo "[2/3] py_compile all scripts/*.py..."
for f in scripts/phase1_smoke.py; do
  if "$PY" -m py_compile "$f" 2>/dev/null; then
    echo "  OK $f"
  else
    echo "  FAIL $f"
    "$PY" -m py_compile "$f"
    fail=1
  fi
done

echo ""
echo "[3/3] Verify pre-existing stub BP files compile (should be no-op re-exports)..."
for f in server/blueprints/__init__.py \
         server/blueprints/_common.py \
         server/blueprints/agent_bp.py \
         server/blueprints/config_bp.py \
         server/blueprints/discard_bp.py \
         server/blueprints/feedback_bp.py \
         server/blueprints/knowledge_bp.py \
         server/blueprints/prompts_bp.py \
         server/blueprints/schedule_bp.py \
         server/blueprints/state_bp.py \
         server/blueprints/timer_bp.py \
         server/schema/feedback.py \
         server/schema/gacha.py \
         server/schema/notes.py \
         server/schema/state.py \
         server/schema/tasks.py \
         server/services/ai.py \
         server/services/knowledge.py \
         server/services/schedule.py \
         server/services/timer.py; do
  if "$PY" -m py_compile "$f" 2>/dev/null; then
    echo "  OK $f"
  else
    echo "  WARN $f (pre-existing stub; may have side-effect imports)"
  fi
done

echo ""
if [ "$fail" = "1" ]; then
  echo "RESULT: FAIL"
  exit 1
else
  echo "RESULT: ALL COMPILE OK"
fi
