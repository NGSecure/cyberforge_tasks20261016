#!/usr/bin/env python3
"""Generate new-platform (Harbor / CyberGym folded 2-image) PoV bundles from CyberForge.

    python3 -I classify.py       <inner_root> records.json
    python3 -I scan_snapshots.py records.json snapshot_scan/
    python3 -I convert.py        <inner_root> records.json <out_dir> [--scan snapshot_scan/]
                                 [--ver v0.0.1] [--only NAME ...]

<inner_root> holds manifest.csv + projects/. One bundle is written per tier-A record
(see classify.py for the tiers). Each bundle is self-contained: its build inputs
(the injected diff, the ground-truth PoV, a copy of the project's OSS-Fuzz setup/,
the list of base-image snapshot files to scrub from the agent image) live in build/,
outside environment/, so nothing secret reaches the agent. Re-running is
deterministic (same inputs -> same bytes, including the auth token).
"""
import argparse
import base64
import collections
import csv
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "templates")
INLINE_MAX = 256 * 1024  # larger ground truths are fetched from /solve by solve.sh

PIPE = {"FZ": "fz", "WF_RAG": "wf-rag", "WF_LLM": "wf-llm"}

# keywords used to check that a description names the class of the actual crash
CRASH_CLASS_KW = {
    "oob": r"out[- ]of[- ]bounds|overflow|over-?read|under-?flow|buffer|bounds",
    "uaf": r"use[- ]after[- ]free|dangling",
    "free": r"double[- ]free|invalid free|freed twice|\bfree",
    "leak": r"leak",
    "null/segv": r"null|segv|segmentation|invalid pointer|dereference",
    "recursion": r"recursion|stack overflow|stack exhaustion|unbounded",
    "arith": r"divi(de|sion)|by zero|arithmetic",
}


def crash_class(rec):
    if rec["signal"] == "lsan":
        return "leak"
    d = (rec["signal_detail"] or "").lower()
    for key, cls in (("heap-buffer-overflow", "oob"), ("stack-buffer-overflow", "oob"),
                     ("global-buffer-overflow", "oob"), ("stack-buffer-underflow", "oob"),
                     ("container-overflow", "oob"), ("heap-use-after-free", "uaf"),
                     ("double-free", "free"), ("free", "free"), ("segv", "null/segv"),
                     ("stack-overflow", "recursion"), ("fpe", "arith")):
        if key in d:
            return cls
    return ""


def keep_post_setup(path):
    """Snapshot files that stay in the agent image: system/package state (apt installs
    made by the snapshot), Python packages and git's safe.directory setting. None of
    them is built from the target; everything else the snapshot added is scrubbed."""
    return (path.startswith(("/etc/", "/dev/", "/proc/", "/sys/", "/run/"))
            or (path.startswith("/var/") and not path.startswith("/var/tmp/"))
            or path in ("/.dockerenv", "/root/.gitconfig")
            or (path.startswith("/usr/") and not path.startswith("/usr/local/"))
            or re.match(r"/usr/local/lib/python3[^/]*/", path) is not None)


def secure_lines(diff):
    """Distinctive lines that only the secure version has (removed by the injection and
    not re-added or kept as context). build.sh greps the agent image for them."""
    minus, other = [], set()
    for line in diff.decode("utf-8", "replace").splitlines():
        if line.startswith(("---", "+++")):
            continue
        if line.startswith("-"):
            minus.append(line[1:].strip())
        elif line[:1] in ("+", " "):
            other.add(line[1:].strip())
    cand = [s for s in dict.fromkeys(minus)
            if len(s) >= 24 and s not in other and re.search(r"[A-Za-z_]{3}", s)
            and not s.startswith(("//", "/*", "*", "#"))]
    return sorted(cand, key=lambda s: (-len(s), s))[:5]


def setup_workdir(dockerfile):
    """The WORKDIR the project's OSS-Fuzz Dockerfile ends in (base-builder starts at
    /src); `compile` runs build.sh from there, and build.sh may use relative paths."""
    wd = "/src"
    text = re.sub(r"\\\n", " ", open(dockerfile, encoding="utf-8").read())
    for m in re.finditer(r"^\s*WORKDIR\s+(\S+)", text, re.M | re.I):
        d = re.sub(r"\$\{?SRC\}?", "/src", m.group(1).strip("\"'"))
        wd = os.path.normpath(d if d.startswith("/") else os.path.join(wd, d))
    return wd


