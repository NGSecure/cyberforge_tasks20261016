#!/bin/bash
# Reference solution (oracle): none for kamailio / vulnerability_FZ_12. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit only greps fmsg.c for the new condition; the changed function runs only for faked messages of a running server, which no built program creates.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
