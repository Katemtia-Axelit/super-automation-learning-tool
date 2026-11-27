#!/usr/bin/env bash
# Phase 1 node --check self-test
cd "/d/Axelit/.工作/trae/超级自动化学习工具"

echo "[1/2] node --check all new JS files..."
fail=0
for f in static/core/state.js \
         static/core/constants.js \
         static/core/ui/modal.js \
         static/core/ui/toast.js \
         static/core/ui/theme.js \
         static/core/ui/sandbox.js \
         static/shared/timer.js \
         static/shared/xss.js \
         static/shared/formatters.js \
         static/modules/gacha/index.js \
         static/modules/tasks/index.js \
         static/app.entry.js; do
  if node --check "$f" 2>/dev/null; then
    echo "  OK $f"
  else
    echo "  FAIL $f"
    node --check "$f"
    fail=1
  fi
done

echo ""
echo "[2/2] Re-verify pre-existing static/core/ files (from earlier worker)..."
for f in static/core/event-bus.js \
         static/core/api.js \
         static/core/router.js \
         static/core/theme.js \
         static/core/theme-init.js \
         static/core/ui.js; do
  if node --check "$f" 2>/dev/null; then
    echo "  OK $f"
  else
    echo "  FAIL $f"
    node --check "$f"
    fail=1
  fi
done

echo ""
if [ "$fail" = "1" ]; then
  echo "RESULT: FAIL"
  exit 1
else
  echo "RESULT: ALL JS SYNTAX OK"
fi
