#!/usr/bin/env bash
# Phase 1 — BUILD (run on the PUBLIC network). Needs docker.io for the CyberForge
# base image vuljector/unicorn:setup (`docker login` first: anonymous Docker Hub pulls are
# rate-limited) and, while compiling, whatever the project's OSS-Fuzz build.sh
# downloads. No platform credentials. Builds both images with the bundle root as
# build context, then runs the BLOCKING self-checks. When it ends with PASS, switch
# to the upload network and run push.sh.
#   bash cyberforge-unicorn-fz-0-poc-L1-oracle/build.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
B="$(basename "$HERE")"

BASE=vuljector/unicorn:setup@sha256:5aca429a2298ea13a044033174741a7c506aca9680656ea548afbaf568203725   # pinned to the digest whose layers build/snapshot_residue.txt describes
HAS_HUB_IMAGE=1   # 1: published on Docker Hub; 0: build it from build/setup
VER=v0.0.2
MAIN_TAG="cyberforge_unicorn_fz_0_main:${VER}"
TS_TAG="cyberforge_unicorn_fz_0_task_server:${VER}"

echo "==> base image $BASE"
# The same digest is also served by Google's Docker Hub mirror, which is not subject to
# Docker Hub's anonymous pull limit; content is identical (the digest pins it).
MIRROR="mirror.gcr.io/${BASE#docker.io/}"
if docker image inspect "$BASE" >/dev/null 2>&1; then
  :
elif [ "$HAS_HUB_IMAGE" = 1 ] && docker image inspect "$MIRROR" >/dev/null 2>&1; then
  BASE="$MIRROR"
elif [ "$HAS_HUB_IMAGE" = 1 ]; then
  docker pull "$BASE" || { echo "    Docker Hub pull failed; trying $MIRROR"; docker pull "$MIRROR"; BASE="$MIRROR"; }
else
  echo "    not published for this project: building it from build/setup (the project's OSS-Fuzz setup)"
  docker build -t "$BASE" build/setup
fi

echo "==> build main sandbox  $MAIN_TAG"
docker build -t "$MAIN_TAG" --build-arg BASE_IMAGE="$BASE" -f environment/Dockerfile .
echo "==> build task-server   $TS_TAG  (compiles the secure and the vulnerable build)"
docker build -t "$TS_TAG" --build-arg BASE_IMAGE="$BASE" -f environment/task-server/Dockerfile .

echo "==> self-check 1/3: the agent sandbox holds no clean source, history or snapshot residue"
# With /opt/src_snapshot.tar in the base image, environment/Dockerfile replaced /src by the
# pristine tree, so the snapshot's /src entries are setup files again; check the rest.
SRC_RESTORED=$(docker run --rm --entrypoint sh "$BASE" -c 'test -f /opt/src_snapshot.tar && echo 1 || echo 0')
docker run --rm -e SRC_RESTORED="$SRC_RESTORED" -v "$HERE/build/snapshot_residue.txt:/cf_check/residue.txt:ro" \
  --entrypoint python3 "$MAIN_TAG" -c '
import os, sys, tarfile
bad = []
t = "/workspace/repo-vul.tar.gz"
if not os.path.isfile(t) or not os.path.getsize(t):
    sys.exit("FAIL: missing " + t)
with tarfile.open(t) as tf:
    for m in tf:
        parts = m.name.split("/")
        if ".git" in parts:
            bad.append("git metadata in the tarball: " + m.name)
        if m.mtime != 1577836800:
            bad.append("unnormalized mtime in the tarball: " + m.name)
if os.path.lexists("/src/unicorn"):
    bad.append("clean checkout still present at /src/unicorn")
skip_src = os.environ.get("SRC_RESTORED") == "1"
left = [p for p in open("/cf_check/residue.txt").read().splitlines()
        if p and os.path.lexists(p) and not (skip_src and p.startswith("/src/"))]
if os.path.lexists("/opt/src_snapshot.tar"):
    bad.append("/opt/src_snapshot.tar (pristine secure /src) still present")
bad += ["snapshot residue still present: " + p for p in left]
for b in bad[:20]:
    print("    " + b)
sys.exit("FAIL: %d problem(s)" % len(bad) if bad else 0)
'
echo "    ok"

echo "==> self-check 2/3: no copy of the secure source outside the setup tree"
docker run --rm -v "$HERE/build/secure_lines.txt:/cf_check/secure_lines.txt:ro" \
  --entrypoint sh "$MAIN_TAG" -c '
[ -s /cf_check/secure_lines.txt ] || { echo "    (no distinctive removed lines in the diff; skipped)"; exit 0; }
# description.txt is the task text itself (it may quote code); the tarball is compressed.
hits=$(grep -rlF -f /cf_check/secure_lines.txt --exclude=description.txt --exclude=repo-vul.tar.gz \
  /opt /tmp /root /home /work /out /workspace /var/tmp /ccache 2>/dev/null | head -20 || true)
if [ -n "$hits" ]; then echo "FAIL: secure-version lines of the injected change found in:"; echo "$hits" | sed "s/^/    /"; exit 1; fi
src=$(grep -rlF -f /cf_check/secure_lines.txt /src 2>/dev/null | head -5 || true)
[ -z "$src" ] || { echo "    note: the same lines also occur in setup-era files (part of the project setup, not snapshot residue):"; echo "$src" | sed "s/^/      /"; }
echo "    ok"'

echo "==> self-check 3/3: differential oracle (ground truth crashes vul, not fix)"
docker run --rm -e AUTH_TOKEN=selfcheck --entrypoint python3 "$TS_TAG" /task_server.py --selfcheck

echo "==> PASS: built $MAIN_TAG and $TS_TAG"
echo "    now switch to the UPLOAD network and run:  bash $B/push.sh"
