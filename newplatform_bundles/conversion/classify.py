#!/usr/bin/env python3
"""Classify every CyberForge task for conversion to a new-platform PoC bundle.

Tier A  convertible: crash evidence + a concrete ground-truth PoC file that the
        task's own exploit is shown to feed to a fuzz harness (`/out/<fuzzer> <poc>`).
Tier B  needs a different bundle type: the PoV is a custom program/script, drives a
        project CLI/test binary instead of a harness, or the oracle is a
        behavioral divergence (no sanitizer crash by nature).
Tier C  insufficient ground truth: empty report, no saved PoC, harness ambiguous,
        a timeout/OOM signal the exit-code judge cannot score, or a recorded report
        that does not satisfy exploit.sh's own trigger check.

Harness resolution trusts what the exploit actually executes (literal /out/<x> or a
FUZZER="x" ... /out/${FUZZER} indirection) and crash_report.json for libFuzzer
crash artifacts. hints/manifest/contract selected_fuzzer are a last resort only and
are frequently wrong, so disagreements are recorded. When snapshot_scan/ (from
scan_snapshots.py) is present next to this script, a harness name must also be one
the dataset's own compile of the base image put in /out.

Usage: python3 -I classify.py <inner_root> <out_records.json>
       (run it again after scan_snapshots.py so the /out check applies)
"""
import csv
import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter

ROOT, OUT = sys.argv[1], sys.argv[2]
PROJ = os.path.join(ROOT, "projects")
rows = list(csv.DictReader(open(os.path.join(ROOT, "manifest.csv"), encoding="utf-8")))

NOT_FUZZERS = {"vuln_fuzzer", "llvm-symbolizer"}
NON_BIN_SUFFIX = (".zip", ".dict", ".options", ".log", ".txt", ".json", ".out", ".so", ".a")
POC_SKIP_EXT = (".sh", ".md", ".out", ".json", ".log", ".py", ".c", ".cc", ".cpp", ".h")
ASSIGN_RE = re.compile(r"^\s*(?:export\s+|local\s+)?([A-Za-z_]\w*)=([\"']?)([^\s\"';|&]+)\2\s*(?:#.*)?$", re.M)


