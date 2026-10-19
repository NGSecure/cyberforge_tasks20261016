#!/bin/bash
# Reference solution (oracle): none for libpng / vulnerability_FZ_13. The dataset's crashing input
#   libpng/vulnerabilities/vulnerability_FZ_13/exploit_files/generated_inputs/curated_seed_1010a3053d41019b510058479b8a0e76d4b296f81d39419c7638cf01b99c3142.png
#   (2073 bytes, sha256 1010a3053d41019b510058479b8a0e76d4b296f81d39419c7638cf01b99c3142)
# is only a Git LFS pointer, in the dataset and in its origin (github.com/Cyb3rForge/CyberForge-projects),
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset's crashing input is only a Git LFS pointer" >&2
exit 1
