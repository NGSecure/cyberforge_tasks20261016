#!/usr/bin/env python3
"""Build bundles and record their self-check verdicts; optionally try other ground truths.

    python3 -I verify_bundles.py <plan.json> <results.jsonl> [--max-seconds N] [--ca <proxy CA bundle>]

plan.json is a list of {"bundle": <bundle dir>, "alts": {label: file}, "judge_alts":
{label: {judge.json keys to override}}}, in the order to run. For each bundle this runs
its build.sh (both images and the three blocking self-checks) and records the exit code,
the self-check 3 verdict and report and, when the build failed, why (e.g. a build step that needs the
network). Then, in the task-server image build.sh made, it runs the self-check again with
each alternative ground truth (e.g. the dataset's own pov.bin when the bundle's ground
truth differs from it) and with each alternative judge.json (e.g. leak detection on).
When a self-check fails, verify_diag.py runs the same inputs on both builds with and
without the judge's sandbox (fresh uid, seccomp, rlimits) and its sanitizer options. On a
one-harness bundle whose ground truth came from an exploit run or a file the exploit names
(or failed), verify_exploit.py runs the dataset's exploit.sh itself against the two builds
in the project's image (up to 20 times when it draws its input at random and the ground
truth failed) and records whether the harness got our ground truth; the input of a call
that crashed is saved in verification/exploit_inputs/.

Results already in results.jsonl are kept (the run can be resumed); when a build runs out
of disk or needs the network (without --ca), the project's remaining bundles are recorded
as not built; --max-seconds stops
after the bundle that crosses the limit. --ca builds each bundle from a copy of its base
image that also trusts the given CA, for machines whose outbound TLS goes through an
intercepting proxy (a build step that clones or downloads otherwise fails); the bundles
themselves are not changed (results carry "built_with_proxy_ca"). A bundle's images are removed after it, and the
build cache whenever the next bundle is of another project, so the run fits a fixed disk.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

NETWORK_RE = re.compile(r"Could not resolve host|unable to access 'https?://|server certificate verification failed|"
                        r"Temporary failure in name resolution|Failed to connect to|Network is unreachable|"
                        r"cannot verify \S+'s certificate|CERTIFICATE_VERIFY_FAILED|Failed to download")
DISK_RE = re.compile(r"no space left on device", re.I)  # BuildKit says it in lower case
PROXY_DOWN_RE = re.compile(r"proxyconnect tcp: dial tcp [0-9.]+:\d+: connect: connection refused")
LOW_DISK = 8 << 30  # bytes free below which the build cache is cleared between two bundles of a project


def verdict_of(text):
    v = re.findall(r'"verdict": "([^"]+)"', text)
    return v[-1] if v else ""


def report_of(text):
    """The last self-check report (task_server.py --selfcheck's JSON) in text, or {}."""
    for m in reversed(list(re.finditer(r"(?m)^\{$", text))):
        try:
            d = json.JSONDecoder().raw_decode(text, m.start())[0]
        except ValueError:
            continue
        if isinstance(d, dict) and "verdict" in d:
            return d
    return {}


def selfcheck(ts_tag, mounts):
    cmd = ["docker", "run", "--rm", "-e", "AUTH_TOKEN=selfcheck"]
    for src, dst in mounts:
        cmd += ["-v", "%s:%s:ro" % (src, dst)]
    p = subprocess.run(cmd + ["--entrypoint", "python3", ts_tag, "/task_server.py", "--selfcheck"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", timeout=3600)
    return {"exit": p.returncode, "verdict": verdict_of(p.stdout), "report": report_of(p.stdout)}


def diag(ts_tag, files):
    """verify_diag.py in the task-server image: each file on both builds, with and without the sandbox."""
    here = os.path.dirname(os.path.abspath(__file__))
    cmd, args = ["docker", "run", "--rm", "-v", "%s:/cf_diag.py:ro" % os.path.join(here, "verify_diag.py")], []
    for i, f in enumerate(files):
        if f == "/tests/ground_truth_poc":
            args.append(f)
        else:
            cmd += ["-v", "%s:/cf_alt/%d:ro" % (os.path.abspath(f), i)]
            args.append("/cf_alt/%d" % i)
    try:
        p = subprocess.run(cmd + ["--entrypoint", "python3", ts_tag, "/cf_diag.py"] + args, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, errors="replace", timeout=3600)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    try:
        d = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": p.stdout[-1000:]}
    names = dict(zip(args, files))
    d["inputs"] = {("ours" if k == "/tests/ground_truth_poc" else names[k]): v for k, v in d.get("inputs", {}).items()}
    return d


def task_dir(source_task):
    """The dataset task directory: under CF_DATASET_ROOT (the directory holding the dataset
    folder, e.g. a copy lfs_restore.py made with the Git LFS contents restored), else the repo."""
    root = os.environ.get("CF_DATASET_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, source_task)


def exploit_run(ts_tag, bundle, tries):
    """verify_exploit.py in the task-server image: the dataset's exploit.sh against both builds."""
    here = os.path.dirname(os.path.abspath(__file__))
    src = json.load(open(os.path.join(bundle, "cyberforge_source.json")))["source_task"]
    ef = os.path.join(task_dir(src), "exploit_files")
    # a directory per run: a later run of the same bundle must not overwrite what an earlier one saved
    xout = os.path.join(here, "verification", "exploit_inputs", os.path.basename(bundle),
                        time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + "-%d" % os.getpid())
    os.makedirs(xout, exist_ok=True)
    cmd = ["docker", "run", "--rm", "--network", "none", "-v", "%s:/cf_exploit.py:ro" % os.path.join(here, "verify_exploit.py"),
           "-v", "%s:/cf_exploit_src:ro" % ef, "-v", "%s:/cf_xout" % xout,
           "--entrypoint", "python3", ts_tag, "/cf_exploit.py", str(tries)]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                           timeout=tries * 1200)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    saved = os.path.relpath(xout, here) if os.listdir(xout) else None
    if not saved:
        os.rmdir(xout)
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": p.stdout[-1000:]}
    if saved:
        out["saved_to"] = saved
    return out


EXPLOIT_SOURCED = ("exploit_replay", "hints.successful_seed", "named_file", "referenced_by_exploit.sh",
                   "single_input_file", "dataset_pov", "exploit_live")
RANDOM_RE = re.compile(r"/dev/u?random|\$RANDOM|\brandom\.|os\.urandom|randint|rand\(\)|openssl rand|shuf\b")


CA_DOCKERFILE = """FROM %s
COPY ca.crt /usr/local/share/ca-certificates/cf-verify-proxy.crt
RUN (update-ca-certificates || cat /usr/local/share/ca-certificates/cf-verify-proxy.crt >> /etc/ssl/certs/ca-certificates.crt) \\
    && cat /usr/local/share/ca-certificates/cf-verify-proxy.crt >> /etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt GIT_SSL_CAINFO=/etc/ssl/certs/ca-certificates.crt \\
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
"""


def ca_build_script(bd, ca):
    """--ca: a copy of build.sh whose base image also trusts this machine's TLS-intercepting
    proxy (only for verifying here: some builds clone or download from the network). The
    bundle itself is unchanged; the copy is written next to build.sh and removed after."""
    text = open(os.path.join(bd, "build.sh")).read()
    base = re.search(r"^BASE=(\S+)", text, re.M).group(1)
    if re.search(r"^HAS_HUB_IMAGE=0", text, re.M):
        return None  # the base is built from build/setup, which downloads without the CA
    tag = "cf_verify_ca:" + hashlib.sha1(base.encode()).hexdigest()[:12]
    if subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode != 0:
        if subprocess.run(["docker", "image", "inspect", base], capture_output=True).returncode != 0 and \
                subprocess.run(["docker", "pull", "-q", base], capture_output=True).returncode != 0:
            mirror = "mirror.gcr.io/" + base
            if subprocess.run(["docker", "pull", "-q", mirror], capture_output=True).returncode != 0:
                return None
            base = mirror
        with tempfile.TemporaryDirectory() as ctx:
            shutil.copyfile(ca, os.path.join(ctx, "ca.crt"))
            open(os.path.join(ctx, "Dockerfile"), "w").write(CA_DOCKERFILE % base)
            if subprocess.run(["docker", "build", "-q", "-t", tag, ctx], capture_output=True).returncode != 0:
                return None
    text = re.sub(r"^BASE=\S+", "BASE=" + tag, text, count=1, flags=re.M)
    text = re.sub(r'^HERE=.*$', 'HERE="%s"' % bd, text, count=1, flags=re.M)
    path = os.path.join(bd, ".build.verify-ca.sh")
    open(path, "w").write(text)
    return path


def project_of(bundle):
    d = json.load(open(os.path.join(bundle, "cyberforge_source.json")))
    return d["source_task"].split("/projects/", 1)[1].split("/")[0]


def main():
    plan_f, results_f = sys.argv[1], sys.argv[2]
    max_s = int(sys.argv[sys.argv.index("--max-seconds") + 1]) if "--max-seconds" in sys.argv else 0
    ca = sys.argv[sys.argv.index("--ca") + 1] if "--ca" in sys.argv else ""
    plan = json.load(open(plan_f))
    done = set()
    if os.path.isfile(results_f):
        done = {json.loads(l)["bundle"] for l in open(results_f) if l.strip()}
    start, last_project, no_disk, no_net = time.monotonic(), None, set(), {}
    for item in plan:
        bd = os.path.abspath(item["bundle"])
        name = os.path.basename(bd)
        if name in done:
            continue
        project = project_of(bd)
        if project in no_disk or project in no_net:  # an earlier build of this project could not finish here
            rec = {"bundle": name, "project": project, "exit": 1, "verdict": "", "seconds": 0,
                   "failure": "out of disk (this machine): not built, an earlier build of this project ran out of disk"
                   if project in no_disk else
                   "needs network: not built, an earlier build of this project needed the network (%s)" % no_net[project]}
            with open(results_f, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print("%s - skipped: %s" % (name, rec["failure"]), flush=True)
            continue
        if last_project and project != last_project:
            subprocess.run(["docker", "system", "prune", "-af"], capture_output=True)
            subprocess.run(["docker", "builder", "prune", "-af"], capture_output=True)
        elif shutil.disk_usage("/var/lib/docker").free < LOW_DISK:
            # the build cache keeps every vulnerable build of the project; keep the disk free
            subprocess.run(["docker", "builder", "prune", "-af"], capture_output=True)
        last_project = project
        t0 = time.monotonic()
        script = ca_build_script(bd, ca) if ca else os.path.join(bd, "build.sh")
        try:
            if not script:
                log, rc = "--ca: could not prepare a base image that trusts the proxy CA", 1
            else:
                p = subprocess.run(["bash", script], cwd=bd, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, errors="replace", timeout=4 * 3600)
                log, rc = p.stdout, p.returncode
        except subprocess.TimeoutExpired as e:
            log, rc = e.stdout if isinstance(e.stdout, str) else "", 124
        finally:
            if ca and script and os.path.isfile(script):
                os.remove(script)
        if PROXY_DOWN_RE.search(log):
            # dockerd cannot reach its HTTP(S) proxy (e.g. the proxy moved): nothing can be pulled
            # or built until it is restarted; stop rather than record a failure for every bundle
            print("%s: docker cannot reach its proxy; stopping (restart dockerd, then resume)" % name, flush=True)
            sys.exit(3)
        rec = {"bundle": name, "project": project, "exit": rc, "verdict": verdict_of(log),
               "seconds": int(time.monotonic() - t0),
               # the ground truth this result is evidence for (choose_gt.py)
               "gt_sha256": hashlib.sha256(open(os.path.join(bd, "build", "ground_truth_poc"), "rb").read()).hexdigest()}
        if ca:
            rec["built_with_proxy_ca"] = True
        if report_of(log):
            rec["selfcheck"] = report_of(log)
        # what the task-server build log says about the two builds: a compile that exited non-zero
        # but made the harness (the Dockerfile goes on, as the dataset did), and the files that differ
        # step numbers restart with each `docker build`; the task-server image is build.sh's last one
        starts = [m.start() for m in re.finditer(r"(?m)^#1 \[internal\] load build definition", log)]
        ts_log = log[starts[-1]:] if starts else log
        stage = dict(re.findall(r"(?m)^#(\d+) \[(fix|vul) ", ts_log))
        tolerated = {stage[n]: "cached" for n in re.findall(r"(?m)^#(\d+) CACHED$", ts_log) if n in stage}
        tolerated.update({stage[n]: int(c) for n, c in re.findall(r"(?m)^#(\d+) [\d.]+ WARN: compile exited (\d+)", ts_log)
                          if n in stage})
        if any(v != "cached" for v in tolerated.values()):
            rec["compile_exit_tolerated"] = tolerated
        m = re.search(r"(?m)^#\d+ [\d.]+ (builds differ in \d+ file\(s\): [^\n]*)", ts_log)
        if m:
            rec["builds_differ"] = m.group(1)[:300]
        if rc != 0:
            net = NETWORK_RE.search(log)
            disk = DISK_RE.search(log)
            if disk and not net:
                no_disk.add(project)
            if net and not ca:
                no_net[project] = net.group(0)[:80]
            rec["failure"] = ("needs network: " + net.group(0)) if net else \
                "out of disk (this machine): No space left on device" if disk else \
                ("self-check 3: " + rec["verdict"]) if rec["verdict"] else \
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
        # A self-check that failed: run the same inputs without the judge's sandbox too.
        failed = not rec["verdict"].startswith("PASS") or \
            any(not a["verdict"].startswith("PASS") for a in (rec.get("alts") or {}).values())
        if have_ts and failed:
            rec["diag"] = diag(ts_tag, ["/tests/ground_truth_poc"] + list((item.get("alts") or {}).values()))
        # The dataset's exploit.sh against the two builds, in the project's own image: for a
        # ground truth taken from an exploit run (or a file the exploit names), and for any
        # one-harness bundle whose ground truth failed.
        src = json.load(open(os.path.join(bd, "cyberforge_source.json")))
        harness = "fuzzer_candidates" in json.load(open(os.path.join(bd, "environment", "task-server", "judge.json")))
        how = src["ground_truth"].get("how_found", "")
        if have_ts and harness and (how.split(" (")[0] in EXPLOIT_SOURCED or not rec["verdict"].startswith("PASS")):
            ef = os.path.join(task_dir(src["source_task"]), "exploit_files")
            text = "".join(open(os.path.join(ef, f), errors="replace").read() for f in os.listdir(ef)
                           if f.endswith((".sh", ".py", ".c", ".cc")))
            randomized = bool(RANDOM_RE.search(text))
            rec["exploit"] = exploit_run(ts_tag, bd, 20 if randomized and not rec["verdict"].startswith("PASS") else 1)
            gt = hashlib.sha256(open(os.path.join(bd, "build", "ground_truth_poc"), "rb").read()).hexdigest()
            runs = rec["exploit"].get("runs") or [{}]
            rec["exploit"].update({"randomized": randomized, "how_found": how, "gt_seen": any(
                v[0] == gt for c in runs[0].get("calls", []) for v in list(c["inputs"].values()) + [c["stdin"] or [""]])})
        if ts_tag:
            subprocess.run(["docker", "rmi", "-f", ts_tag, ts_tag.replace("_task_server:", "_main:")], capture_output=True)
        # BuildKit's build history keeps each build's exported layers (~50 builds, GBs of disk)
        subprocess.run(["docker", "buildx", "history", "rm", "--all"], capture_output=True)
        with open(results_f, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print("%s %s exit=%d %ds %s" % (name, rec["verdict"] or "-", rc, rec["seconds"], rec.get("failure", "")), flush=True)
        if max_s and time.monotonic() - start > max_s:
            break
    subprocess.run(["docker", "system", "prune", "-af"], capture_output=True)


if __name__ == "__main__":
    main()