def rd(p):
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def jl(p):
    try:
        v = json.load(open(p, encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def clean_fuzzer(n):
    """A usable harness name, or '' for placeholders / corpus names / 'main'."""
    n = (n or "").strip()
    if (not n or n in NOT_FUZZERS or n == "main" or n.endswith(("_", "-"))
            or "seed_corpus" in n or n.endswith(NON_BIN_SUFFIX)):
        return ""
    return n


def signal_of(t):
    s = t.strip()
    if not s:
        return "empty", ""
    if "DIFFERENTIAL / BEHAVIORAL" in t:
        return "behavioral", ""
    names = {"AddressSanitizer": "asan", "LeakSanitizer": "lsan", "MemorySanitizer": "msan",
             "ThreadSanitizer": "tsan", "UndefinedBehaviorSanitizer": "ubsan"}
    m = re.search(r"ERROR: (AddressSanitizer|LeakSanitizer|MemorySanitizer|ThreadSanitizer|"
                  r"UndefinedBehaviorSanitizer):? ?(?:attempting )?([\w\-]+)", t)
    if m:
        return names[m.group(1)], m.group(2)
    m = re.search(r"SUMMARY: (AddressSanitizer|LeakSanitizer|UndefinedBehaviorSanitizer|"
                  r"MemorySanitizer): ([\w\-]+)", t)
    if m:
        return names[m.group(1)], m.group(2)
    if "runtime error:" in t:
        return "ubsan", "runtime-error"
    if re.search(r"libFuzzer: (out-of-memory|malloc\(\d+\))|out-of-memory", t):
        return "oom", ""
    if re.search(r"libFuzzer: timeout|ALARM: working on the last Unit for", t):
        return "timeout", ""
    if re.search(r"deadly signal|Segmentation fault|\bSEGV\b", t):
        return "signal", "deadly-signal"
    if re.search(r"Assertion .* failed|\babort\b", t):
        return "signal", "abort"
    return "nocrash", ""


def exploit_harnesses(es):
    """Harness names the exploit executes under /out/ (resolving simple variables)."""
    assigns = {m.group(1): m.group(3) for m in ASSIGN_RE.finditer(es)}
    names = [n.rstrip(".") for n in re.findall(r"/out/([\w.\-+]+)", es)]
    for var in re.findall(r"/out/\$\{?([A-Za-z_]\w*)\}?", es):
        v = assigns.get(var, "")
        if v and "/" not in v and "$" not in v:
            names.append(v)
    for var in re.findall(r"\$\{?([A-Za-z_]\w*)\}?", es):
        v = assigns.get(var, "")
        if v.startswith("/out/"):
            names.append(v[len("/out/"):].rstrip("."))
    renamed = "/out/vuln_fuzzer" in es
    keep = []
    for n in names:  # ordered, de-duplicated; drop data files/dirs that live under /out
        if (n and n not in keep and n not in NOT_FUZZERS and not n.endswith(NON_BIN_SUFFIX)
                and "seed_corpus" not in n and not n.endswith("-data")
                and not re.search(r"\.(dic|aff|dat|bin|xml|png|ttf|otf|json|txt)$", n)):
            keep.append(n)
    return keep, renamed


GREP_RE = re.compile(r"grep\s+((?:-[a-zA-Z]+\s+)*)(?:-e\s+)?(['\"])(.+?)\2")
TRIGGER_WORDS = re.compile(r"Sanitizer|SUMMARY|heap-|stack-|SEGV|overflow|use-after|double-free|leak|"
                           r"Segmentation|abort|ERROR", re.I)


def report_satisfies_exploit(es, report):
    """None when exploit.sh decides by exit code only; otherwise whether the recorded
    sanitizer report matches at least one sanitizer pattern exploit.sh greps for (the
    dataset's own trigger condition)."""
    pats = [(f, p) for f, _, p in GREP_RE.findall(es) if TRIGGER_WORDS.search(p)]
    if not pats:
        return None
    for flags, pat in pats:
        rx = pat if ("E" in flags or "P" in flags) else pat.replace("\\|", "|")
        try:
            if re.search(rx, report, re.I if "i" in flags else 0):
                return True
        except re.error:
            if pat in report:
                return True
    return False


SCAN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshot_scan")
REPLAY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay")


def replayed(rel, dataset_files):
    """The input exploit.sh fed its harness when replayed with stub harnesses
    (replay_exploits.py), as a path relative to this script's dir, plus replay.json.
    One distinct input: that one. Several (e.g. a warm-up run first): only one that is
    byte-identical to a dataset file; otherwise None (ambiguous)."""
    d = os.path.join(REPLAY_DIR, *rel.split("/vulnerabilities/"))
    info = jl(os.path.join(d, "replay.json"))
    inputs = [i for i in info.get("inputs") or [] if os.path.isfile(os.path.join(d, i["file"]))]
    pick = None
    if len(inputs) == 1:
        pick = inputs[0]
    elif inputs:
        known = set()
        for f in dataset_files:
            try:
                known.add(hashlib.sha256(open(f, "rb").read()).hexdigest())
            except OSError:
                pass
        hits = [i for i in inputs if i["sha256"] in known]
        pick = hits[0] if len(hits) == 1 else None
    if pick:
        return os.path.relpath(os.path.join(d, pick["file"]), os.path.dirname(REPLAY_DIR)), info
    return None, info


def snapshot_out(project):
    """Names in /out after the dataset's own compile (from scan_snapshots.py), or None."""
    f = os.path.join(SCAN_DIR, project + ".json")
    if not os.path.isfile(f):
        return None
    return {x[len("/out/"):] for x in json.load(open(f, encoding="utf-8"))["post_setup_files"]
            if x.startswith("/out/")}


def poc_path(vd, poc, poc_src):
    return os.path.join(os.path.dirname(REPLAY_DIR), poc) if poc_src == "exploit_replay" else os.path.join(vd, poc)


def asan_options_of(es):
    m = re.search(r"\bASAN_OPTIONS=([\"']?)([^\s\"']+)\1", es)
    return m.group(2) if m else ""


records = []
for r in rows:
    t, p = r["type"], r["project"]
    vd = os.path.join(PROJ, r["path"])
    ef = os.path.join(vd, "exploit_files")
    es = rd(os.path.join(ef, "exploit.sh"))
    hints = jl(os.path.join(vd, "hints.json"))
    contract = jl(os.path.join(vd, "task_contract.json"))
    manifest = jl(os.path.join(ef, "fuzz_poc_manifest.json"))
    meta = jl(os.path.join(vd, "vulnerability_metadata.json"))
    pj = jl(os.path.join(PROJ, p, "project.json"))
    crep = jl(os.path.join(ef, "fuzz_results", "vulnerable", "crash_report.json"))

    report = rd(os.path.join(vd, "sanitizer_report.txt"))
    sig, sig_detail = signal_of(report)
    sig_src = "sanitizer_report.txt"
    report_ok = report_satisfies_exploit(es, report)
    if sig in ("empty", "nocrash") and crep.get("asan_like") and crep.get("result_kind") == "real_crash":
        sig, sig_detail, sig_src = "asan", "crash_report.asan_like", "crash_report.json"

    ef_files = []
    if os.path.isdir(ef):
        for dp, _, fn in os.walk(ef):
            for f in fn:
                ef_files.append(os.path.relpath(os.path.join(dp, f), vd))
    top_files = [f for f in ef_files if os.path.dirname(f) == "exploit_files"]

    custom = []
    if re.search(r"\b(gcc|g\+\+|clang\+\+|clang|cc)\b[^\n]*\s-o\s", es):
        custom.append("exploit.sh compiles code")
    code = "\n".join(l for l in es.splitlines() if not l.strip().startswith("#"))
    if re.search(r"(\)|[\w\"'])[ \t]*&[ \t]*$", code, re.M):
        custom.append("exploit races a background process (not a single-input PoV)")
    for f in top_files:
        b = os.path.basename(f)
        if b in ("driver", "attack.sh", "attack") or b.endswith((".c", ".cc", ".cpp")):
            custom.append(f"exploit ships {b}")
            break

    # ---- ground-truth PoC ----
    poc, poc_src = "", ""
    arts = sorted(glob.glob(os.path.join(ef, "fuzz_results", "vulnerable", "crash-*")))
    if arts:
        poc, poc_src = os.path.relpath(arts[0], vd), "fuzz_crash_artifact"
    rp, rinfo = replayed(r["path"], [os.path.join(vd, f) for f in ef_files])
    if not poc and rp:
        # what the exploit really ran; the harvested pov.bin is often something else
        poc, poc_src = rp, "exploit_replay"
    if not poc:
        rel = hints.get("successful_seed_relative_path") or ""
        if rel and os.path.isfile(os.path.join(vd, rel)):
            poc, poc_src = rel, "hints.successful_seed"
    if not poc:
        for cand in ("exploit_files/pov.bin", "exploit_files/crash_poc.bin"):
            if os.path.isfile(os.path.join(vd, cand)):
                poc, poc_src = cand, "named_file"
                break
    if not poc and es:
        refd = [f for f in top_files if not f.endswith(POC_SKIP_EXT)
                and os.path.basename(f) not in ("driver", "attack") and os.path.basename(f) in es]
        if len(refd) == 1:
            poc, poc_src = refd[0], "referenced_by_exploit.sh"
    if not poc:
        lone = [f for f in top_files if not f.endswith(POC_SKIP_EXT)
                and os.path.basename(f) not in ("driver", "attack")]
        if len(lone) == 1:
            poc, poc_src = lone[0], "single_input_file"

    # ---- harness ----
    sel = manifest.get("selected_fuzzer")
    meta_fz = [clean_fuzzer(x) for x in (hints.get("selected_fuzzer"), contract.get("selected_fuzzer"),
                                         sel.get("fuzzer") if isinstance(sel, dict) else "")]
    meta_fz = [x for x in meta_fz if x]
    ex_h, uses_renamed = exploit_harnesses(es)
    fuzzer, fuzzer_src, note = "", "", ""
    if poc_src == "fuzz_crash_artifact" and clean_fuzzer(crep.get("fuzzer")):
        fuzzer, fuzzer_src = crep["fuzzer"], "crash_report.json"
    elif len(ex_h) == 1:
        fuzzer, fuzzer_src = ex_h[0], "exploit.sh"
    elif len(ex_h) > 1:
        # exploits that try fallback names: keep them ordered; the task-server uses
        # the first one that exists after the build (recorded as candidates)
        fuzzer, fuzzer_src = ex_h[0], "exploit.sh (fallback candidates)"
        note = "candidates: " + ",".join(ex_h)
    elif uses_renamed:
        m = re.search(r"/out/([\w.\-+]+): Running", rd(os.path.join(ef, "run.out")))
        if m and clean_fuzzer(m.group(1)):
            fuzzer, fuzzer_src = m.group(1), "run.out (vuln_fuzzer rename)"
        elif meta_fz:
            fuzzer, fuzzer_src = meta_fz[0], "metadata (vuln_fuzzer rename)"
    elif "fuzz_poc.py" in es and meta_fz:
        fuzzer, fuzzer_src = meta_fz[0], "metadata (fuzz_poc.py)"
    mismatch = bool(fuzzer and meta_fz and fuzzer not in meta_fz)

    # A name exploit.sh runs from /out that the dataset's own compile of this image never
    # put in /out (snapshot_scan/) is the project's CLI/test binary, not a fuzz harness.
    # Without a scan: "/out/X if present, else the repo's X" (jq, qjs) means the same.
    outs = snapshot_out(p)
    if ex_h and outs is not None and not any(n in outs for n in ex_h):
        custom.append("exploit runs a binary the OSS-Fuzz build does not put in /out (CLI/test/custom harness)")
    elif ex_h and outs is None:
        for n in ex_h:
            if re.search(r"(\$\{?REPO\w*\}?|/src/[\w.+-]+)/%s\b" % re.escape(n), es):
                custom.append("exploit drives a project CLI/test binary, not the fuzz harness")
                break
    if not custom and not ex_h and not uses_renamed and "fuzz_poc.py" not in es:
        if re.search(r"(^|[\s;|&(\"'=])(/src/\S+|\./[\w.\-+]+|\$\{?\w*(BIN|BINARY)\w*\}?)", es, re.M) \
                or (hints.get("selected_fuzzer") or "") == "main":
            custom.append("exploit drives a project CLI/test binary, not the fuzz harness")

    # ---- tier ----
    crash_sigs = ("asan", "lsan", "ubsan", "msan", "tsan", "signal")
    if sig == "behavioral" or custom:
        tier, reason = "B", ("behavioral-divergence oracle" if sig == "behavioral" else custom[0])
    elif sig == "empty":
        tier, reason = "C", "sanitizer_report.txt is empty (no trigger evidence)"
    elif sig in ("timeout", "oom"):
        tier, reason = "C", f"{sig} signal (exit-code judge excludes it; env-dependent)"
    elif sig not in crash_sigs:
        tier, reason = "C", "report shows no sanitizer crash"
    elif not poc:
        tier, reason = "C", ("crash input not saved (fuzz-campaign replay; seed unrecorded)"
                             if crep else "no concrete PoC file (payload only inline / missing)")
    elif not fuzzer:
        tier, reason = "C", note or "fuzz harness not identifiable"
    elif os.path.getsize(poc_path(vd, poc, poc_src)) == 0:
        tier, reason = "C", "ground-truth PoC file is empty (pov.bin harvest failure or degenerate empty-input trigger)"
    elif sig_src == "sanitizer_report.txt" and report_ok is False and poc_src != "exploit_replay":
        tier, reason = "C", ("sanitizer report does not show what exploit.sh checks for "
                             "(recorded run did not trigger; ground truth unverified)")
    else:
        tier, reason = "A", ""

    vj = jl(os.path.join(vd, "bug_description_variants.json"))
    variants = vj.get("variants") or []
    records.append({
        "seq": int(r["seq"]), "type": t, "project": p, "vuln": r["vuln"], "path": r["path"],
        "tier": tier, "reason": reason,
        "signal": sig, "signal_detail": sig_detail, "signal_src": sig_src,
        "report_matches_exploit_check": report_ok,
        "poc": poc, "poc_src": poc_src, "fuzzer": fuzzer, "fuzzer_src": fuzzer_src,
        "replay_captured": len(rinfo.get("captured") or []),
        "replay_distinct_inputs": len(rinfo.get("inputs") or []),
        "fuzzer_candidates": ex_h if len(ex_h) > 1 else ([fuzzer] if fuzzer else []),
        "fuzzer_metadata": meta_fz, "fuzzer_mismatch": mismatch,
        "asan_options": asan_options_of(es),
        "cwe_meta": meta.get("cwe_id", ""),
        "cwe_variants": sorted(set(re.findall(r"CWE-\d+", json.dumps(variants)))),
        "n_variants": len(variants),
        "secure_base_commit": pj.get("secure_base_commit", ""),
        "dockerhub_image": pj.get("dockerhub_image", ""),
        "target_dir": pj.get("target_dir", ""), "language": pj.get("language", ""),
        "verified": jl(os.path.join(vd, "verification_result.json")).get("checks") or None,
    })

json.dump(records, open(OUT, "w"), indent=1)

print("total:", len(records))
print("tier:", dict(Counter(x["tier"] for x in records)))
print("tier x type:", dict(sorted(Counter(f"{x['tier']}:{x['type']}" for x in records).items())))
print("\nreasons (B/C):")
for k, v in Counter(x["reason"] for x in records if x["tier"] != "A").most_common():
    print(f"  {v:4d}  {k}")
A = [x for x in records if x["tier"] == "A"]
print("\nTier A: poc source:", dict(Counter(x["poc_src"] for x in A)))
print("Tier A: fuzzer source:", dict(Counter(x["fuzzer_src"] for x in A)))
print("Tier A: signal:", dict(Counter(x["signal"] for x in A)))
print("Tier A: exploit-set ASAN_OPTIONS:", sum(1 for x in A if x["asan_options"]))
print("Tier A: harness differs from hints/manifest/contract metadata:", sum(1 for x in A if x["fuzzer_mismatch"]))
print("Tier A: projects:", len({x["project"] for x in A}),
      "| without dockerhub_image:", sorted({x["project"] for x in A if not x["dockerhub_image"]}))
print("Tier A: variants missing:", sum(1 for x in A if x["n_variants"] == 0),
      "| variant CWE contradicts metadata:",
      sum(1 for x in A if x["cwe_variants"] and x["cwe_meta"] and x["cwe_meta"] not in x["cwe_variants"]))
print("Tier A: with dataset verification record:", sum(1 for x in A if x["verified"]))
print("ALL: harness metadata disagrees with what exploit runs:", sum(1 for x in records if x["fuzzer_mismatch"]))
