#!/usr/bin/env python3
"""Pick ground truths from what verify_bundles.py found, for classify.py.

    python3 -I choose_gt.py <inner_root> <records.json> <results.jsonl> [more results.jsonl ...]

For a one-harness bundle whose ground truth is not the dataset's verified fuzz replay
(crash_report.json) or a file the dataset's own report names, and whose exploit does not
race a background process:
- the dataset's pov.bin crashes the vulnerable build and not the secure one in this
  bundle's builds, and our ground truth is no file of the task's (a replay's capture):
  pov.bin (the dataset's file);
- else, our ground truth failed, and exploit.sh, run in the project's image against the
  two builds (verify_exploit.py), fed the harness an input that crashed the vulnerable
  build and not the secure one: that input ("exploit_live"; for an exploit that draws its
  input at random, the first such draw);
- else nothing changes.
Later results files override earlier ones for the same bundle. Writes gt_choice.json and
exploit_live/<project>/<vuln>/<file> next to this script; classify.py reads them.
"""
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
RACE_RE = re.compile(r"(\)|[\w\"'])[ \t]*&[ \t]*$", re.M)  # classify.py's background-process test
CHOOSABLE = ("exploit_replay", "hints.successful_seed", "named_file", "referenced_by_exploit.sh",
             "single_input_file", "dataset_pov", "exploit_live")


def main():
    root, records = sys.argv[1], sys.argv[2]
    recs = {"%s/vulnerabilities/%s" % (r["project"], r["vuln"]): r for r in json.load(open(records))}
    results = {}
    for f in sys.argv[3:]:
        for line in open(f):
            if line.strip():
                r = json.loads(line)
                results[r["bundle"]] = r
    choice, notes = {}, []
    shutil.rmtree(os.path.join(HERE, "exploit_live"), ignore_errors=True)  # derived: made again below
    for name, r in sorted(results.items()):
        bd = next((os.path.join(REPO, d, name) for d in ("newplatform_bundles", "newplatform_bundles2",
                                                         "newplatform_bundles3")
                   if os.path.isdir(os.path.join(REPO, d, name))), None)
        if not bd or not r.get("verdict"):
            continue
        src = json.load(open(os.path.join(bd, "cyberforge_source.json")))
        rel = src["source_task"].split("/projects/", 1)[1]
        rec = recs.get(rel)
        judge = json.load(open(os.path.join(bd, "environment", "task-server", "judge.json")))
        base = (rec or {}).get("gt_base") or rec or {}  # the ground truth before an earlier choice
        if not rec or "fuzzer_candidates" not in judge or not base.get("poc_src", "").startswith(CHOOSABLE):
            continue
        ours = r["verdict"].startswith("PASS")
        pov = (r.get("alts") or {}).get("dataset exploit_files/pov.bin")
        vd = os.path.join(root, "projects", rel)
        # the base ground truth (before any choice), as classify.py resolves its path
        bp = base["poc"]
        gt = open(os.path.join(HERE, bp) if base["poc_src"].startswith(("exploit_replay", "project_file"))
                  or bp.startswith(("report_inputs/", "exploit_live/")) else os.path.join(vd, bp), "rb").read()
        es = open(os.path.join(vd, "exploit_files", "exploit.sh"), errors="replace").read()
        code = "\n".join(l for l in es.splitlines() if not l.strip().startswith("#"))
        if RACE_RE.search(code):
            continue  # what crashed depended on a process running beside the call (classify.py)
        shipped = {hashlib.sha256(open(os.path.join(dp, n), "rb").read()).hexdigest()
                   for dp, _, ns in os.walk(vd) for n in ns}
        if pov and pov["verdict"].startswith("PASS") and not pov["verdict"].startswith("PASS-DEGENERATE") \
                and hashlib.sha256(gt).hexdigest() not in shipped:
            # our ground truth is no file of the dataset's (a replay's capture): its own pov.bin does it
            choice[rel] = {"poc": "exploit_files/pov.bin",
                           "poc_src": "dataset_pov (the dataset's pov.bin: in this bundle's builds it crashes the "
                                      "vulnerable build and not the secure one)",
                           "was": base["poc_src"], "evidence": name}
            continue
        e = r.get("exploit") or {}
        if ours or not e.get("crash") or (e.get("fix") or {}).get("crashed"):
            continue
        call = e["runs"][e["crash"]["run"]]["calls"][e["crash"]["call"]]
        inputs = call.get("inputs") or {}
        if len(inputs) != 1 or call.get("stdin"):
            notes.append("%s: the crashing call had %d file inputs (and stdin %s); not chosen"
                         % (rel, len(inputs), bool(call.get("stdin"))))
            continue
        i, (digest, size) = next(iter(inputs.items()))
        f = os.path.join(HERE, "verification", "exploit_inputs", name, "input-%s" % i)
        data = open(f, "rb").read() if os.path.isfile(f) else b""
        if hashlib.sha256(data).hexdigest() != digest or len(data) != size:
            notes.append("%s: saved input does not match the recorded call; not chosen" % rel)
            continue
        dst = os.path.join(HERE, "exploit_live", *rel.split("/vulnerabilities/"), "input")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(f, dst)
        draw = " (draw %d of %d: the exploit draws its input at random)" % (e["crash"]["run"] + 1, e["tries"]) \
            if e.get("tries", 1) > 1 else ""
        choice[rel] = {"poc": os.path.relpath(dst, HERE),
                       "poc_src": "exploit_live (what exploit.sh fed %s in the project's image%s: it crashed the "
                                  "vulnerable build and not the secure one)" % (os.path.basename(call["path"]), draw),
                       "fuzzer": os.path.basename(call["path"]), "was": base["poc_src"], "evidence": name,
                       "sanitizer": call.get("gist", [])[:2]}
    json.dump(choice, open(os.path.join(HERE, "gt_choice.json"), "w"), indent=1, sort_keys=True)
    print("%d ground truths chosen (%d dataset pov.bin, %d exploit_live)" % (
        len(choice), sum(1 for c in choice.values() if c["poc"].endswith("pov.bin")),
        sum(1 for c in choice.values() if c["poc"].startswith("exploit_live/"))))
    for n in notes:
        print("note:", n)


if __name__ == "__main__":
    main()
