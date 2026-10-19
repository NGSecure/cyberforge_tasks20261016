#!/usr/bin/env python3
"""Per-bundle verification status from verify_bundles.py's results, for convert.py's manifest.

    python3 -I verification_summary.py <results.jsonl> [more results.jsonl ...] > verification/summary.json

Later files override earlier ones for the same bundle. Status:
  pass / pass-degenerate   build.sh passed here (an empty input also passes: degenerate);
  pass-no-gt               a bundle made without a ground truth (the dataset's crashing input is only
                           a Git LFS pointer): build.sh and the checks that need none passed here;
  fail                     the ground truth is not differential in the rebuilt images; the
                           note says what the judge-free runs and the dataset's own exploit did;
  not-built                the build did not finish here: needs network, out of disk, or the
                           build itself fails (e.g. the injected diff does not compile).
  stale                    the result tested another ground truth than the bundle has now
                           (results record it as gt_sha256): verify the bundle again. A result whose
                           alternative ground truth (verify_bundles.py's "alts", e.g. "dataset <path>")
                           is the bundle's ground truth now verified that one too: its verdict counts.
Bundles without a result are absent (not verified yet).
"""
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def current_gt(name):
    """SHA-256 of the bundle's ground truth as it is now, "" for a bundle made without one, or None."""
    for d in ("newplatform_bundles", "newplatform_bundles2", "newplatform_bundles3", "newplatform_bundles4",
              "newplatform_bundles5", "other_errors"):
        f = os.path.join(REPO, d, name, "build", "ground_truth_poc")
        if os.path.isfile(f):
            return hashlib.sha256(open(f, "rb").read()).hexdigest()
        if os.path.isfile(os.path.join(REPO, d, name, "cyberforge_source.json")):
            return ""
    return None


def alt_verdict(name, r, cur):
    """The verdict of the alternative of result r whose file is the bundle's ground truth now, or ''.
    Labels name the file: "dataset <path in the task>", "report_inputs <path>" / "constructed <path>"
    (next to this script)."""
    src = None
    for d in ("newplatform_bundles", "newplatform_bundles2", "newplatform_bundles3", "newplatform_bundles4",
              "newplatform_bundles5", "other_errors"):
        f = os.path.join(REPO, d, name, "cyberforge_source.json")
        if os.path.isfile(f):
            src = json.load(open(f))
    if not src:
        return ""
    task = os.path.join(REPO, src["source_task"])
    for label, a in (r.get("alts") or {}).items():
        kind, _, path = label.partition(" ")
        f = os.path.join(task, path) if kind == "dataset" else \
            os.path.join(os.path.dirname(os.path.abspath(__file__)), path) if kind in ("report_inputs", "constructed") else ""
        if f and os.path.isfile(f) and hashlib.sha256(open(f, "rb").read()).hexdigest() == cur:
            return a.get("verdict") or ""
    return ""


def note(r):
    e, d = r.get("exploit") or {}, r.get("diag") or {}
    parts = []
    sup = [f for f, x in (d.get("inputs") or {}).items()
           if not x["differential"]["judge"] and (x["differential"]["no-sandbox"] or x["differential"]["no-sandbox-env"])]
    if ((d.get("inputs") or {}).get("ours") or {}).get("differential", {}).get("judge"):
        # self-check 3 failed, yet the judge's own rerun of the same input was differential
        parts.append("nondeterministic: on a rerun the judge found the same ground truth differential")
    elif sup:
        parts.append("differential only without the judge's sandbox or sanitizer options")
    elif d.get("inputs"):
        parts.append("same result without the judge's sandbox and with the image's own environment")
    if e and not e.get("error"):
        if e.get("crash"):
            parts.append("the dataset's exploit.sh crashed the vulnerable build%s (try %d of %d)" % (
                ", and the secure one too" if (e.get("fix") or {}).get("crashed") else ", not the secure one",
                e["crash"]["run"] + 1, e["tries"]))
        else:
            parts.append("the dataset's exploit.sh crashed neither build (%d run%s)" % (e.get("tries", 0),
                                                                                  "s" if e.get("tries", 0) != 1 else ""))
        if e.get("gt_seen") is not None:
            parts.append("its harness input %s our ground truth" % ("was" if e["gt_seen"] else "was not"))
    for k, a in (r.get("alts") or {}).items():
        parts.append("%s: %s" % (k, "passes" if a["verdict"].startswith("PASS") else "fails"))
    return "; ".join(parts)


def main():
    # a category-5 bundle (newplatform_bundles5) counts only the results of its own judge (results_c5*.jsonl):
    # results of an earlier bundle of the same name tested another judge
    d5, d6 = os.path.join(REPO, "newplatform_bundles5"), os.path.join(REPO, "other_errors")
    fifth = set(os.listdir(d5)) if os.path.isdir(d5) else set()
    for n in (os.listdir(d6) if os.path.isdir(d6) else []):
        f = os.path.join(d6, n, "cyberforge_source.json")
        if os.path.isfile(f) and "category5" in json.load(open(f)):
            fifth.add(n)
    res = {}
    for f in sys.argv[1:]:
        c5_file = os.path.basename(f).startswith("results_c5")
        for line in open(f):
            if line.strip():
                r = json.loads(line)
                if (r["bundle"] in fifth) == c5_file:
                    res[r["bundle"]] = r
    out = {}
    for name, r in sorted(res.items()):
        v = r.get("verdict") or ""
        cur = current_gt(name)
        if cur is None:
            continue  # the bundle is no longer made (e.g. a task found unconvertible)
        alt_note = ""
        if v and name in fifth and not r.get("gt_sha256") and cur:
            # a category-5 bundle verified before its ground truth existed (generated in the built image,
            # c5_specs.json ground_truth.generate): the self-check of that file, as an alternative, counts
            v2 = alt_verdict(name, r, cur)
            if v2:
                v, alt_note = v2, "the ground truth was generated in the built image and self-checked there"
            else:
                out[name] = {"status": "stale", "note": "verified without the ground truth it has now"}
                continue
        elif v and r.get("gt_sha256") and r["gt_sha256"] != cur:
            v = alt_verdict(name, r, cur)
            if not v:
                out[name] = {"status": "stale", "note": "verified with another ground truth (%s...)" % r["gt_sha256"][:12]}
                continue
            alt_note = "the ground truth was verified as an alternative of the first one, in the same build"
        if v.startswith("PASS-DEGENERATE"):
            out[name] = {"status": "pass-degenerate", "note": ""}
        elif v.startswith("PASS-NO-GROUND-TRUTH"):
            out[name] = {"status": "pass-no-gt", "note": "no ground truth: the ground-truth check is not run"}
        elif v.startswith("PASS"):
            out[name] = {"status": "pass", "note": ""}
        elif v:
            out[name] = {"status": "fail", "note": note(r)}
        else:
            out[name] = {"status": "not-built", "note": (r.get("failure") or "")[:200]}
        if alt_note:
            out[name]["note"] = (alt_note + "; " + out[name]["note"]).rstrip("; ") if out[name]["status"] == "fail" else alt_note
        if r.get("built_with_proxy_ca"):
            out[name]["note"] = ("built with this machine's proxy CA added (verification only); " + out[name]["note"]).rstrip("; ")
    json.dump({"_about": "verify_bundles.py results per bundle (verification_summary.py)", "bundles": out},
              sys.stdout, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
