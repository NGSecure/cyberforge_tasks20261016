#!/bin/bash
# Reference solution (oracle): none for @@PROJECT@@ / @@VULN_ID@@. The dataset's crashing input
#   @@POC_SRC_PATH@@
#   (@@POC_SIZE@@ bytes, sha256 @@GT_SHA256@@)
# is only a Git LFS pointer, in the dataset and in its origin (github.com/Cyb3rForge/CyberForge-projects),
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset's crashing input is only a Git LFS pointer" >&2
exit 1
