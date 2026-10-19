#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# opencv / vulnerability_FZ_4 (dataset file: newplatform_bundles/conversion/replay/opencv/vulnerability_FZ_4/input-000 (replayed opencv/vulnerabilities/vulnerability_FZ_4/exploit_files/exploit.sh), 2097152 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: 9fefd0cacba2662c436b8dec99f08db1" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
