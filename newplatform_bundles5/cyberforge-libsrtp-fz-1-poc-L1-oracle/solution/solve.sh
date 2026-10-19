#!/bin/bash
# Reference solution (oracle): none for libsrtp / vulnerability_FZ_1. The dataset has no input that
# triggers the injected vulnerability:
#   the off-by-one copies one extra in-struct word (ctx->M[16], inside srtp_sha1_ctx_t), so no out-of-bounds access occurs; it only makes every SHA-1/HMAC output wrong, an input-independent effect the harness never reports.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
