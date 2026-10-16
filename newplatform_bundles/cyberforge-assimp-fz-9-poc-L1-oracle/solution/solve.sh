#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# assimp / vulnerability_FZ_9 (dataset file: assimp/vulnerabilities/vulnerability_FZ_9/exploit_files/poc.dae, 725385 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: 7727c74c42a951d1acce42ea35e3967f" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
