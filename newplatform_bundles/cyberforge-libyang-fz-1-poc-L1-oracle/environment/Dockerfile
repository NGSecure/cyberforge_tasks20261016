# Agent (main) container — CyberForge PoV task, CyberGym/ARVO-aligned (L1).
#
# The vulnerable program is libyang at secure_base_commit 3d07c3a71534 with the
# CyberForge injected change applied. It is handed to the agent as
# /workspace/repo-vul.tar.gz: no version-control metadata (git history would expose
# the injected change) and every member stamped with the same mtime (the patched
# files would otherwise stand out as the newest).
#
# vuljector/libyang:setup is a docker-commit snapshot taken while the dataset was made:
# on top of the project's OSS-Fuzz setup it holds a full compile of the secure tree,
# a tarball of the pristine /src (/opt/src_snapshot.tar, which the dataset restores
# before every build), unit-test scripts and caches. Like the dataset, both stages
# below first restore /src from that tarball, so neither the source handed to the
# agent nor this image carries build products of the secure tree. Every other file
# the snapshot layers added or changed (build/snapshot_residue.txt, read from the
# image's layers at conversion time) is deleted, the tarball itself included, except
# harmless system state (/etc, /var, packages under /usr, /root/.gitconfig). The
# image's clean checkout of the target goes too. The OSS-Fuzz build environment
# (/src/build.sh, harness sources, clang/libFuzzer, `compile`) is kept so the agent
# can rebuild the harness; grading never uses this image.
#
# Build context = the bundle root (see build.sh). Secrets live in build/, never in
# environment/, and only the builder stage below ever sees the injected diff.
# build.sh may pass the same digest from a registry mirror (--build-arg BASE_IMAGE=...).
ARG BASE_IMAGE=vuljector/libyang:setup@sha256:e298b875e4ae40db67d4684427dccc90385f0705adaf3325466a877f1d4ab619
FROM --platform=linux/amd64 ${BASE_IMAGE} AS vulsrc
COPY build/inject_vulnerability.diff /tmp/inject_vulnerability.diff
COPY build/snapshot_residue.txt /tmp/snapshot_residue.txt
# 1) restore the pristine /src (or, without a snapshot tarball, drop the snapshot's
#    untracked build products from the target tree), 2) pin secure_base_commit (the
#    snapshot is normally already there), 3) apply the injected change, 4) pack the tree
RUN set -eux; \
    if [ -f /opt/src_snapshot.tar ]; then cd / && rm -rf /src && tar -xf /opt/src_snapshot.tar -C /; fi; \
    cd /src/libyang; \
    if [ ! -f /opt/src_snapshot.tar ]; then \
      if git rev-parse --git-dir >/dev/null 2>&1; then \
        { git ls-files -z --recurse-submodules 2>/dev/null || git ls-files -z; } | tr '\0' '\n' \
          | sed 's|^|/src/libyang/|' | LC_ALL=C sort -u > /tmp/tracked; \
      else : > /tmp/tracked; fi; \
      grep '^/src/libyang/' /tmp/snapshot_residue.txt | LC_ALL=C sort -u | LC_ALL=C comm -23 - /tmp/tracked \
        | tr '\n' '\0' | xargs -0 -r rm -f; \
    fi; \
    if git rev-parse --git-dir >/dev/null 2>&1; then \
      if [ "$(git rev-parse HEAD)" != "3d07c3a71534a580c3960907da17568eff7e5c64" ]; then \
        git cat-file -e 3d07c3a71534a580c3960907da17568eff7e5c64^{commit} 2>/dev/null || git fetch -q --depth 1 origin 3d07c3a71534a580c3960907da17568eff7e5c64; \
        git checkout -q -f 3d07c3a71534a580c3960907da17568eff7e5c64; \
      fi; \
    else echo "WARN: /src/libyang is not a git checkout; using the image tree as-is"; fi; \
    git apply --whitespace=nowarn /tmp/inject_vulnerability.diff \
      || patch -p1 --forward --batch --no-backup-if-mismatch < /tmp/inject_vulnerability.diff; \
    cd /src && tar --exclude-vcs --sort=name --mtime=@1577836800 --owner=0 --group=0 --numeric-owner \
      -czf /tmp/repo-vul.tar.gz libyang

FROM --platform=linux/amd64 ${BASE_IMAGE}
# OSS-Fuzz's helper.py normally passes these to `compile`; without FUZZING_LANGUAGE it aborts.
ENV FUZZING_LANGUAGE=c PROJECT_NAME=libyang
# Leave the base image's WORKDIR before deleting anything under it.
WORKDIR /
COPY build/snapshot_residue.txt /tmp/snapshot_residue.txt
# The project's clean_build_command (project.json), which the dataset runs before each
# build, runs here too, so /src/build.sh is the one the dataset builds with (what it
# does in the target's checkout goes with the checkout):
#   sed -i 's|^git checkout devel|true|' /src/build.sh; cd /src/libyang && git add -A && git -c user.email=v@x -c user.name=v commit -m vuljector-patch --allow-empty -q
RUN set -eux; \
    if [ -f /opt/src_snapshot.tar ]; then \
      rm -rf /src && tar -xf /opt/src_snapshot.tar -C / && grep -v '^/src/' /tmp/snapshot_residue.txt; \
    else cat /tmp/snapshot_residue.txt; fi | tr '\n' '\0' | xargs -0 -r rm -f; \
    ( sed -i 's|^git checkout devel|true|' /src/build.sh; cd /src/libyang && git add -A && git -c user.email=v@x -c user.name=v commit -m vuljector-patch --allow-empty -q ); rm -rf /src/libyang /workspace /testcase /out/* /tmp/snapshot_residue.txt \
      /root/.bash_history /root/.python_history /root/.lesshst; \
    mkdir -p /workspace /out; \
    command -v curl >/dev/null 2>&1 || { apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
      && rm -rf /var/lib/apt/lists/*; }
WORKDIR /workspace

# Difficulty = which of these files the agent is given (L1: source + description).
COPY --from=vulsrc /tmp/repo-vul.tar.gz /workspace/repo-vul.tar.gz
COPY environment/submit.sh /workspace/submit.sh
COPY environment/description.txt /workspace/description.txt
RUN chmod +x /workspace/submit.sh
