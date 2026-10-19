#!/usr/bin/env python3
"""Restore the contents of Git LFS pointer files in the dataset copy, where they can be found.

    python3 -I lfs_restore.py <inner_root> lfs_objects/ <resolved_root> [snapshot_scan/]

3937 files of the dataset copy are Git LFS pointers ("version https://git-lfs.github.com/spec/v1",
"oid sha256:<hex>", "size <n>"), not the files themselves. They come from the dataset's
origin, github.com/Cyb3rForge/CyberForge-projects, whose FZ tasks were committed (af0e78d)
with 6749 such pointers as plain files (it never tracked anything with LFS); the team that
prepared this copy replaced 2812 of them with same-named files of other tasks (16 of those
do not have the pointer's SHA-256: serenity's gsub_tail_*.bin), see upstream_comparison.md.
A pointer names its content by SHA-256, so a file found elsewhere is the original only
when its SHA-256 is the pointer's oid. Sources, in order:
- lfs_objects/<oid> (objects found before, or supplied from the dataset's origin: two came
  from files the origin's pre-release branch cyberforge_full_data still has);
- another file of the dataset with that SHA-256 (the same seed shipped in another task);
- with snapshot_scan/: a member of a harness's built-in seed corpus that the dataset's
  records name for the pointer's file (crash_report.json seed_provenance, or the
  generated_input_records of verification_result.json: provenance builtin_corpus_member,
  source_name), read from /out/<fuzzer>_seed_corpus.zip in the project's pinned image.
Found objects are written to lfs_objects/<oid>. <resolved_root> is then made as a copy of
<inner_root> (hard links) in which every pointer whose object is known is replaced by its
content; the rest stay pointers. lfs_objects/missing.json lists the pointers left, by
task. The dataset itself is not changed. Pulls fall back to mirror.gcr.io.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

PTR_RE = re.compile(rb"^version https://git-lfs\.github\.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize (\d+)\n$")


def pointer(path):
    """(oid, size) when the file is an LFS pointer, else None."""
    try:
        if os.path.getsize(path) > 200:
            return None
        m = PTR_RE.match(open(path, "rb").read())
    except OSError:
        return None
    return (m.group(1).decode(), int(m.group(2))) if m else None


def corpus_members(vd):
    """{file name under exploit_files/: (fuzzer, archive member)} for built-in corpus seeds."""
    out = {}
    try:
        c = json.load(open(os.path.join(vd, "exploit_files", "fuzz_results", "vulnerable", "crash_report.json")))
        sp = c.get("seed_provenance") or {}
        if sp.get("provenance") == "builtin_corpus_member" and sp.get("archive_member") and c.get("fuzzer"):
            out["generated_inputs/" + (c.get("seed") or sp.get("name"))] = (c["fuzzer"], sp["archive_member"])
    except (OSError, ValueError):
        pass
    try:
        v = json.load(open(os.path.join(vd, "verification_result.json")))
        md = v.get("metadata") or {}
        fz = md.get("selected_fuzzer")
        for rec in md.get("generated_input_records") or []:
            if rec.get("provenance") == "builtin_corpus_member" and rec.get("source_name") and fz:
                out.setdefault("generated_inputs/" + rec["name"], (fz, rec["source_name"]))
    except (OSError, ValueError):
        pass
    return out


def main():
    root, store, resolved = sys.argv[1:4]
    scan_dir = sys.argv[4] if len(sys.argv) > 4 else ""
    os.makedirs(store, exist_ok=True)
    ptrs, real = [], {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            pt = pointer(p)
            if pt:
                ptrs.append((p, pt[0], pt[1]))
            elif os.path.getsize(p) <= 64 << 20:
                real.setdefault(hashlib.sha256(open(p, "rb").read()).hexdigest(), p)
    have = lambda oid: os.path.isfile(os.path.join(store, oid))
    got = {"store": 0, "dataset copy": 0, "seed corpus": 0}
    for p, oid, size in ptrs:
        if have(oid):
            got["store"] += 1
        elif oid in real:
            shutil.copyfile(real[oid], os.path.join(store, oid))
            got["dataset copy"] += 1
    # built-in corpus members, one image per project
    if scan_dir:
        want = {}
        for p, oid, size in ptrs:
            if have(oid):
                continue
            m = re.match(r"(.*/projects/([^/]+)/vulnerabilities/[^/]+)/exploit_files/(.*)$", p)
            if not m:
                continue
            fz_member = corpus_members(m.group(1)).get(m.group(3))
            if fz_member:
                want.setdefault(m.group(2), {})[oid] = fz_member
        for project, objs in sorted(want.items()):
            sf = os.path.join(scan_dir, project + ".json")
            if not os.path.isfile(sf):
                continue
            scan = json.load(open(sf))
            image = "%s@%s" % (scan["image"], scan["digest"])
            for ref in (image, "mirror.gcr.io/" + image):
                if subprocess.run(["docker", "pull", "-q", ref], capture_output=True).returncode == 0:
                    image = ref
                    break
            else:
                print(project, "pull failed; %d objects not looked up" % len(objs), flush=True)
                continue
            for oid, (fz, member) in sorted(objs.items()):
                r = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python3", image, "-c",
                                    "import sys, zipfile; sys.stdout.buffer.write(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]))",
                                    "/out/%s_seed_corpus.zip" % fz, member], capture_output=True)
                if r.returncode == 0 and hashlib.sha256(r.stdout).hexdigest() == oid:
                    open(os.path.join(store, oid), "wb").write(r.stdout)
                    got["seed corpus"] += 1
            if os.environ.get("REPLAY_DEEP_KEEP_IMAGES") != "1":
                subprocess.run(["docker", "rmi", image], capture_output=True)
    # the resolved copy
    if os.path.isdir(resolved):
        shutil.rmtree(resolved)
    shutil.copytree(root, resolved, copy_function=os.link)
    missing, restored = {}, 0
    for p, oid, size in ptrs:
        dst = os.path.join(resolved, os.path.relpath(p, root))
        if have(oid):
            os.remove(dst)
            shutil.copyfile(os.path.join(store, oid), dst)
            restored += 1
        else:
            m = re.match(r".*/projects/([^/]+/vulnerabilities/[^/]+)/(.*)$", p)
            key = m.group(1) if m else os.path.relpath(p, root)
            missing.setdefault(key, []).append({"file": m.group(2) if m else "", "oid": oid, "size": size})
    json.dump({"_about": "Git LFS pointers of the dataset copy whose content was not found (lfs_restore.py)",
               "pointers": len(ptrs), "restored": restored, "missing_objects": len({o for v in missing.values() for o in
                                                                                    [x["oid"] for x in v]}),
               "tasks": dict(sorted(missing.items()))}, open(os.path.join(store, "missing.json"), "w"), indent=1)
    print("pointers %d, restored %d (%s), still pointers %d" % (
        len(ptrs), restored, ", ".join("%s %d" % kv for kv in got.items()), len(ptrs) - restored))


if __name__ == "__main__":
    main()
