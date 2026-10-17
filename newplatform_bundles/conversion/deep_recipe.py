"""Turn a replay_deep.py recording (calls.json) into a runnable recipe.

recipe(task_dir) -> None, or a dict:
  kind       "harness" | "cli-file" | "cli-stdin" | "cli-argv" | "program"
  gt         ground-truth bytes (the input / argument list / source the exploit used)
  gt_file    (harness) the saved file holding gt
  generated  (harness, cli) the input was made by a program the exploit built and ran first
  fuzzer     (harness) the /out harness name
  steps      [{role: compile|run, argv: [...], cwd, env, stdin: "poc"|None}]; "{poc}" marks
             the PoC path in argv, "{args}" the PoC's lines (cli-argv)
  poc_path   absolute path the PoC is put at (cli-file, program)
  aux        {absolute path: saved file name} other files the exploit had made
  dirs       scratch directories to recreate before a run
  language   (program) "c" | "c++"
  why        (None result only, via recipe_or_reason) what made it unusable
Only unambiguous recordings give a recipe: one harness input, one CLI invocation, or
compile steps plus one run of the program they built. Programs the exploit built and
ran before feeding a harness or CLI only made that input and are left out.
"""
import hashlib
import json
import os
import re

SYSTEM = ("/src/", "/usr/", "/out/", "/opt/", "/lib", "/bin/", "/etc/", "/proc/", "/dev/", "/work/")
SOURCE_EXT = (".c", ".cc", ".cpp", ".cxx", ".C", ".c++")
SCRATCH = ("/tmp/", "/workspace/", "/exploit")


def _abs(path, cwd):
    return os.path.normpath(path if path.startswith("/") else os.path.join(cwd or "/", path))


LIMIT = 16 << 20  # replay_deep.py runs exploits under `ulimit -f` 16 MiB
PRUNED = b"CF-PRUNED "  # a large capture of an unconverted task, replaced by its hash and size


class Truncated(Exception):
    pass


def _saved(d, name, digest=False):
    """A file the recorder saved: its bytes, or (digest=True) its sha256. A file of the
    replay's size limit was cut off by it, so it is not what the exploit made."""
    data = open(os.path.join(d, name), "rb").read()
    if data.startswith(PRUNED):
        if not digest:
            raise Truncated(name)
        return data.split()[1].decode()
    if len(data) >= LIMIT:
        raise Truncated(name)
    return hashlib.sha256(data).hexdigest() if digest else data


BUILD_TREES = ("/src/", "/work/", "/out/", "/usr/local/")
URL_RE = re.compile(r"\b(https?|ftp)://|\blocalhost\b|\b127\.0\.0\.1\b")


def _mkdir_names(exploit_sh):
    """Basenames of the directories exploit.sh creates (literal or through simple variables)."""
    vals = dict(re.findall(r"^\s*(?:export\s+|local\s+)?([A-Za-z_]\w*)=[\"']?([^\"'\s;]+)", exploit_sh, re.M))
    names = set()
    for line in re.findall(r"\bmkdir\b([^\n;&|]*)", exploit_sh):
        for tok in line.split():
            tok = tok.strip("\"'")
            m = re.fullmatch(r"\$\{?(\w+)\}?(/.*)?", tok)
            if m:
                tok = vals.get(m.group(1), "") + (m.group(2) or "")
            if tok and not tok.startswith("-"):
                names.add(os.path.basename(tok.rstrip("/")))
    return names


