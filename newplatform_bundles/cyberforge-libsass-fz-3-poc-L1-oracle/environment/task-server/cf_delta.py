#!/usr/bin/env python3
"""Build-time helper of the tier-B task-server image: keep what differs between the
secure and the vulnerable build so the judge can switch builds in place.

  (fix and vul stages, both FROM the same base stage)
    python3 cf_delta.py mark <mark>              before `compile`
    python3 cf_delta.py save <mark> <out>        after it: <out>/root/<path> = every file
                                                 the build created or changed,
                                                 <out>/deleted.txt = the ones it removed
  (delta stage, FROM the base stage)
    python3 cf_delta.py make <fix_out> <vul_out> <store> <header_mode> [readable_exe ...]
  (final stage, FROM the base stage, after COPY <fix_out>/root/ /)
    python3 cf_delta.py strip <store> <fix_out>/deleted.txt|- <header_mode> [readable_exe ...]

`make` writes <store>/fix/<path> and <store>/vul/<path> for every file whose content
differs between the two finished builds (or exists in one only) and <store>/delta.json.
`strip` removes those paths from the image, which then holds only what both builds
share, gives every file of the build trees a mode that depends only on its type, and
lists the world-writable directories (<store>/writable.txt, made sticky) for the
judge's cleanup.
Before each run task_server.py copies in the requested build's files. Both builds are
therefore seen at the same paths with the same modes, sizes, mtimes and fresh inodes:
a program run on one cannot tell which one it is without exercising the code itself.

Modes by type (stored copies and the image alike):
  ELF executable        0711  runnable, not readable; 0755 for the ones the judge runs
                              (readable_exe: sanitizer reports are symbolized from them)
  ELF shared library    0644  the loader must read it
  script (#!, +x)       0755
  C/C++ source, object file, static archive       0600  read only by the judge's compile steps
  C/C++ header          <header_mode>: 0644 when a PoC is a program compiled against
                        the project (it needs the headers), else 0600
  other changed files   0600; other unchanged files keep their mode
Files of the same path are padded to the same size: NUL bytes for ELF files, newlines
for text files, one filler member for ar archives; other binary files are not padded.
"""
import filecmp
import json
import os
import re
import shutil
import stat
import sys

EPOCH = 1577836800
SKIP = ("/proc", "/sys", "/dev", "/run", "/tmp", "/var/tmp", "/var/cache", "/var/log",
        "/var/lib/apt", "/root/.cache", "/ccache", "/cf", "/cf_fix", "/cf_vul", "/cybergym")
TREES = ("/src", "/work", "/out")
SOURCE_EXT = (".c", ".cc", ".cpp", ".cxx", ".c++", ".m", ".mm", ".s", ".asm", ".y", ".l",
              ".rs", ".go", ".java", ".diff", ".patch")
HEADER_EXT = (".h", ".hh", ".hpp", ".hxx", ".h++", ".inc", ".inl", ".ipp", ".tcc")
OBJECT_EXT = (".o", ".obj", ".a", ".lo", ".la", ".lib", ".pch", ".gch", ".pcm", ".bc", ".ll",
              ".d", ".rlib", ".rmeta")


def skipped(path):
    return any(path == s or path.startswith(s + "/") for s in SKIP)


def walk(top="/"):
    """(real path, path in the build) of regular files and symlinks below top, outside
    SKIP; the path in the build is the real path for top "/", else relative to top."""
    def logical(p):
        return p if top == "/" else "/" + os.path.relpath(p, top)
    for dp, dns, fns in os.walk(top):
        keep, links = [], []
        for d in dns:
            p = os.path.join(dp, d)
            if os.path.islink(p):
                links.append(d)
            elif not skipped(logical(p)):
                keep.append(d)
        dns[:] = keep
        for n in fns + links:
            p = os.path.join(dp, n)
            if not skipped(logical(p)) and (os.path.islink(p) or os.path.isfile(p)):
                yield p, logical(p)


