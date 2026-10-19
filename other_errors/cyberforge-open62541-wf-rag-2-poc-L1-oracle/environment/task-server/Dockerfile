# CyberForge task-server (category 5, harness, oracle crash) — judge for open62541 / vulnerability_WF_RAG_2.
#
# Builds the project twice from vuljector/open62541:setup with its own OSS-Fuzz build.sh
# (`compile`), exactly as the tier-A task-server does:
#   fix  = project at secure_base_commit 8d060e94c11b        (the secure build)
#   vul  = fix + build/inject_vulnerability.diff                 (the injected build)
# The PoC goes to the fuzz harness `/out/fuzz_binary_message` (judge.json "steps"; newplatform_bundles/conversion/
# c5_specs.json says where they come from), so the judge needs each build's whole state.
# The image keeps what the two builds share in place and the files that differ under
# /cybergym (root only, cf_delta.py); task_server.py copies one build's files into place
# before each run, runs the steps with the PoC and reports each run; tests/verify.py
# applies the task's rule (tests/oracle.json). The agent container never sees these
# builds, the diff or the ground truth.
#
# Build context = the bundle root (see build.sh).
# build.sh may pass the same digest from a registry mirror (--build-arg BASE_IMAGE=...).
ARG BASE_IMAGE=vuljector/open62541:setup@sha256:7d330c729380e9bd84794db6c6cd6d6420110b1561c155d0d4e973e882feb3bc
FROM --platform=linux/amd64 ${BASE_IMAGE} AS base
# OSS-Fuzz's helper.py normally passes these to `compile`; without FUZZING_LANGUAGE it aborts.
ENV FUZZING_LANGUAGE=c++ PROJECT_NAME=open62541
# As the dataset does before its own builds: restore the pristine /src from
# /opt/src_snapshot.tar and keep $WORK (see the tier-A task-server for why).
RUN set -eux; \
    if [ -f /opt/src_snapshot.tar ]; then cd / && rm -rf /src && tar -xf /opt/src_snapshot.tar -C /; fi; \
    rm -rf /out/*; \
    cd /src/open62541; \
    if git rev-parse --git-dir >/dev/null 2>&1; then \
      if [ "$(git rev-parse HEAD)" != "8d060e94c11ba5025438bc92bd3ae2df4ba87ed0" ]; then \
        git cat-file -e 8d060e94c11ba5025438bc92bd3ae2df4ba87ed0^{commit} 2>/dev/null || git fetch -q --depth 1 origin 8d060e94c11ba5025438bc92bd3ae2df4ba87ed0; \
        git checkout -q -f 8d060e94c11ba5025438bc92bd3ae2df4ba87ed0; \
      fi; \
    else echo "WARN: /src/open62541 is not a git checkout; using the image tree as-is"; fi
COPY environment/task-server/cf_delta.py /cf_delta.py

# Each build records the files it creates, changes or removes (cf_delta.py mark/save).
# As in the dataset, a build is used when `compile` exits non-zero after making what the PoC
# runs (e.g. pcapplusplus: its build.sh builds the fuzzers, then fails in a unit-test build);
# it fails when the program the PoC runs was not made.
FROM base AS fix
RUN set -eux; python3 /cf_delta.py mark /cf_mark; compile || echo "WARN: compile exited $?"; [ -e /out/fuzz_binary_message ] || { echo "FAIL: the build did not make /out/fuzz_binary_message"; exit 1; }; python3 /cf_delta.py save /cf_mark /cf

FROM base AS vul
COPY build/inject_vulnerability.diff /tmp/inject_vulnerability.diff
# `compile` runs the project's build.sh from the image WORKDIR (/src/open62541), so patch in a subshell.
RUN set -eux; python3 /cf_delta.py mark /cf_mark; \
    ( cd /src/open62541 && { git apply --whitespace=nowarn /tmp/inject_vulnerability.diff \
        || patch -p1 --forward --batch --no-backup-if-mismatch < /tmp/inject_vulnerability.diff; } ); \
    compile || echo "WARN: compile exited $?"; [ -e /out/fuzz_binary_message ] || { echo "FAIL: the build did not make /out/fuzz_binary_message"; exit 1; }; python3 /cf_delta.py save /cf_mark /cf

FROM base AS delta
COPY --from=fix /cf /cf_fix
COPY --from=vul /cf /cf_vul
RUN python3 /cf_delta.py make /cf_fix /cf_vul /cybergym 0600 /out/fuzz_binary_message

FROM base
WORKDIR /
# The snapshot's copy of the secure source tree, its caches and temporary files go.
RUN rm -rf /workspace /testcase /opt/src_snapshot.tar /ccache && find /tmp /var/tmp -mindepth 1 -delete
COPY --from=fix /cf/root/ /
COPY --from=fix /cf/deleted.txt /cf_deleted.txt
COPY --from=delta /cybergym /cybergym
RUN python3 /cf_delta.py strip /cybergym /cf_deleted.txt 0600 /out/fuzz_binary_message \
 && rm -f /cf_deleted.txt /cf_delta.py /cf_mark /cf_mark.list && chmod 700 /cybergym
COPY build/aux/ /cf_aux/
COPY environment/task-server/judge.json /judge.json
COPY environment/task-server/task_server.py /task_server.py
COPY tests/cf_oracle.py /cf_oracle.py
# PoC code runs in this container: it must not read the ground truth, the recipe or the server.
RUN mkdir -p /tests && chmod 700 /tests /cf_aux && chmod 600 /judge.json /task_server.py /cf_oracle.py

EXPOSE 9111
CMD ["python3", "-u", "/task_server.py"]
