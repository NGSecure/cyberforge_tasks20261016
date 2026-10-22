#!/usr/bin/env python3
"""Hide the project's name in bundles whose images were already built and pushed, without
building them again (see SKILL.md, "No project name for the agent").

    python3 -I salvage_noname.py <this repo> <dir with the pushed bundles> [--rebuilt NAME ...] [--dry-run]

For every bundle directory found under the second argument (at most two levels down, e.g. the
repo's own newplatform_bundles*/ folders after `git pull`) it takes from this repo only what is
read at run time, not built into an image:

  - instruction.md;
  - environment/docker-compose.yaml, which empties PROJECT_NAME for the agent (images built before
    v0.0.3 set it to the project's name);
  - in task.toml the lines description, keywords, fuzzer and cyberforge_project (removed). The
    task's name and the [environment] image references push.sh wrote stay as they are.

A category-5 bundle whose driver file the agent sees under a new name (c5_specs.json "agent_files")
gets the instruction that names the file as its old image has it (with `<project>` for the name),
unless it is listed after --rebuilt. Everything else (the agent image's PROJECT_NAME, a
description the conversion wrote, the agent's copies of the drivers) is in the images: the bundles
that need building again for it are listed at the end.
"""
import json
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import noname  # noqa: E402

FOLDERS = ("newplatform_bundles", "newplatform_bundles2", "newplatform_bundles3", "newplatform_bundles4",
           "newplatform_bundles5", "other_errors", "PotentialFalsePositive")
TOML_KEYS = ("description", "keywords", "fuzzer", "cyberforge_project")


def repo_bundles(repo):
    out = {}
    for f in FOLDERS:
        d = os.path.join(repo, f)
        for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if n.startswith("cyberforge-") and os.path.isfile(os.path.join(d, n, "instruction.md")):
                out[n] = os.path.join(d, n)
    return out


def pushed_bundles(root, names):
    out = {}
    for dp, dn, _ in os.walk(root):
        if dp[len(root):].count(os.sep) >= 2:
            dn[:] = []
        for n in dn:
            if n in names and os.path.isfile(os.path.join(dp, n, "task.toml")):
                out.setdefault(n, os.path.join(dp, n))
    return out


def toml_lines(text):
    """{key: its line} for the keys salvage_noname.py sets (the first of each)."""
    out = {}
    for line in text.split("\n"):
        m = re.match(r"(\w+) = ", line)
        if m and m.group(1) in TOML_KEYS:
            out.setdefault(m.group(1), line)
    return out


def merged_toml(old, new):
    """old (the pushed task.toml) with the description, keywords, fuzzer and cyberforge_project
    lines of new (this repo's): a key new no longer has is dropped."""
    want, out = toml_lines(new), []
    for line in old.split("\n"):
        m = re.match(r"(\w+) = ", line)
        if m and m.group(1) in TOML_KEYS:
            if m.group(1) in want:
                out.append(want.pop(m.group(1)))
            continue
        out.append(line)
    if want:
        raise ValueError("the pushed task.toml lacks %s" % ", ".join(sorted(want)))
    return "\n".join(out)


def old_image_instruction(text, agent_files, project, target_dir):
    """The repo's instruction for an agent image built before the agent's driver files were renamed:
    the files as that image names them, with `<project>` for the project's name."""
    for old, new in sorted(agent_files.items()):
        shown = noname.hide_code(old, project, target_dir)
        text = text.replace("- `%s`:" % new, "- `%s`:" % shown).replace("/workspace/%s" % new, "/workspace/%s" % shown)
    line = "- `repo-vul.tar.gz`: source code of the vulnerable program\n"
    if noname.PLACEHOLDER in text and line in text:  # `<project>` is used again: say what it is
        text = text.replace(line, line[:-1] + " " + noname.unpack_note() + "\n", 1)
    return text


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    rebuilt = set()
    if "--rebuilt" in args:
        i = args.index("--rebuilt")
        rebuilt, args = set(args[i + 1:]), args[:i]
    if len(args) != 2:
        print(__doc__.split("\n\n")[1])
        return 2
    repo, root = (os.path.abspath(a) for a in args)
    mine = repo_bundles(repo)
    theirs = pushed_bundles(root, set(mine))
    if not theirs:
        print("no bundle of this repo under %s" % root)
        return 1
    changed, rebuild = {}, {}
    for n, bd in sorted(theirs.items()):
        r = mine[n]
        src = json.load(open(os.path.join(r, "cyberforge_source.json"), encoding="utf-8"))
        files = {}
        instr = open(os.path.join(r, "instruction.md"), encoding="utf-8").read()
        drv = (src.get("recipe") or {}).get("driver") or {}
        if drv.get("agent_files") and n not in rebuilt:
            target_dir = re.search(r"-czf /tmp/repo-vul\.tar\.gz (\S+)$",
                                   open(os.path.join(r, "environment", "Dockerfile")).read(), re.M).group(1)
            instr = old_image_instruction(instr, drv["agent_files"], src["source_task"].split("/projects/")[1].split("/")[0],
                                          target_dir)
        files["instruction.md"] = instr
        files[os.path.join("environment", "docker-compose.yaml")] = open(
            os.path.join(r, "environment", "docker-compose.yaml"), encoding="utf-8").read()
        try:
            files["task.toml"] = merged_toml(open(os.path.join(bd, "task.toml"), encoding="utf-8").read(),
                                             open(os.path.join(r, "task.toml"), encoding="utf-8").read())
        except ValueError as e:  # left as it is; the other files are still updated
            print("  %s: task.toml not updated: %s" % (n, e))
        for rel, text in files.items():
            p = os.path.join(bd, rel)
            if not os.path.isfile(p) or open(p, encoding="utf-8").read() != text:
                changed.setdefault(n, []).append(rel)
                if not dry:
                    with open(p, "w", encoding="utf-8", newline="\n") as f:
                        f.write(text)
        why = []
        if (src.get("description") or {}).get("from", "").startswith("bug_report.txt"):
            why.append("description.txt")
        if drv.get("files"):
            why.append("the agent's copies of the driver files")
        if why and n not in rebuilt:
            rebuild[n] = why
    print("%s %d of %d bundles found under %s (%d already up to date)" % (
        "would update" if dry else "updated", len(changed), len(theirs), root, len(theirs) - len(changed)))
    for n in sorted(changed):
        print("  %s: %s" % (n, ", ".join(changed[n])))
    print("PROJECT_NAME: hidden by docker-compose.yaml where the platform starts the agent from it; "
          "otherwise only rebuilt images (v0.0.3) lose it.")
    print("%d bundles need their images built again (build.sh, push.sh) for the rest:" % len(rebuild))
    for n in sorted(rebuild):
        print("  %s: %s" % (n, ", ".join(rebuild[n])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
