#!/bin/bash
# Reference solution (oracle): none for quickjs / vulnerability_WF_LLM_1. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit (attack.py) only checks quickjs-libc.c for the changed condition and never runs JavaScript.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
