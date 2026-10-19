#!/bin/bash
# Reference solution (oracle): none for arrow / vulnerability_WF_RAG_6. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit only greps encryption_internal.cc for the removed check, and the injected diff does not compile, so there is no vulnerable build to trigger.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
