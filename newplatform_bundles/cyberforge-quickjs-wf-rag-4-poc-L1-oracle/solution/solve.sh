#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# quickjs / vulnerability_WF_RAG_4 (dataset file: quickjs/vulnerabilities/vulnerability_WF_RAG_4/exploit_files/pov.bin, 400002 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: 90ce0d9ad03c90c288e47f6ccbf42940" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
