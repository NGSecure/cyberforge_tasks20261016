#!/usr/bin/env python3
"""Build bundles and record their self-check verdicts; optionally try other ground truths.

    python3 -I verify_bundles.py <plan.json> <results.jsonl> [--max-seconds N]

plan.json is a list of {"bundle": <bundle dir>, "alts": {label: file}, "judge_alts":
{label: {judge.json keys to override}}}, in the order to run. For each bundle this runs
its build.sh (both images and the three blocking self-checks) and records the exit code,
the self-check 3 verdict and, when the build failed, why (e.g. a build step that needs the
network). Then, in the task-server image build.sh made, it runs the self-check again with
each alternative ground truth (e.g. the dataset's own pov.bin when the bundle's ground
truth differs from it) and with each alternative judge.json (e.g. leak detection on).

Results already in results.jsonl are kept (the run can be resumed); --max-seconds stops
after the bundle that crosses the limit. A bundle's images are removed after it, and the
build cache whenever the next bundle is of another project, so the run fits a fixed disk.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time

NETWORK_RE = re.compile(r"Could not resolve host|unable to access 'https?://|server certificate verification failed|"
                        r"Temporary failure in name resolution|Failed to connect to|Network is unreachable")


def verdict_of(text):
    v = re.findall(r'"verdict": "([^"]+)"', text)
    return v[-1] if v else ""


def selfcheck(ts_tag, mounts):
    cmd = ["docker", "run", "--rm", "-e", "AUTH_TOKEN=selfcheck"]
    for src, dst in mounts:
        cmd += ["-v", "%s:%s:ro" % (src, dst)]
    p = subprocess.run(cmd + ["--entrypoint", "python3", ts_tag, "/task_server.py", "--selfcheck"],
                       capture_output=True, text=True, errors="replace", timeout=3600)
    out = p.stdout + p.stderr
    m = re.search(r"\{.*\}", out, re.S)
    try:
        report = json.loads(m.group(0)) if m else {}
    except ValueError:
        report = {}
    return {"exit": p.returncode, "verdict": verdict_of(out), "report": report}


def project_of(bundle):
    d = json.load(open(os.path.join(bundle, "cyberforge_source.json")))
    return d["source_task"].split("/projects/", 1)[1].split("/")[0]


def main():
    plan_f, results_f = sys.argv[1], sys.argv[2]
    max_s = int(sys.argv[sys.argv.index("--max-seconds") + 1]) if "--max-seconds" in sys.argv else 0
    plan = json.load(open(plan_f))
    done = set()
    if os.path.isfile(results_f):
        done = {json.loads(l)["bundle"] for l in open(results_f) if l.strip()}
    start, last_project = time.monotonic(), None
    for item in plan:
        bd = os.path.abspath(item["bundle"])
        name = os.path.basename(bd)
        if name in done:
            continue
        project = project_of(bd)
        if last_project and project != last_project:
            subprocess.run(["docker", "system", "prune", "-af"], capture_output=True)
            subprocess.run(["docker", "builder", "prune", "-af"], capture_output=True)
        last_project = project
        t0 = time.monotonic()
        try:
            p = subprocess.run(["bash", os.path.join(bd, "build.sh")], cwd=bd, capture_output=True, text=True,
                               errors="replace", timeout=4 * 3600)
            log, rc = p.stdout + p.stderr, p.returncode
        except subprocess.TimeoutExpired as e:
            log, rc = (e.stdout or "") + (e.stderr or "") if isinstance(e.stdout, str) else "", 124
        rec = {"bundle": name, "project": project, "exit": rc, "verdict": verdict_of(log),
               "seconds": int(time.monotonic() - t0)}
        if rc != 0:
            net = NETWORK_RE.search(log)
            rec["failure"] = ("needs network: " + net.group(0)) if net else \
                (re.findall(r"(?m)^(FAIL[^\n]*|ERROR[^\n]*)", log) or [log.strip().splitlines()[-1] if log.strip() else ""])[-1][:300]
            rec["log_tail"] = log[-2000:]
        m = re.search(r'TS_TAG="([^"]+)"', open(os.path.join(bd, "build.sh")).read())
        ver = re.search(r'^VER="?([^"\n]+)"?', open(os.path.join(bd, "build.sh")).read(), re.M)
        ts_tag = m.group(1).replace("${VER}", ver.group(1) if ver else "") if m else ""
        have_ts = ts_tag and subprocess.run(["docker", "image", "inspect", ts_tag], capture_output=True).returncode == 0
        if have_ts and (item.get("alts") or item.get("judge_alts")):
            rec["alts"] = {}
            for label, f in (item.get("alts") or {}).items():
                rec["alts"][label] = selfcheck(ts_tag, [(os.path.abspath(f), "/tests/ground_truth_poc")])
            judge = json.load(open(os.path.join(bd, "environment", "task-server", "judge.json")))
            for label, over in (item.get("judge_alts") or {}).items():
                with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as t:
                    json.dump(dict(judge, **over), t)
                try:
                    rec["alts"][label] = selfcheck(ts_tag, [(t.name, "/judge.json")])
                finally:
                    os.unlink(t.name)
        if ts_tag:
            subprocess.run(["docker", "rmi", "-f", ts_tag, ts_tag.replace("_task_server:", "_main:")], capture_output=True)
        with open(results_f, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print("%s %s exit=%d %ds %s" % (name, rec["verdict"] or "-", rc, rec["seconds"], rec.get("failure", "")), flush=True)
        if max_s and time.monotonic() - start > max_s:
            break
    subprocess.run(["docker", "system", "prune", "-af"], capture_output=True)


if __name__ == "__main__":
    main()
