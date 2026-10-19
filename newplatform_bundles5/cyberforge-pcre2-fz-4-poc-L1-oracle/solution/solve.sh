#!/bin/bash
# Reference solution (oracle): none for pcre2 / vulnerability_FZ_4. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit only greps pcre2_jit_compile.c for the removed check (its exploit.c is never compiled), so the dataset has no input.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
