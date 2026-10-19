#!/bin/bash
# Reference solution (oracle): none for open62541 / vulnerability_WF_RAG_2. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit only compiles a pasted copy of the source into a stub program (which fails to compile on the vulnerable tree), and the injected OpenSSL plugin is not compiled by the OSS-Fuzz build.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
