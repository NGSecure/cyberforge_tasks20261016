#!/usr/bin/env python3
"""Copy out of the project image the project file a task's report shows crashing.

    python3 -I report_inputs.py <inner_root> snapshot_scan/ report_inputs/ <task> ...

Some FZ exploits run a harness over the project's own test files and ship none of them;
their sanitizer_report.txt still shows which one crashed (libFuzzer's "Running: /src/..."
right before the crash). This copies that file from the pinned base image's
/opt/src_snapshot.tar (the pristine /src every dataset build starts from) to
report_inputs/<project>/<vuln>/<basename>, where classify.py looks for it. Existing
files are kept. Needs Docker; a pull falls back to mirror.gcr.io like replay_deep.py.
"""
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


def main():
    root, scan_dir, out_root = sys.argv[1:4]
    by_project = {}
    for rel in sys.argv[4:]:
        report = open(os.path.join(root, "projects", rel, "sanitizer_report.txt"), errors="replace").read()
        src = crashing_file(report)
        if not src:
            print(rel, "skipped (the report shows no project file crashing)", flush=True)
            continue
        dst = os.path.join(out_root, *rel.split("/vulnerabilities/"), os.path.basename(src))
        if not os.path.isfile(dst):
            by_project.setdefault(rel.split("/")[0], []).append((rel, src, dst))
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
        for rel, src, dst in tasks:
            got = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "tar", image,
                                  "-xOf", "/opt/src_snapshot.tar", src.lstrip("/")], capture_output=True)
            if got.returncode != 0 or not got.stdout:
                print(rel, "not in /opt/src_snapshot.tar: %s" % src, flush=True)
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(got.stdout)
            print(rel, "%s (%d bytes)" % (src, len(got.stdout)), flush=True)
        if os.environ.get("REPLAY_DEEP_KEEP_IMAGES") != "1":
            subprocess.run(["docker", "rmi", image], capture_output=True)


if __name__ == "__main__":
    main()
