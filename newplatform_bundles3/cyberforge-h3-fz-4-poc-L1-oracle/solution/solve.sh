#!/bin/bash
# Reference solution (oracle): none for h3 / vulnerability_FZ_4. The dataset's crashing input
#   h3/vulnerabilities/vulnerability_FZ_4/exploit_files/generated_inputs/curated_seed_0bff19072fa99dad78bf998531108a726d446ccdb6a1152683f2872877254fd8.bin
#   (2048 bytes, sha256 0bff19072fa99dad78bf998531108a726d446ccdb6a1152683f2872877254fd8)
# is only a Git LFS pointer, in the dataset and in its origin (github.com/Cyb3rForge/CyberForge-projects),
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset's crashing input is only a Git LFS pointer" >&2
exit 1
