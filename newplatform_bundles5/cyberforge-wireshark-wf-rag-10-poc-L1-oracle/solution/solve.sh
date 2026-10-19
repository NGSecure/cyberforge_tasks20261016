#!/bin/bash
# Reference solution (oracle): none for wireshark / vulnerability_WF_RAG_10. The dataset has no input that
# triggers the injected vulnerability:
#   the dataset exploit only greps cosine.c for 'caplen + 16' and runs nothing.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
