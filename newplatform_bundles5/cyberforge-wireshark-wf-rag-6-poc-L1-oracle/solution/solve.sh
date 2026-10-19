#!/bin/bash
# Reference solution (oracle): none for wireshark / vulnerability_WF_RAG_6. The dataset has no input that
# triggers the injected vulnerability:
#   the dataset exploit runs no wiretap code: it greps cosine.c to choose a format and sscanf's its own copy of a header line.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
