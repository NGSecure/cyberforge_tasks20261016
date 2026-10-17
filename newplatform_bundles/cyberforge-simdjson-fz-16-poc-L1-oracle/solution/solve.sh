#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# simdjson / vulnerability_FZ_16 (dataset file: simdjson/vulnerabilities/vulnerability_FZ_16/exploit_files/generated_inputs/exploit_bin_orig_4657153f81.bin, 636248 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: fdf59c42b6388bec4560dd01522e29be" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
