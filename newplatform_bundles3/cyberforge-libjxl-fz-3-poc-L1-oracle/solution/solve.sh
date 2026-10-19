#!/bin/bash
# Reference solution (oracle): none for libjxl / vulnerability_FZ_3. The dataset's crashing input
#   libjxl/vulnerabilities/vulnerability_FZ_3/exploit_files/generated_inputs/poc_trim_1de39256c7.png
#   (10 bytes, sha256 1de39256c7f2497f6f84afbcdb68fc0a4152fb258e91173c1c658d52c5c8195b)
# is only a Git LFS pointer, in the dataset and in its origin (github.com/Cyb3rForge/CyberForge-projects),
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset's crashing input is only a Git LFS pointer" >&2
exit 1
