#!/usr/bin/env python3
"""Find out which of an exploit's fixed candidates is its PoV by running them for real.

    python3 -I select_candidates.py <inner_root> snapshot_scan/ replay_deep/ candidates/ <task> ...

Some exploits try a fixed list of inputs or command lines and stop at the first one that
fails (`for p in ...; do /out/x payload || exit 1; done`); the dataset does not record
which one crashed, and replay_deep.py recorded them all. This builds the project in its
pinned base image the way the task-server does (pristine /src from /opt/src_snapshot.tar,
`compile` with the injected diff), runs exploit.sh with each program it called replaced
by a wrapper that records the call and runs the real program, takes the first call that
crashed (a sanitizer report or a fatal signal; leak reports do not count, as in the
judge); when none did (an exploit may stop early on its own output check), it runs the
recorded calls the exploit did not reach, in recorded order, with the inputs replay_deep
saved. Then it rebuilds without the diff and runs that call again on the secure build.

candidates/<project>/<vuln>/selection.json records each call that ran and the verdicts;
"call" is the index of the chosen call in replay_deep's calls.json (same program,
arguments and input digests), or null. When that call's inputs were pruned from
replay_deep/ (prune_replay_deep.py), the bytes the live run captured are put back, after
checking them against the stub's SHA-256. classify.py (and prune_replay_deep.py) then
read the recording as that one call. Existing selections are kept. Needs Docker; a pull
falls back to mirror.gcr.io like replay_deep.py.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deep_recipe  # noqa: E402

EXPLOIT_DIRS = ["/tmp/exploit", "/workspace/run/attempt/artifacts/exploit_files", "/exploit", "/tmp/attack"]

WRAPPER = r'''#!/usr/bin/env python3
# select_candidates.py: record this call, run the real program, pass its output and status on
import hashlib, json, os, signal, stat, subprocess, sys
me = sys.argv[0]
out = "/cf_out"
n = len([f for f in os.listdir(out) if f.startswith("call-")])
d = os.path.join(out, "call-%03d" % n)
os.makedirs(d)
rec = {"path": me, "argv": sys.argv[1:], "cwd": os.getcwd(), "files": {}, "paths": {}, "stdin": None,
       "env": {k: v for k, v in os.environ.items()
               if k.endswith("_OPTIONS") or k in ("LD_LIBRARY_PATH", "LD_PRELOAD")}}
for i, a in enumerate(sys.argv[1:]):
    for cand in (a, a.split("=", 1)[1] if a.startswith("-") and "=" in a else None):
        if cand and os.path.isfile(cand):
            data = open(cand, "rb").read()
            open(os.path.join(d, "arg-%d" % i), "wb").write(data)
            rec["files"][str(i)] = hashlib.sha256(data).hexdigest()
            rec["paths"][str(i)] = os.path.join(os.getcwd(), cand)
            break
stdin = None
try:
    st = os.fstat(0)
    if stat.S_ISREG(st.st_mode) or stat.S_ISFIFO(st.st_mode):
        stdin = sys.stdin.buffer.read()
        open(os.path.join(d, "stdin"), "wb").write(stdin)
        rec["stdin"] = hashlib.sha256(stdin).hexdigest()
except OSError:
    pass
env = dict(os.environ)
env["ASAN_OPTIONS"] = (env.get("ASAN_OPTIONS", "") + ":detect_leaks=0").lstrip(":")
try:
    p = subprocess.run([me + ".cf-real"] + sys.argv[1:], input=stdin, capture_output=True, env=env, timeout=120)
    rc, o, e = p.returncode, p.stdout, p.stderr
except subprocess.TimeoutExpired as t:
    rc, o, e = 124, t.stdout or b"", t.stderr or b""
rec["rc"] = rc
open(os.path.join(d, "output"), "wb").write(o + b"\n" + e)
json.dump(rec, open(os.path.join(d, "call.json"), "w"))
sys.stdout.buffer.write(o); sys.stderr.buffer.write(e)
sys.exit(128 - rc if rc < 0 else rc)
'''

RUN = r'''
set -u
export FUZZING_LANGUAGE=%(lang)s PROJECT_NAME=%(project)s
restore() {
  if [ -f /opt/src_snapshot.tar ]; then cd / && rm -rf /src && tar -xf /opt/src_snapshot.tar -C /; fi
  cd /src/%(td)s
  if git rev-parse --git-dir >/dev/null 2>&1 && [ "$(git rev-parse HEAD)" != "%(commit)s" ]; then
    git checkout -q -f %(commit)s || exit 3
  fi
}
build() {  # build vul|fix, as the task-server image does
  restore
  if [ "$1" = vul ]; then
    ( cd /src/%(td)s && { git apply --whitespace=nowarn /cf_in/diff \
        || patch -p1 --forward --batch --no-backup-if-mismatch < /cf_in/diff; } ) || exit 3
  fi
  rm -rf /out/*; cd %(workdir)s && compile > /cf_out/build-$1.log 2>&1 || { echo "build $1 failed"; exit 3; }
}
build vul
while read -r p; do
  [ -f "$p" ] || continue
  mv "$p" "$p.cf-real" && cp /cf_in/wrapper.py "$p" && chmod 755 "$p"
done < /cf_in/targets.txt
for d in %(dirs)s; do mkdir -p "$d" && cp -a /cf_in/exploit_files/. "$d/"; done
mkdir -p /tmp/exploit_work
(cd /tmp && ulimit -f %(max_kb)d && EXPLOIT_DIR=/tmp/exploit timeout 900 bash /tmp/exploit/exploit.sh > /cf_out/exploit.log 2>&1;
 echo "exit=$?" >> /cf_out/exploit.log)
python3 /cf_in/pick.py /cf_out > /cf_out/pick.json || exit 4
python3 /cf_in/rest.py /cf_out /cf_in/recorded.json || exit 4
python3 -c 'import json,sys; sys.exit(0 if json.load(open("/cf_out/pick.json"))["live"] is not None else 5)' || exit 0
build fix
python3 /cf_in/rerun.py /cf_out
'''

# crash: a sanitizer report (not a leak), libFuzzer's crash handler, or a fatal signal
CRASH_RE = re.compile(rb"==\d+==\s?ERROR: (AddressSanitizer|MemorySanitizer|UndefinedBehaviorSanitizer)|"
                      rb"runtime error:|ERROR: libFuzzer: deadly signal")
FATAL = {-4, -6, -7, -8, -11, 132, 134, 135, 136, 139}

PICK = r'''
import json, os, re, sys
CRASH_RE = re.compile(%r)
FATAL = %r
out = sys.argv[1]
calls = []
for c in sorted(f for f in os.listdir(out) if f.startswith("call-")):
    j = os.path.join(out, c, "call.json")
    if not os.path.isfile(j):
        continue
    rec = json.load(open(j))
    o = open(os.path.join(out, c, "output"), "rb").read()
    rec["dir"] = c
    rec["crashed"] = bool(CRASH_RE.search(o)) or rec["rc"] in FATAL
    m = re.search(rb"SUMMARY: \w+Sanitizer: ([^\n]*)", o)
    rec["summary"] = m.group(1).decode("utf-8", "replace")[:300] if m else ""
    calls.append(rec)
live = next((i for i, c in enumerate(calls) if c["crashed"]), None)
json.dump({"calls": calls, "live": live}, sys.stdout)
''' % (CRASH_RE.pattern, sorted(FATAL))

REST = r'''
import hashlib, json, os, re, shutil, subprocess, sys
CRASH_RE = re.compile(%r)
FATAL = %r
out, recorded = sys.argv[1], json.load(open(sys.argv[2]))
pick = json.load(open(os.path.join(out, "pick.json")))
if pick["live"] is not None:
    sys.exit(0)
ran = {json.dumps([c["path"], c["argv"]]) for c in pick["calls"]}
for k, r in enumerate(recorded):  # recorded order; calls whose inputs were pruned are not in the list
    if json.dumps([r["path"], r["argv"]]) in ran:
        continue
    d = os.path.join(out, "call-r%%03d" %% k)
    os.makedirs(d)
    paths, files = {}, {}
    for i, src in r["files"].items():
        a = r["argv"][int(i)]
        cand = a.split("=", 1)[1] if a.startswith("-") and "=" in a else a
        dst = os.path.join(r["cwd"], cand)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join("/cf_in", src), dst)
        shutil.copyfile(os.path.join("/cf_in", src), os.path.join(d, "arg-" + i))
        paths[i], files[i] = dst, hashlib.sha256(open(dst, "rb").read()).hexdigest()
    stdin = open(os.path.join("/cf_in", r["stdin"]), "rb").read() if r["stdin"] else None
    if stdin is not None:
        open(os.path.join(d, "stdin"), "wb").write(stdin)
    os.makedirs(r["cwd"], exist_ok=True)
    env = dict(os.environ, **r["env"])
    env["ASAN_OPTIONS"] = (env.get("ASAN_OPTIONS", "") + ":detect_leaks=0").lstrip(":")
    real = r["path"] + ".cf-real" if os.path.exists(r["path"] + ".cf-real") else r["path"]
    try:
        p = subprocess.run([real] + r["argv"], cwd=r["cwd"], input=stdin, capture_output=True, env=env, timeout=120)
        rc, o = p.returncode, p.stdout + b"\n" + p.stderr
    except subprocess.TimeoutExpired:
        rc, o = 124, b""
    open(os.path.join(d, "output"), "wb").write(o)
    m = re.search(rb"SUMMARY: \w+Sanitizer: ([^\n]*)", o)
    rec = {"path": r["path"], "argv": r["argv"], "cwd": r["cwd"], "files": files, "paths": paths,
           "stdin": hashlib.sha256(stdin).hexdigest() if stdin is not None else None, "env": r["env"], "rc": rc,
           "dir": os.path.basename(d), "crashed": bool(CRASH_RE.search(o)) or rc in FATAL,
           "summary": m.group(1).decode("utf-8", "replace")[:300] if m else "", "recorded_index": r["index"]}
    json.dump(rec, open(os.path.join(d, "call.json"), "w"))
    pick["calls"].append(rec)
    if rec["crashed"]:
        pick["live"] = len(pick["calls"]) - 1
        break
json.dump(pick, open(os.path.join(out, "pick.json"), "w"))
''' % (CRASH_RE.pattern, sorted(FATAL))

RERUN = r'''
import json, os, re, shutil, subprocess, sys
CRASH_RE = re.compile(%r)
FATAL = %r
out = sys.argv[1]
pick = json.load(open(os.path.join(out, "pick.json")))
c = pick["calls"][pick["live"]]
d = os.path.join(out, c["dir"])
for i, dst in c["paths"].items():  # the inputs where the vulnerable run had them
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(os.path.join(d, "arg-" + i), dst)
os.makedirs(c["cwd"], exist_ok=True)
env = dict(os.environ, **c["env"])
env["ASAN_OPTIONS"] = (env.get("ASAN_OPTIONS", "") + ":detect_leaks=0").lstrip(":")
stdin = open(os.path.join(d, "stdin"), "rb").read() if c["stdin"] else None
try:
    p = subprocess.run([c["path"]] + c["argv"], cwd=c["cwd"], input=stdin, capture_output=True, env=env, timeout=120)
    rc, o = p.returncode, p.stdout + b"\n" + p.stderr
except subprocess.TimeoutExpired:
    rc, o = 124, b""
m = re.search(rb"SUMMARY: \w+Sanitizer: ([^\n]*)", o)
json.dump({"rc": rc, "crashed": bool(CRASH_RE.search(o)) or rc in FATAL,
           "summary": m.group(1).decode("utf-8", "replace")[:300] if m else ""}, open(os.path.join(out, "fix.json"), "w"))
''' % (CRASH_RE.pattern, sorted(FATAL))


def workdir_of(dockerfile):
    """The WORKDIR the project's OSS-Fuzz Dockerfile ends in, as convert.py's setup_workdir()."""
    wd = "/src"
    text = re.sub(r"\\\n", " ", open(dockerfile, encoding="utf-8").read())
    for m in re.finditer(r"^\s*WORKDIR\s+(\S+)", text, re.M | re.I):
        d = re.sub(r"\$\{?SRC\}?", "/src", m.group(1).strip("\"'"))
        wd = os.path.normpath(d if d.startswith("/") else os.path.join(wd, d))
    return wd


def run_task(root, rel, scan, image, deep_root, out_root):
    project, vuln = rel.split("/vulnerabilities/")
    dst = os.path.join(out_root, project, vuln)
    if os.path.isfile(os.path.join(dst, "selection.json")):
        return "cached"
    vd = os.path.join(root, "projects", rel)
    dd = os.path.join(deep_root, project, vuln)
    calls = json.load(open(os.path.join(dd, "calls.json")))
    targets = sorted({c["path"] for c in calls if c["kind"] in ("harness", "cli")})
    pj = json.load(open(os.path.join(root, "projects", project, "project.json")))
    yml = open(os.path.join(root, "projects", project, "setup", "project.yaml"), encoding="utf-8").read()
    m = re.search(r"^language:\s*['\"]?([\w+]+)", yml, re.M)
    work = tempfile.mkdtemp(prefix="select_")
    try:
        cin, cout = os.path.join(work, "in"), os.path.join(work, "out")
        os.makedirs(cin)
        os.makedirs(cout)
        shutil.copytree(os.path.join(vd, "exploit_files"), os.path.join(cin, "exploit_files"))
        shutil.copyfile(os.path.join(vd, "inject_vulnerability.diff"), os.path.join(cin, "diff"))
        open(os.path.join(cin, "targets.txt"), "w").write("\n".join(targets) + "\n")
        recorded = []  # for exploits that stop before trying every candidate (e.g. on their own output check)
        os.makedirs(os.path.join(cin, "rec"))
        for j, rc in enumerate(calls):
            names = list(rc["files"].values()) + ([rc["stdin"]] if rc["stdin"] else [])
            if rc["kind"] not in ("harness", "cli") or any(
                    open(os.path.join(dd, n), "rb").read(len(deep_recipe.PRUNED)) == deep_recipe.PRUNED for n in names):
                continue
            for n in names:
                shutil.copyfile(os.path.join(dd, n), os.path.join(cin, "rec", n))
            recorded.append({"index": j, "path": rc["path"], "argv": rc["argv"], "cwd": rc["cwd"], "env": rc["env"],
                             "files": {i: "rec/" + n for i, n in rc["files"].items()},
                             "stdin": "rec/" + rc["stdin"] if rc["stdin"] else None})
        json.dump(recorded, open(os.path.join(cin, "recorded.json"), "w"))
        for name, text in (("wrapper.py", WRAPPER), ("pick.py", PICK), ("rest.py", REST), ("rerun.py", RERUN)):
            open(os.path.join(cin, name), "w").write(text)
        script = RUN % {"lang": m.group(1) if m else (pj.get("language") or "c++"), "project": project,
                        "td": pj.get("target_dir") or project, "commit": pj.get("secure_base_commit", ""),
                        "workdir": workdir_of(os.path.join(root, "projects", project, "setup", "Dockerfile")),
                        "dirs": " ".join(EXPLOIT_DIRS), "max_kb": deep_recipe.LIMIT >> 10}
        r = subprocess.run(["docker", "run", "--rm", "--network", "none", "--memory", "6g", "--pids-limit", "4096",
                            "-v", "%s:/cf_in:ro" % cin, "-v", "%s:/cf_out" % cout,
                            "--entrypoint", "bash", image, "-c", script], capture_output=True, timeout=7200)
        if not os.path.isfile(os.path.join(cout, "pick.json")):
            return "failed (exit %d): %s" % (r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")[-300:])
        pick = json.load(open(os.path.join(cout, "pick.json")))
        fix = json.load(open(os.path.join(cout, "fix.json"))) if os.path.isfile(os.path.join(cout, "fix.json")) else None
        sel = {"task": rel, "image": image, "calls_run": [
            dict({k: c[k] for k in ("path", "argv", "cwd", "rc", "crashed", "summary")},
                 **({"from_recording": c["recorded_index"]} if c.get("recorded_index") is not None else {}))
            for c in pick["calls"]],
            "live": pick["live"], "fix": fix, "call": None, "why": ""}
        if pick["live"] is None:
            sel["why"] = "no call crashed the rebuilt vulnerable build"
        else:
            c = pick["calls"][pick["live"]]
            if c.get("recorded_index") is not None:
                sel["call"] = c["recorded_index"]
            for j, rc in enumerate(calls if sel["call"] is None else []):  # the same call in replay_deep's recording
                if rc["kind"] not in ("harness", "cli") or rc["path"] != c["path"] or rc["argv"] != c["argv"] \
                        or sorted(rc["files"]) != sorted(c["files"]):
                    continue
                try:
                    same = all(deep_recipe._saved(dd, rc["files"][i], digest=True) == c["files"][i] for i in c["files"])
                except deep_recipe.Truncated:
                    same = False
                if same:
                    sel["call"] = j
                    break
            if sel["call"] is None:
                sel["why"] = "the crashing call is not one replay_deep.py recorded"
            elif fix is None or fix["crashed"]:
                sel["why"] = "the call crashes the secure build too"
            else:  # put the pruned inputs of that call back
                rc = calls[sel["call"]]
                for i, name in rc["files"].items():
                    p = os.path.join(dd, name)
                    if open(p, "rb").read(len(deep_recipe.PRUNED)) == deep_recipe.PRUNED:
                        shutil.copyfile(os.path.join(cout, c["dir"], "arg-" + i), p)
        os.makedirs(dst, exist_ok=True)
        json.dump(sel, open(os.path.join(dst, "selection.json"), "w"), indent=1)
        for f in ("build-vul.log", "build-fix.log", "exploit.log"):
            if os.path.isfile(os.path.join(cout, f)):
                data = open(os.path.join(cout, f), "rb").read()
                open(os.path.join(dst, f), "wb").write(data[:16 << 10] + (b"\n...\n" + data[-16 << 10:]
                                                                          if len(data) > 32 << 10 else b""))
        return "call %s (%s)" % (sel["call"], sel["why"] or "vul crashes, fix does not")
    finally:
        subprocess.run(["rm", "-rf", work])


def main():
    root, scan_dir, deep_root, out_root = sys.argv[1:5]
    by_project = {}
    for rel in sys.argv[5:]:
        by_project.setdefault(rel.split("/")[0], []).append(rel)
    for project, tasks in sorted(by_project.items()):
        scan = json.load(open(os.path.join(scan_dir, project + ".json")))
        image = "%s@%s" % (scan["image"], scan["digest"])
        for ref in (image, "mirror.gcr.io/" + image):
            if subprocess.run(["docker", "pull", "-q", ref], capture_output=True).returncode == 0:
                image = ref
                break
        else:
            for rel in tasks:
                print(rel, "skipped (pull failed)", flush=True)
            continue
        for rel in tasks:
            print(rel, run_task(root, rel, scan, image, deep_root, out_root), flush=True)
        if os.environ.get("REPLAY_DEEP_KEEP_IMAGES") != "1":
            subprocess.run(["docker", "rmi", image], capture_output=True)


if __name__ == "__main__":
    main()
