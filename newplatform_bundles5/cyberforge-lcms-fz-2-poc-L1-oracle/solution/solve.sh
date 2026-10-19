#!/bin/bash
# Reference solution (oracle): none for lcms / vulnerability_FZ_2. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit greps cmsps2.c for a string ('if (0)') the diff does not contain and never runs lcms.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
