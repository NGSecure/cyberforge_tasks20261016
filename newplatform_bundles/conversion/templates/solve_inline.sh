#!/bin/bash
# Reference solution (oracle): materialize the CyberForge ground-truth PoV for
# @@PROJECT@@ / @@VULN_ID@@ (dataset file: @@POC_SRC_PATH@@) at /workspace/poc.
# It does not build anything: grading runs on the task-server's own builds.
set -euo pipefail

mkdir -p /workspace
base64 -d > /workspace/poc <<'B64'
@@POC_B64@@
B64

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
