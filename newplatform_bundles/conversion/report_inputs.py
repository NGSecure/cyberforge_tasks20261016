#!/usr/bin/env python3
"""Copy out of the project image the crashing inputs the dataset names but does not ship.

    python3 -I report_inputs.py <inner_root> snapshot_scan/ report_inputs/ <task> ...

- Some FZ exploits run a harness over the project's own test files and ship none of
  them; their sanitizer_report.txt still shows which one crashed (libFuzzer's
  "Running: /src/..." right before the crash). That file is copied from the pinned base
  image's /opt/src_snapshot.tar (the pristine /src every dataset build starts from).
- fuzz_results/vulnerable/crash_report.json may name as the exact crashing seed a member
  of the harness's built-in corpus (seed_provenance.provenance "builtin_corpus_member"),
  which fuzz_poc.py read from /out/<fuzzer>_seed_corpus.zip; that member is copied from
  the zip in the image's /out, and kept only when its size is the one the report records
  (and, for corpus files named by their SHA-1, when the content has that SHA-1).

Output: report_inputs/<project>/<vuln>/<basename or seed name>, where classify.py looks
for it. Existing files are kept. Needs Docker; a pull falls back to mirror.gcr.io like
replay_deep.py.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

# the same crash marker as classify.py's report_run()
CRASH_AT_RE = re.compile(r"==\d+==\s?ERROR: |ERROR: libFuzzer: (deadly signal|out-of-memory)|: Assertion `.*' failed|"
                         r"runtime error:")


def crashing_file(report):
    m = CRASH_AT_RE.search(report)
    runs = re.findall(r"^Running: (\S+)", report[:m.start()] if m else "", re.M)
    return runs[-1] if runs and runs[-1].startswith("/src/") else ""


def corpus_seed(vd):
    """(fuzzer, archive member, seed name, size) of a built-in corpus seed crash_report.json
    names as the exact seed that crashed the vulnerable build, or None."""
    f = os.path.join(vd, "exploit_files", "fuzz_results", "vulnerable", "crash_report.json")
    if not os.path.isfile(f):
        return None
    c = json.load(open(f))
    sp = c.get("seed_provenance") or {}
    if c.get("mode") != "replay" or c.get("attribution_kind") != "exact_seed" or c.get("returncode") in (0, None) \
            or sp.get("provenance") != "builtin_corpus_member" or not sp.get("archive_member") or not c.get("fuzzer"):
        return None
    return c["fuzzer"], sp["archive_member"], c.get("seed") or sp.get("name"), sp.get("size")


def main():
    root, scan_dir, out_root = sys.argv[1:4]
    by_project = {}
    for rel in sys.argv[4:]:
        vd = os.path.join(root, "projects", rel)
        report = open(os.path.join(vd, "sanitizer_report.txt"), errors="replace").read()
        src, seed = crashing_file(report), corpus_seed(vd)
        if not src and not seed:
            print(rel, "skipped (nothing the dataset names is missing)", flush=True)
            continue
        if src:
            dst = os.path.join(out_root, *rel.split("/vulnerabilities/"), os.path.basename(src))
            if not os.path.isfile(dst):
                by_project.setdefault(rel.split("/")[0], []).append((rel, ("tar", src, None), dst))
        if seed:
            fuzzer, member, name, size = seed
            dst = os.path.join(out_root, *rel.split("/vulnerabilities/"), name)
            if not os.path.isfile(dst):
                by_project.setdefault(rel.split("/")[0], []).append(
                    (rel, ("zip", "/out/%s_seed_corpus.zip" % fuzzer, member, size), dst))
    for project, tasks in sorted(by_project.items()):
        scan = json.load(open(os.path.join(scan_dir, project + ".json")))
        image = "%s@%s" % (scan["image"], scan["digest"])
        for ref in (image, "mirror.gcr.io/" + image):
            if subprocess.run(["docker", "pull", "-q", ref], capture_output=True).returncode == 0:
                image = ref
                break
        else:
            for rel, _, _ in tasks:
                print(rel, "skipped (pull failed)", flush=True)
            continue
        for rel, what, dst in tasks:
            if what[0] == "tar":
                cmd, label = ["--entrypoint", "tar", image, "-xOf", "/opt/src_snapshot.tar", what[1].lstrip("/")], what[1]
            else:
                cmd = ["--entrypoint", "python3", image, "-c",
                       "import sys, zipfile; sys.stdout.buffer.write(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]))",
                       what[1], what[2]]
                label = "%s:%s" % (what[1], what[2])
            got = subprocess.run(["docker", "run", "--rm", "--network", "none"] + cmd, capture_output=True)
            data = got.stdout
            if got.returncode != 0 or not data:
                print(rel, "not in the image: %s" % label, flush=True)
                continue
            if what[0] == "zip":
                base = os.path.basename(what[2])
                if what[3] is not None and len(data) != what[3]:
                    print(rel, "%s: %d bytes, crash_report.json says %d; not kept" % (label, len(data), what[3]), flush=True)
                    continue
                if re.fullmatch(r"[0-9a-f]{40}", base) and hashlib.sha1(data).hexdigest() != base:
                    print(rel, "%s: content does not have the SHA-1 its name says; not kept" % label, flush=True)
                    continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            print(rel, "%s (%d bytes)" % (label, len(data)), flush=True)
        if os.environ.get("REPLAY_DEEP_KEEP_IMAGES") != "1":
            subprocess.run(["docker", "rmi", image], capture_output=True)


if __name__ == "__main__":
    main()
