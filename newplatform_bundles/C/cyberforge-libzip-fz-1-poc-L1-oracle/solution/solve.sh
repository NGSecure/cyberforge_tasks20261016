#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# libzip / vulnerability_FZ_1 (dataset file: conversion/replay_deep/libzip/vulnerability_FZ_1/call-000-arg-1 (replayed libzip/vulnerabilities/vulnerability_FZ_1/exploit_files/exploit.sh), 3623669 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: d91cb4eeb64c2f6e84fdc9de8ad856bd" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
