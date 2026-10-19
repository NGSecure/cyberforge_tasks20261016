#!/bin/bash
# Reference solution (oracle): none for double-conversion / vulnerability_FZ_12. The dataset's crashing input
#   double-conversion/vulnerabilities/vulnerability_FZ_12/exploit_files/generated_inputs/curated_seed_dcd5943ced96826e5ba593d59ae3246389fdb495927b0e24fbc3c9b905c57fe8.bin
#   (4 bytes, sha256 dcd5943ced96826e5ba593d59ae3246389fdb495927b0e24fbc3c9b905c57fe8)
# is only a Git LFS pointer, in the dataset and in its origin (github.com/Cyb3rForge/CyberForge-projects),
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset's crashing input is only a Git LFS pointer" >&2
exit 1
