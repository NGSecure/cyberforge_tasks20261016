#!/usr/bin/env python3
"""Static checks over generated CyberForge bundles (no Docker needed).

    python3 -I validate.py <out_dir> [--out-b DIR] [--out-c DIR] [bundle ...]

Checks per bundle: required files, no unfilled @@placeholders@@, task.toml /
judge.json / cyberforge_source.json parse, `bash -n` on every script, in-memory
compile of the Python files (no .pyc written), one auth token used consistently,
the ground truth matches its recorded sha256 (and solve.sh decodes to it), the
build inputs referenced by the Dockerfiles exist, every FROM is the recorded
(digest-pinned) base image, the snapshot residue list is consistent and covers
/opt/src_snapshot.tar, and environment/ holds only the expected non-secret files.
Bundles of category 1 (quality.py: the dataset task is fine) live in <out_dir>, category 2
in <out_dir>2, category 3 and pending in <out_dir>3 (as convert.py writes them); a bundle's
directory must match the category its cyberforge_source.json records (or, for a bundle made
without one, its tier: A, B, C).
CLI/program bundles (tier-B templates) also need a recorded recipe whose placeholders
fit its kind and whose extra files exist in build/aux/.
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

ENV_ALLOWED = {"Dockerfile", "docker-compose.yaml", "submit.sh", "description.txt", "task-server/Dockerfile",
               "task-server/task_server.py", "task-server/judge.json", "task-server/cf_delta.py"}
REQUIRED = ["instruction.md", "task.toml", "build.sh", "push.sh", "cyberforge_source.json",
            "tests/test.sh", "tests/verify.py", "solution/solve.sh",
            "build/inject_vulnerability.diff", "build/ground_truth_poc", "build/setup/Dockerfile",
            "build/snapshot_residue.txt", "build/secure_lines.txt"]
B_KINDS = ("cli-file", "cli-stdin", "cli-argv", "program")


def check_recipe(bd, judge):
    """The tier-B judge.json: steps fit the kind, extra files are in build/aux/."""
    errs = []
    kind, steps = judge.get("kind"), judge.get("steps") or []
    runs = [st for st in steps if st.get("role") == "run"]
    if kind not in B_KINDS or not runs or steps[-1].get("role") != "run":
        return ["judge.json: bad kind %r or no final run step" % kind]
    flat = [a for st in steps for a in st["argv"]]
    if kind == "cli-file" and not any("{poc}" in a for a in runs[0]["argv"]):
        errs.append("cli-file run step does not name {poc}")
    if kind == "cli-stdin" and runs[0].get("stdin") != "poc":
        errs.append("cli-stdin run step does not read the PoC on stdin")
    if kind == "cli-argv" and runs[0]["argv"][1:] != ["{args}"]:
        errs.append("cli-argv run step is not <program> {args}")
    if kind == "program":
        comp = [st for st in steps if st.get("role") == "compile"]
        if not comp or not any("{poc}" in st["argv"] for st in comp):
            errs.append("program recipe has no compile step that takes {poc}")
        if not judge.get("touched_files"):
            errs.append("program recipe without touched_files (its crash check needs them)")
    if kind in ("cli-file", "program") and not (judge.get("poc_path") or "").startswith(("/tmp/", "/workspace/", "/exploit")):
        errs.append("poc_path %r is not a scratch path" % judge.get("poc_path"))
    if kind not in ("cli-file", "program") and judge.get("poc_path"):
        errs.append("poc_path set for %s" % kind)
    if any("{poc}" in a for a in flat) and kind not in ("cli-file", "program"):
        errs.append("{poc} in a %s recipe" % kind)
    for dst, n in (judge.get("aux_files") or {}).items():
        if not os.path.isfile(os.path.join(bd, "build", "aux", n)):
            errs.append("aux file missing: build/aux/" + n)
    return errs


FOLDER_CATS = {"A": ("第一类",), "B": ("第二类",), "C": ("第三类", "待确认")}  # <out_dir>, <out_dir>2, <out_dir>3


def check(bd, tier):
    errs = []
    name = os.path.basename(bd)
    try:
        src = json.load(open(os.path.join(bd, "cyberforge_source.json")))
    except Exception as e:
        return ["cyberforge_source.json: %s" % e]
    b = src.get("pov_kind") in B_KINDS
    env_allowed = ENV_ALLOWED
    for f in REQUIRED + ["environment/" + f for f in sorted(env_allowed)] + (["build/aux/README.txt"] if b else []):
        if not os.path.isfile(os.path.join(bd, f)):
            errs.append("missing " + f)
    if errs:
        return errs
    q = (src.get("quality") or {}).get("category")
    if q and q not in FOLDER_CATS[tier]:
        errs.append("bundle is in the %s directory but its category is %s" % ("/".join(FOLDER_CATS[tier]), q))
    elif not q and src.get("tier") != tier:
        errs.append("bundle is in the tier-%s directory but its tier is %s" % (tier, src.get("tier")))
    env_files = set()
    for dp, _, fn in os.walk(os.path.join(bd, "environment")):
        for f in fn:
            env_files.add(os.path.relpath(os.path.join(dp, f), os.path.join(bd, "environment")))
    if env_files != env_allowed:
        errs.append("environment/ has unexpected files: %s" % sorted(env_files ^ env_allowed))
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
    except Exception as e:
        return errs + ["judge.json: %s" % e]
    if b:
        errs += check_recipe(bd, judge)
    elif not judge.get("fuzzer_candidates"):
        errs.append("judge.json has no fuzzer candidates")
    for f in ("build.sh", "push.sh", "tests/test.sh", "solution/solve.sh", "environment/submit.sh"):
        r = subprocess.run(["bash", "-n", os.path.join(bd, f)], capture_output=True, text=True)
        if r.returncode:
            errs.append("bash -n %s: %s" % (f, r.stderr.strip()[:200]))
        if not os.access(os.path.join(bd, f), os.X_OK):
            errs.append("not executable: " + f)
    for f in ("environment/task-server/task_server.py", "tests/verify.py", "environment/task-server/cf_delta.py"):
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
    if hashlib.sha256(gt).hexdigest() != src["ground_truth"]["sha256"] \
            or not (gt or src["ground_truth"].get("degenerate_empty_input")):
        errs.append("ground truth sha256 mismatch, or empty without degenerate_empty_input")
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
        arg = re.search(r"^ARG BASE_IMAGE=(\S+)$", t, re.M)
        froms = re.findall(r"^FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", t, re.M | re.I)
        stages = {s for _, s in froms if s}
        images = [arg.group(1) if arg and f == "${BASE_IMAGE}" else f
                  for f, _ in froms if f not in stages]  # `FROM base AS fix` reuses a stage
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
    if not b and src["harness"].get("built_by_dataset_snapshot_compile") == []:
        errs.append("no harness candidate exists in the base image's own compile (/out)")
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
    args = sys.argv[1:]
    opts = {}
    for flag in ("--out-b", "--out-c"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    out = os.path.abspath(args[0])
    dirs = {"A": out, "B": os.path.abspath(opts.get("--out-b", out + "2")),
            "C": os.path.abspath(opts.get("--out-c", out + "3"))}
    todo = []
    for tier, d in dirs.items():
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if os.path.isdir(os.path.join(d, n)) and n.startswith("cyberforge-") and (len(args) == 1 or n in args[1:]):
                todo.append((tier, os.path.join(d, n)))
    stray = [x for x in ("A", "B", "C") if os.path.isdir(os.path.join(out, x))]
    if stray:
        print("FAIL: leftover tier subdirectories in %s: %s" % (out, stray))
        return 1
    bad = 0
    for tier, bd in todo:
        e = check(bd, tier)
        if e:
            bad += 1
            print("FAIL", os.path.relpath(bd, os.path.dirname(out)))
            for x in e:
                print("    -", x)
    by = {t: sum(1 for x, _ in todo if x == t) for t in dirs}
    print("checked %d bundles (%s): %d ok, %d failed" % (len(todo), ", ".join(
        "%d in %s" % (by[t], os.path.basename(dirs[t])) for t in dirs), len(todo) - bad, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
