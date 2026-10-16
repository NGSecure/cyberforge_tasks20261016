#!/usr/bin/env python3
"""Static checks over generated CyberForge bundles (no Docker needed).

    python3 -I validate.py <out_dir> [bundle ...]

Checks per bundle: required files, no unfilled @@placeholders@@, task.toml /
judge.json / cyberforge_source.json parse, `bash -n` on every script, in-memory
compile of the Python files (no .pyc written), one auth token used consistently,
the ground truth matches its recorded sha256 (and solve.sh decodes to it), the
build inputs referenced by the Dockerfiles exist, every FROM is the recorded
(digest-pinned) base image, the snapshot residue list is consistent and covers
/opt/src_snapshot.tar, and environment/ holds only the expected non-secret files.
Exits non-zero if any bundle fails.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib

ENV_ALLOWED = {"Dockerfile", "docker-compose.yaml", "submit.sh", "description.txt",
               "task-server/Dockerfile", "task-server/task_server.py", "task-server/judge.json"}
REQUIRED = ["instruction.md", "task.toml", "build.sh", "push.sh", "cyberforge_source.json",
            "tests/test.sh", "tests/verify.py", "solution/solve.sh",
            "build/inject_vulnerability.diff", "build/ground_truth_poc", "build/setup/Dockerfile",
            "build/snapshot_residue.txt", "build/secure_lines.txt"] + \
    ["environment/" + f for f in sorted(ENV_ALLOWED)]


def check(bd):
    errs = []
    name = os.path.basename(bd)
    for f in REQUIRED:
        if not os.path.isfile(os.path.join(bd, f)):
            errs.append("missing " + f)
    if errs:
        return errs
    env_files = set()
    for dp, _, fn in os.walk(os.path.join(bd, "environment")):
        for f in fn:
            env_files.add(os.path.relpath(os.path.join(dp, f), os.path.join(bd, "environment")))
    if env_files != ENV_ALLOWED:
        errs.append("environment/ has unexpected files: %s" % sorted(env_files ^ ENV_ALLOWED))
    for dp, dn, fn in os.walk(bd):
        if "__pycache__" in dn or any(f.endswith(".pyc") for f in fn):
            errs.append("bytecode under " + os.path.relpath(dp, bd))
        if os.path.relpath(dp, bd).startswith("build"):
            continue  # dataset-provided inputs are copied verbatim
        for f in fn:
            p = os.path.join(dp, f)
            try:
                t = open(p, encoding="utf-8").read()
            except UnicodeDecodeError:
                continue
            if re.search(r"@@[A-Z0-9_]+@@", t):
                errs.append("unfilled placeholder in " + os.path.relpath(p, bd))
    try:
        toml = tomllib.load(open(os.path.join(bd, "task.toml"), "rb"))
        if toml["task"]["name"] != "nwrc/" + name:
            errs.append("task.toml name %r != dir" % toml["task"]["name"])
        if "network_mode" in toml.get("agent", {}) or "allowed_hosts" in toml.get("agent", {}):
            errs.append("[agent] declares network policy")
    except Exception as e:
        errs.append("task.toml: %s" % e)
    try:
        judge = json.load(open(os.path.join(bd, "environment/task-server/judge.json")))
        if not judge.get("fuzzer_candidates"):
            errs.append("judge.json has no fuzzer candidates")
        src = json.load(open(os.path.join(bd, "cyberforge_source.json")))
    except Exception as e:
        return errs + ["json: %s" % e]
    for f in ("build.sh", "push.sh", "tests/test.sh", "solution/solve.sh", "environment/submit.sh"):
        r = subprocess.run(["bash", "-n", os.path.join(bd, f)], capture_output=True, text=True)
        if r.returncode:
            errs.append("bash -n %s: %s" % (f, r.stderr.strip()[:200]))
        if not os.access(os.path.join(bd, f), os.X_OK):
            errs.append("not executable: " + f)
    for f in ("environment/task-server/task_server.py", "tests/verify.py"):
        try:
            compile(open(os.path.join(bd, f), encoding="utf-8").read(), f, "exec")
        except SyntaxError as e:
            errs.append("python %s: %s" % (f, e))
    compose = open(os.path.join(bd, "environment/docker-compose.yaml")).read()
    test_sh = open(os.path.join(bd, "tests/test.sh")).read()
    solve = open(os.path.join(bd, "solution/solve.sh")).read()
    toks = set(re.findall(r"AUTH_TOKEN=([0-9a-f]{32})", compose)) | \
        set(re.findall(r'AUTH_TOKEN="([0-9a-f]{32})"', test_sh)) | \
        set(re.findall(r"X-Submission-Token: ([0-9a-f]{32})", solve))
    if len(toks) != 1:
        errs.append("auth token inconsistent: %s" % sorted(toks))
    gt = open(os.path.join(bd, "build/ground_truth_poc"), "rb").read()
    if hashlib.sha256(gt).hexdigest() != src["ground_truth"]["sha256"] or not gt:
        errs.append("ground truth sha256 mismatch or empty")
    m = re.search(r"<<'B64'\n(.*?)\nB64\n", solve, re.S)  # the terminator is a line of its own
    if m and base64.b64decode(m.group(1)) != gt:
        errs.append("solve.sh payload != ground truth")
    if not m and "/solve" not in solve:
        errs.append("solve.sh neither inlines nor fetches the ground truth")
    for df in ("environment/Dockerfile", "environment/task-server/Dockerfile"):
        t = open(os.path.join(bd, df)).read()
        for ref in re.findall(r"^COPY\s+(?!--from)(\S+)\s", t, re.M):
            if not os.path.exists(os.path.join(bd, ref)):
                errs.append("%s copies missing %s" % (df, ref))
        froms = re.findall(r"^FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", t, re.M | re.I)
        stages = {s for _, s in froms if s}
        images = [f for f, _ in froms if f not in stages]  # `FROM base AS fix` reuses a stage
        if not images or any(f != src["base_image"] for f in images):
            errs.append(df + " does not build FROM the recorded base image")
    if src["base_image_published"] and "@sha256:" not in src["base_image"]:
        errs.append("published base image is not pinned by digest")
    if "BASE=%s " % src["base_image"] not in open(os.path.join(bd, "build.sh")).read():
        errs.append("build.sh BASE != recorded base image")
    for f in ("build/snapshot_residue.txt", "build/secure_lines.txt"):
        lines = open(os.path.join(bd, f), encoding="utf-8").read().split("\n")
        if lines[-1] != "" or any(not x.strip() for x in lines[:-1]):
            errs.append(f + " must be newline-terminated with no blank lines")
    residue = open(os.path.join(bd, "build/snapshot_residue.txt"), encoding="utf-8").read().splitlines()
    snap = src.get("base_image_snapshot")
    if (snap or {}).get("scrubbed_from_agent_image", 0) != len(residue):
        errs.append("snapshot_residue.txt length != cyberforge_source.json")
    if snap and snap.get("secure_source_tarball_present") and "/opt/src_snapshot.tar" not in residue:
        errs.append("/opt/src_snapshot.tar is not scrubbed")
    desc = open(os.path.join(bd, "environment/description.txt")).read().strip()
    if not desc or "\n" in desc:
        errs.append("description.txt must be one non-empty line")
    if src["secure_base_commit"] in open(os.path.join(bd, "instruction.md")).read() + desc:
        errs.append("agent-visible text leaks the secure base commit")
    return errs


def main():
    out = sys.argv[1]
    names = sys.argv[2:] or sorted(d for d in os.listdir(out)
                                   if os.path.isdir(os.path.join(out, d)) and d.startswith("cyberforge-"))
    bad = 0
    for n in names:
        e = check(os.path.join(out, n))
        if e:
            bad += 1
            print("FAIL", n)
            for x in e:
                print("    -", x)
    print("checked %d bundles: %d ok, %d failed" % (len(names), len(names) - bad, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
