#!/bin/bash
# Reference solution (oracle): none for kamailio / vulnerability_FZ_4. The dataset has no input that
# triggers the injected vulnerability:
#   The exploit only greps dns_cache.c and echoes a made-up AddressSanitizer report; the changed loop runs only during NAPTR DNS resolution in a running server, which no built program does.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