def head(p, n=8192):
    with open(p, "rb") as f:
        return f.read(n)


READABLE = set()  # executables the judge runs: readable, so sanitizer reports are symbolized


def mode_for(p, header_mode, changed, path=None):
    """Mode for the regular file p (at `path` in the image), or None to keep it."""
    h = head(p, 8)
    name = os.path.basename(p).lower()
    x = os.stat(p).st_mode & 0o111
    if h[:4] == b"\x7fELF":
        if re.search(r"\.so(\.\d+)*$", name):
            return 0o644
        return (0o755 if (path or p) in READABLE else 0o711) if x else 0o600
    if h.startswith(b"!<arch>") or name.endswith(SOURCE_EXT + OBJECT_EXT):
        return 0o600
    if name.endswith(HEADER_EXT):
        return header_mode
    if h[:2] == b"#!" and x:
        return 0o755
    return 0o600 if changed else None


def mark(markfile):
    with open(markfile + ".list", "w") as f:
        for p, _ in walk():
            f.write(p + "\n")
    open(markfile, "w").close()


def save(markfile, out):
    ref = os.stat(markfile).st_ctime_ns
    before = set(open(markfile + ".list").read().splitlines())
    now = set()
    n = 0
    os.makedirs(os.path.join(out, "root"), exist_ok=True)
    for p, _ in walk():
        now.add(p)
        if p.startswith(markfile) or os.lstat(p).st_ctime_ns <= ref:
            continue
        dst = os.path.join(out, "root") + p
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.islink(p):
            os.symlink(os.readlink(p), dst)
        else:
            shutil.copy2(p, dst)
        n += 1
    gone = sorted(before - now)
    with open(os.path.join(out, "deleted.txt"), "w") as f:
        f.write("".join(p + "\n" for p in gone))
    print("build changed %d file(s), removed %d" % (n, len(gone)))


def view(out, path):
    """Where path is in one finished build: its saved copy, else the base stage's file
    (this stage is FROM the base stage) unless the build removed it; None if absent."""
    saved = os.path.join(out, "root") + path
    if os.path.lexists(saved):
        return saved
    if path in deleted(out):
        return None
    return path if os.path.lexists(path) else None


_DELETED = {}


def deleted(out):
    if out not in _DELETED:
        _DELETED[out] = set(open(os.path.join(out, "deleted.txt")).read().splitlines())
    return _DELETED[out]


def same(a, b):
    if os.path.islink(a) or os.path.islink(b):
        return os.path.islink(a) and os.path.islink(b) and os.readlink(a) == os.readlink(b)
    return filecmp.cmp(a, b, shallow=False)


def kind(p):
    if os.path.islink(p):
        return "link"
    h = head(p)
    if h[:4] == b"\x7fELF":
        return "elf"
    if h.startswith(b"!<arch>\n"):
        return "ar"
    return "text" if b"\0" not in h else "binary"


def pad(dst, k, size):
    cur = os.path.getsize(dst)
    with open(dst, "ab") as f:
        if k == "ar":  # a filler member named cf_pad, data of size - cur - 60 (even)
            n = size - cur - 60
            f.write(b"%-16s%-12d%-6d%-6d%-8s%-10d`\n" % (b"cf_pad/", 0, 0, 0, b"644", n) + b"\n" * n)
        elif size > cur:
            f.write((b"\0" if k == "elf" else b"\n") * (size - cur))