def judge_asan_options(rec):
    """ASAN_OPTIONS for the judge: the exploit's own options (minus shell expansions),
    plus detect_leaks=1 only when the injected bug is a leak. Many harnesses leak on
    benign inputs; with leak detection on, such a leak in the secure build would make
    a correct PoV fail the "fix build exits 0" check, and the dataset counts a leak as
    the vulnerability only for its leak tasks."""
    raw = re.sub(r"\$\{[^}]*\}|\$\w+", "", rec.get("asan_options") or "")
    opts = {}
    for part in raw.split(":"):
        k, sep, val = part.partition("=")
        if sep and re.fullmatch(r"[a-z_]+", k) and val:
            opts[k] = val
    if "detect_leaks" not in opts:
        opts["detect_leaks"] = "1" if rec["signal"] == "lsan" else "0"
    return ":".join("%s=%s" % kv for kv in opts.items())


def jl(p):
    try:
        v = json.load(open(p, encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def choose_description(vd, rec):
    """Pick the dataset's own one-line description (no rewriting).

    Prefer the concise-cve-style variant (closest to CyberGym's L1 one-liner). If it
    does not name the class of the actual crash but another variant does, use that
    one instead. Tasks without variants get the bug_report.txt header fields.
    """
    variants = jl(os.path.join(vd, "bug_description_variants.json")).get("variants") or []
    variants = [v for v in variants if isinstance(v, dict) and (v.get("description") or "").strip()]
    if not variants:
        br = open(os.path.join(vd, "bug_report.txt"), encoding="utf-8", errors="replace").read()
        cwe = re.search(r"^CWE:\s*(.+)$", br, re.M)
        tf = re.search(r"^Target File:\s*(.+)$", br, re.M)
        text = "%s: %s in %s." % (rec["project"], cwe.group(1).strip() if cwe else rec["cwe_meta"],
                                  tf.group(1).strip() if tf else "the project")
        return text, "bug_report.txt (header fields)", None
    order = sorted(variants, key=lambda v: 0 if v.get("style") == "concise-cve-style" else 1)
    cls = crash_class(rec)
    chosen, mismatch = order[0], None
    if cls:
        ok = [v for v in order if re.search(CRASH_CLASS_KW[cls], v["description"], re.I)]
        if ok:
            chosen, mismatch = ok[0], False
        else:
            mismatch = True
    text = " ".join(chosen["description"].split())
    return text, "%s/%s" % (chosen.get("variant_id", "?"), chosen.get("style", "?")), mismatch


def render(name, values):
    text = open(os.path.join(TPL, name), encoding="utf-8").read()
    for k, v in values.items():
        text = text.replace("@@%s@@" % k, str(v))
    left = sorted(set(re.findall(r"@@[A-Z0-9_]+@@", text)))
    if left:
        raise ValueError("%s: unfilled placeholders %s" % (name, left))
    return text


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.chmod(path, mode)


def build_bundle(root, rec, out_dir, ver, scan_dir):
    proj = rec["project"]
    n = rec["vuln"].rsplit("_", 1)[-1]
    pipe = PIPE[rec["type"]]
    bundle = "cyberforge-%s-%s-%s-poc-L1-oracle" % (proj.lower(), pipe, n)
    tag_prefix = "cyberforge_%s_%s_%s" % (re.sub(r"[^a-z0-9]+", "_", proj.lower()).strip("_"),
                                          pipe.replace("-", "_"), n)
    vd = os.path.join(root, "projects", rec["path"])
    bd = os.path.join(out_dir, bundle)
    if os.path.isdir(bd):
        shutil.rmtree(bd)

    diff = open(os.path.join(vd, "inject_vulnerability.diff"), "rb").read()
    gt = open(os.path.join(vd, rec["poc"]), "rb").read()
    token = hashlib.sha256(b"cyberforge-auth-v1|" + bundle.encode() + b"|"
                           + hashlib.sha256(diff).hexdigest().encode()).hexdigest()[:32]
    has_hub = 1 if rec["dockerhub_image"] else 0
    base_name = rec["dockerhub_image"] or "vuljector/%s:setup" % proj
    snap = None
    if has_hub:
        sp = os.path.join(scan_dir, proj + ".json")
        if not os.path.isfile(sp):
            raise SystemExit("no snapshot scan for %s: run scan_snapshots.py first (%s)" % (proj, sp))
        snap = json.load(open(sp, encoding="utf-8"))
        if snap["image"] != base_name:
            raise SystemExit("%s: scan is for %s, record says %s" % (proj, snap["image"], base_name))
        base_image = "%s@%s" % (base_name, snap["digest"])
        # with /opt/src_snapshot.tar every build stage replaces /src by the pristine tree,
        # so the snapshot's /src entries need no list of their own
        restore = "/opt/src_snapshot.tar" in snap["post_setup_files"]
        residue = [p for p in snap["post_setup_files"]
                   if not keep_post_setup(p) and not (restore and p.startswith("/src/"))]
    else:
        base_image, residue = base_name, []
    cands = rec.get("fuzzer_candidates") or [rec["fuzzer"]]
    if len(cands) == 1:
        phrase = "`%s`, i.e. it is run as `/out/%s <poc>`," % (cands[0], cands[0])
    else:
        phrase = ("(built as %s, depending on the build), i.e. it is run as `/out/<harness> <poc>`,"
                  % " or ".join("`%s`" % c for c in cands))
    description, desc_src, desc_mismatch = choose_description(vd, rec)
    # OSS-Fuzz takes the language from project.yaml (project.json disagrees for openssl)
    yml = open(os.path.join(root, "projects", proj, "setup", "project.yaml"), encoding="utf-8").read()
    m = re.search(r"^language:\s*['\"]?([\w+]+)", yml, re.M)
    fuzz_lang = m.group(1) if m else (rec["language"] or "c++")
    build_workdir = setup_workdir(os.path.join(root, "projects", proj, "setup", "Dockerfile"))

    v = {
        "BUNDLE": bundle, "PROJECT": proj, "VULN_ID": rec["vuln"], "PIPELINE": rec["type"],
        "PIPELINE_KW": pipe, "CWE": rec["cwe_meta"] or "unknown", "FUZZER": cands[0],
        "FUZZER_PHRASE": phrase, "TARGET_DIR": rec["target_dir"], "FUZZ_LANG": fuzz_lang,
        "BUILD_WORKDIR": build_workdir,
        "COMMIT": rec["secure_base_commit"], "COMMIT_SHORT": rec["secure_base_commit"][:12],
        "BASE_IMAGE": base_image, "BASE_IMAGE_NAME": base_name, "HAS_HUB_IMAGE": has_hub, "VER": ver,
        "TAG_PREFIX": tag_prefix, "AUTH_TOKEN": token,
        "POC_SRC_PATH": "%s/%s" % (rec["path"], rec["poc"]), "POC_SIZE": len(gt),
    }

    write(os.path.join(bd, "instruction.md"), render("instruction.md", v))
    write(os.path.join(bd, "task.toml"), render("task.toml", v))
    write(os.path.join(bd, "environment", "Dockerfile"), render("Dockerfile.main", v))
    write(os.path.join(bd, "environment", "docker-compose.yaml"), render("docker-compose.yaml", v))
    write(os.path.join(bd, "environment", "submit.sh"), render("submit.sh", v), 0o755)
    write(os.path.join(bd, "environment", "description.txt"), description + "\n")
    write(os.path.join(bd, "environment", "task-server", "Dockerfile"), render("task-server.Dockerfile", v))
    write(os.path.join(bd, "environment", "task-server", "task_server.py"), render("task_server.py", v), 0o755)
    judge = {"fuzzer_candidates": cands, "asan_options": judge_asan_options(rec),
             "asan_options_from_exploit": rec.get("asan_options") or "",
             "leak_detection": "on: the injected bug is a leak" if rec["signal"] == "lsan" else
                               "per exploit.sh" if "detect_leaks" in (rec.get("asan_options") or "") else
                               "off: the injected bug is not a leak",
             "timeout_sec": 60,
             "cyberforge": {"project": proj, "vulnerability_id": rec["vuln"], "pipeline": rec["type"]}}
    write(os.path.join(bd, "environment", "task-server", "judge.json"), json.dumps(judge, indent=2) + "\n")
    write(os.path.join(bd, "tests", "test.sh"), render(os.path.join("tests", "test.sh"), v), 0o755)
    write(os.path.join(bd, "tests", "verify.py"), render(os.path.join("tests", "verify.py"), v), 0o755)
    if len(gt) <= INLINE_MAX:
        b64 = base64.encodebytes(gt).decode("ascii").rstrip("\n")
        write(os.path.join(bd, "solution", "solve.sh"), render("solve_inline.sh", dict(v, POC_B64=b64)), 0o755)
    else:
        write(os.path.join(bd, "solution", "solve.sh"), render("solve_fetch.sh", v), 0o755)
    write(os.path.join(bd, "build.sh"), render("build.sh", v), 0o755)
    write(os.path.join(bd, "push.sh"), render("push.sh", v), 0o755)

    # build inputs (never copied into environment/)
    os.makedirs(os.path.join(bd, "build"), exist_ok=True)
    with open(os.path.join(bd, "build", "inject_vulnerability.diff"), "wb") as f:
        f.write(diff)
    with open(os.path.join(bd, "build", "ground_truth_poc"), "wb") as f:
        f.write(gt)
    write(os.path.join(bd, "build", "snapshot_residue.txt"), "".join(p + "\n" for p in residue))
    sec = secure_lines(diff)
    write(os.path.join(bd, "build", "secure_lines.txt"), "".join(s + "\n" for s in sec))
    shutil.copytree(os.path.join(root, "projects", proj, "setup"), os.path.join(bd, "build", "setup"))

    src = {
        "bundle": bundle, "source_dataset": "cyberforge_tasks20261016",
        "source_task": "cyberforge_tasks20261016/projects/" + rec["path"],
        "base_image": base_image, "base_image_published": bool(has_hub),
        "base_image_snapshot": None if snap is None else {
            "setup_end": snap["setup_end"],
            "post_setup_layers": [{"created": x["created"], "created_by": x["created_by"], "bytes": x["size"]}
                                  for x in snap["post_layers"]],
            "post_setup_files": len(snap["post_setup_files"]),
            "src_restored_from_snapshot_tarball": restore,
            "post_setup_files_under_src": sum(1 for p in snap["post_setup_files"] if p.startswith("/src/")),
            "scrubbed_from_agent_image": len(residue),
            "scrubbed_by_location": dict(sorted(collections.Counter(
                "/src/" + rec["target_dir"] if p.startswith("/src/%s/" % rec["target_dir"])
                else "/".join(p.split("/")[:3]) for p in residue).items())),
            "secure_source_tarball_present": "/opt/src_snapshot.tar" in snap["post_setup_files"]},
        "secure_lines_checked": len(sec),
        "image_tags": {"docker_image": tag_prefix + "_main:" + ver,
                       "task_server_image": tag_prefix + "_task_server:" + ver},
        "ground_truth": {"dataset_file": rec["poc"], "how_found": rec["poc_src"], "bytes": len(gt),
                         "sha256": hashlib.sha256(gt).hexdigest(),
                         "solve_sh": "inline" if len(gt) <= INLINE_MAX else "fetch /solve"},
        "harness": {"candidates": cands, "how_found": rec["fuzzer_src"],
                    "dataset_metadata_said": rec["fuzzer_metadata"],
                    "metadata_disagrees": rec["fuzzer_mismatch"]},
        "trigger_evidence": {"signal": rec["signal"], "detail": rec["signal_detail"], "from": rec["signal_src"],
                             "dataset_verification_record": rec["verified"]},
        "description": {"from": desc_src, "names_actual_crash_class": (None if desc_mismatch is None
                                                                       else not desc_mismatch)},
        "asan_options_from_exploit": rec.get("asan_options") or None,
        "cwe_id": rec["cwe_meta"], "cwe_in_description_variants": rec["cwe_variants"],
        "secure_base_commit": rec["secure_base_commit"],
    }
    write(os.path.join(bd, "cyberforge_source.json"), json.dumps(src, indent=2) + "\n")
    return bundle, desc_src, desc_mismatch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("records")
    ap.add_argument("out_dir")
    ap.add_argument("--scan", default=os.path.join(HERE, "snapshot_scan"),
                    help="scan_snapshots.py output (default: snapshot_scan/ next to this script)")
    ap.add_argument("--ver", default="v0.0.1")
    ap.add_argument("--only", nargs="*", default=None, help="bundle names or dataset paths to (re)build")
    a = ap.parse_args()
    recs = json.load(open(a.records, encoding="utf-8"))
    os.makedirs(a.out_dir, exist_ok=True)

    rows, built = [], 0
    for rec in sorted(recs, key=lambda r: r["seq"]):
        bundle, desc_src, desc_mismatch = "", "", None
        if rec["tier"] == "A":
            n = rec["vuln"].rsplit("_", 1)[-1]
            name = "cyberforge-%s-%s-%s-poc-L1-oracle" % (rec["project"].lower(), PIPE[rec["type"]], n)
            if a.only is None or name in a.only or rec["path"] in a.only:
                bundle, desc_src, desc_mismatch = build_bundle(a.root, rec, a.out_dir, a.ver, a.scan)
                built += 1
            else:
                bundle = name
        rows.append({
            "seq": rec["seq"], "pipeline": rec["type"], "project": rec["project"], "vulnerability": rec["vuln"],
            "source_path": rec["path"], "tier": rec["tier"], "reason": rec["reason"], "bundle": bundle,
            "harness": rec["fuzzer"], "harness_found_by": rec["fuzzer_src"],
            "harness_metadata_disagrees": rec["fuzzer_mismatch"], "ground_truth": rec["poc"],
            "ground_truth_found_by": rec["poc_src"], "signal": rec["signal"], "signal_detail": rec["signal_detail"],
            "description_from": desc_src,
            "description_names_crash_class": "" if desc_mismatch is None else (not desc_mismatch),
            "exploit_asan_options": rec.get("asan_options") or "", "cwe_id": rec["cwe_meta"],
        })
    if a.only is None:
        with open(os.path.join(a.out_dir, "conversion_manifest.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print("bundles written:", built)


if __name__ == "__main__":
    sys.exit(main())
