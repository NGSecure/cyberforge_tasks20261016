#!/usr/bin/env python3
"""Classify every CyberForge task for conversion to a new-platform PoC bundle.

Tier A  crash evidence + a concrete ground-truth PoC file that the task's own exploit
        is shown to feed to a fuzz harness (`/out/<fuzzer> <poc>`): harness bundle.
Tier B  crash evidence, but the PoV drives a project CLI/test binary or is a program
        compiled against the project: CLI/program bundle (templates/task_server_b.py),
        when replay_deep.py recorded one unambiguous way the exploit ran it.
Tier C  no usable crash evidence (empty report, no sanitizer crash, a timeout, a report
        that does not show what exploit.sh checks for): bundles are still made when a
        ground truth and a way to run it are known, but nothing in the dataset shows
        that this ground truth triggers the bug; build.sh's self-check decides.
A task is converted ("converted" in the record) only when its tier's bundle can be made;
the rest stay listed with the reason: a behavioral oracle (the exploit compares outputs,
nothing crashes), a recording that is ambiguous (several inputs, races, unit tests,
mixed programs), or a missing / empty / oversized ground truth. Before giving up on a
task with crash evidence, the dataset's own report is read for the harness and the file
libFuzzer was running when it crashed (report_input(); report_inputs.py copies such
files of the project tree out of the base image). "DIFFERENTIAL / BEHAVIORAL" reports
(exploit.sh's output on both builds) count as crash evidence only when the vulnerable
run really crashed and the secure one did not (differential_signal()).

Harness resolution trusts what the exploit actually executes (literal /out/<x> or a
FUZZER="x" ... /out/${FUZZER} indirection) and crash_report.json for libFuzzer
crash artifacts. hints/manifest/contract selected_fuzzer are a last resort only and
are frequently wrong, so disagreements are recorded. When snapshot_scan/ (from
scan_snapshots.py) is present next to this script, a harness name must also be one
the dataset's own compile of the base image put in /out.

Usage: python3 -I classify.py <inner_root> <out_records.json>
       (run it again after scan_snapshots.py so the /out check applies, and after
       replay_exploits.py / replay_deep.py so their recordings are used)
"""
import csv
import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deep_recipe  # noqa: E402

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


SAN_NAMES = {"AddressSanitizer": "asan", "LeakSanitizer": "lsan", "MemorySanitizer": "msan",
             "ThreadSanitizer": "tsan", "UndefinedBehaviorSanitizer": "ubsan"}
# a real sanitizer report, libFuzzer's crash handler, or bash's job message for a crashed harness
DIFF_CRASH_RE = re.compile(r"==\d+==\s?ERROR: (AddressSanitizer|LeakSanitizer|MemorySanitizer|"
                           r"UndefinedBehaviorSanitizer):? ?(?:attempting )?([\w\-]+)"
                           r"|==\d+== ERROR: libFuzzer: (deadly signal)"
                           r"|line \d+: +\d+ (Aborted|Segmentation fault)[^\n]*?/out/[\w.+-]+")


def differential_signal(t):
    """The dataset's "DIFFERENTIAL / BEHAVIORAL" reports hold what exploit.sh printed on
    each build. They count as crash evidence only when the vulnerable run shows a real
    crash and exploit.sh's verdict (___RC) differs: nonzero there, 0 on the secure build.
    "both": the secure run crashed too."""
    if "=== VULNERABLE" not in t or "=== SECURE" not in t:
        return "behavioral", ""
    vul, sec = t.split("=== VULNERABLE", 1)[1].split("=== SECURE", 1)
    rc = lambda s: (re.findall(r"^___RC=(\d+)", s, re.M) or [""])[-1]
    v, s = DIFF_CRASH_RE.search(vul), DIFF_CRASH_RE.search(sec)
    if not v or rc(vul) in ("", "0") or rc(sec) != "0":
        return "behavioral", ""
    if s:
        return "both", ""
    if v.group(1):
        return SAN_NAMES[v.group(1)], v.group(2)
    return "signal", "deadly-signal" if v.group(3) or v.group(4) == "Segmentation fault" else "abort"


def signal_of(t):
    s = t.strip()
    if not s:
        return "empty", ""
    if "DIFFERENTIAL / BEHAVIORAL" in t:
        return differential_signal(t)
    names = SAN_NAMES
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


