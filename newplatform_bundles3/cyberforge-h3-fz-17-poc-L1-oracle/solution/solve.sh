#!/bin/bash
# Reference solution (oracle): materialize the CyberForge ground-truth PoV for
# h3 / vulnerability_FZ_17 (dataset file: h3/vulnerabilities/vulnerability_FZ_17/exploit_files/generated_inputs/empty.bin) at /workspace/poc.
# It does not build anything: grading runs on the task-server's own builds.
set -euo pipefail

mkdir -p /workspace
base64 -d > /workspace/poc <<'B64'

B64

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
