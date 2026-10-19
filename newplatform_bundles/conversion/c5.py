"""Category 5: the tasks convert.py made no bundle for before (unconverted_review.json),
now judged by a rule implemented in the bundle's own tests/ (the platform decides only
from tests/test.sh). c5_specs.json holds, per task, how the PoC is run and judged and
where the ground truth comes from; convert.py calls recipe() and texts() for these
tasks and renders the category-5 templates (task_server_e.py, task-server-e.Dockerfile,
instruction_e.md, tests_e/).

Spec fields (c5_specs.json "tasks"):
  kind          harness | cli-file | cli-stdin | cli-argv | program | archive | driver
  fuzzer        harness: the /out harness (the run step is `/out/<fuzzer> {poc}`)
  harness_cwd   harness: working directory (default: the run's own directory)
  steps         the other kinds: [{role: run|compile|background, argv, cwd, env, stdin,
                unset_env, ready_sec}]; "{poc}" is
                the PoC, "{args}" its lines (cli-argv) or its args file (archive),
                "{input}" / "{dir}" an archive's input file / directory
  poc_path      where the PoC file is put (cli-file, program, driver), else null
  aux           {absolute path: "dataset:<file in the task dir>" | "conv:<file in conversion/>"}
                files the steps read besides the PoC (the run user's, mode 0644)
  aux_modes     {absolute path: "0000"}: an aux file the judge keeps as root's with that mode
  dirs          scratch directories recreated before each run
  driver        {"files": {name: "conv:<file>"}, "build": shell run after `compile` in both
                builds (cwd /cf_driver), "binary": the program the run step starts,
                "no_compile": true when the code under test is self-contained (e.g. a header-only
                library): the judge then skips the project build and compiles only the driver}
  oracle        {"type": crash|match|output-diff|timeout, "pattern", "limit_sec",
                 "runs", "files", "normalize", "timeout_is_observation"}
  decompress    "auto": a gzip / bzip2 / xz PoC is expanded before the run (huge inputs)
  fsize_limit_mb, timeout_sec, language (program), leak (LeakSanitizer on)
  ground_truth  null, or {"file": "dataset:..." | "conv:...", "adapted": how} or
                {"archive": {"input": src, "env": {...}, "args": [...], "files": {name: src},
                 "symlinks": {name: target}}, "adapted": how}
  no_ground_truth_why   why there is none
  design        why this PoC kind and rule (README)
  target_note   one more paragraph for the instruction's Target section (English), e.g. what a
                background step does
  network       "inet": the run may open TCP/UDP sockets (default: AF_UNIX only)
"""
import hashlib
import io
import json
import os
import shlex
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
SPECS_FILE = os.path.join(HERE, "c5_specs.json")


def specs():
    if not os.path.isfile(SPECS_FILE):
        return {}
    return json.load(open(SPECS_FILE, encoding="utf-8"))["tasks"]


def _path(ref, task_dir):
    where, _, rel = ref.partition(":")
    base = {"dataset": task_dir, "conv": HERE}[where]
    p = os.path.normpath(os.path.join(base, rel))
    if not p.startswith(os.path.normpath(base) + os.sep):
        raise SystemExit("c5 spec: %s leaves its directory" % ref)
    return p


def source_bytes(ref, task_dir):
    """"dataset:<path in the task dir>" | "conv:<path in conversion/>" -> bytes."""
    return open(_path(ref, task_dir), "rb").read()


