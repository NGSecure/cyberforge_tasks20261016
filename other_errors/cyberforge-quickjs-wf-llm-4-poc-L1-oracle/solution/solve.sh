#!/bin/bash
# Reference solution (oracle): none for quickjs / vulnerability_WF_LLM_4. The dataset has no input that
# triggers the injected vulnerability:
#   The injection only adds a comment, so no input behaves differently on the two builds.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
