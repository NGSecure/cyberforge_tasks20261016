#!/bin/bash
# Reference solution (oracle): none for wireshark / vulnerability_WF_RAG_8. The dataset has no input that
# triggers the injected vulnerability:
#   the dataset exploit runs no wiretap code: it greps file_wrappers.c and runs its own copy of a zlib loop.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
