#!/bin/bash
# Reference solution (oracle): none for open62541 / vulnerability_WF_RAG_0. The dataset has no input that
# triggers the injected vulnerability:
#   the exploit calls a copy of clear_pubsub_aes256ctr_tpm on a stub struct and checks a pointer, it has no input for any program, and no built program contains the function.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
