#!/bin/bash
# Reference solution (oracle): none for kamailio / vulnerability_FZ_14. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit only greps msg_parser.c for the new condition, and in every state the built fuzzers reach the new and the old condition agree.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
