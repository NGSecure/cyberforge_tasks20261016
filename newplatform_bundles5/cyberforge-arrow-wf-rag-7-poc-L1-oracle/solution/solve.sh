#!/bin/bash
# Reference solution (oracle): none for arrow / vulnerability_WF_RAG_7. The dataset has no input that
# triggers the injected vulnerability:
#   the dataset exploit is a placeholder that only greps builder_nested.cc; nothing in the dataset ever called FixedSizeListBuilder::ValidateOverflow.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
