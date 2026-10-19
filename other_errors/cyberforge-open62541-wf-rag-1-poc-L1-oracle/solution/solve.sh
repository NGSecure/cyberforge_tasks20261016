#!/bin/bash
# Reference solution (oracle): none for open62541 / vulnerability_WF_RAG_1. The dataset has no input that
# triggers the injected vulnerability:
#   the exploit calls a copy of UA_Client_getState with a stub client and a counting UA_malloc; there is no input for any built program, and the project build does not complete in its image.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
