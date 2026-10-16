#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# @@PROJECT@@ / @@VULN_ID@@ (dataset file: @@POC_SRC_PATH@@, @@POC_SIZE@@ bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: @@AUTH_TOKEN@@" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
