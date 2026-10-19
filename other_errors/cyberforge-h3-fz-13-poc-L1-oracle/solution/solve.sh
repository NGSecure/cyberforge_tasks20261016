#!/bin/bash
# Reference solution (oracle): none for h3 / vulnerability_FZ_13. The dataset has no input that
# triggers the injected vulnerability:
#   The change only sets the private _parentRes field of a null iterator, which no public function or harness reads, so no input makes the builds differ.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
