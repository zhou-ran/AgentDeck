#!/usr/bin/env bash
# Demo: start a long-running task that produces periodic output.
set -euo pipefail

TASK_NAME="${1:-demo-long-task}"
DURATION="${2:-60}"

echo "Starting demo long task: $TASK_NAME (duration: ${DURATION}s)"
echo ""

agent-foreman-local start "$TASK_NAME" \
  --dir "$(pwd)" \
  --goal "Demonstrate long-running task monitoring" \
  --feature "demo" \
  --criteria "Produces output every 5 seconds" \
  --tag demo \
  -- bash -c '
    for i in $(seq 1 '"$DURATION"'); do
      echo "[$(date +%H:%M:%S)] Step $i/'"$DURATION"' -- processing data chunk..."
      sleep 5
    done
    echo "[$(date +%H:%M:%S)] All steps completed successfully."
  '

echo ""
echo "Task started. Watch with:"
echo "  agent-foreman-local tail $TASK_NAME -f"
echo ""
echo "Or open the dashboard:"
echo "  agent-foreman-local serve"
