#!/usr/bin/env python3
"""instruction.md without the name of the project.

An agent that is told which project it works on can look the bug up by that name instead of
finding it, so no instruction.md names the project: convert.py passes each one through hide(),
validate.py checks the result with named().

A name is the project's own (records.json "project", e.g. `brotli`, `c-blosc2`) or that of its
source directory (`target_dir`, e.g. `ghostpdl`, `lighttpd1.4`), in any capitalisation and with
`-`, `_` or nothing between its parts. It counts as a word of its own anywhere (`H3 indices`,
`cJSON_Parse`, `JQ_COLORS`, `/src/brotli`, `libpng_read_fuzzer`) and inside a word of a command,
path or file name (`pcre2test`, `libh3.a`, `-lsimdjson`). The code's own abbreviations and
prefixes (`png_`, `hb-`, `blosc2_`) are not the project's name and stay.

hide() writes `<project>` for each name and says once, where the instruction lists
repo-vul.tar.gz, that `<project>` stands for the name of the directory the source unpacks to, so
every command, path and harness name stays exact. The source still shows the name (and the
dataset's descriptions often do; neither is the conversion's to change), but nothing the conversion
writes for the agent hands it over: see also hide_in_comments() and SKILL.md.
"""
import os
import re

PLACEHOLDER = "<project>"
# names that are also words of the instruction's own text: only a path component counts (`/src/file`)
WORDS = {"file"}
# never a name: tar's options (`tar -xzf`, project xz)
NOT_NAMES = re.compile(r"-xzf\b")
UNPACK = "(it unpacks to `%s/`)"
MARK = "\0unpack\0"


def norm(s):
    return re.sub(r"[-_]", "", s).lower()


def spellings(project, target_dir):
    """A name as written, and with `-`, `_` or nothing between its parts (longest first)."""
    out = set()
    for n in (project, target_dir):
        parts = [p for p in re.split(r"[-_]", n) if p]
        out |= {n, "-".join(parts), "_".join(parts), "".join(parts)}
    return sorted(out, key=lambda s: (-len(s), s))


def code_mask(text):
    """For each character: whether it is inside a fenced code block or an inline `code` span."""
    mask = [False] * len(text)
    for m in re.finditer(r"(?ms)^```[^\n]*\n.*?^```[ \t]*$|`[^`\n]+`", text):
        for i in range(m.start(), m.end()):
            mask[i] = True
    return mask


def _matches(text, project, target_dir):
    """(start, end, spelling) of each name in text."""
    alts = [(r"(?<=/)%s(?![A-Za-z0-9])" if s.lower() in WORDS else "%s") % re.escape(s)
            for s in spellings(project, target_dir)]
    mask = code_mask(text)
    blocked = [m.span() for m in NOT_NAMES.finditer(text)]
    out = []
    for m in re.finditer("|".join(alts), text, re.I):
        a, b = m.span()
        if any(x < b and a < y for x, y in blocked):
            continue
        inside_word = (a > 0 and text[a - 1].isalnum()) or (b < len(text) and text[b].isalnum())
        if inside_word and not mask[a]:  # a word of the prose that merely contains the name
            continue
        out.append((a, b, m.group(0)))
    return out


def named(text, project, target_dir):
    """The names of the project left in text (validate.py)."""
    return [s for _, _, s in _matches(text, project, target_dir)]


# The category-5 drivers (c5/drivers/) are shown to the agent in /workspace/. Their code calls the
# project's own API (`cJSON_Parse`, `#include "cJSON.h"`) and stays as it is; what the conversion
# wrote around it, the comments, names the project and the dataset task ("Driver of the CyberForge
# task cjson WF_LLM_4", "projects/h3/setup/build.sh"). hide_in_comments() rewrites only the comments
# of the agent's copy, line for line, so its code and line numbers are the judge's.
TASK_ID = r"(?:FZ|WF_RAG|WF_LLM)_\d+"
TASK_IDS = r"%s(?:(?:, | and )%s)*" % (TASK_ID, TASK_ID)


