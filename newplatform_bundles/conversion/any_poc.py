#!/usr/bin/env python3
"""Which bundles pass with any PoC: the PASS-DEGENERATE bundles (an empty PoC passes), self-checked
again with arbitrary PoCs in place of the ground truth (verify_bundles.py, plan_anypoc.json).

    python3 -I any_poc.py verification/results_anypoc.jsonl

Writes verification/any_poc.json: for each bundle, whether the empty PoC and each arbitrary PoC
passed. A bundle passes with any PoC when all of them did. Every other verified bundle has a PoC
that does not pass (the empty PoC, or its ground truth), so it cannot be one of these; the
results are not part of summary.json and change no bundle.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = {  # plan_anypoc.json's alternatives (the files are in conversion/verification/any_poc_inputs/)
    "any:1-byte A": "1 字节 `A`", "any:64 random bytes": "64 字节随机数据", "any:4096 random bytes": "4096 字节随机数据",
    "any:1024 zero bytes": "1024 字节全零",
    "any:argv A": "参数 `A`", "any:argv --help": "参数 `--help`", "any:argv 1": "参数 `1`",
    "any:argv 3 random tokens": "3 个任意参数",
}


def result(r):
    """passes, why: what the self-check said of its ground truth (here: one arbitrary PoC). The
    self-check reports of the judges differ (tier A: exit codes; tier B: crashed or not; category 5: per-run records)."""
    verdict = r.get("verdict", "") or "no verdict"
    gt = (r.get("report") or {}).get("ground_truth") or {}
    if "vul_exit" in gt:
        why = "vul exit %s, fix exit %s" % (gt.get("vul_exit"), gt.get("fix_exit"))
    elif "vul_crashed" in gt:
        why = "vul crashed %s, fix crashed %s" % (gt.get("vul_crashed"), gt.get("fix_crashed"))
    else:
        why = gt.get("why", "")
    return verdict.startswith("PASS"), ("%s; %s" % (verdict, why) if why else verdict)[:300]


def main():
    Q = json.load(open(os.path.join(HERE, "quality.json"), encoding="utf-8"))["bundles"]
    out = {}
    for line in open(sys.argv[1], encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        name = r["bundle"]
        e = {"category": Q[name]["category"], "retested": bool(r.get("alts"))}
        if r.get("verify_deps_from_image"):  # see plan_anypoc_deps.json
            e["note"] = ("built with the dependency sources the dataset's own build left in the project image (%s): "
                         "this machine's GitHub proxy refuses their download" % ", ".join(r["verify_deps_from_image"]))
        if not e["retested"]:
            e["why"] = (r.get("failure") or r.get("verdict") or "not built")[:300]
        else:
            e["empty_poc_passes"] = r.get("verdict", "").startswith("PASS-DEGENERATE")  # "an empty input also passes"
            e["inputs"] = {}
            for label, a in r["alts"].items():
                ok, why = result(a)
                e["inputs"][label] = {"passes": ok, "why": why}
            e["any_poc_passes"] = e["empty_poc_passes"] and all(x["passes"] for x in e["inputs"].values())
        out[name] = e
    json.dump({"_about": __doc__.split("\n\n")[0] + " (any_poc.py)", "inputs": INPUTS, "bundles": dict(sorted(out.items()))},
              open(os.path.join(HERE, "verification", "any_poc.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    from collections import Counter
    print("bundles:", len(out), "retested:", sum(1 for e in out.values() if e["retested"]))
    print("any PoC passes:", dict(Counter(e["category"] for e in out.values() if e.get("any_poc_passes"))))
    print("not every PoC passes:", sorted(n for n, e in out.items() if e["retested"] and not e["any_poc_passes"]))


if __name__ == "__main__":
    main()
