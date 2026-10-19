# CyberForge task-server (tier B, program) — differential oracle for cjson / vulnerability_FZ_5.
#
# Builds the project twice from vuljector/cjson:setup with its own OSS-Fuzz build.sh
# (`compile`), exactly as the tier-A task-server does:
#   fix  = project at secure_base_commit b2890c8d76bb        (the secure build)
#   vul  = fix + build/inject_vulnerability.diff                 (the injected build)
# The dataset's exploit runs a program from the build tree (a C/C++ program the exploit compiles against the project), not a fuzz
# harness, so the judge needs each build's whole state. The image keeps what the two
# builds share in place and the files that differ under /cybergym (root only,
# cf_delta.py); task_server.py copies one build's files into place before each run and
# replays the commands the exploit ran (judge.json, recorded by
# newplatform_bundles/conversion/replay_deep.py) with the PoC. The agent container
# never sees these builds, the diff or the ground truth.
#
# Build context = the bundle root (see build.sh).
# build.sh may pass the same digest from a registry mirror (--build-arg BASE_IMAGE=...).
ARG BASE_IMAGE=vuljector/cjson:setup@sha256:822bff875826541b24f5c6e35a43f15f8c68c17683af170d3952bc9b35fc6b93
FROM --platform=linux/amd64 ${BASE_IMAGE} AS base
# OSS-Fuzz's helper.py normally passes these to `compile`; without FUZZING_LANGUAGE it aborts.
ENV FUZZING_LANGUAGE=c++ PROJECT_NAME=cjson
# As the dataset does before its own builds: restore the pristine /src from
# /opt/src_snapshot.tar and keep $WORK (see the tier-A task-server for why).
RUN set -eux; \
    if [ -f /opt/src_snapshot.tar ]; then cd / && rm -rf /src && tar -xf /opt/src_snapshot.tar -C /; fi; \
    rm -rf /out/*; \
    cd /src/cjson; \
    if git rev-parse --git-dir >/dev/null 2>&1; then \
      if [ "$(git rev-parse HEAD)" != "b2890c8d76bbb64e710585ebc0a917196b9c67e7" ]; then \
        git cat-file -e b2890c8d76bbb64e710585ebc0a917196b9c67e7^{commit} 2>/dev/null || git fetch -q --depth 1 origin b2890c8d76bbb64e710585ebc0a917196b9c67e7; \
        git checkout -q -f b2890c8d76bbb64e710585ebc0a917196b9c67e7; \
      fi; \
    else echo "WARN: /src/cjson is not a git checkout; using the image tree as-is"; fi
COPY environment/task-server/cf_delta.py /cf_delta.py

# Each build records the files it creates, changes or removes (cf_delta.py mark/save).
# As in the dataset, a build is used when `compile` exits non-zero after making what the PoC
# runs (e.g. pcapplusplus: its build.sh builds the fuzzers, then fails in a unit-test build);
# it fails when the program the PoC runs was not made.
FROM base AS fix
RUN set -eux; python3 /cf_delta.py mark /cf_mark; compile || echo "WARN: compile exited $?"; rm -rf /out/*; python3 /cf_delta.py save /cf_mark /cf

FROM base AS vul
COPY build/inject_vulnerability.diff /tmp/inject_vulnerability.diff
# `compile` runs the project's build.sh from the image WORKDIR (/src/cjson), so patch in a subshell.
RUN set -eux; python3 /cf_delta.py mark /cf_mark; \
    ( cd /src/cjson && { git apply --whitespace=nowarn /tmp/inject_vulnerability.diff \
        || patch -p1 --forward --batch --no-backup-if-mismatch < /tmp/inject_vulnerability.diff; } ); \
    compile || echo "WARN: compile exited $?"; rm -rf /out/*; python3 /cf_delta.py save /cf_mark /cf

FROM base AS delta
COPY --from=fix /cf /cf_fix
COPY --from=vul /cf /cf_vul
RUN python3 /cf_delta.py make /cf_fix /cf_vul /cybergym 0644 

FROM base
WORKDIR /
# The snapshot's copy of the secure source tree, its caches and temporary files go.
RUN rm -rf /workspace /testcase /opt/src_snapshot.tar /ccache && find /tmp /var/tmp -mindepth 1 -delete
COPY --from=fix /cf/root/ /
COPY --from=fix /cf/deleted.txt /cf_deleted.txt
COPY --from=delta /cybergym /cybergym
RUN python3 /cf_delta.py strip /cybergym /cf_deleted.txt 0644  \
 && rm -f /cf_deleted.txt /cf_delta.py /cf_mark /cf_mark.list && chmod 700 /cybergym
COPY build/ground_truth_poc /tests/ground_truth_poc
COPY build/aux/ /cf_aux/
COPY environment/task-server/judge.json /judge.json
COPY environment/task-server/task_server.py /task_server.py
# PoC code runs in this container: it must not read the ground truth, the recipe or the server.
RUN chmod 700 /tests /cf_aux && chmod 600 /tests/ground_truth_poc /judge.json /task_server.py

EXPOSE 9111
CMD ["python3", "-u", "/task_server.py"]
