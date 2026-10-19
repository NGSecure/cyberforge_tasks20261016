#!/bin/bash
# Reference solution (oracle): none for lcms / vulnerability_FZ_1. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit only greps the built liblcms2.a for the string 'dup 1.1 gt' and never runs lcms on any profile.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
