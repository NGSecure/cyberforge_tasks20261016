#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# icu / vulnerability_WF_LLM_1 (dataset file: icu/vulnerabilities/vulnerability_WF_LLM_1/exploit_files/pov.bin, 1300002 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: 90fa0687a8f1b1690d5aa2aec9941367" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
