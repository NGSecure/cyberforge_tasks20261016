#!/usr/bin/env python3
"""Pick ground truths from what verify_bundles.py found, for classify.py.

    python3 -I choose_gt.py <inner_root> <records.json> <results.jsonl> [more results.jsonl ...]

For a one-harness bundle whose exploit does not race a background process:
- when our ground truth came from an exploit run or a file the exploit names, the dataset's
  pov.bin crashes the vulnerable build and not the secure one in this bundle's builds, and
  our ground truth is no file of the task's (a replay's capture): pov.bin (the dataset's file);
- else, when our ground truth (wherever it came from: also a fuzz campaign's crash file the
  dataset never replayed alone, quickjs FZ_22) failed, and exploit.sh, run in the project's
  image against the two builds (verify_exploit.py), fed the harness a single input that
  crashed the vulnerable build and not the secure one: that input ("exploit_live"; for an
  exploit that draws its input at random, the first such draw);
- else nothing changes.
Results files are read in the order given (oldest first), so each bundle has a history.
A result records the ground truth it tested (gt_sha256; older results do not). A choice is
evidence-backed and kept: when the bundle's latest result passed with the chosen ground truth
(or, for an older result, passed after the choice was made), the choice stays even though
"ours failed" no longer holds; when the latest result tested the chosen input and failed, the
choice is dropped. The exploit_live evidence is the latest result that tested the base ground
truth (or an older result) and in which exploit.sh crashed the vulnerable build and not the
secure one. Writes gt_choice.json and exploit_live/<project>/<vuln>/input next to this
script (files of dropped choices are removed); classify.py reads them.
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
# a recorded "crash" that was ASan failing to reserve its shadow memory at start-up (verify_exploit.py
# no longer counts these; older records did)
ASAN_INIT_FAIL = re.compile(r"AddressSanitizer failed to allocate 0x[0-9a-f]+ \(\d+\) bytes at address|"
                            r"ReserveShadowMemoryRange failed|Shadow memory range interleaves")
CHOOSABLE = ("exploit_replay", "hints.successful_seed", "named_file", "referenced_by_exploit.sh",
             "single_input_file", "dataset_pov", "exploit_live")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    root, records = sys.argv[1], sys.argv[2]
    recs = {"%s/vulnerabilities/%s" % (r["project"], r["vuln"]): r for r in json.load(open(records))}
    hist = {}  # bundle -> its results, oldest first
    for f in sys.argv[3:]:
        for line in open(f):
            if line.strip():
                r = json.loads(line)
                hist.setdefault(r["bundle"], []).append(r)
    gc = os.path.join(HERE, "gt_choice.json")
    prev = json.load(open(gc)) if os.path.isfile(gc) else {}
    choice, notes = {}, []
    for name, rs in sorted(hist.items()):
        r = rs[-1]
        bd = next((os.path.join(REPO, d, name) for d in ("newplatform_bundles", "newplatform_bundles2",
                                                         "newplatform_bundles3")
                   if os.path.isdir(os.path.join(REPO, d, name))), None)
        if not bd:
            continue
        src = json.load(open(os.path.join(bd, "cyberforge_source.json")))
        rel = src["source_task"].split("/projects/", 1)[1]
        rec = recs.get(rel)
        pc = prev.get(rel)  # the choice made before, if any
        pc_file = os.path.join(HERE, pc["poc"]) if pc and pc["poc"].startswith("exploit_live/") else \
            os.path.join(root, "projects", rel, pc["poc"]) if pc else None
        pc_sha = sha(open(pc_file, "rb").read()) if pc_file and os.path.isfile(pc_file) else None
        if not r.get("verdict"):
            if pc_sha:
                choice[rel] = pc  # not built this time (network, disk): nothing contradicts the choice
            continue
        judge = json.load(open(os.path.join(bd, "environment", "task-server", "judge.json")))
        base = (rec or {}).get("gt_base") or rec or {}  # the ground truth before an earlier choice
        if not rec or "fuzzer_candidates" not in judge or not base.get("poc"):
            continue
        replay_gt = base.get("poc_src", "").startswith(CHOOSABLE)  # ours came from an exploit run or a file it names
        ours = r["verdict"].startswith("PASS")
        tested = r.get("gt_sha256")
        vd = os.path.join(root, "projects", rel)
        # the base ground truth (before any choice), as classify.py resolves its path
        bp = base["poc"]
        gt = open(os.path.join(HERE, bp) if base["poc_src"].startswith(("exploit_replay", "project_file"))
                  or bp.startswith(("report_inputs/", "exploit_live/")) else os.path.join(vd, bp), "rb").read()
        base_sha = sha(gt)
        if pc_sha and pc_sha != base_sha:
            if ours and tested in (pc_sha, None):
                choice[rel] = pc  # verified with the chosen ground truth
                continue
            if not ours and tested == pc_sha:
                notes.append("%s: the chosen ground truth failed in %s's latest result; dropped" % (rel, name))
                continue
        es = open(os.path.join(vd, "exploit_files", "exploit.sh"), errors="replace").read()
        code = "\n".join(l for l in es.splitlines() if not l.strip().startswith("#"))
        if RACE_RE.search(code):
            continue  # what crashed depended on a process running beside the call (classify.py)
        shipped = {sha(open(os.path.join(dp, n), "rb").read()) for dp, _, ns in os.walk(vd) for n in ns}
        pov = (r.get("alts") or {}).get("dataset exploit_files/pov.bin")
        if replay_gt and pov and pov["verdict"].startswith("PASS") and not pov["verdict"].startswith("PASS-DEGENERATE") \
                and base_sha not in shipped:
            # our ground truth is no file of the dataset's (a replay's capture): its own pov.bin does it
            choice[rel] = {"poc": "exploit_files/pov.bin",
                           "poc_src": "dataset_pov (the dataset's pov.bin: in this bundle's builds it crashes the "
                                      "vulnerable build and not the secure one)",
                           "was": base["poc_src"], "evidence": name}
            continue
        if ours:
            continue
        # the latest run of the dataset's exploit, on the base ground truth's builds, that crashed the
        # vulnerable build and not the secure one
        def real_crash(x):
            e = x.get("exploit") or {}
            if not e.get("crash") or (e.get("fix") or {}).get("crashed"):
                return False
            c = e["runs"][e["crash"]["run"]]["calls"][e["crash"]["call"]]
            return not any(ASAN_INIT_FAIL.search(g) for g in c.get("gist") or [])
        ev = next((x for x in reversed(rs) if x.get("verdict") and not x["verdict"].startswith("PASS")
                   and x.get("gt_sha256") in (base_sha, None) and real_crash(x)), None)
        if not ev:
            continue
        e = ev["exploit"]
        call = e["runs"][e["crash"]["run"]]["calls"][e["crash"]["call"]]
        inputs = call.get("inputs") or {}
        if len(inputs) != 1 or call.get("stdin"):
            notes.append("%s: the crashing call had %d file inputs (and stdin %s); not chosen"
                         % (rel, len(inputs), bool(call.get("stdin"))))
            continue
        i, (digest, size) = next(iter(inputs.items()))
        if size > 16 << 20:  # verify_exploit.py's SAVE_MAX: such an input cannot be a bundled ground truth
            notes.append("%s: the crashing input is %d bytes, too large to bundle; not chosen" % (rel, size))
            continue
        f = os.path.join(HERE, e["saved_to"], "input-%s" % i) if e.get("saved_to") else \
            os.path.join(HERE, "verification", "exploit_inputs", name, "input-%s" % i)  # before per-run dirs
        data = open(f, "rb").read() if os.path.isfile(f) else b""
        if sha(data) != digest or len(data) != size:
            notes.append("%s: saved input does not match the recorded call; not chosen" % rel)
            continue
        tried = [x["bundle"] for x in rs if x.get("gt_sha256") == digest and x.get("verdict")
                 and not x["verdict"].startswith("PASS")]
        if tried:
            notes.append("%s: the exploit's input was tried as the ground truth and failed; not chosen again" % rel)
            continue
        if digest == base_sha:
            # the same bytes crashed in the exploit's run and not in the judge's: how they were run differs
            notes.append("%s: the exploit's crashing input is the ground truth itself; the judge's run of it differs "
                         "from the exploit's (working directory, arguments or environment)" % rel)
            continue
        dst = os.path.join(HERE, "exploit_live", *rel.split("/vulnerabilities/"), "input")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(f, dst)
        draw = " (draw %d of %d: the exploit draws its input at random)" % (e["crash"]["run"] + 1, e["tries"]) \
            if e.get("tries", 1) > 1 else ""
        choice[rel] = {"poc": os.path.relpath(dst, HERE),
                       "poc_src": "exploit_live (what exploit.sh fed %s in the project's image%s: it crashed the "
                                  "vulnerable build and not the secure one)" % (os.path.basename(call["path"]), draw),
                       "fuzzer": os.path.basename(call["path"]), "was": base["poc_src"], "evidence": ev["bundle"],
                       "sanitizer": call.get("gist", [])[:2]}
    # exploit_live/ holds the inputs of the choices made, nothing else
    keep = {os.path.join(HERE, c["poc"]) for c in choice.values() if c["poc"].startswith("exploit_live/")}
    for dp, dns, fns in os.walk(os.path.join(HERE, "exploit_live"), topdown=False):
        for fn in fns:
            if os.path.join(dp, fn) not in keep:
                os.remove(os.path.join(dp, fn))
        if not os.listdir(dp):
            os.rmdir(dp)
    json.dump(choice, open(gc, "w"), indent=1, sort_keys=True)
    print("%d ground truths chosen (%d dataset pov.bin, %d exploit_live); before: %d" % (
        len(choice), sum(1 for c in choice.values() if c["poc"].endswith("pov.bin")),
        sum(1 for c in choice.values() if c["poc"].startswith("exploit_live/")), len(prev)))
    for k in sorted(set(prev) - set(choice)):
        print("dropped:", k)
    for k in sorted(set(choice) - set(prev)):
        print("new:", k, "->", choice[k]["poc"])
    for n in notes:
        print("note:", n)


if __name__ == "__main__":
    main()
