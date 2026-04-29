#!/usr/bin/env bash
# Demo: start a task that will fail.
set -euo pipefail

TASK_NAME="${1:-demo-fail-task}"

echo "Starting demo failing task: $TASK_NAME"
echo ""

agentdeck start "$TASK_NAME" \
  --dir "$(pwd)" \
  --goal "Demonstrate failure detection" \
  --feature "demo" \
  --tag demo \
  -- bash -c '
    echo "[$(date +%H:%M:%S)] Starting computation..."
    echo "[$(date +%H:%M:%S)] Loading dataset..."
    sleep 3
    echo "[$(date +%H:%M:%S)] Processing..."
    sleep 2
    echo "ERROR: Out of memory -- cannot allocate 128GB tensor"
    echo "Traceback (most recent call last):"
    echo "  File \"train.py\", line 42, in <module>"
    echo "    model.fit(data)"
    echo "MemoryError: Unable to allocate array"
    exit 1
  '

echo ""
echo "Task started (will fail in ~5 seconds). Watch with:"
echo "  agentdeck tail $TASK_NAME -f"
echo ""
echo "Check status:"
echo "  agentdeck status $TASK_NAME"
