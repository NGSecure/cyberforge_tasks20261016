#!/usr/bin/env python3
"""Shrink replay_deep/ for the repository without changing what classify.py decides.

    python3 -I prune_replay_deep.py <inner_root> records.json replay_deep/

Every saved capture whose bytes deep_recipe.py's result for its task does not need is
replaced by a stub "CF-PRUNED <sha256> <size>" (deep_recipe.py compares stubs by their
hash, e.g. "fed its harness N different inputs", but never uses one as a ground truth).
A capture is only stubbed when the task's result stays exactly the same, so ground
truths and the files a recipe uses are kept. log.txt files are cut to their first and
last 32 KB.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deep_recipe  # noqa: E402


def result(d, es, names):
    r, why = deep_recipe.recipe_or_reason(d, es, names)
    return json.dumps([r and {k: (v.hex() if isinstance(v, bytes) else v) for k, v in r.items()}, why], sort_keys=True)


def main():
    root, records, rd = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
    pruned = kept = saved = 0
    for r in json.load(open(records)):
        project, vuln = r["path"].split("/vulnerabilities/")
        d = os.path.join(rd, project, vuln)
        if not os.path.isfile(os.path.join(d, "calls.json")):
            continue
        log = os.path.join(d, "log.txt")
        if os.path.isfile(log) and os.path.getsize(log) > 64 * 1024:
            data = open(log, "rb").read()
            open(log, "wb").write(data[:32 * 1024] + b"\n... [cut by prune_replay_deep.py] ...\n" + data[-32 * 1024:])
        vd = os.path.join(root, "projects", r["path"])
        es = open(os.path.join(vd, "exploit_files", "exploit.sh"), encoding="utf-8", errors="replace").read()
        names = [f for _, _, fs in os.walk(os.path.join(vd, "exploit_files")) for f in fs]
        caps = [n for n in os.listdir(d) if n not in ("calls.json", "log.txt")
                and open(os.path.join(d, n), "rb").read(len(deep_recipe.PRUNED)) != deep_recipe.PRUNED]
        if not caps:
            continue
        before = result(d, es, names)
        trial = tempfile.mkdtemp()
        try:
            for n in os.listdir(d):
                shutil.copyfile(os.path.join(d, n), os.path.join(trial, n))
            stubbed = []
            for n in sorted(caps, key=lambda n: -os.path.getsize(os.path.join(d, n))):  # largest first
                data = open(os.path.join(trial, n), "rb").read()
                stub = deep_recipe.PRUNED + ("%s %d\n" % (hashlib.sha256(data).hexdigest(), len(data))).encode()
                open(os.path.join(trial, n), "wb").write(stub)
                if result(trial, es, names) == before:
                    stubbed.append(n)
                else:  # the result needs this capture's bytes
                    open(os.path.join(trial, n), "wb").write(data)
            for n in stubbed:
                saved += os.path.getsize(os.path.join(d, n))
                shutil.copyfile(os.path.join(trial, n), os.path.join(d, n))
            pruned += len(stubbed)
            kept += len(caps) - len(stubbed)
        finally:
            shutil.rmtree(trial)
    print("pruned %d capture(s) (%.1f MB); %d capture(s) are needed" % (pruned, saved / 1e6, kept))


if __name__ == "__main__":
    main()
