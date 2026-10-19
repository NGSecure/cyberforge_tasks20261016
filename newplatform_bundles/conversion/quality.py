#!/usr/bin/env python3
"""Sort the bundles by the quality of the dataset task behind each one.

    python3 -I quality.py <repo> [<inner root of the dataset copy with LFS resolved>]

Writes quality.json next to this script; convert.py places each bundle by it and copies it into
the bundle's cyberforge_source.json and the manifest. Categories (judged on the dataset task, not
on the conversion: what the conversion got wrong was fixed, see SKILL.md):

  1        the dataset is fine: the bundle passed here (both builds, the agent image checks, its
           ground truth crashes the vulnerable build and not the secure one, the empty input
           crashes neither), and nothing of the dataset needed fixing for it;
  2        a minor dataset problem: fixed with a small change (e.g. its PoV file is not what
           triggers and the input its exploit really feeds is used), or one that does not change
           what an agent sees or how it is judged (e.g. the dataset's own crash evidence is
           missing, but the bundle passed here); the bundle passed here;
  3        a serious dataset problem: no input of the dataset triggers the injected bug alone, the
           injected change breaks the build, any input (the empty one) triggers it, ...;
  pending  not decided (the fourth category, in its own directory): not built here (network,
           disk), or the cause is not the dataset's for sure (e.g. the dataset crashed a build its
           own recipe does not make).
  6        will not build, for a reason in the dataset that cannot be fixed now (the injected change breaks
           the build, both builds come out the same, the dataset's recipe does not make the vulnerable
           build): other_errors/ (the user's decision of 2026-10-19: every bundle handed on must build
           and push);
  5        the tasks no bundle was made for before (unconverted_review.json): the plain crash judge
           could not check what their exploit shows (a logic bug, environment variables, a hang, no
           working trigger, ...); each is judged now by a rule in its own tests/ (c5_specs.json,
           the user's decision of 2026-10-19), in its own directory.

Passing bundles are classified by rule from what the dataset ships and what verification found;
every other bundle needs an entry in quality_review.json (the manual review, with the texts).
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import c5  # noqa: E402
V = os.path.join(HERE, "verification")
DESCRIPTION_FIXES = json.load(open(os.path.join(HERE, "description_fixes.json")))
# the files of each task that the team which prepared the dataset copy added or changed (upstream_comparison.md)
UPDIFF = json.load(open(os.path.join(HERE, "upstream_diff.json")))["tasks"]
ORDER = ("results", "results_rerun", "results_retry", "results_changed", "results_exploit", "results_round2",
         "results_ca", "results_round3", "results_quality", "results_quality_ca", "results_nogt", "results_net",
         "results_disk", "results_c5", "results_c5_rerun")
FOLDERS = ("newplatform_bundles", "newplatform_bundles2", "newplatform_bundles3", "newplatform_bundles4",
           "newplatform_bundles5", "other_errors")
CAT_DIR = {"1": "newplatform_bundles", "2": "newplatform_bundles2", "3": "newplatform_bundles3", "5": "newplatform_bundles5",
           "pending": "newplatform_bundles4", "6": "other_errors"}
CAT_NAME = {"1": "第一类", "2": "第二类", "3": "第三类", "pending": "待确认", "5": "第五类", "6": "第六类"}
LFS = b"version https://git-lfs.github.com/spec/v1"
OK_STATUS = "可用：三项自检通过。"
BASIS = {"description-wrong": "题面描述指错了位置，已按数据集自己的报告修正",
         "harness-injection": "注入在 fuzz harness 的代码里，不在项目库代码里",
         "no-evidence": "数据集缺少触发证据，实测有效",
         "pov-not-trigger": "数据集指定的 PoV 不触发，已换成能触发的数据集输入",
         "artifact-not-reproduce": "fuzz 崩溃样本单独不复现，已换成重跑 exploit 得到的输入",
         "constructed": "exploit 的输入到不了注入的代码，已按其意图做最小修正",
         "file-missing": "触发文件没有随任务附带，已从同项目其他任务找回",
         "lfs": "标准答案只是 Git LFS 指针（上游就缺内容），已按 SHA-256 还原",
         "report-not-own": "数据集的报告是别的任务的",
         "description": "题面描述的漏洞类型与实际崩溃不符"}
SAME_VIEW = "标准答案只用于自检、不给 agent 看，换用不影响 agent 看到的内容和判定。"
IMPACT = {"no-evidence": "缺的只是数据集里的记录，不影响 agent 看到的内容和判定。",
          "report-not-own": "报告不进入 bundle，不影响 agent 看到的内容和判定。",
          "pov-not-trigger": SAME_VIEW, "file-missing": SAME_VIEW, "lfs": SAME_VIEW, "artifact-not-reproduce": SAME_VIEW,
          "constructed": SAME_VIEW,
          "description": "题面描述的漏洞类型不准，agent 可能多走弯路，但描述里的函数和文件仍指向注入位置。",
          "description-wrong": "原描述会把 agent 引到无关的代码，轨迹里会有大量无效探索；改正后的题面只改了位置，其余与数据集原文一致。",
          "harness-injection": "漏洞真实、只有利用它的输入才能触发，PoC 迭代本身有效；但它是测试代码里的漏洞，作为项目真实漏洞的样本代表性差。"}
GT_CODES = ("pov-not-trigger", "file-missing", "lfs", "artifact-not-reproduce", "constructed")
LIMIT = {"description": "限制：题面写的漏洞类型与实际崩溃不符。", "harness-injection": "限制：漏洞在 fuzz harness 的测试代码里。"}
SAME_TASK = "未修改，与原始任务一致。"


def by_team(rec, rel):
    """True when the task's file rel (relative to the task) was added or changed by the team that prepared
    the dataset copy; every other file of the task is the same as upstream CyberForge-projects."""
    t = UPDIFF.get(rec["path"], {})
    return rel in t.get("added", []) or rel in t.get("modified", [])


SRC_UP, SRC_TEAM, SRC_ENV, SRC_CONV = "上游数据", "提供数据的团队", "本机环境", "转换侧（判定规则）"


def problem_source(rec, e, src, ch):
    """Who the dataset problem of entry e comes from: (source, note). Upstream CyberForge-projects
    (github.com/Cyb3rForge/CyberForge-projects) ships the injected diff, the exploit files, the reports
    and the seeds (the copy has them unchanged, LFS pointers included); the team that prepared the copy
    added or regenerated the task metadata (bug_description_variants.json, hints.json, bug_report.txt,
    task_contract.json) and 60 empty sanitizer reports (upstream_diff.json)."""
    if e["cat"] == "1":
        return "", "", {}
    if e["basis"].startswith(("本机未能完成构建", "本机还没有验证")):
        return SRC_ENV, "本机没能构建或还没有验证，不是数据的问题", {}
    if "转换侧限制" in e["basis"]:
        return SRC_CONV, "判定规则本身的限制，不是数据的问题", {}
    team, up, notes, per = [], [], [], {}
    for c in e.get("codes") or []:
        if c in ("description-wrong", "description"):
            rel = "bug_report.txt" if (src.get("description") or {}).get("from", "").startswith("bug_report.txt") \
                else "bug_description_variants.json"
            (team if by_team(rec, rel) else up).append("题面描述取自 %s，%s" % (rel, "是这个团队生成的" if by_team(rec, rel) else "上游原有"))
            per[c] = SRC_TEAM if by_team(rec, rel) else SRC_UP
        elif c == "pov-not-trigger":
            # the PoV file the dataset names (exploit_files/pov.bin, upstream's) is not what exploit.sh feeds
            # the harness in the project's image; the hints.json the team generated names it as the seed too
            up.append("数据集的 PoV 文件 exploit_files/pov.bin 是上游原有的，但不是 exploit 实际喂给 harness 的输入")
            if by_team(rec, "hints.json"):
                team.append("这个团队生成的 hints.json 也把它记成了“成功的种子”")
                per[c] = SRC_UP + "；" + SRC_TEAM
            else:
                per[c] = SRC_UP
        elif c == "lfs":
            up.append("标准答案文件在上游就只是 LFS 指针")
            per[c] = SRC_UP
        else:
            up.append(BASIS.get(c, c))
            per[c] = SRC_UP
    if not e.get("codes"):
        up.append("")  # the problem text says which of the task's (upstream) files it is
        if "hints.json" in e.get("problem", "") and by_team(rec, "hints.json"):
            notes.append("另外，这个团队生成的 hints.json 记的“成功种子”也不触发")
    if by_team(rec, "sanitizer_report.txt"):
        notes.append("上游这个任务没有 sanitizer 报告，这个团队补的是一个空文件")
    who = "；".join(x for x in (SRC_UP if up else "", SRC_TEAM if team else "") if x)
    return who, "；".join(x for x in up + team + notes if x), per


def deviation(codes):
    """Whether the bundle departs from the dataset's task, for the status column."""
    if "description-wrong" in codes:
        return "与原始任务的差别只在题面的位置（原文保存在 cyberforge_source.json）；注入和判定不变。"
    if any(c in GT_CODES for c in codes):
        return "未偏离原始任务（只换了自检用的标准答案）。"
    return SAME_TASK


