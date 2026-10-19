#!/bin/bash
# Reference solution (oracle): none for double-conversion / vulnerability_FZ_14. The dataset has no input that
# triggers the injected vulnerability:
#   The change is only observable through the internal Bignum class (the failing check is the test's own CheckFloat helper); no public conversion shifts a zero bignum, so no input makes the builds differ.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