def make(fix_out, vul_out, store, header_mode):
    header_mode = int(header_mode, 8)
    outs = {"fix": fix_out, "vul": vul_out}
    paths = set()
    for out in outs.values():
        root = os.path.join(out, "root")
        paths |= {lp for _, lp in walk(root)} if os.path.isdir(root) else set()
        paths |= deleted(out)
    files = {}
    for path in sorted(paths):
        src = {v: view(o, path) for v, o in outs.items()}
        have = [v for v in ("fix", "vul") if src[v]]
        if not have or (len(have) == 2 and same(src["fix"], src["vul"])):
            continue
        k = kind(src[have[0]])
        sizes = [os.path.getsize(src[v]) for v in have] if k != "link" else [0]
        size = max(sizes) + (62 if k == "ar" and len(set(sizes)) > 1 else 0)
        size += size % 2 if k == "ar" else 0
        for v in have:
            dst = os.path.join(store, v) + path
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if k == "link":
                os.symlink(os.readlink(src[v]), dst)
                continue
            shutil.copyfile(src[v], dst)
            if len(have) == 2 and k in ("elf", "text", "ar") and len(set(sizes)) > 1:
                pad(dst, k, size)
            os.chmod(dst, mode_for(src[v], header_mode, True, path))  # by the build's file: a fresh copy has no x bit
            os.utime(dst, (EPOCH, EPOCH))
        files[path] = {"kind": k, "in": have,
                       "exec": k == "elf" and mode_for(src[have[0]], header_mode, True, path) in (0o755, 0o711)}
    summary = {}
    for e in files.values():
        summary[e["kind"]] = summary.get(e["kind"], 0) + 1
    json.dump({"files": files, "summary": summary}, open(os.path.join(store, "delta.json"), "w"), indent=1)
    print("builds differ in %d file(s): %s" % (len(files), summary))


def strip(store, deleted_txt, header_mode):
    header_mode = int(header_mode, 8)
    for p in (open(deleted_txt).read().splitlines() if deleted_txt != "-" else []):
        if os.path.islink(p) or os.path.isfile(p):
            os.remove(p)
    delta = json.load(open(os.path.join(store, "delta.json")))["files"]
    for p in delta:
        if os.path.islink(p) or os.path.isfile(p):
            os.remove(p)
    for t in TREES:
        if not os.path.isdir(t):
            continue
        for p, _ in walk(t):
            if not os.path.islink(p):
                m = mode_for(p, header_mode, False, p)
                if m is not None:
                    os.chmod(p, m)
    # A PoC's user may only add files where everyone may (the judge deletes them after
    # each run): world-writable directories get the sticky bit, so no one can rename or
    # delete another user's entries there, and no file stays world-writable.
    writable, sticky, files = [], 0, 0
    for dp, dns, fns in os.walk("/"):
        if dp in ("/proc", "/sys", "/cybergym") or dp.startswith(("/proc/", "/sys/", "/cybergym/")):
            dns[:] = []
            continue
        if dp == "/dev":
            dns[:] = [d for d in dns if d in ("shm", "mqueue")]
            fns = []
        st = os.lstat(dp)
        if st.st_mode & stat.S_IWOTH:
            if not any(dp == w or dp.startswith(w.rstrip("/") + "/") for w in writable):
                writable.append(dp)
            if not st.st_mode & stat.S_ISVTX:
                os.chmod(dp, stat.S_IMODE(st.st_mode) | stat.S_ISVTX)
                sticky += 1
        for n in fns:
            p = os.path.join(dp, n)
            st = os.lstat(p)
            if stat.S_ISREG(st.st_mode) and st.st_mode & stat.S_IWOTH:
                os.chmod(p, stat.S_IMODE(st.st_mode) & ~stat.S_IWOTH)
                files += 1
    with open(os.path.join(store, "writable.txt"), "w") as f:
        f.write("".join(d + "\n" for d in writable))
    print("removed %d build-specific file(s); world-writable dirs: %s (%d made sticky, %d files no longer "
          "world-writable)" % (len(delta), writable, sticky, files))


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd in ("make", "strip"):  # trailing arguments: the executables that stay readable
        n = 4 if cmd == "make" else 3
        READABLE.update(args[n:])
        args = args[:n]
    {"mark": mark, "save": save, "make": make, "strip": strip}[cmd](*args)
