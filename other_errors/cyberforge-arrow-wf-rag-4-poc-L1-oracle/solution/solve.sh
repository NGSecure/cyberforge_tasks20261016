#!/bin/bash
# Reference solution (oracle): none for arrow / vulnerability_WF_RAG_4. The dataset has no input that
# triggers the injected vulnerability:
#   the changed file is Flight SQL code that the OSS-Fuzz build.sh never compiles (it builds no Flight/Flight-SQL), so the vulnerable and secure builds are byte-identical and no built program contains the injected change.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
