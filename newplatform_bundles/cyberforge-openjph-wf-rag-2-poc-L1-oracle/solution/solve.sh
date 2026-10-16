#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# openjph / vulnerability_WF_RAG_2 (dataset file: conversion/replay/openjph/vulnerability_WF_RAG_2/input-000 (replayed openjph/vulnerabilities/vulnerability_WF_RAG_2/exploit_files/exploit.sh), 674100 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: 2ced3c233c90118026e5cf8bc48b161d" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