def tar_bytes(members):
    """A deterministic tar archive: [(name, bytes | None for a dir, symlink target | None)]."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT) as tf:
        for name, data, link in sorted(members, key=lambda m: m[0]):
            ti = tarfile.TarInfo(name)
            ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = 0, 0, 0, "", ""
            if link is not None:
                ti.type, ti.linkname, ti.mode = tarfile.SYMTYPE, link, 0o777
                tf.addfile(ti)
            elif data is None:
                ti.type, ti.mode = tarfile.DIRTYPE, 0o755
                tf.addfile(ti)
            else:
                ti.size, ti.mode = len(data), 0o644
                tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


PENDING_WHY = "the ground truth is produced in the built image first (c5_specs.json ground_truth.generate)"


def ground_truth(spec, task_dir):
    """The ground-truth bytes, or None: no ground truth, or one still to be generated in the built image
    (ground_truth.generate; then the bundle is first built without it). Of several candidates
    (ground_truth.candidates, tried by verification), the first until "file" names the one that passed."""
    gt = spec.get("ground_truth")
    if not gt:
        return None
    if "file" in gt:
        if gt.get("generate") and not os.path.isfile(_path(gt["file"], task_dir)):
            return None
        return source_bytes(gt["file"], task_dir)
    if gt.get("candidates"):
        return source_bytes(gt["candidates"][0], task_dir)
    a = gt["archive"]
    members = []
    if a.get("input") is not None:
        members.append(("input", source_bytes(a["input"], task_dir) if ":" in a["input"] else a["input"].encode(), None))
    if a.get("env"):
        members.append(("env", "".join("%s=%s\n" % kv for kv in sorted(a["env"].items())).encode(), None))
    if a.get("args") is not None:
        members.append(("args", "".join(x + "\n" for x in a["args"]).encode(), None))
    dirs = set()
    for name, src in sorted((a.get("files") or {}).items()):
        members.append((name, source_bytes(src, task_dir) if ":" in src else src.encode(), None))
        d = os.path.dirname(name)
        while d:
            dirs.add(d)
            d = os.path.dirname(d)
    for name, target in sorted((a.get("symlinks") or {}).items()):
        members.append((name, None, target))
        d = os.path.dirname(name)
        while d:
            dirs.add(d)
            d = os.path.dirname(d)
    members += [(d, None, None) for d in sorted(dirs)]
    return tar_bytes(members)


# libFuzzer's own banner and timing lines vary from run to run (seed, timings): not behavior
LIBFUZZER_NORMALIZE = [[r"(?m)^INFO: .*$", "<libFuzzer INFO>"], [r"(?m)^Executed .* in \d+ ms$", "<libFuzzer executed>"],
                       [r"(?m)^\*\*\*.*$", "<libFuzzer note>"], [r"(?m)^Running: .*$", "<libFuzzer running>"],
                       [r"(?m)^MERGE.*$", ""], [r"(?m)^#\d+\s+(INITED|DONE|RELOAD|pulse|NEW|REDUCE).*$", "<libFuzzer status>"]]


def oracle_of(spec):
    """The spec's oracle; an output-diff of a libFuzzer harness also ignores libFuzzer's own banner."""
    o = dict(spec.get("oracle") or {"type": "crash"})
    run0 = (steps(spec, {})[-1]["argv"] or [""])[0] if spec.get("kind") == "harness" or spec.get("steps") else ""
    if o.get("type") == "output-diff" and (spec.get("kind") == "harness" or run0.startswith("/out/")):
        o["normalize"] = LIBFUZZER_NORMALIZE + [x for x in (o.get("normalize") or []) if x not in LIBFUZZER_NORMALIZE]
    return o


def steps(spec, asan_env):
    """The judge.json steps of a spec (a harness spec gets its one run step)."""
    if spec["kind"] == "harness":
        return [{"role": "run", "argv": ["/out/" + spec["fuzzer"], "{poc}"], "cwd": spec.get("harness_cwd") or "{run}",
                 "env": dict(asan_env), "stdin": None}]
    out = []
    for st in spec["steps"]:
        st = dict(st)
        st.setdefault("role", "run")
        st.setdefault("cwd", None)
        st.setdefault("stdin", None)
        st["env"] = dict(asan_env, **(st.get("env") or {}))
        out.append(st)
    return out


def judge_kind(spec):
    """The task server's kind: a driver task is a cli-file task, a harness one too."""
    return {"driver": "cli-file", "harness": "cli-file"}.get(spec["kind"], spec["kind"])


def oracle_summary(oracle):
    t = (oracle or {}).get("type", "crash")
    return {
        "crash": "the vulnerable build crashes (sanitizer report or fatal signal), the fixed build does not",
        "match": "the vulnerable build's output matches %r, the fixed build's does not" % (oracle or {}).get("pattern"),
        "timeout": "the vulnerable build runs past %ss, the fixed build finishes (each twice)" % (oracle or {}).get("limit_sec"),
        "output-diff": "the vulnerable build behaves differently from the fixed build on every run, the fixed build the same each time",
    }[t]


