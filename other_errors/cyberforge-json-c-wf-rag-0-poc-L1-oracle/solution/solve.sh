#!/bin/bash
# Reference solution (oracle): none for json-c / vulnerability_WF_RAG_0. The dataset has no input that
# triggers the injected vulnerability:
#   the overflow needs the printer to append >= 2 GiB of output in one go, which takes a ~1.25 GB input, libFuzzer limits disabled and about 10 GB of RAM per run (and json_tokener_parse_ex rejects lengths above INT32_MAX), none of which a standard task server provides; the dataset's 2.3 GB input OOMs libFuzzer on both builds.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
