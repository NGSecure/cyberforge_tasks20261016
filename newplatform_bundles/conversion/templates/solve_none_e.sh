#!/bin/bash
# Reference solution (oracle): none for @@PROJECT@@ / @@VULN_ID@@. The dataset has no input that
# triggers the injected vulnerability:
#   @@NOGT_WHY@@
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
