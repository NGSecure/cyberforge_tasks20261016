#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# assimp / vulnerability_FZ_1 (dataset file: assimp/vulnerabilities/vulnerability_FZ_1/exploit_files/generated_inputs/poc_orig_812da06965.fbx, 294935 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: d83a8ea86a9ec8191018f40309b2ed2b" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
