#!/bin/bash
# Reference solution (oracle): none for hdf5 / vulnerability_FZ_2. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit only greps H5FScache.c for the injected loop bound and never runs a harness; the dataset has no HDF5 file that reaches the changed loop.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
