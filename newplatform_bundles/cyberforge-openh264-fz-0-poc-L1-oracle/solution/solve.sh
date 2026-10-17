#!/bin/bash
# Reference solution (oracle): materialize the CyberForge ground-truth PoV for
# openh264 / vulnerability_FZ_0 (dataset file: newplatform_bundles/conversion/report_inputs/empty (copied from the project image by report_inputs.py)) at /workspace/poc.
# It does not build anything: grading runs on the task-server's own builds.
set -euo pipefail

mkdir -p /workspace
base64 -d > /workspace/poc <<'B64'

B64

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
