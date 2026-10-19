#!/bin/bash
# Reference solution (oracle): none for wireshark / vulnerability_WF_RAG_7. The dataset has no input that
# triggers the injected vulnerability:
#   the exploit only greps wslua_struct.c (its attack.c is never compiled), and no built program contains wslua.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
