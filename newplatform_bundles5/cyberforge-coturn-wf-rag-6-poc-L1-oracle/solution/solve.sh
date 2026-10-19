#!/bin/bash
# Reference solution (oracle): none for coturn / vulnerability_WF_RAG_6. The dataset has no input that
# triggers the injected vulnerability:
#   the dataset exploit calls a copy of free_http_request cut out of http_server.c on a hand-built struct and has no HTTP input.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
