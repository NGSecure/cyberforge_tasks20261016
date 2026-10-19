#!/bin/bash
# Reference solution (oracle): none for h3 / vulnerability_WF_LLM_1. The dataset has no input that
# triggers the injected vulnerability:
#   the dataset's input is 200M invalid H3 cells (reserved high bit set) that validateCellSet rejects before the changed code, and libFuzzer OOMs loading the 1.6 GB file on both builds; the injected NULL-check removal is reachable only when a calloc fails, which no dataset input arranges.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
