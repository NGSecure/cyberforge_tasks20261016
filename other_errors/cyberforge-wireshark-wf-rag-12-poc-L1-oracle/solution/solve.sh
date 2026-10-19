#!/bin/bash
# Reference solution (oracle): none for wireshark / vulnerability_WF_RAG_12. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit only greps ui/recent.c (its exploit.c is never compiled), and the changed function runs only when the GUI writes its recent file, which no built program does.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