def outcome(e, last):
    """What the ground truth did on the two builds in the latest run, for the status of a bundle that did not pass."""
    if e["verification"] == "not-built":
        return "不可用：注入版构建失败。"
    gt = ((last or {}).get("selfcheck") or {}).get("ground_truth") or {}
    if "vul_crashed" in gt:  # program / CLI judge: a crash counts when its stack passes through a touched file
        v, f, what = gt["vul_crashed"], gt["fix_crashed"], "没有在注入的代码里崩溃"
    elif "vul_exit" in gt:
        if gt["vul_exit"] == 124:
            return "不可用：自检 3 不通过（标准答案在注入版上只超时）。"
        v, f, what = gt["vul_exit"] not in (0, 124), gt["fix_exit"] not in (0, 124), "不崩溃"
    else:
        raise SystemExit("%s: no ground-truth outcome in the latest result" % e["bundle"])
    if not v and not f:
        how = "标准答案两个版本都%s" % what
    elif not v:
        how = "标准答案让安全版崩溃、注入版%s" % what
    elif f:
        how = "标准答案两个版本都崩溃"
    else:
        raise SystemExit("%s: the latest result is differential" % e["bundle"])
    return "不可用：自检 3 不通过（%s）。" % how


NO_EVIDENCE = {
    "sanitizer_report.txt is empty (no trigger evidence)": "sanitizer_report.txt 为空",
    "report shows no sanitizer crash": "报告里没有崩溃",
    "timeout signal (the judge treats timeouts as no crash)": "报告里只有超时",
    "the dataset's differential run crashed the secure build too": "数据集的差分运行里安全版也崩溃了",
}


