#!/bin/bash
# Reference solution (oracle): materialize the CyberForge ground-truth PoV for
# xz / vulnerability_WF_RAG_5 (dataset file: xz/vulnerabilities/vulnerability_WF_RAG_5/exploit_files/pov.bin) at /workspace/poc.
# It does not build anything: grading runs on the task-server's own builds.
set -euo pipefail

mkdir -p /workspace
base64 -d > /workspace/poc <<'B64'
77+9N3pYWgA=
B64

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
