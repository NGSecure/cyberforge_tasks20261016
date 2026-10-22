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
every command, path and harness name stays exact. The source and the environment still show the
name (/src/<directory>, the PROJECT_NAME variable `compile` reads): the instruction only does not
hand it over.
"""
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
    note = "(it unpacks to one directory, written `%s` below%s)" % (PLACEHOLDER, (
        "; in names in its code `%s` may be capitalised differently or use `_` for `-`" % PLACEHOLDER)
        if recased else "")
    return text.replace(MARK, note)
