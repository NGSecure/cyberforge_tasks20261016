#!/bin/bash
# Reference solution (oracle): none for serenity / vulnerability_FZ_16. The dataset's crashing input
#   serenity/vulnerabilities/vulnerability_FZ_16/exploit_files/generated_inputs/poc_orig_291fd302e9.bin
#   (8 bytes, sha256 291fd302e9f934a2600e313eff93e17d3e052e11fb2b96bb909aca9758eac2a7)
# is only a Git LFS pointer, in the dataset and in its origin (github.com/Cyb3rForge/CyberForge-projects),
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset's crashing input is only a Git LFS pointer" >&2
exit 1
