#!/bin/bash
# Reference solution (oracle): none for brotli / vulnerability_FZ_4. The dataset's crashing input
#   brotli/vulnerabilities/vulnerability_FZ_4/exploit_files/generated_inputs/curated_seed_060ecfec95844561e55d79d9fe4ca996b849c9d1045738713b8d445f2bfd93f4.bin
#   (67 bytes, sha256 060ecfec95844561e55d79d9fe4ca996b849c9d1045738713b8d445f2bfd93f4)
# is only a Git LFS pointer, in the dataset and in its origin (github.com/Cyb3rForge/CyberForge-projects),
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset's crashing input is only a Git LFS pointer" >&2
exit 1