def _outside_heredocs(sh):
    """exploit.sh without the bodies of its here-documents (where it writes its sources)."""
    out, end = [], None
    for line in sh.splitlines():
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        out.append(line)
        m = re.search(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?", line)
        if m:
            end = m.group(1)
    return "\n".join(out)


def recipe_or_reason(task_dir, exploit_sh="", exploit_files=()):
    """exploit_sh: the task's exploit.sh text; exploit_files: names in its exploit_files/."""
    try:
        return _recipe(task_dir, exploit_sh, set(exploit_files))
    except Truncated:
        return None, "the exploit's input is larger than 16 MB (the replay cut it off)"


def _recipe(task_dir, exploit_sh, exploit_files):
    f = os.path.join(task_dir, "calls.json")
    if not os.path.isfile(f):
        return None, "not replayed in the project image"
    calls = [c for c in json.load(open(f)) if c["kind"] != "build"]
    if not calls:
        return None, "the exploit ran no program the replay could record"
    generated = False
    prog = [i for i, c in enumerate(calls) if c["kind"] in ("cc", "driver")]
    target = [i for i, c in enumerate(calls) if c["kind"] in ("harness", "cli")]
    if prog and target:
        if max(prog) > min(target):
            return None, "the exploit mixes %s calls" % "/".join(sorted({c["kind"] for c in calls}))
        # the exploit's own programs only ran first, to make the input it then feeds
        calls, generated = [calls[i] for i in target], True
    kinds = {c["kind"] for c in calls}

    if kinds == {"harness"}:
        inputs = {}
        for c in calls:
            for i, name in sorted(c["files"].items(), key=lambda kv: int(kv[0])):
                try:
                    inputs.setdefault(_saved(task_dir, name, digest=True), (os.path.basename(c["path"]), name))
                except Truncated:
                    return None, "the exploit's input is larger than 16 MB (the replay cut it off)"
        if len(inputs) != 1:
            return None, "the exploit fed its harness %d different inputs" % len(inputs)
        fuzzer, name = next(iter(inputs.values()))
        try:
            data = _saved(task_dir, name)
        except Truncated:
            return None, "the exploit's input is larger than 16 MB (the replay cut it off)"
        return {"kind": "harness", "fuzzer": fuzzer, "gt": data, "gt_file": name, "generated": generated}, None

    if kinds == {"cli"}:
        try:
            distinct = {json.dumps([c["path"], c["argv"], c["stdin"] and _saved(task_dir, c["stdin"], digest=True),
                                    {k: _saved(task_dir, v, digest=True) for k, v in c["files"].items()}])
                        for c in calls}
        except Truncated:
            return None, "the exploit's input is larger than 16 MB (the replay cut it off)"
        if len(distinct) != 1:
            return None, "the exploit ran its CLI %d different ways" % len(distinct)
        c = calls[0]
        if not _abs(c["path"], c["cwd"]).startswith(BUILD_TREES):
            return None, "the program the exploit ran is a copy outside the build tree"
        if any(URL_RE.search(a) for a in c["argv"]):
            return None, "the exploit points its CLI at a server it started (no network for the judge)"
        if c["argv"] and all(a.startswith("--gtest_") for a in c["argv"]):
            return None, "the exploit selects one of the project's unit tests (no PoC input)"
        argv = [c["path"]] + list(c["argv"])
        step = {"role": "run", "argv": argv, "cwd": c["cwd"], "env": c["env"], "stdin": None}
        files = sorted(c["files"].items(), key=lambda kv: int(kv[0]))
        made = _mkdir_names(exploit_sh)
        dirs = {c["cwd"]} if c["cwd"].startswith(SCRATCH) else set()
        for i, a in enumerate(c["argv"]):  # directories the exploit made and names on the command line
            p = _abs(a.split("=", 1)[-1], c["cwd"]) if "/" in a else ""
            if p.startswith(SCRATCH) and str(i) not in c["files"] and os.path.basename(p) in made:
                dirs.add(p)
        out = {"steps": [step], "aux": {}, "generated": generated, "dirs": sorted(dirs)}
        if files:
            idx, name = files[-1]  # the last file argument is the input; earlier ones are aux
            poc_abs = _abs(c["argv"][int(idx)].split("=", 1)[-1], c["cwd"])
            if not poc_abs.startswith(SCRATCH):
                return None, "the exploit's input is a file of the project tree, not one it made"
            for i, n in files[:-1]:
                out["aux"][_abs(c["argv"][int(i)].split("=", 1)[-1], c["cwd"])] = n
            a = c["argv"][int(idx)]
            argv[int(idx) + 1] = a[:a.index("=") + 1] + "{poc}" if a.startswith("-") and "=" in a else "{poc}"
            if not _saved(task_dir, name):
                return None, "the exploit's input file is empty (its trigger is on the command line)"
            out.update(kind="cli-file", gt=_saved(task_dir, name), poc_path=poc_abs)
            out["dirs"] = sorted(set(out["dirs"]) | {os.path.dirname(p) for p in [poc_abs, *out["aux"]]
                                                       if p.startswith(SCRATCH)})
            return out, None
        if c["stdin"]:
            step["stdin"] = "poc"
            out.update(kind="cli-stdin", gt=_saved(task_dir, c["stdin"]), poc_path=None)
            return out, None
        if not c["argv"]:
            return None, "the exploit runs a project program without input (nothing for a PoC to supply)"
        if any("\n" in a for a in c["argv"]):
            return None, "an argument contains a newline"
        step["argv"] = [c["path"], "{args}"]
        out.update(kind="cli-argv", gt="".join(a + "\n" for a in c["argv"]).encode(), poc_path=None)
        return out, None

    if kinds == {"cc", "driver"}:
        drivers = [c for c in calls if c["kind"] == "driver"]
        if len({json.dumps([d["path"], d["argv"]]) for d in drivers}) != 1:
            return None, "the exploit ran its compiled program %d different ways" % len(drivers)
        drv = drivers[0]
        drv_abs = _abs(drv["path"], drv["cwd"])
        ccs = [c for c in calls if c["kind"] == "cc"]
        outputs = set()
        srcs = {}
        for c in ccs:
            if "-o" in c["argv"]:
                outputs.add(_abs(c["argv"][c["argv"].index("-o") + 1], c["cwd"]))
            for i, name in c["files"].items():
                p = _abs(c["argv"][int(i)], c["cwd"])
                if p.endswith(SOURCE_EXT) and not p.startswith(SYSTEM):
                    srcs[p] = name
        if drv_abs not in outputs:
            return None, "the program that was run is not one the compile steps produced"
        cands = list(srcs)
        if len(cands) > 1:
            cands = [p for p in cands if re.search(rb"\bmain\s*\(", _saved(task_dir, srcs[p]))]
        if len(cands) != 1:
            return None, "%d candidate PoC source files" % len(srcs)
        poc_abs = cands[0]
        if not poc_abs.startswith(SCRATCH):
            return None, "the exploit's program source is not a file it made"
        if re.search(rb'^\s*#\s*include\s*["<][^">]*\.(c|cc|cpp|cxx)[">]', _saved(task_dir, srcs[poc_abs]), re.M):
            # the judge keeps the project's sources unreadable to a PoV (they differ between the builds)
            return None, "the exploit's program #includes project source files"
        src_text = _saved(task_dir, srcs[poc_abs])
        named = {os.path.basename(m.decode("utf-8", "replace")) for m in
                 re.findall(rb'"((?:/tmp/|/workspace/|/exploit)[^"\n]*)"', src_text) +
                 re.findall(rb'\bf?open\s*\(\s*"([^"/\n][^"\n]*)"', src_text)}
        named.discard(os.path.basename(poc_abs))
        script = _outside_heredocs(exploit_sh)
        if any(n and (n in exploit_files or re.search(r"(^|[^\w.-])%s($|[^\w.-])" % re.escape(n), script))
               for n in named):
            # a file the exploit shipped or wrote: the recording only has files named on command lines
            return None, "the exploit's program reads a file the exploit made"
        if not any(re.search(r"(^|[=I L])/(src|work|out|usr/local/(lib|include))/", a) for c in ccs for a in c["argv"]) \
                and not any(c["cwd"].startswith(("/src/", "/work/")) for c in ccs):
            return None, "the exploit's program does not build against the project's code"
        if any(not _abs(drv["argv"][int(i)], drv["cwd"]).startswith(SYSTEM) for i in drv["files"]):
            # its payload would be a judge-side file a submitted program could read
            return None, "the exploit's program reads input files the exploit made"
        steps, aux = [], {}
        for c in ccs:
            argv = [c["path"]] + [("{poc}" if _abs(a, c["cwd"]) == poc_abs else a) for a in c["argv"]]
            steps.append({"role": "compile", "argv": argv, "cwd": c["cwd"], "env": c["env"], "stdin": None})
            for i, name in c["files"].items():
                p = _abs(c["argv"][int(i)], c["cwd"])
                if p != poc_abs and p not in outputs and not p.startswith(SYSTEM):
                    aux[p] = name
        run_argv = [drv_abs] + list(drv["argv"])
        steps.append({"role": "run", "argv": run_argv, "cwd": drv["cwd"], "env": drv["env"], "stdin": None})
        dirs = {c["cwd"] for c in ccs + [drv]} | {os.path.dirname(p) for p in [poc_abs, *aux]}
        cpp = poc_abs.endswith((".cc", ".cpp", ".cxx", ".C", ".c++"))
        return {"kind": "program", "gt": _saved(task_dir, srcs[poc_abs]), "steps": steps, "aux": aux,
                "poc_path": poc_abs, "dirs": sorted(d for d in dirs if d.startswith(SCRATCH)),
                "language": "c++" if cpp else "c"}, None

    if kinds == {"cc"}:
        return None, "the exploit compiled code but ran no program the replay recorded"
    return None, "the exploit mixes %s calls" % "/".join(sorted(kinds))
