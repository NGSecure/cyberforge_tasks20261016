#!/bin/bash
# Reference solution (oracle): materialize the CyberForge ground-truth PoV for
# openssl / vulnerability_WF_RAG_0 (dataset file: newplatform_bundles/conversion/replay_deep/openssl/vulnerability_WF_RAG_0/call-000-arg-0 (replayed openssl/vulnerabilities/vulnerability_WF_RAG_0/exploit_files/exploit.sh)) at /workspace/poc.
# It does not build anything: grading runs on the task-server's own builds.
set -euo pipefail

mkdir -p /workspace
base64 -d > /workspace/poc <<'B64'

B64

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
