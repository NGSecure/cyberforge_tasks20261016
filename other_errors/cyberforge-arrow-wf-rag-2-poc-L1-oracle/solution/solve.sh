#!/bin/bash
# Reference solution (oracle): none for arrow / vulnerability_WF_RAG_2. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit never runs Arrow code (it greps numpy_convert.cc and fails to link an unrelated CPython program), and the injected file is not compiled by the OSS-Fuzz build.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