MISMATCH = ("sanitizer report does not show what exploit.sh checks for "
            "(recorded run did not trigger; ground truth unverified)")
GREP_RE = re.compile(r"grep\s+((?:-[a-zA-Z]+\s+)*)(?:-e\s+)?(['\"])(.+?)\2")
TRIGGER_WORDS = re.compile(r"Sanitizer|SUMMARY|heap-|stack-|SEGV|overflow|use-after|double-free|leak|"
                           r"Segmentation|abort|ERROR", re.I)


def exploit_checks_leak_only(es):
    """exploit.sh's sanitizer greps all look for a leak (its own trigger condition is a leak)."""
    pats = [p for _, _, p in GREP_RE.findall(es) if TRIGGER_WORDS.search(p)]
    return bool(pats) and all(re.search(r"leak", p, re.I) and not re.search(
        r"SEGV|overflow|use-after|double-free|AddressSanitizer(?!.*leak)", p, re.I) for p in pats)


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
DEEP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay_deep")


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


LFS_PTR_RE = re.compile(rb"^version https://git-lfs\.github\.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize \d+\n$")


# environment the shell or the sanitizers use, not what the program under test reads
# environment the shell, the sanitizers or a build use, not what the program under test reads
SHELL_ENV = {"ASAN_OPTIONS", "UBSAN_OPTIONS", "MSAN_OPTIONS", "LSAN_OPTIONS", "HWASAN_OPTIONS", "TSAN_OPTIONS",
             "ASAN_SYMBOLIZER_PATH", "LLVM_SYMBOLIZER_PATH", "PATH", "HOME", "LANG", "LC_ALL", "LANGUAGE", "TMPDIR",
             "TERM", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "SRC", "OUT", "WORK", "EXPLOIT_DIR",
             "LD_LIBRARY_PATH", "CC", "CXX", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS"}


def exploit_env(es):
    """Environment variables exploit.sh exports for the programs it runs (or LD_PRELOAD it sets for one),
    except plumbing: a value that only names the build's own files under /out (espeak-ng WF_LLM_5's
    ESPEAK_DATA_PATH=${ESPEAK_DATA_PATH:-/out/espeak-ng-data})."""
    code = "\n".join(l for l in es.splitlines() if not l.strip().startswith("#"))
    names = [v for v, val in re.findall(r"(?m)(?:^|[;&|]\s*)export\s+([A-Za-z_]\w*)=(\S*)", code)
             if v not in SHELL_ENV and not re.fullmatch(r'"?(\$\{\w+:-)?/out/[\w./-]*\}?"?', val)]
    names += re.findall(r"(?m)(?:^|[;&|]\s*)(LD_PRELOAD)=\S+\s+\S", code)
    return sorted(set(names))


def lfs_pointer(path):
    """The oid when the file is a Git LFS pointer (the dataset copy lacks its content), else ''.
    lfs_restore.py replaces the pointers it can resolve; the rest count as missing files."""
    try:
        if os.path.getsize(path) > 200:
            return ""
        m = LFS_PTR_RE.match(open(path, "rb").read())
    except OSError:
        return ""
    return m.group(1).decode() if m else ""


def exact_seed(vd, project, crep):
    """(path relative to vd, how) of the seed crash_report.json says crashed the vulnerable
    build. Seeds drawn from the built-in corpus are not always shipped with the task; then
    a file of that name in another task of the same project is used, but only when every
    copy found has the same content."""
    sp = crep.get("seed_provenance") or {}
    rel = sp.get("relative_path") or ""
    if "exploit_files/" in rel:
        f = os.path.join(vd, "exploit_files", rel.split("exploit_files/", 1)[1])
        if os.path.isfile(f) and not lfs_pointer(f):
            return os.path.relpath(f, vd), "fuzz_exact_seed"
    name = crep.get("seed") or sp.get("name") or ""
    if not name or "/" in name:
        return "", ""
    hits = sorted(h for h in glob.glob(os.path.join(PROJ, project, "vulnerabilities", "*", "exploit_files",
                                                    "generated_inputs", name)) if not lfs_pointer(h))
    if hits and len({hashlib.sha256(open(h, "rb").read()).hexdigest() for h in hits}) == 1:
        return os.path.relpath(hits[0], vd), "fuzz_exact_seed (same-named seed of a sibling task)"
    # a member of the harness's built-in corpus: fuzz_poc.py read it from
    # /out/<fuzzer>_seed_corpus.zip, and report_inputs.py copies it from there
    f = os.path.join(REPORT_INPUTS, project, os.path.basename(vd), name)
    if sp.get("provenance") == "builtin_corpus_member" and os.path.isfile(f):
        return (os.path.relpath(f, os.path.dirname(REPORT_INPUTS)),
                "fuzz_exact_seed (built-in corpus member %s of /out/%s_seed_corpus.zip, copied from the image)"
                % (sp.get("archive_member"), crep.get("fuzzer")))
    return "", ""


def poc_path(vd, poc, poc_src):
    """Ground truths of the replays, of report_inputs.py and of choose_gt.py's exploit runs
    are relative to this script's directory, the dataset's own files to the task directory."""
    return (os.path.join(os.path.dirname(REPLAY_DIR), poc)
            if poc_src.startswith(("exploit_replay", "project_file")) or poc.startswith(("report_inputs/", "exploit_live/"))
            else os.path.join(vd, poc))


# choose_gt.py: ground truths picked by running the bundles (verify_bundles.py): the
# dataset's pov.bin where it is differential in the bundle's builds, or what exploit.sh fed
# the harness in the project's image where our first ground truth failed
GT_CHOICE = jl(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gt_choice.json"))


REPORT_INPUTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_inputs")
EMPTY_SHA1 = hashlib.sha1(b"").hexdigest()
CRASH_AT_RE = re.compile(r"==\d+==\s?ERROR: |ERROR: libFuzzer: (deadly signal|out-of-memory)|: Assertion `.*' failed|"
                         r"runtime error:")


def report_run(report):
    """(harness, input) libFuzzer printed right before the report's first crash:
    "/out/<harness>: Running N inputs ..." and "Running: <file>" ('' when absent)."""
    m = CRASH_AT_RE.search(report)
    pre = report[:m.start()] if m else ""
    hs = re.findall(r"^/out/([\w.+-]+): Running \d+ inputs", pre, re.M)
    runs = re.findall(r"^Running: (\S+)", pre, re.M)
    return (hs[-1] if hs else ""), (runs[-1] if runs else "")


def report_harness(name, report, known):
    """A harness name the dataset used, resolving its /out/vuln_fuzzer rename by the harness
    source in the report's stack (LLVMFuzzerTestOneInput /src/<name>.cc); '' unless the
    name is one the project's /out holds."""
    if name == "vuln_fuzzer":
        src = re.findall(r" in LLVMFuzzerTestOneInput /\S*?([\w.+-]+)\.(?:c|cc|cpp|cxx):\d+", report)
        name = src[0] if len(set(src)) == 1 else ""
    return name if name and name in known else ""


_sha1_cache = {}


def dataset_file_by_sha1(project, sha1):
    """A file of any task of the project with this SHA-1 (libFuzzer names crash files
    crash-<sha1 of the content>), or ''. The empty file's SHA-1 always resolves, to the
    project's own empty file or else to report_inputs/empty."""
    if project not in _sha1_cache:
        idx = {}
        for f in sorted(glob.glob(os.path.join(PROJ, project, "vulnerabilities", "*", "exploit_files", "**"),
                                  recursive=True)):
            if os.path.isfile(f) and os.path.getsize(f) <= 16 << 20:
                idx.setdefault(hashlib.sha1(open(f, "rb").read()).hexdigest(), f)
        _sha1_cache[project] = idx
    if sha1 == EMPTY_SHA1 and sha1 not in _sha1_cache[project]:
        return os.path.join(REPORT_INPUTS, "empty")
    return _sha1_cache[project].get(sha1, "")


def report_input(vd, rel, project, report, es, ef_files, known, harnesses=()):
    """(poc, poc_src, harness) when the dataset's own report pins down the crashing input
    and its harness: the file libFuzzer was running right before the crash (or, when it
    found the crash itself, the crash file it wrote: "Test unit written to"), found by
    content (crash-<sha1>, crash-da39a3ee... being the empty file), as the one file of
    that name the exploit ships, or as a file of the project tree (extracted by
    report_inputs.py). The harness is the one the report shows running, else the task's."""
    h, inp = report_run(report)
    if not inp:
        m = re.search(r"Test unit written to (\S*crash-[0-9a-f]{40})", report)
        inp = m.group(1) if m else ""
    h = report_harness(h, report, known) or next((x for x in harnesses if x in known), "")
    if not h or not inp:
        return None
    base = os.path.basename(inp)
    m = re.fullmatch(r"crash-([0-9a-f]{40})", base)
    if m:
        f = dataset_file_by_sha1(project, m.group(1))
        if not f:
            return None
        return (os.path.relpath(f, os.path.dirname(REPORT_INPUTS)) if f.startswith(REPORT_INPUTS + os.sep)
                else os.path.relpath(f, vd)), "report_sha1 (the crash file the report names, found by SHA-1)", h
    same = [f for f in ef_files if os.path.basename(f) == base and os.path.getsize(os.path.join(vd, f)) > 0]
    if len(same) == 1 and not re.search(r"/dev/u?random|\$RANDOM", es):
        return same[0], "report_running (the file the report shows crashing, shipped with the exploit)", h
    f = os.path.join(REPORT_INPUTS, *rel.split("/vulnerabilities/"), base)
    if inp.startswith("/src/") and os.path.isfile(f) and os.path.getsize(f) > 0:
        return (os.path.relpath(f, os.path.dirname(REPORT_INPUTS)),
                "project_file (%s, the file the report shows crashing)" % inp, h)
    return None


def asan_options_of(es):
    m = re.search(r"\bASAN_OPTIONS=([\"']?)([^\s\"']+)\1", es)
    return m.group(2) if m else ""


# the /out names each project's exploits run (stands in for a snapshot scan where there is none)
used_out = {}
for r in rows:
    used_out.setdefault(r["project"], set()).update(
        exploit_harnesses(rd(os.path.join(PROJ, r["path"], "exploit_files", "exploit.sh")))[0])

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
    if "DIFFERENTIAL / BEHAVIORAL" in report and sig != "behavioral":
        report_ok = None  # the report holds exploit.sh's own verdict on both builds (___RC)
    if sig in ("empty", "nocrash") and crep.get("asan_like") and crep.get("result_kind") == "real_crash":
        sig, sig_detail, sig_src = "asan", "crash_report.asan_like", "crash_report.json"
    vres = jl(os.path.join(vd, "verification_result.json"))
    if sig in ("empty", "nocrash", "timeout") and (vres.get("checks") or {}).get("exploit_on_vulnerable") == "passed" \
            and crep.get("returncode") not in (0, None, 124, 137, -9):
        # the dataset's verified replay (fuzz_poc.py) of this task crashed the vulnerable build
        sig, sig_detail, sig_src = "verified", "replay exit %s" % crep["returncode"], "verification_result.json"

    ef_files = []
    if os.path.isdir(ef):
        for dp, _, fn in os.walk(ef):
            for f in fn:
                ef_files.append(os.path.relpath(os.path.join(dp, f), vd))
    top_files = [f for f in ef_files if os.path.dirname(f) == "exploit_files"]

    custom = []
    if "DIFFERENTIAL / BEHAVIORAL" in report:
        # the exploit ran in the dataset's image (seed corpora, /src): only the deep replay,
        # in that image too, shows what it fed the target
        custom.append("differential-run report")
    if re.search(r"\b(gcc|g\+\+|clang\+\+|clang|cc)\b[^\n]*\s-o\s", es):
        custom.append("exploit.sh compiles code")
    code = "\n".join(l for l in es.splitlines() if not l.strip().startswith("#"))
    RACE = "exploit races a background process (not a single-input PoV)"
    if re.search(r"(\)|[\w\"'])[ \t]*&[ \t]*$", code, re.M):
        custom.append(RACE)
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
    if not poc and crep.get("mode") == "replay" and crep.get("attribution_kind") == "exact_seed" \
            and crep.get("returncode") not in (0, None):
        # fuzz_poc.py replayed seeds and the report names the one that crashed the
        # vulnerable build (fuzz_results/vulnerable/crash_report.json)
        seed, how = exact_seed(vd, p, crep)
        if seed:
            poc, poc_src = seed, how
    # the seed crash_report.json names is shipped as a Git LFS pointer whose content was not
    # found: the dataset's verified crashing input exists but is not in this copy; nothing
    # else stands in for it
    lfs_seed = ""
    if not poc and crep.get("mode") == "replay" and crep.get("attribution_kind") == "exact_seed" \
            and crep.get("returncode") not in (0, None):
        rel_s = (crep.get("seed_provenance") or {}).get("relative_path") or ""
        if "exploit_files/" in rel_s:
            lfs_seed = lfs_pointer(os.path.join(ef, rel_s.split("exploit_files/", 1)[1]))
    rp, rinfo = replayed(r["path"], [os.path.join(vd, f) for f in ef_files])
    if lfs_seed:
        rp = None
    if not poc and rp:
        # what the exploit really ran; the harvested pov.bin is often something else
        poc, poc_src = rp, "exploit_replay"
    if not poc and not lfs_seed:
        rel = hints.get("successful_seed_relative_path") or ""
        if rel and os.path.isfile(os.path.join(vd, rel)):
            poc, poc_src = rel, "hints.successful_seed"
    if not poc and not lfs_seed:
        for cand in ("exploit_files/pov.bin", "exploit_files/crash_poc.bin"):
            if os.path.isfile(os.path.join(vd, cand)):
                poc, poc_src = cand, "named_file"
                break
    if not poc and not lfs_seed and es:
        refd = [f for f in top_files if not f.endswith(POC_SKIP_EXT)
                and os.path.basename(f) not in ("driver", "attack") and os.path.basename(f) in es]
        if len(refd) == 1:
            poc, poc_src = refd[0], "referenced_by_exploit.sh"
    if not poc and not lfs_seed:
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
    if poc_src.startswith(("fuzz_crash_artifact", "fuzz_exact_seed")) and clean_fuzzer(crep.get("fuzzer")):
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

    # The report shows libFuzzer running a file the task ships, right before the crash, on
    # this harness: that file is the dataset's crashing input, and it outranks what our
    # replay of exploit.sh captured (the exploit may pick its input from the project tree,
    # which the replay container does not have).
    if poc_src in ("exploit_replay", "hints.successful_seed", "named_file", "referenced_by_exploit.sh",
                   "single_input_file") and fuzzer:
        got = report_input(vd, r["path"], p, report, es, ef_files, {fuzzer}, [fuzzer])
        if got and got[1].startswith("report_running") and got[2] == fuzzer \
                and not lfs_pointer(os.path.join(vd, got[0])) and got[0] != poc:
            poc, poc_src = got[0], got[1]

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
    # libFuzzer's own out-of-memory report exits 71, which the judge counts as a crash
    crash_sigs = ("asan", "lsan", "ubsan", "msan", "tsan", "signal", "oom", "verified")
    # fuzz_results/vulnerable/crash_report.json holds the dataset's verified crash input and
    # harness: they outrank whatever else exploit.sh does (e.g. it also runs unit tests)
    from_crash_report = poc_src.startswith(("fuzz_crash_artifact", "fuzz_exact_seed")) and fuzzer_src == "crash_report.json"
    empty_gt = bool(poc) and os.path.getsize(poc_path(vd, poc, poc_src)) == 0
    degenerate = empty_gt and from_crash_report  # the dataset's crashing seed is the empty file
    if (sig == "behavioral" or custom) and not from_crash_report:
        tier, reason = "B", ("behavioral-divergence oracle" if sig == "behavioral" else custom[0])
    elif sig == "empty":
        tier, reason = "C", "sanitizer_report.txt is empty (no trigger evidence)"
    elif sig == "timeout":
        tier, reason = "C", "timeout signal (the judge treats timeouts as no crash)"
    elif sig not in crash_sigs:
        tier, reason = "C", "report shows no sanitizer crash"
    elif not poc:
        tier, reason = "C", ("the dataset's crashing seed %s is a Git LFS pointer in this copy: its content "
                             "(sha256 %s) is missing" % (os.path.basename(crep.get("seed") or ""), lfs_seed[:16])
                             if lfs_seed else "crash input not saved (fuzz-campaign replay; seed unrecorded)"
                             if crep else "no concrete PoC file (payload only inline / missing)")
    elif not fuzzer:
        tier, reason = "C", note or "fuzz harness not identifiable"
    elif empty_gt and not degenerate:
        tier, reason = "C", "ground-truth PoC file is empty (pov.bin harvest failure or degenerate empty-input trigger)"
    elif "file size limit" in (rinfo.get("problems") or []) and \
            not poc_src.startswith(("fuzz_crash_artifact", "fuzz_exact_seed")):
        tier, reason = "C", "the exploit's real payload is larger than 16 MB (too large to bundle; pov.bin is not it)"
    elif sig_src == "sanitizer_report.txt" and report_ok is False and poc_src != "exploit_replay":
        tier, reason = "C", MISMATCH
    else:
        tier, reason = "A", ""

    # ---- B/C: what the exploit really ran in the project's own image (replay_deep.py) ----
    # Evidence-first: B needs crash evidence like A; without it a task is C, whose
    # bundles carry a ground truth the dataset never showed to trigger the bug.
    evidence = sig in crash_sigs and not (sig_src == "sanitizer_report.txt" and report_ok is False)
    no_evidence = {"empty": "sanitizer_report.txt is empty (no trigger evidence)",
                   "timeout": "timeout signal (the judge treats timeouts as no crash)",
                   "behavioral": "behavioral-divergence oracle",
                   "both": "the dataset's differential run crashed the secure build too"}.get(
        sig, MISMATCH if sig in crash_sigs else "report shows no sanitizer crash")
    bundle, deep_kind, deep_why, converted = "", "", "", tier == "A"
    if tier == "A":
        bundle = "harness"
    else:
        deep, deep_why = deep_recipe.recipe_or_reason(os.path.join(DEEP_DIR, p, r["vuln"]), es,
                                                      [os.path.basename(f) for f in ef_files])
        deep_why = deep_why or ""
        deep_kind = deep["kind"] if deep else ""
        if sig == "behavioral":
            # the exploit compares outputs and nothing crashes: a crash-based judge cannot score it
            tier, reason = "B", "behavioral-divergence oracle (the exploit compares outputs; nothing crashes)"
        elif RACE in custom:
            # what crashed depended on a process running beside the recorded call (a server, a
            # file being truncated meanwhile): no single recorded input reproduces it
            tier, reason = "B", RACE
        elif lfs_seed:
            pass  # the verified crashing seed is known, only missing from this copy: no stand-in
        elif deep and deep_kind == "harness":
            poc = os.path.relpath(os.path.join(DEEP_DIR, p, r["vuln"], deep["gt_file"]),
                                  os.path.dirname(DEEP_DIR))
            poc_src = "exploit_replay_deep" + (" (made by the exploit's own program)" if deep["generated"] else "") + \
                (" (the first of the exploit's candidates that crashed the rebuilt vulnerable build)"
                 if deep.get("selected") else "")
            fuzzer, fuzzer_src, ex_h = deep["fuzzer"], "replay_deep", [deep["fuzzer"]]
            mismatch = bool(meta_fz and fuzzer not in meta_fz)
            tier, reason = ("A", "") if evidence else ("C", no_evidence)
            bundle, converted, degenerate = "harness", True, not deep["gt"]
        elif deep:
            mains = re.findall(r"#\d+ 0x[0-9a-f]+ in main (/\S+?):\d+", report)
            if deep_kind == "program" and evidence and mains and \
                    not any(os.path.basename(m) == os.path.basename(deep["poc_path"]) for m in mains):
                # the dataset's crash came from another program than the one the exploit ships
                evidence, no_evidence = False, ("the dataset's report comes from another program (%s), "
                                                "not the exploit's %s" % (os.path.basename(mains[0]),
                                                                          os.path.basename(deep["poc_path"])))
            tier, reason = ("B", "") if evidence else ("C", no_evidence)
            bundle, converted = deep_kind, True
        elif tier == "C" and reason == no_evidence and poc and fuzzer \
                and os.path.getsize(poc_path(vd, poc, poc_src)) > 0 \
                and "file size limit" not in (rinfo.get("problems") or []) and "larger than 16 MB" not in deep_why:
            # the dataset's own PoC + harness, unconfirmed (not when a replay showed the
            # exploit's real payload is larger than 16 MB: then that file is not it)
            bundle, converted = "harness", True
        if not converted and deep_why and tier == "B":
            reason = "%s; replay: %s" % (reason, deep_why)
        elif not converted and "larger than 16 MB" in deep_why:
            reason = "the exploit's real payload is larger than 16 MB (too large to bundle)"

    # ---- still nothing: the dataset's own report may pin down input and harness ----
    if not converted and evidence and sig_src == "sanitizer_report.txt" and RACE not in custom:
        known = outs if outs is not None else used_out.get(p, set())
        got = report_input(vd, r["path"], p, report, es, ef_files, known, ex_h or [fuzzer])
        rh = report_harness(report_run(report)[0], report, known)
        if not got and rp and len(rinfo.get("inputs") or []) == 1 and report_ok is not False and rh \
                and report_harness(rinfo["inputs"][0]["harness"], report, known) == rh \
                and os.path.getsize(poc_path(vd, rp, "exploit_replay")) > 0:
            # the exploit's one replayed input went to the very harness the report shows crashing
            got = rp, "exploit_replay", rh
        if got:
            poc, poc_src, fuzzer = got
            fuzzer_src, ex_h = "sanitizer_report.txt", [fuzzer]
            mismatch = bool(meta_fz and fuzzer not in meta_fz)
            tier, reason, bundle, converted = "A", "", "harness", True
            degenerate = os.path.getsize(poc_path(vd, poc, poc_src)) == 0

    # a choice applies only to the ground truth it was made against (choose_gt.py's "was")
    ch, gt_base = GT_CHOICE.get(r["path"]), None
    if ch and converted and bundle == "harness" and ch.get("was") == poc_src \
            and os.path.isfile(poc_path(vd, ch["poc"], ch["poc_src"])):
        gt_base = {"poc": poc, "poc_src": poc_src}
        poc, poc_src = ch["poc"], ch["poc_src"]
        if ch.get("fuzzer") and ch["fuzzer"] != fuzzer:
            fuzzer, fuzzer_src, ex_h = ch["fuzzer"], "exploit.sh, run in the project's image", [ch["fuzzer"]]
        degenerate = os.path.getsize(poc_path(vd, poc, poc_src)) == 0

    env_set = exploit_env(es)
    if converted and env_set:
        # the exploit sets the environment of what it runs: what crashed depended on it, and a PoV is
        # only an input (verification: harfbuzz FZ_5 crashes on any input with HB_SHAPER_LIST=harfbuzz
        # and on none without; espeak-ng plants a voice file and points ESPEAK_DATA_PATH at it; jq's
        # bug is in parsing JQ_COLORS)
        tier, reason, converted, bundle = tier, ("the exploit sets %s for the program it runs; a PoV is only an input"
                                                 % " and ".join(env_set)), False, ""

    if converted and poc and lfs_pointer(poc_path(vd, poc, poc_src)):
        # the dataset copy holds a Git LFS pointer, not the file (lfs_restore.py could not find it)
        tier, reason, converted, bundle = tier, ("the dataset's PoV file %s is a Git LFS pointer in this copy: its "
                                                 "content (sha256 %s) is missing" % (os.path.basename(poc),
                                                 lfs_pointer(poc_path(vd, poc, poc_src))[:16])), False, ""

    vj = jl(os.path.join(vd, "bug_description_variants.json"))
    variants = vj.get("variants") or []
    records.append({
        "seq": int(r["seq"]), "type": t, "project": p, "vuln": r["vuln"], "path": r["path"],
        "tier": tier, "reason": reason, "converted": converted, "bundle_type": bundle,
        "degenerate_empty_input": bool(converted and degenerate),
        "deep_replay": deep_kind or deep_why,
        "signal": sig, "signal_detail": sig_detail, "signal_src": sig_src,
        "report_matches_exploit_check": report_ok,
        "exploit_checks_leak_only": exploit_checks_leak_only(es),
        "poc": poc, "poc_src": poc_src, "gt_base": gt_base, "fuzzer": fuzzer, "fuzzer_src": fuzzer_src,
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
print("converted:", dict(Counter("%s:%s" % (x["tier"], x["bundle_type"]) for x in records if x["converted"])))
print("not converted:", dict(Counter(x["tier"] for x in records if not x["converted"])))
print("tier x type:", dict(sorted(Counter(f"{x['tier']}:{x['type']}" for x in records).items())))
print("\nreasons (not converted):")
for k, v in Counter("%s  %s" % (x["tier"], x["reason"]) for x in records if not x["converted"]).most_common():
    print(f"  {v:4d}  {k}")
print("\nreasons (C, converted):")
for k, v in Counter(x["reason"] for x in records if x["converted"] and x["tier"] == "C").most_common():
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
