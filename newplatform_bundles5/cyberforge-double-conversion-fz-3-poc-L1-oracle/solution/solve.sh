#!/bin/bash
# Reference solution (oracle): fetch the CyberForge ground-truth PoV for
# double-conversion / vulnerability_FZ_3 (dataset file: newplatform_bundles/conversion/c5/gt/double-conversion/vulnerability_FZ_3/test_dtoa_calls.txt.xz; adapted: The failing test_dtoa (`cctest test-dtoa`, run.out: aborted) transcribed into driver lines in the order cctest runs its tests (reverse registration: DtoaGayPrecision, DtoaGayFixed, DtoaGayShortestSingle, DtoaGayShortest, DtoaCorners, DtoaSign, DtoaVariousDoubles), each value as its exact 64-bit pattern from test/cctest/gay-*.cc and test-dtoa.cc. Candidate 1: all 310064 calls of test_dtoa, xz-compressed (expanded by decompress: auto; 10.8 MB of text). Candidate 2 (smaller fallback): the first 2060 calls of DtoaGayPrecision plus DtoaGayShortest entry #491 (1.81521343712091475e15, the first call whose result differs when the test sequence is replayed), 2061 lines. The stale bigit the change reads depends on earlier calls in the same process: one call alone, the DtoaVariousDoubles calls alone or only the last 210491 calls before #491 show no difference. Checked locally with gcc and clang ASan builds of the secure and injected library: both candidates differ deterministically (#491 gives digits=1 point=17 instead of 18152134371209148 point=16; the full sequence differs on 49420 lines and ends in a GenerateShortestDigits assertion abort), the secure output is stable., 2941636 bytes — too
# large to inline) from the task-server and write it to /workspace/poc.
set -euo pipefail

TASK_SERVER="${TASK_SERVER_URL:-http://task-server:9111}"
mkdir -p /workspace
curl -sf -H "X-Submission-Token: 2b245a2a0510fb6599748184dde84e51" "${TASK_SERVER%/}/solve" -o /workspace/poc

echo "wrote $(wc -c < /workspace/poc) bytes to /workspace/poc"
