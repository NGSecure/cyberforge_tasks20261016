#!/bin/bash
# Reference solution (oracle): none for serenity / vulnerability_FZ_17. The dataset's crashing input
#   serenity/vulnerabilities/vulnerability_FZ_17/exploit_files/generated_inputs/poc_orig_81c2a21c99.bin
#   (2 bytes, sha256 81c2a21c99c2e261ad6d91443ffb383b57c321d7e33f09cb64c8b946bb14939b)
# is only a Git LFS pointer, in the dataset and in its origin (github.com/Cyb3rForge/CyberForge-projects),
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset's crashing input is only a Git LFS pointer" >&2
exit 1
