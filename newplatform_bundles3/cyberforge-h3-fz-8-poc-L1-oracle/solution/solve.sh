#!/bin/bash
# Reference solution (oracle): none for h3 / vulnerability_FZ_8. The dataset's crashing input
#   h3/vulnerabilities/vulnerability_FZ_8/exploit_files/generated_inputs/curated_seed_4ceec3009d51e60bcbd77bf5c11ce695781f5846d19d8d29054e0b275ac31dd2.bin
#   (1027 bytes, sha256 4ceec3009d51e60bcbd77bf5c11ce695781f5846d19d8d29054e0b275ac31dd2)
# is only a Git LFS pointer, in the dataset and in its origin (github.com/Cyb3rForge/CyberForge-projects),
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset's crashing input is only a Git LFS pointer" >&2
exit 1
