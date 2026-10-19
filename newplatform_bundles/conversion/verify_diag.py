#!/usr/bin/env python3
"""Run inputs on both builds with and without the judge's sandbox (verify_bundles.py helper).

    docker run --rm -v verify_diag.py:/cf_diag.py:ro [-v <file>:/cf_alt/<n>:ro ...] \
        --entrypoint python3 <task-server image> /cf_diag.py <file> ...

Runs inside a bundle's task-server image as root and uses its own task_server.py: each
input file is run on the vulnerable and the secure build three ways,
  judge          -- exactly as the task server does (fresh uid, seccomp, rlimits, judge env);
  no-sandbox     -- the same run as root, without the uid switch, seccomp and rlimits;
  no-sandbox-env -- that, with the image's own environment instead of the judge's
                    sanitizer options (judge.json asan_options / the leak policy).
When the ground truth is differential without the sandbox but not with it, the judge's
own isolation is what suppresses the crash. Prints one JSON object.
"""
import importlib.util
import json
import os
import re
import sys

spec = importlib.util.spec_from_file_location("task_server", "/task_server.py")
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)

MARK = re.compile(r"==\d+==\s?ERROR: [^\n]*|^SUMMARY: [^\n]*|ERROR: libFuzzer: [^\n]*|: Assertion `[^\n]*|"
                  r"runtime error: [^\n]*|^Executed [^\n]* in \d+ ms|\[[^\n]*(failed|timeout)[^\n]*\]", re.M)
IMAGE_ENV = {k: v for k, v in os.environ.items() if k != "AUTH_TOKEN"}
TIER_A = hasattr(ts, "_run_poc")
SANDBOX, SANITIZER_ENV, ENV = ts._sandbox, getattr(ts, "SANITIZER_ENV", None), getattr(ts, "_env", None)


def image_env(step, home=None, extra=None):  # tiers B/E: the step's own env, no leak policy added
    env = dict(ts.BASE_ENV, **(step.get("env") or {}))
    if home:
        env["HOME"] = home
    env.update(extra or {})  # category 5: an archive PoC's own variables
    for k in step.get("unset_env") or []:
        env.pop(k, None)
    return env


def setup(way):
    ts._sandbox = SANDBOX if way == "judge" else (lambda uid: None)
    if TIER_A:
        ts.SANITIZER_ENV = IMAGE_ENV if way == "no-sandbox-env" else SANITIZER_ENV
    else:
        ts._env = image_env if way == "no-sandbox-env" else ENV


def run(variant, poc):
    """-> (crashed, exit code or None, output)"""
    if TIER_A:
        code, out = ts._run_poc(variant, ts.VUL_FUZZER if variant == "vul" else ts.FIX_FUZZER, poc)
        return ts._crashed(code), code, out
    crashed, out = ts._run(variant, poc)
    if isinstance(crashed, dict):  # category 5: a run record
        return bool(crashed.get("triggered")), None, out
    return crashed, None, out


def main():
    os.makedirs(ts.RUN_ROOT, exist_ok=True)
    os.chmod(ts.RUN_ROOT, 0o711)
    report = {"tier_a": TIER_A, "image_env_asan": IMAGE_ENV.get("ASAN_OPTIONS"), "inputs": {}}
    if TIER_A and not (ts.VUL_FUZZER and ts.FIX_FUZZER):
        report["error"] = "harness missing from a build"
        print(json.dumps(report))
        return
    for f in sys.argv[1:] or [ts.GROUND_TRUTH_POC]:
        res, diff = {}, {}
        for way in ("judge", "no-sandbox", "no-sandbox-env"):
            setup(way)
            crashed = {}
            for variant in ("vul", "fix"):
                poc = ts._save_poc(open(f, "rb").read())
                try:
                    crashed[variant], code, out = run(variant, poc)
                finally:
                    ts._remove(poc)
                res["%s %s" % (way, variant)] = {"crashed": crashed[variant], "exit": code,
                                                 "gist": [m.group(0)[:200] for m in MARK.finditer(out)][:3]}
            diff[way] = crashed["vul"] and not crashed["fix"]
        res["differential"] = diff
        report["inputs"][f] = res
    setup("judge")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
