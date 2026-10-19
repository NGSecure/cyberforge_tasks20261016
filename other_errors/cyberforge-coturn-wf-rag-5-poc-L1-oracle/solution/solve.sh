#!/bin/bash
# Reference solution (oracle): none for coturn / vulnerability_WF_RAG_5. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit only greps stun_buffer.c and echoes a made-up UBSAN line, and the changed return value is never used, so no input can show it.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
