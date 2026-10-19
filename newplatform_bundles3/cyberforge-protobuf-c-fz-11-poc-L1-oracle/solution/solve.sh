#!/bin/bash
# Reference solution (oracle): none for protobuf-c / vulnerability_FZ_11. The dataset's crashing input
#   protobuf-c/vulnerabilities/vulnerability_FZ_11/exploit_files/generated_inputs/curated_seed_4b0ba71ad53bd38f1fd05ac92859ecc0df91b4561c36d27c8fb667196cdbb955.bin
#   (102 bytes, sha256 4b0ba71ad53bd38f1fd05ac92859ecc0df91b4561c36d27c8fb667196cdbb955)
# is only a Git LFS pointer, in the dataset and in its origin (github.com/Cyb3rForge/CyberForge-projects),
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset's crashing input is only a Git LFS pointer" >&2
exit 1
