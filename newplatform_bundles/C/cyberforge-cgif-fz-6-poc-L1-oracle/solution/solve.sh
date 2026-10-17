#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# cgif / vulnerability_FZ_6 (dataset file: cgif/vulnerabilities/vulnerability_FZ_6/exploit_files/generated_inputs/builtin_02_animated_color_gradient.seed_9a4cc69b2b_text_boundary_probe_055955f50f.seed, 528270 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: 84fec1fe3a7c7697bdf20b11bd5cb2f7" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
