#!/bin/bash
# Reference solution (oracle): none for htslib / vulnerability_FZ_7. The dataset has no input that
# triggers the injected vulnerability:
#   the injected `|| option == E_INT` is dead code (the branch just above already handles E_INT), so it changes nothing observable and the two builds behave identically.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
