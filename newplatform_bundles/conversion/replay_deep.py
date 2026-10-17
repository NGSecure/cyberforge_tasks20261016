#!/usr/bin/env python3
"""Record exactly what each exploit.sh runs, inside the project's own base image.

    python3 -I replay_deep.py <inner_root> <snapshot_scan/> <out_dir/> TASK_PATH ...

replay_exploits.py runs exploits in a generic container and only sees fuzz-harness
calls. Tier-B exploits drive other programs: a project CLI built by `compile`, or a
C/C++ driver they compile themselves. This replays each given task in a throwaway
container of the project's pinned base image (no network) with every program the
exploit may run replaced by a recorder that saves its argv, cwd, sanitizer-related
environment, stdin and every file argument, then exits 0:

    harness   every executable in /out (the snapshot's fuzz harnesses)
    cli       compile products under /src or /usr/local/bin that exploit.sh names
              (by path or by basename), per snapshot_scan/<project>.json
    cc        clang/clang++/gcc/g++/cc/c++; with `-o X` a `driver` recorder is
              written at X, so the exploit's later run of X is recorded too
    build     make, cmake, ninja (no-ops)

Output: <out_dir>/<project>/<vuln>/calls.json  [{kind, path, argv, cwd, env,
files: {argv_index: saved_name}, stdin}, ...] plus the saved files, and log.txt.
Tasks are processed per project (one image pull each); existing calls.json are kept.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

MAX_KB = 16 * 1024
EXPLOIT_DIRS = ["/tmp/exploit", "/workspace/run/attempt/artifacts/exploit_files", "/exploit", "/tmp/attack"]

RECORDER = r'''#!/usr/bin/env python3
import json, os, stat, sys
kind, me, args = sys.argv[1], sys.argv[2], sys.argv[3:]
cap = "/captured"
n = len([f for f in os.listdir(cap) if f.startswith("call-") and f.endswith(".json")])
rec = {"kind": kind, "path": me, "argv": args, "cwd": os.getcwd(),
       "env": {k: v for k, v in os.environ.items()
               if k.endswith("_OPTIONS") or k in ("LD_LIBRARY_PATH", "LD_PRELOAD")},
       "files": {}, "stdin": None}
for i, a in enumerate(args):
    for cand in (a, a.split("=", 1)[1] if a.startswith("-") and "=" in a else None):
        if cand and os.path.isfile(cand) and os.path.getsize(cand) <= %d * 1024:
            name = "call-%%03d-arg-%%d" %% (n, i)
            with open(cand, "rb") as s, open(os.path.join(cap, name), "wb") as d:
                d.write(s.read())
            rec["files"][str(i)] = name
            break
try:
    st = os.fstat(0)
    if stat.S_ISREG(st.st_mode) or stat.S_ISFIFO(st.st_mode):
        data = os.read(0, %d * 1024)
        if data:
            name = "call-%%03d-stdin" %% n
            open(os.path.join(cap, name), "wb").write(data)
            rec["stdin"] = name
except OSError:
    pass
if kind == "cc" and "-o" in args and args.index("-o") + 1 < len(args):
    out = args[args.index("-o") + 1]
    try:
        with open(out, "w") as f:
            f.write("#!/bin/sh\nexec /cf_rec/py /cf_rec/rec.py driver \"$0\" \"$@\"\n")
        os.chmod(out, 0o755)
    except OSError:
        pass
json.dump(rec, open(os.path.join(cap, "call-%%03d.json" %% n), "w"))
sys.exit(0)
''' % (MAX_KB, MAX_KB)

SETUP = r'''
set -u
mkdir -p /cf_rec && cp /cf_in/rec.py /cf_rec/rec.py && chmod 755 /cf_rec/rec.py
ln -s "$(command -v python3)" /cf_rec/py
wrap() {  # wrap <kind> <path>: replace the program at <path> by the recorder
  [ -e "$2" ] || [ "$1" = harness ] || return 0
  rm -f "$2"; mkdir -p "$(dirname "$2")"
  printf '#!/bin/sh\nexec /cf_rec/py /cf_rec/rec.py %%s "$0" "$@"\n' "$1" > "$2"; chmod 755 "$2"
}
for f in /out/*; do [ -f "$f" ] && [ -x "$f" ] && [ "${f##*/}" != llvm-symbolizer ] && wrap harness "$f"; done
while read -r p; do [ -n "$p" ] && [ -f "$p" ] && wrap cli "$p"; done < /cf_in/cli_paths.txt
for d in /usr/local/bin /usr/bin /bin; do
  for c in clang clang++ gcc g++ cc c++; do [ -e "$d/$c" ] && wrap cc "$d/$c"; done
  for b in make cmake ninja; do [ -e "$d/$b" ] && wrap build "$d/$b"; done
done
for d in %s; do mkdir -p "$d" && cp -a /cf_in/exploit_files/. "$d/"; done
mkdir -p /tmp/exploit_work /captured
cd /tmp && ulimit -f %d && EXPLOIT_DIR=/tmp/exploit timeout 120 bash /tmp/exploit/exploit.sh > /captured/log.txt 2>&1
echo "exit=$?" >> /captured/log.txt
''' % (" ".join(EXPLOIT_DIRS), MAX_KB)


def cli_candidates(es, scan, target_dir):
    """Compile products of the snapshot that exploit.sh names, by path or basename."""
    code = "\n".join(l for l in es.splitlines() if not l.strip().startswith("#"))
    code = re.sub(r"\$\{?(REPO|REPO_DIR|SRC_DIR|PROJECT_DIR|ROOT)\}?", "/src/" + target_dir, code)
    code = re.sub(r"\$\{?SRC\}?", "/src", code)
    words = set(re.findall(r"[\w.+-]+", code))
    out = []
    for p in scan.get("post_setup_files", []):
        if not p.startswith(("/src/", "/usr/local/bin/")) or "/.git/" in p:
            continue
        base = os.path.basename(p)
        if re.search(r"\.(o|a|so[.\d]*|la|lo|c|cc|cpp|h|hpp|py|sh|txt|json|md|log|zip|cmake|in|am|d|Plo|Po)$", base):
            continue
        if p in code or (base in words and len(base) > 2):
            out.append(p)
    return sorted(set(out))


def run_task(root, rel, scan, image, out_root):
    vd = os.path.join(root, "projects", rel)
    project, vuln = rel.split("/vulnerabilities/")
    dst = os.path.join(out_root, project, vuln)
    if os.path.isfile(os.path.join(dst, "calls.json")):
        return "cached"
    es = open(os.path.join(vd, "exploit_files", "exploit.sh"), encoding="utf-8", errors="replace").read()
    td = json.load(open(os.path.join(root, "projects", project, "project.json"))).get("target_dir") or project
    work = tempfile.mkdtemp(prefix="replay_deep_")
    try:
        cin = os.path.join(work, "in")
        os.makedirs(cin)
        shutil.copytree(os.path.join(vd, "exploit_files"), os.path.join(cin, "exploit_files"))
        open(os.path.join(cin, "rec.py"), "w").write(RECORDER)
        open(os.path.join(cin, "cli_paths.txt"), "w").write("\n".join(cli_candidates(es, scan, td)) + "\n")
        cap = os.path.join(work, "captured")
        os.makedirs(cap)
        subprocess.run(["docker", "run", "--rm", "--network", "none", "--memory", "3g", "--pids-limit", "512",
                        "-v", "%s:/cf_in:ro" % cin, "-v", "%s:/captured" % cap,
                        "--entrypoint", "bash", image, "-c", SETUP], capture_output=True, timeout=600)
        calls = []
        for f in sorted(os.listdir(cap)):
            if f.startswith("call-") and f.endswith(".json"):
                calls.append(json.load(open(os.path.join(cap, f))))
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(cap):
            if f.startswith("call-") and not f.endswith(".json") or f == "log.txt":
                shutil.copyfile(os.path.join(cap, f), os.path.join(dst, f))
        json.dump(calls, open(os.path.join(dst, "calls.json"), "w"), indent=1)
        return "%d call(s)" % len(calls)
    finally:
        subprocess.run(["rm", "-rf", work])


def main():
    root, scan_dir, out_root = sys.argv[1:4]
    rels = sys.argv[4:]
    by_project = {}
    for rel in rels:
        by_project.setdefault(rel.split("/")[0], []).append(rel)
    for project, tasks in sorted(by_project.items()):
        pj = json.load(open(os.path.join(root, "projects", project, "project.json")))
        sp = os.path.join(scan_dir, project + ".json")
        if not pj.get("dockerhub_image") or not os.path.isfile(sp):
            for rel in tasks:
                print(rel, "skipped (no published image / scan)", flush=True)
            continue
        scan = json.load(open(sp))
        image = "%s@%s" % (scan["image"], scan["digest"])
        if all(os.path.isfile(os.path.join(out_root, project, r.split("/vulnerabilities/")[1], "calls.json"))
               for r in tasks):
            continue
        # the same digest from Google's Docker Hub mirror when Docker Hub's anonymous limit is hit
        for ref in (image, "mirror.gcr.io/" + image):
            if subprocess.run(["docker", "pull", "-q", ref], capture_output=True).returncode == 0:
                image = ref
                break
        else:
            for rel in tasks:
                print(rel, "skipped (pull failed)", flush=True)
            continue
        for rel in tasks:
            print(rel, run_task(root, rel, scan, image, out_root), flush=True)
        if os.environ.get("REPLAY_DEEP_KEEP_IMAGES") != "1":
            subprocess.run(["docker", "rmi", image], capture_output=True)


if __name__ == "__main__":
    main()