def comment_spans(text, name):
    """(start, end) of each comment of a C/C++, Python or Ruby source; a Python triple-quoted
    string (the drivers' docstrings) counts as a comment. Strings and characters are skipped."""
    ext = os.path.splitext(name)[1].lower()
    c_like = ext in (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp")
    if not c_like and ext not in (".py", ".rb"):
        raise ValueError("no comment syntax known for %s" % name)
    spans, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if c_like and text.startswith("//", i) or not c_like and ch == "#":
            j = text.find("\n", i)
            j = n if j < 0 else j
            spans.append((i, j))
            i = j
        elif c_like and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            spans.append((i, j))
            i = j
        elif ext == ".py" and text.startswith(('"""', "'''"), i):
            q = text[i:i + 3]
            j = text.find(q, i + 3)
            j = n if j < 0 else j + 3
            spans.append((i, j))
            i = j
        elif ch in "\"'":
            j = i + 1
            while j < n and text[j] != ch and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            i = j + 1
        else:
            i += 1
    return spans


def _comment(text, project, target_dir, ids):
    names = "|".join(re.escape(s) for s in spellings(project, target_dir))

    def tasks(m):
        return "these tasks" if len(re.findall(TASK_ID, m.group(0))) > 1 else "this task"
    text = re.sub(r"the CyberForge (?:(?:%s) )?tasks? (?:(?:%s) )?%s" % (names, names, TASK_IDS), tasks, text, flags=re.I)
    text = re.sub(r"(?:%s) %s" % (names, TASK_IDS), tasks, text, flags=re.I)
    text = re.sub(r"projects/(?:%s)/setup/" % names, "", text, flags=re.I)
    text = re.sub(TASK_ID, lambda m: ids.setdefault(m.group(0), "task %s" % chr(ord("A") + len(ids))), text)
    if re.search("cyberforge", text, re.I):
        raise ValueError("a comment still names the dataset: %r" % text[:200])
    return hide_code(text, project, target_dir)


def hide_code(text, project, target_dir):
    """text, all of it read as code, with `<project>` for each name of the project."""
    out, last = [], 0
    for a, b, _ in _matches("```\n%s\n```" % text, project, target_dir):
        out += [text[last:a - 4], PLACEHOLDER]
        last = b - 4
    return "".join(out + [text[last:]])


def hide_in_comments(data, name, project, target_dir):
    """The agent's copy of a driver file: its comments without the project's name or the dataset
    task, its code byte for byte, every line where it was."""
    text = data.decode("utf-8")
    ids, out, last = {}, [], 0
    for a, b in comment_spans(text, name):
        out += [text[last:a], _comment(text[a:b], project, target_dir, ids)]
        last = b
    new = "".join(out + [text[last:]])
    if new.count("\n") != text.count("\n"):
        raise ValueError("%s: rewriting its comments moved its lines" % name)
    return new.encode("utf-8")


def hide(text, project, target_dir):
    """text with `<project>` for each name of the project; raises ValueError for a name that
    `<project>` (the source directory's name) cannot stand for."""
    unpack = UNPACK % target_dir
    if text.count(unpack) != 1:
        raise ValueError("instruction does not say once what repo-vul.tar.gz unpacks to (%s)" % unpack)
    text = text.replace(unpack, MARK)
    mask = code_mask(text)
    found = _matches(text, project, target_dir)
    for _, _, s in found:
        if norm(s) != norm(target_dir):
            raise ValueError("the instruction names the project as %r, which <project> (the source "
                             "directory, %r) cannot stand for" % (s, target_dir))
    recased = any(s != target_dir for _, _, s in found)
    # In code the placeholder replaces the name. In prose the whole path or file name around it
    # (`src/pcre2_fuzzsupport.c`, but not the `'s` of `PCRE2's`) becomes code, so it reads as one name.
    spans = []  # [start, end, [names in it]]
    for a, b, _ in found:
        x, y = a, b
        if not mask[a]:
            while x > 0 and re.match(r"[A-Za-z0-9_./-]", text[x - 1]):
                x -= 1
            while y < len(text) and re.match(r"[A-Za-z0-9_./-]", text[y]):
                y += 1
            while y > b and text[y - 1] in ".-/":  # the end of a sentence, not of the name
                y -= 1
            if text.startswith("()", y):  # a function: `cJSON_ParseWithOpts()`
                y += 2
        if spans and x < spans[-1][1]:
            spans[-1][1] = max(y, spans[-1][1])
            spans[-1][2].append((a, b))
        else:
            spans.append([x, y, [(a, b)]])
    out, last = [], 0
    for x, y, names in spans:
        word, at = [], x
        for a, b in names:
            word += [text[at:a], PLACEHOLDER]
            at = b
        word = "".join(word + [text[at:y]])
        out += [text[last:x], word if mask[x] else "`%s`" % word]
        last = y
    out.append(text[last:])
    text = "".join(out)
    if PLACEHOLDER not in text:
        return text.replace(" " + MARK, "")
    return text.replace(MARK, unpack_note(recased))


def unpack_note(recased=False):
    """What the repo-vul.tar.gz line says of `<project>` once the instruction uses it."""
    return "(it unpacks to one directory, written `%s` below%s)" % (PLACEHOLDER, (
        "; in names in its code `%s` may be capitalised differently or use `_` for `-`" % PLACEHOLDER)
        if recased else "")
