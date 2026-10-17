#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# grok / vulnerability_WF_RAG_0 (dataset file: newplatform_bundles/conversion/replay_deep/grok/vulnerability_WF_RAG_0/call-000-arg-0 (replayed grok/vulnerabilities/vulnerability_WF_RAG_0/exploit_files/exploit.sh), 264635 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: b1dd76a832447158247e9b8bae55adef" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