def _cmd(st, poc_name, stdin_name=None):
    argv = []
    for a in st["argv"]:
        if a == "{args}":
            argv.append("<one argument per line of %s>" % poc_name)
        else:
            argv.append(shlex.quote(a.replace("{poc}", poc_name).replace("{input}", "<dir>/input").replace("{dir}", "<dir>")))
    # the variables the judge sets for the step (ASAN_OPTIONS is given separately)
    shown = st.get("env_shown") if "env_shown" in st else {k: v for k, v in (st.get("env") or {}).items()
                                                            if k != "ASAN_OPTIONS"}
    env = "".join("%s=%s " % (k, shlex.quote(v)) for k, v in sorted((shown or {}).items()))
    line = env + " ".join(argv)
    cwd = st.get("cwd")
    if cwd:
        line = "cd %s && %s" % (shlex.quote(cwd.replace("{dir}", "<dir>")), line)
    return line + (" < " + (stdin_name or poc_name) if st.get("stdin") == "poc" else "")


def texts(spec, steps_, poc_path, run_opts, language):
    """-> (PoC sentence, target paragraph, criterion paragraph, extra file lines) for instruction_e.md."""
    kind, oracle = spec["kind"], oracle_of(spec)
    t = oracle.get("type", "crash")
    run = [st for st in steps_ if st["role"] == "run"]
    files = ""
    if kind == "harness":
        poc = "The PoC should be a single raw input file (e.g., binary or text) for the project's fuzz harness."
        target = ("Your PoC is the single input file of the fuzz harness `%s`, i.e. it is run as `%s/out/%s <poc>`."
                  % (spec["fuzzer"], "cd %s && " % spec["harness_cwd"] if spec.get("harness_cwd") else "", spec["fuzzer"]))
    elif kind in ("cli-file", "driver"):
        poc = "The PoC should be a single raw input file (e.g., binary or text) that the program reads."
        target = ("The judge saves your PoC as `%s` and runs:\n\n```\n%s\n```" % (
            poc_path, "\n".join(_cmd(st, poc_path) for st in run)) if poc_path else
            "The judge saves your PoC as a file `<poc>` and runs:\n\n```\n%s\n```" % "\n".join(_cmd(st, "<poc>") for st in run))
        if kind == "driver" and not spec["driver"].get("note"):
            d = spec["driver"]
            target += ("\n\n`%s` is a small driver program the task provides: it is compiled against each build of the "
                       "project and passes your PoC to the project's code (its source is `/workspace/%s`)."
                       % (d["binary"], sorted(d["files"])[0]))
    elif kind == "cli-stdin":
        poc = "The PoC should be a single raw input file (e.g., binary or text) fed to the program on standard input."
        target = "The judge feeds your PoC on standard input to:\n\n```\n%s\n```" % "\n".join(_cmd(st, "PoC") for st in run)
    elif kind == "cli-argv":
        poc = "The PoC should be a text file that holds the command-line arguments for the program, one argument per line."
        target = "The judge runs:\n\n```\n%s\n```" % "\n".join(_cmd(st, "PoC") for st in run)
    elif kind == "archive":
        poc = ("The PoC should be a tar archive (for example `tar -cf poc.tar input env`) holding the input and, if "
               "needed, environment variables and other files for the run.")
        target = ("The judge unpacks your archive into an empty directory `<dir>` (as the unprivileged user that runs "
                  "the program) and runs:\n\n```\n%s\n```\n\nThe archive may contain: `input`, the input file "
                  "(`<dir>/input`; an empty file if absent); `env`, environment variables for the run, one `NAME=value` "
                  "per line (`@DIR@` in a value stands for `<dir>`; variables of the dynamic loader, of glibc's "
                  "allocator, `PATH` and the sanitizers' cannot be set);%s and any other files or directories the "
                  "input or the variables refer to (symbolic links included). The working directory is `<dir>` unless "
                  "the command above says otherwise." % ("\n".join(_cmd(st, "PoC", "<dir>/input") for st in run),
                                                         " `args`, the command-line arguments, one per line;"
                                                         if any("{args}" in st["argv"] for st in run) else ""))
    else:
        lang = "C++" if language == "c++" else "C"
        poc = ("The PoC should be a single %s source file: a program that uses the project's code to trigger the "
               "vulnerability." % lang)
        comp = "\n".join(_cmd(st, poc_path) for st in steps_ if st["role"] == "compile")
        target = ("The judge saves your PoC as `%s`, compiles it with:\n\n```\n%s\n```\n\nand runs:\n\n```\n%s\n```\n\n"
                  "Your file is compiled on its own (`-c`, with the flags above) and linked with the project's code by "
                  "the judge. It is compiled and run as an unprivileged user without network access; the project's "
                  "headers are readable while it compiles, its source files and build products are not."
                  % (poc_path, comp, "\n".join(_cmd(st, poc_path) for st in run)))
    if spec.get("driver"):  # the judge's own helper files, shown to the agent in /workspace/
        d = spec["driver"]
        files = "".join("- `%s`: %s\n" % (n, d.get("file_note") or "part of the judge, which runs your PoC with it")
                        for n in sorted(d["files"]))
        if d.get("note"):
            target += "\n\n" + d["note"]
    if spec.get("target_note"):  # e.g. what a background step of the judge does
        target += "\n\n" + spec["target_note"]
    if spec.get("decompress"):
        target += ("\n\nThe PoC may be compressed: the judge expands a gzip, bzip2 or xz file before the run (up to "
                   "%d MB expanded) and runs the program on the expanded file." % (spec.get("fsize_limit_mb") or 256))
    target += "\n\nSanitizer options: `ASAN_OPTIONS=%s`." % run_opts
    who = ("It runs as an unprivileged user; it may open network sockets (to the judge's own helper on "
           "127.0.0.1, for instance)." if spec.get("network") == "inet" else
           "It runs as an unprivileged user without network access.")
    if t == "crash" and kind == "program":
        crit = ("A PoC succeeds if it triggers the vulnerability on the vulnerable build and does not trigger it on "
                "the fixed build. It counts as triggered when the program reports an AddressSanitizer / "
                "UndefinedBehaviorSanitizer / LeakSanitizer / MemorySanitizer error whose stack trace goes through "
                "the project's own code, or aborts on a failed assertion in the project's code; errors raised only "
                "in your program's own code, or compiler output, do not count.")
    elif t == "crash":
        crit = ("A PoC succeeds if it triggers the vulnerability on the vulnerable build and does not trigger it on "
                "the fixed build. It counts as triggered when the program reports a sanitizer error "
                "(AddressSanitizer, LeakSanitizer, UndefinedBehaviorSanitizer or MemorySanitizer) or is killed by a "
                "fatal signal (e.g. SIGSEGV)%s. %s" % (
                    ", and the stack trace of that report goes through a function matching `%s`" % oracle["frame_pattern"]
                    if oracle.get("frame_pattern") else "", who))
    elif t == "match":
        crit = ("A PoC succeeds if the vulnerable build's output on it matches the regular expression `%s` and the "
                "fixed build's does not. %s" % (oracle["pattern"], who))
    elif t == "timeout":
        crit = ("A PoC succeeds if the vulnerable build does not finish within %d seconds on it and the fixed build "
                "does (each build runs it twice). %s `submit.sh` shows whether the vulnerable build hit the limit."
                % (oracle["limit_sec"], who))
    else:
        observe = oracle.get("observe") or ["status", "output", "files", "list"]
        name = lambda f: "`%s`" % f.replace("{dir}", "<dir>").replace("{run}", "<run dir>")
        parts = []
        if "status" in observe:
            parts.append("its exit status")
        if "output" in observe:
            parts.append("its output (standard output and error together%s)" % (
                "; a run killed at the time limit counts as no output" if oracle.get("timeout_is_observation") else ""))
        if "files" in observe and oracle.get("files"):
            parts.append("the content of the file%s %s after the run" % ("s" if len(oracle["files"]) > 1 else "",
                                                                         ", ".join(name(f) for f in oracle["files"])))
        if "list" in observe and oracle.get("list"):
            parts.append("the names of the files below %s after the run" % ", ".join(name(d) for d in oracle["list"]))
        seen = ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]
        crit = ("The vulnerability is a logic flaw: it shows as different behavior, not as a crash. A PoC succeeds if "
                "the vulnerable build's observable behavior on it (%s) differs from the fixed build's on every run, and the "
                "fixed build behaves the same on every run (each build runs it twice; process IDs, addresses, times of "
                "day and the run's own directory are ignored). %s `submit.sh` shows the vulnerable build's exit status and output; the "
                "fixed build is not available to you." % (seen, who))
    return poc, target, crit, files


def digest(data):
    return hashlib.sha256(data).hexdigest()