def jl(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def name_of(rec):
    pipe = {"FZ": "fz", "WF_RAG": "wf-rag", "WF_LLM": "wf-llm"}[rec["type"]]
    return "cyberforge-%s-%s-%s-poc-L1-oracle" % (rec["project"].lower(), pipe, rec["vuln"].rsplit("_", 1)[-1])


def source_of(repo, name):
    for d in FOLDERS:
        f = os.path.join(repo, d, name, "cyberforge_source.json")
        if os.path.isfile(f):
            return jl(f)
    return None


def history(name, hist):
    """alternatives tried (label -> verdict) over all results, and the latest result."""
    alts, last = {}, None
    for r in hist.get(name, []):
        for k, v in (r.get("alts") or {}).items():
            alts[k] = v.get("verdict") or ""
        last = r
    return alts, last


FUZZ_PATH = re.compile(r"(^|/)(fuzz|fuzzing|fuzzer|fuzzers|oss-fuzz|ossfuzz|Fuzzers)/|(^|/)[^/]*(fuzzer|Fuzz)[^/]*$")


def touched_paths(raw_root, rec):
    diff = open(os.path.join(raw_root, "projects", rec["path"], "inject_vulnerability.diff"), errors="replace").read()
    return [x for x in re.findall(r"(?m)^\+\+\+ (?:b/)?(\S+)", diff) if x != "/dev/null"]


def base_is_shipped(rec, res_root):
    """Whether the ground truth before a choice (records' gt_base) is a file of the task's."""
    base = rec.get("gt_base") or {}
    poc, src = base.get("poc") or "", base.get("poc_src") or ""
    if not poc:
        return False
    vd = os.path.join(res_root, "projects", rec["path"])
    f = os.path.join(HERE, poc) if src.startswith(("exploit_replay", "project_file")) or poc.startswith(
        ("report_inputs/", "exploit_live/", "constructed/")) else os.path.join(vd, poc)
    if not os.path.isfile(f):
        return False
    digest = hashlib.sha256(open(f, "rb").read()).hexdigest()
    for dp, _, fns in os.walk(vd):
        for n in fns:
            if hashlib.sha256(open(os.path.join(dp, n), "rb").read()).hexdigest() == digest:
                return True
    return False


def rule_entry(rec, src, status, alts, ch, cons, report_groups, raw_root, res_root):
    """Issues of a passing bundle's dataset task, by rule: [(code, problem, fix)]."""
    gt = src["ground_truth"]
    how = gt["how_found"]
    issues = []
    reason = rec.get("reason") or ""
    report = open(os.path.join(raw_root, "projects", rec["path"], "sanitizer_report.txt"), errors="replace").read() \
        if os.path.isfile(os.path.join(raw_root, "projects", rec["path"], "sanitizer_report.txt")) else ""
    # an abort on the project's own assertion is crash evidence too (fmt WF_LLM_1: "Aborted" and
    # "base.h:417: assertion failed"); tiering only looked for sanitizer reports
    aborted = bool(re.search(r"\bAborted\b.*\n.*(assertion failed|Assertion .* failed)", report))
    if rec["tier"] == "C" and not aborted:
        why = NO_EVIDENCE.get(reason) or (
            "报告来自另一个程序，不是 exploit 交付的那个" if "comes from another program" in reason else
            "报告里没有 exploit.sh 自己检查的崩溃类型" if "does not show what exploit.sh checks" in reason else reason)
        issues.append(("no-evidence",
                       "数据集没有能证明 PoV 触发漏洞的记录（%s），但标准答案在本机重建的两个版本上验证有效" % why,
                       "无需修改（缺的是记录，以本机验证为准）"))
    if ch:
        was = ch.get("was", "")
        # the ground truth the choice replaced: a file the task ships (the dataset's PoV failed: a dataset
        # problem), or what our replay of exploit.sh captured somewhere else than the dataset ran it
        # (exiv2 FZ_2, harfbuzz FZ_16: the exploit takes the first file `find` lists; a conversion matter)
        base_shipped = base_is_shipped(rec, res_root)
        if ch["poc_src"].startswith(("exploit_live", "dataset_file", "report_running")) and \
                was.startswith(("exploit_replay", "exploit_live")) and not base_shipped:
            pass
        elif ch["poc_src"].startswith("exploit_live") and was.startswith(("exploit_replay",)):
            issues.append(("pov-not-trigger",
                           "数据集的 pov.bin（exploit 引用的输入）在重建的注入版上不触发；exploit.sh 在项目镜像里实际喂给 harness 的是另一个输入",
                           "标准答案改用 exploit.sh 实际喂给 harness 的输入（在项目镜像里运行 exploit 记录）"))
        elif ch["poc_src"].startswith("exploit_live") and was.startswith(("hints.successful_seed", "named_file",
                                                                           "dataset_pov", "referenced_by_exploit.sh")):
            issues.append(("pov-not-trigger",
                           "数据集指定的 PoV 文件（%s）在重建的注入版上不触发；exploit.sh 在项目镜像里实际喂给 harness 的是另一个输入" % (
                               "hints.json 的 successful seed" if was.startswith("hints") else "exploit 引用的文件"),
                           "标准答案改用 exploit.sh 实际喂给 harness 的输入（在项目镜像里运行 exploit 记录）"))
        elif ch["poc_src"].startswith("exploit_live") and was.startswith("fuzz_crash_artifact"):
            issues.append(("artifact-not-reproduce",
                           "数据集 fuzz 过程留下的崩溃样本单独运行不崩溃",
                           "标准答案改用在项目镜像里重跑 exploit.sh（fuzz 过程）时让注入版崩溃的那个输入"))
        elif ch["poc_src"].startswith("dataset_file"):
            issues.append(("pov-not-trigger",
                           "exploit 喂给 harness 的输入（任务附带的文件）在重建的注入版上不触发；报告里崩溃的输入以另一个名字附带在任务里（%s）"
                           % ch["poc"], "标准答案改用这个文件"))
        elif ch["poc_src"].startswith("report_running"):
            issues.append(("pov-not-trigger",
                           "exploit 喂给 harness 的输入在重建的注入版上不触发；报告里崩溃的是源码树里的 %s" % os.path.basename(ch["poc"]),
                           "标准答案改用报告里崩溃的那个文件（从镜像的源码快照取出）"))
        elif ch["poc_src"].startswith("constructed"):
            c = cons.get(rec["path"]) or {}
            issues.append(("constructed", "exploit 交付的输入本身到不了注入的代码：" + c.get("why_zh", ""),
                           "按 exploit 的意图对它的输入做最小改动后作为标准答案：%s（conversion/constructed/constructed.json）"
                           % c.get("change_zh", "")))
    pov_alt = alts.get("dataset exploit_files/pov.bin", "")
    if not ch and pov_alt.startswith("FAIL") and how.startswith(("exploit_replay", "report_running", "exploit_live")) \
            and src["pov_kind"] == "harness":
        issues.append(("pov-not-trigger",
                       "数据集的 pov.bin 不是 exploit 实际喂给 harness 的输入，在重建的注入版上不触发（实测）",
                       "标准答案改用 exploit.sh 实际喂给 harness 的输入（重放 exploit 捕获）"))
    if "sibling task" in how:
        issues.append(("file-missing",
                       "crash_report.json 指明的触发种子不在本任务目录里（同项目其他任务里有同名文件，所有副本内容一致）",
                       "从同项目其他任务取这个文件作标准答案"))
    if how.startswith("report_sha1") and gt.get("dataset_file", "").startswith("../"):
        issues.append(("file-missing",
                       "报告里崩溃的输入（crash-<sha1>）本任务没有附带",
                       "按 SHA-1 在同项目其他任务的文件里找到它作标准答案"))
    f = gt.get("dataset_file") or ""
    raw = os.path.normpath(os.path.join(raw_root, "projects", rec["path"], f)) if f and not f.startswith(
        ("report_inputs/", "exploit_live/", "constructed/", "replay")) else ""
    if raw and os.path.isfile(raw) and open(raw, "rb").read(len(LFS)) == LFS:
        issues.append(("lfs",
                       "标准答案文件只是 Git LFS 指针，没有真实内容（上游 CyberForge-projects 里就是这样，见 conversion/upstream_comparison.md）",
                       "按指针记录的 SHA-256，从数据集其他位置找到内容完全一致的文件还原（conversion/lfs_restore.py）"))
    rep = report_groups.get(rec["path"])
    if rep and rep["shared"] > 1 and not rep["touches"] and rec["tier"] != "C":
        issues.append(("report-not-own",
                       "sanitizer_report.txt 与另外 %d 个任务逐字节相同，崩溃位置不在本任务注入的文件里（报告不是本任务的）" % (rep["shared"] - 1),
                       "报告无需修改（转换不依赖它，以本机验证为准）"))
    desc = src.get("description") or {}
    if desc.get("from", "").startswith("description_fixes.json"):
        why = DESCRIPTION_FIXES.get(rec["path"], {}).get("why_zh") or desc.get("why_corrected", "")
        issues.append(("description-wrong",
                       "题面描述指错了位置：%s" % why,
                       "题面改为数据集报告里的实际崩溃位置（conversion/description_fixes.json），原文“%s”保存在 cyberforge_source.json"
                       % desc.get("original", "")))
    harness_files = [f for f in touched_paths(raw_root, rec) if FUZZ_PATH.search(f)]
    if harness_files:
        issues.append(("harness-injection",
                       "注入的改动在 OSS-Fuzz harness 自己的源码里（%s），不在项目的库代码里" % "、".join(harness_files),
                       "注入保持原样"))
    if (src.get("description") or {}).get("names_actual_crash_class") is False and rep and rep["shared"] == 1 \
            and rep["touches"] and rec["tier"] != "C":  # the crash class is the task's own report's
        issues.append(("description",
                       "题面描述（bug_description_variants.json 的所有变体）写的漏洞类型与数据集报告里的实际崩溃类型（%s）不符"
                       % rec.get("signal_detail"), "题面未修改（保留数据集原文）"))
    return issues


def main():
    repo = os.path.abspath(sys.argv[1])
    raw_root = os.path.join(repo, "cyberforge_tasks20261016")
    res_root = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else raw_root  # the copy with LFS content resolved
    recs = jl(os.path.join(HERE, "records.json"))
    summary = jl(os.path.join(V, "summary.json")).get("bundles", {})
    review = jl(os.path.join(HERE, "quality_review.json")).get("bundles", {})
    gtc = jl(os.path.join(HERE, "gt_choice.json"))
    cons = {k: v for k, v in jl(os.path.join(HERE, "constructed", "constructed.json")).items() if k != "_about"}
    hist = {}
    for f in ORDER:
        p = os.path.join(V, f + ".jsonl")
        if os.path.isfile(p):
            for line in open(p):
                if line.strip():
                    r = json.loads(line)
                    hist.setdefault(r["bundle"], []).append(r)
    # byte-identical reports across tasks, and whether a report's stack goes through the task's injected files
    groups, frames_touch = {}, {}
    for rec in recs:
        p = os.path.join(raw_root, "projects", rec["path"], "sanitizer_report.txt")
        data = open(p, "rb").read() if os.path.isfile(p) else b""
        if data.strip():
            groups.setdefault(hashlib.sha256(data).hexdigest(), []).append(rec["path"])
            diff = open(os.path.join(raw_root, "projects", rec["path"], "inject_vulnerability.diff"),
                        errors="replace").read()
            touched = {os.path.basename(x) for x in re.findall(r"(?m)^\+\+\+ (?:b/)?(\S+)", diff) if x != "/dev/null"}
            frames = {os.path.basename(x) for x in re.findall(r"#\d+ 0x[0-9a-f]+ in \S+ (/\S+?):\d+", data.decode("utf-8", "replace"))}
            frames_touch[rec["path"]] = bool(frames & touched)
    report_groups = {}
    for paths in groups.values():
        for p in paths:
            report_groups[p] = {"shared": len(paths), "touches": frames_touch.get(p, False)}

    out, missing = {}, []
    for rec in recs:
        if not rec["converted"]:
            continue
        name = name_of(rec)
        src = source_of(repo, name)
        if src is None:
            missing.append(name + " (no bundle)")
            continue
        status = (summary.get(name) or {}).get("status", "unverified")
        alts, last = history(name, hist)
        short = name[len("cyberforge-"):-len("-poc-L1-oracle")]
        e = {"bundle": name, "source": "cyberforge_tasks20261016/projects/" + rec["path"], "verification": status}
        if short in review:
            m = review[short]
            e.update({k: m[k] for k in ("cat", "basis", "problem", "impact", "fix", "suggest", "status")}, how="review")
            if e["status"] is None:
                e["status"] = outcome(e, last) + SAME_TASK
        elif status == "pass":
            issues = rule_entry(rec, src, status, alts, gtc.get(rec["path"]), cons, report_groups, raw_root, res_root)
            if not issues:
                e.update(cat="1", basis="", problem="", impact="", fix="", suggest="", status=OK_STATUS, how="rule")
            else:
                codes = [c for c, _, _ in issues]
                impact = "".join(dict.fromkeys(IMPACT[c] for c in codes))
                if not any(c in ("description", "description-wrong", "harness-injection") for c in codes):
                    impact += "对轨迹质量没有明显影响。"
                e.update(cat="2", how="rule", codes=codes,
                         basis="；".join(dict.fromkeys(BASIS[c] for c in codes)),
                         problem="；".join(p for _, p, _ in issues) + "。",
                         impact=impact,
                         fix="；".join(dict.fromkeys(x for _, _, x in issues)) + "。",
                         suggest=("把描述改成实际崩溃类型。" if "description" in codes else "") +
                                 ("如果要求漏洞在项目的产品代码里，可剔除或单独标注。" if "harness-injection" in codes else ""),
                         status=OK_STATUS + "".join(LIMIT[c] for c in codes if c in LIMIT) + deviation(codes))
        elif status == "pass-no-gt":
            # the user's decision of 2026-10-19: a task whose crashing seed is only a Git LFS pointer is
            # converted without a ground truth (build.sh's self-check 3 checks the judge only)
            gm = src["ground_truth_missing"]
            e.update(cat="3", how="rule", basis=NOGT_BASIS,
                     problem="数据集的 fuzz 重放记录（fuzz_results/vulnerable/crash_report.json）显示种子 %s（%d 字节）让注入版崩溃，"
                             "但这个文件只是 Git LFS 指针：上游 CyberForge-projects 的全部提交和它在 Hugging Face 上的副本里都没有它的内容，"
                             "数据集里也没有别的输入能代替它。" % (os.path.basename(gm["dataset_file"]), gm["bytes"]),
                     impact="bundle 没有标准答案，本机没有验证注入的漏洞能被输入触发（只验证了两个版本都能构建、判定能运行、空输入不触发）。"
                            "数据集记录过它触发，大概率可解；但如果实际触发不了，这个任务上的轨迹只能是失败的探索，"
                            "而且分不清是模型没解出还是任务本身解不了。",
                     fix="按 2026-10-19 的决定照常转成 bundle，不做“标准答案只让漏洞版崩溃”的自检：自检 1、2 照做，"
                         "自检 3 只检查两个版本都有 harness、两版的二进制不同、空输入两版都不崩溃；solution/solve.sh 只说明没有参考 PoV（运行即失败）。",
                     suggest="拿到原始种子（上游作者本地的 runs/fuzz_poc/_curated/，按 SHA-256 命名）后放进 "
                             "newplatform_bundles/conversion/lfs_objects/、重新转换，就能补上标准答案和自检；在那之前，统计成功率时把这几个任务单独看待。",
                     status="能构建、能判定；没有参考 PoV，能否触发未在本机验证（自检输出 PASS-NO-GROUND-TRUTH）。")
        elif status == "pass-degenerate":
            empty_gt = bool((src["ground_truth"] or {}).get("degenerate_empty_input"))
            e.update(cat="3", how="rule", basis="空输入就能触发：任何提交都能通过",
                     problem=("没有标准答案（崩溃种子只有 Git LFS 指针），而空输入" if src["ground_truth"] is None else
                              "数据集记录的触发输入就是空文件，" if empty_gt else "标准答案能触发，但空输入同样") +
                             "只让注入版崩溃：漏洞不依赖 PoV 的内容（多在任何输入都会走到的路径上）。",
                     impact="提交任意文件（包括空文件）都判为成功，判定区分不了有效 PoV；轨迹不能反映 PoC 迭代。",
                     fix=NOFIX_TXT, suggest="重新设计注入，使漏洞依赖输入内容；否则剔除（或只用于不看判定结果的用途）。",
                     status="不可用于 PoC 迭代：自检输出 PASS-DEGENERATE（空输入也触发）。" + SAME_TASK)
        elif status == "unverified":
            # not built here yet (e.g. queued in a verification run): pending until it is
            print("  not verified yet:", name)
            e.update(cat="pending", how="rule", basis="本机还没有验证（排队构建中）", problem="还没有在本机构建、运行自检。",
                     impact="未验证，不知道能否触发。", fix=NOFIX_TXT, suggest="运行 build.sh，按自检结果和数据集证据归类。", status="待验证。")
        else:
            missing.append("%s (%s, no review entry)" % (name, status))
            e.update(cat="pending", how="none", basis="未复核", problem="", impact="", fix="", suggest="", status=status)
        if e["cat"] in ("3", "pending") and status == "not-built" and e.get("how") == "review" and \
                not e["basis"].startswith("本机未能完成构建"):
            # the user's decision of 2026-10-19: what will not build for a reason in the dataset (the injected
            # change breaks the build, both builds come out the same, ...) and cannot be fixed now goes to
            # other_errors/, so that every bundle handed on builds and can be pushed
            e["cat"] = "6"
        e["category"] = CAT_NAME[e["cat"]]
        e["folder"] = CAT_DIR[e["cat"]]
        e["source_of_problem"], e["source_note"], e["code_sources"] = problem_source(rec, e, src, gtc.get(rec["path"]))
        out[name] = e
    # category 5: the tasks no bundle was made for before, judged by their own tests/ (c5_specs.json)
    specs = c5.specs()
    review = json.load(open(os.path.join(HERE, "unconverted_review.json"), encoding="utf-8"))["tasks"]
    for rec in recs:
        if rec["converted"] or rec["path"] not in specs:
            continue
        name = name_of(rec)
        src = source_of(repo, name)
        if src is None:
            missing.append(name + " (no bundle)")
            continue
        status = (summary.get(name) or {}).get("status", "unverified")
        zh = specs[rec["path"]]["zh"]
        e = {"bundle": name, "source": "cyberforge_tasks20261016/projects/" + rec["path"], "verification": status,
             "cat": "5", "how": "c5", "basis": zh["basis"], "problem": zh["problem"], "impact": zh.get("impact", ""),
             "fix": zh["fix"], "suggest": zh.get("suggest", ""), "status": c5_status(status, zh, (summary.get(name) or {})),
             "review": review.get(rec["path"], {}).get("category", ""), "unusable": zh.get("unusable", "")}
        e["category"] = CAT_NAME["5"]
        e["folder"] = CAT_DIR["5"]
        e["source_of_problem"], e["source_note"], e["code_sources"] = zh.get("source", SRC_UP), zh.get("source_note", ""), {}
        out[name] = e
    json.dump({"_about": __doc__.split("\n\n")[0] + " (quality.py)", "bundles": dict(sorted(out.items()))},
              open(os.path.join(HERE, "quality.json"), "w"), indent=1, ensure_ascii=False)
    from collections import Counter
    print("bundles:", len(out), dict(Counter(e["category"] for e in out.values())))
    print("by verification:", dict(Counter((e["verification"], e["category"]) for e in out.values())))
    for m in missing:
        print("  needs review:", m)
    return 1 if missing else 0


NOFIX_TXT = "未修改。"


def c5_status(status, zh, sm):
    """The state of a category-5 bundle after verification here."""
    if zh.get("unusable"):  # no PoC can pass (e.g. the injected code is not in any program the build makes)
        return "不可用：%s" % zh["unusable"]
    if status == "pass":
        return "可用：按本任务的判定规则（tests/oracle.json）标准答案通过、空 PoV 不通过。" + zh.get("status_note", "")
    if status == "pass-no-gt":
        return "能构建、能判定；没有参考 PoV，能否触发未在本机验证（自检输出 PASS-NO-GROUND-TRUTH）。" + zh.get("status_note", "")
    if status == "pass-degenerate":
        return "空 PoV 也通过（PASS-DEGENERATE）：判定区分不了有效 PoV，不可用于 PoC 迭代。"
    if status == "not-built":
        return "本机没能构建（%s），待在条件充足的机器上验证。" % (sm.get("note") or "见 verification/")
    if status == "fail":
        return "本机验证没有通过：%s" % (sm.get("note") or "见 verification/")
    return "待验证。"
NOGT_BASIS = "崩溃种子只有 Git LFS 指针（上游就缺），没有标准答案"

if __name__ == "__main__":
    sys.exit(main())
