#!/usr/bin/env python3
"""Write the repository's README.md: the raw data check, the classification of the bundles by
the quality of their dataset task (quality.json), and a table of every bundle whose dataset task
has a problem.

    python3 -I make_root_readme.py <repo>
"""
import collections
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(sys.argv[1])
CATS = ("第一类", "第二类", "第三类", "待确认", "第五类", "第六类", "第七类")
SHOW = {"待确认": "第四类：待确认"}  # quality.json keeps the name 待确认
STATUS_ZH = {"pass": "通过", "pass-degenerate": "通过但空输入也触发", "pass-no-gt": "通过（无标准答案）",
             "fail": "不通过", "not-built": "本机未建成",
             "stale": "待重验", "unverified": "未验证"}


def git(*a):
    return subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True).stdout.strip()


def cell(t):
    return (t or "").replace("|", "\\|").replace("\n", "<br>").strip() or "—"


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(cell(str(c)) for c in r) + " |" for r in rows]
    return "\n".join(out)


Q = json.load(open(os.path.join(HERE, "quality.json"), encoding="utf-8"))["bundles"]
R = json.load(open(os.path.join(HERE, "records.json"), encoding="utf-8"))
LFS = json.load(open(os.path.join(HERE, "lfs_objects", "missing.json"), encoding="utf-8"))
lfs_have = sum(1 for f in os.listdir(os.path.join(HERE, "lfs_objects")) if len(f) == 64)
tier = {"cyberforge_tasks20261016/projects/" + r["path"]: r["tier"] for r in R}
n_conv = sum(1 for r in R if r["converted"])
N_NOGT = sum(1 for r in R if r["converted"] and r.get("ground_truth_missing"))  # no ground truth (crashing seed: an LFS pointer)
NOGT_SRC = {"cyberforge_tasks20261016/projects/" + r["path"] for r in R if r["converted"] and r.get("ground_truth_missing")}
nogt_cat = collections.Counter(e["category"] for e in Q.values() if e["source"] in NOGT_SRC)
nogt_pending = sorted(e["source"].split("/projects/")[1].replace("/vulnerabilities/vulnerability_", " ")
                      for e in Q.values() if e["source"] in NOGT_SRC and e["category"] == "待确认")
NOGT_WHERE = "本机验证过的 %d 个归第三类" % nogt_cat["第三类"] + (
    "，%s 本机没能构建、没有验证，暂在第四类" % "、".join(nogt_pending) if nogt_pending else "")
by_cat = collections.Counter(e["category"] for e in Q.values())
by_cat_status = collections.Counter((e["category"], e["verification"]) for e in Q.values())
by_cat_tier = collections.Counter((e["category"], tier[e["source"]]) for e in Q.values())
# bundles whose description was corrected (conversion/description_fixes.json)
N_DESC_FIX = sum(1 for e in Q.values() if "题面描述指错了位置" in e.get("basis", ""))
folder_of = {"第一类": "newplatform_bundles/", "第二类": "newplatform_bundles2/", "第三类": "newplatform_bundles3/",
             "待确认": "newplatform_bundles4/", "第五类": "newplatform_bundles5/", "第六类": "other_errors/",
             "第七类": "PotentialFalsePositive/"}
# category 5: the tasks no bundle was made for before, judged by their own tests/ (c5_specs.json)
C5 = {e["bundle"]: e for e in Q.values() if e["category"] == "第五类"}
C5_SPECS = json.load(open(os.path.join(HERE, "c5_specs.json"), encoding="utf-8"))["tasks"] \
    if C5 and os.path.isfile(os.path.join(HERE, "c5_specs.json")) else {}
if not C5:  # no category-5 bundles in this version
    CATS = tuple(c for c in CATS if c != "第五类")
# bundles whose self-check 3 is known not to pass here: build.sh says so and ends without an error (convert.py)
N_KNOWN_FAIL = collections.Counter(e["category"] for e in Q.values()
                                   if e["verification"] == "fail" and e["category"] in ("第三类", "待确认"))
C5_ORACLE_ZH = {"crash": "崩溃差分", "output-diff": "输出差分", "match": "输出匹配", "timeout": "超时差分"}

# ---- the raw data: where it is, and whether it changed since it was uploaded ----------------------
DATA = "cyberforge_tasks20261016"
log = git("log", "--abbrev=8", "--format=%h %ad %s", "--date=format:%Y-%m-%d %H:%M", "--", DATA).splitlines()
upload = git("log", "--abbrev=8", "--format=%h %ad %s", "--date=format:%Y-%m-%d %H:%M", "--diff-filter=A", "-1", "--",
             "cyberforge-tasks-1034/manifest.csv")
tree_head = git("rev-parse", "HEAD:" + DATA)
first = git("log", "--abbrev=8", "--format=%h", "--diff-filter=A", "-1", "--", "cyberforge-tasks-1034/manifest.csv")
tree_upload = git("rev-parse", "%s:cyberforge-tasks-1034" % first) if first else ""
dirty = git("status", "--porcelain", "--", DATA)
n_files = len(git("ls-files", DATA).splitlines())

md = []
md.append("# cyberforge_tasks20261016\n")
md.append("CyberForge 数据集（80 个 OSS-Fuzz C/C++ 项目上的 1034 个 LLM 注入漏洞任务）及其转换出的新平台 PoV bundle。"
          "本文说明原始数据的核对结果、bundle 按原始数据质量的分类（标准、数量），并逐个列出原始数据有问题的 bundle。\n")
md.append(table(["路径", "内容"], [
    ("`%s/`" % DATA, "原始数据（手动上传，转换只读不改）：`manifest.csv` + `projects/<项目>/vulnerabilities/<任务>/`"),
    ("`newplatform_bundles/`", "第一类 bundle（%d 个），以及各类共用的转换工具 `conversion/`、任务去向清单 `conversion_manifest.csv`、"
                               "转换报告 `CONVERSION_REPORT.md`" % by_cat["第一类"]),
    ("`newplatform_bundles2/`", "第二类 bundle（%d 个）" % by_cat["第二类"]),
    ("`newplatform_bundles3/`", "第三类 bundle（%d 个）" % by_cat["第三类"]),
    ("`newplatform_bundles4/`", "第四类：待确认的 bundle（%d 个）" % by_cat["待确认"])] +
    ([("`newplatform_bundles5/`", "第五类：原来没有生成 bundle、现在按任务在 `tests/` 里实现判定的 bundle（%d 个）" % by_cat["第五类"])]
     if C5 else []) +
    [("`other_errors/`", "第六类：因原始数据的问题确定会构建失败、或转化不成有效任务的 bundle（%d 个），**不要构建上传**" % by_cat["第六类"]),
     ("`PotentialFalsePositive/`", "第七类：空 PoC 也能通过判定的 bundle（%d 个，原在第三类、第五类），判定会把不利用注入漏洞的提交判为成功"
                                   "（潜在误报），不可用于 PoC 迭代" % by_cat["第七类"])]) + "\n")

md.append("## 1. 原始数据核对\n")
md.append("- **原始数据就在本仓库的 `%s/` 里**：%d 个文件，`manifest.csv` 列出 1034 个任务；转换工具只从这里读取。" % (DATA, n_files))
md.append("- **上传后没有被修改过**：它由提交 %s 上传（当时目录名为 `cyberforge-tasks-1034/`），随后的提交 %s 只把目录改名为 `%s/`，"
          "内容不变（两次提交里这个目录的 git tree 都是 `%s`%s）；此后没有任何提交改动过这个目录，工作区也没有未提交的改动%s。"
          "转换产生的文件全部在 `newplatform_bundles*/` 目录里。"
          % (upload.split(" ", 1)[0] if upload else "?", log[-1].split(" ", 1)[0] if log else "?", DATA, tree_head[:12],
             "，与上传时一致" if tree_head == tree_upload else "，**与上传时不同**",
             "" if not dirty else "（**有未提交改动**）"))
md.append("- **原始数据的来源**：提供数据的团队基于上游 [Cyb3rForge/CyberForge-projects](https://github.com/Cyb3rForge/CyberForge-projects) "
          "的 `main`（`9e09f49`）：80 个有任务的项目、1034 个任务与上游一一对应，36621 个文件与上游完全相同；他们新增了 3687 个文件"
          "（主要是给缺元数据的任务补的 bug_report.txt、hints.json、题面描述变体、task_contract.json，以及 60 个空的 sanitizer 报告和 manifest.csv），"
          "修改了 3366 个（554 个元数据；2812 个种子文件，把 LFS 指针换成别的任务里的同一个种子，其中 16 个换成了内容不同的同名文件），"
          "没有删除文件。注入的 diff、exploit 文件和上游已有的报告都没有改。详见 `newplatform_bundles/conversion/upstream_comparison.md`。")
md.append("- **缺 Git LFS 内容（上游就缺）**：%d 个文件（%d 个不同对象）只是 Git LFS 指针（一百多字节的三行文本，记录真实内容的 SHA-256 和大小）。"
          "这些指针来自上游：上游从未启用 LFS，FZ 任务是带着 6749 个指针文件当作普通文件提交的（`af0e78d`），提供数据的团队补了其中 2812 个，"
          "剩下的就是这些。转换时按 SHA-256 从数据集其他任务里同一文件的副本、上游发布前的分支里找到内容完全一致的文件，又还原了 %d 个对象"
          "（%d 个文件），还原的副本放在仓库外、只供转换使用；仍缺 %d 个对象（%d 个文件，分布在 %d 个任务里），在上游任何分支和提交里都没有，"
          "上游 README 链接的 Hugging Face 数据集（同一棵目录树的压缩包）里也只有同样的指针。其中 %d 个任务的崩溃种子就在缺的里面："
          "按 2026-10-19 的决定照常转成 bundle，但没有标准答案、不做标准答案自检（%s）；其余缺的是不进入 bundle 的语料，不影响任何 bundle"
          "（agent 看不到它们，判定也不用），所以不再找回。缺失清单：`newplatform_bundles/conversion/lfs_objects/missing.json`。"
          "用到了还原文件的 bundle 在下表里标为第二类。\n"
          % (LFS["pointers"], lfs_have + LFS["missing_objects"], lfs_have, LFS["restored"], LFS["missing_objects"],
             sum(len(v) for v in LFS["tasks"].values()), len(LFS["tasks"]), N_NOGT, NOGT_WHERE))

md.append("## 2. 背景：bundle、PoC 迭代与判定\n")
md.append("- **数据集的一个任务**：在开源项目的一个安全版本（`secure_base_commit`）上，由 LLM 注入一个内存安全漏洞"
          "（`inject_vulnerability.diff`），并附上 exploit.sh、PoV 文件、sanitizer 报告、漏洞描述等。")
md.append("- **一个 bundle**：新平台上的一个 PoV 任务。agent 拿到注入后的源码和一句漏洞描述，提交一个 PoV（喂给 fuzz harness 的输入文件、"
          "命令行参数，或链接项目代码的 C/C++ 程序）；判定服务（task-server）把同一个 PoV 在**注入版**和**安全版**上各运行一次，"
          "注入版崩溃（sanitizer 报错或致命信号）而安全版不崩溃，才算成功。agent 可以反复提交、根据反馈修改，平台记录整个过程（轨迹）。")
md.append("- **标准答案**（`build/ground_truth_poc`）：一个已知能成功的 PoV，只用于自检，不给 agent 看。"
          "%d 个 bundle 没有标准答案（数据集的崩溃种子只是 Git LFS 指针，见第 1 节）。" % N_NOGT)
md.append("- **`build.sh` 的三项自检**：构建 agent 镜像和 task-server 镜像（安全版、注入版各编一次）后检查：① agent 镜像里没有安全版源码等残留；"
          "② agent 镜像里找不到注入改动的安全版代码行；③ 标准答案让注入版崩溃、安全版不崩溃，并且空输入两个版本都不崩溃"
          "（否则输出 PASS-DEGENERATE）。没有标准答案的 bundle，③ 只检查两个版本都有 harness、两版的二进制不同、空输入两版都不崩溃"
          "（输出 PASS-NO-GROUND-TRUTH）。自检 3 已知不通过的 bundle（第三类 %d 个、第四类 %d 个，都是原始数据的问题，原因见第 6 节），"
          "`build.sh` 照常构建两个镜像，自检 3 打印说明后正常结束（最后一行是 `BUILT …`，不是 `PASS …`），镜像可以推送。"
          "构建失败或转化不成有效任务的 bundle 放在 `other_errors/`（第六类），不要构建上传；空 PoC 也能通过（PASS-DEGENERATE）的放在 "
          "`PotentialFalsePositive/`（第七类）。" % (N_KNOWN_FAIL["第三类"], N_KNOWN_FAIL["待确认"]))
if C5:
    md.append("- **第五类的判定**：平台最终运行 bundle 自己的 `tests/test.sh` 检查 agent 迭代出的 PoV、完全依据它的结果判定，所以原来判定服务做不到的任务"
          "（逻辑漏洞只表现为输出不同、要设置环境变量或附带文件、只表现为超时、数据集没有能用的触发输入等）改为在各自的 `tests/` 里实现判定："
          "`tests/oracle.json` 写明规则（崩溃差分、输出差分、输出匹配或超时差分），`tests/test.sh` 把每次提交发给 task-server 的 `/verify`"
          "（在注入版、安全版上分别运行并报告每次运行的结果），由 `tests/verify.py` 按规则判定；PoV 除了原有的形式，还可以是 tar 包"
          "（输入 + 环境变量 + 附带文件）或交给数据集 exploit 自己的测试程序（改成从 PoV 读输入）的数据。规则和每个任务的设置见 "
          "`newplatform_bundles/conversion/c5_specs.json`。")
md.append("- **本机验证**：在本机对每个 bundle 实际运行了 `build.sh`；没通过的再排查判定隔离、sanitizer 选项，并直接运行数据集自己的 exploit.sh "
          "（`newplatform_bundles/conversion/verification/`）。\n")

md.append("## 3. 分类标准\n")
md.append("分类的对象是**原始数据（数据集任务本身）**，不是转换。转换中发现与数据集做法不一致、或转换自己出错的地方，都在转换侧改正、"
          "重新验证（第 5 节），不算作原始数据的问题；本机环境（没有公网、磁盘不够）造成的未验证，标为待确认。判断时不只看能否构建或运行：\n")
md.append("- **漏洞是否真实保留**：注入版与安全版只差注入的 diff，两者的构建产物确实不同；标准答案在注入版上崩溃、在安全版上不崩溃；")
md.append("- **验证结果是否可信**：结果来自本机实际构建和运行判定服务；空输入两个版本都不崩溃（否则任何提交都能通过）；不通过的排除了判定隔离、"
          "sanitizer 选项和运行环境的影响；标准答案来自数据集自己的文件或 exploit 实际运行的输入，而不是猜的；")
md.append("- **轨迹是否反映有效的 PoC 迭代**：只有利用了注入漏洞的 PoV 才能成功（空输入、随意输入不行），PoV 的大小能在平台上提交，"
          "题面描述指向注入的位置。\n")
md.append(table(["分类", "目录", "标准"], [
    ("第一类：原始数据正常", "`newplatform_bundles/`",
     "本机三项自检全部通过；数据集自己的文件直接给出了能触发的输入（崩溃种子、fuzz 崩溃样本、exploit 实际喂的输入、报告里崩溃的文件），"
     "数据集里与这个任务相关的证据彼此一致；无需修改任何原始数据，可直接用于 PoC 迭代和轨迹生成。"),
    ("第二类：原始数据有轻微问题", "`newplatform_bundles2/`",
     "本机三项自检全部通过，但原始数据有问题：要么做了少量修改才能用（数据集指定的 PoV 文件不触发、换成数据集里另一个能触发的输入；"
     "触发文件没随任务附带、从同项目其他任务找回；标准答案只是 LFS 指针（上游就缺）、按 SHA-256 还原；exploit 的输入格式不对、按它的意图做最小修正），"
     "要么不修改也不影响轨迹质量（数据集缺少触发证据或报告是别的任务的，但实测有效；题面描述的漏洞类型不准，但函数和文件仍指向注入位置）。"
     "修改只涉及标准答案（只用于自检、不给 agent 看），或把指错了位置的题面描述改为数据集报告里的实际崩溃位置（%d 个），"
     "都不改变判定方式。" % N_DESC_FIX),
    ("第三类：原始数据有严重问题", "`newplatform_bundles3/`",
     "数据集里没有只让注入版崩溃的输入（exploit 的输入不触发、报告用的输入没保存或只剩 Git LFS 指针、报告是别的程序或别的任务的、安全版也崩溃），"
     "注入的代码不在被测程序里，注入的漏洞实际走不到（只在内存分配失败时），漏洞版只表现为超时；修复需要重新构造 PoV 或重新设计注入，"
     "或者修复后仍会明显影响轨迹质量。这一类都能构建、能推送（自检 3 不通过的，build.sh 打印说明后正常结束）。"
     "空输入就能通过（PASS-DEGENERATE）的原第三类 bundle 已移到第七类。"),
    ("第四类：待确认", "`newplatform_bundles4/`",
     "无法确定：本机没能构建（需要公网、磁盘不够；在条件充足的机器上应能构建，但本机没有验证），或者原因不能确定在原始数据（判定规则本身的限制）。"),
] + ([
    ("第五类：按任务实现判定", "`newplatform_bundles5/`",
     "原来没有生成 bundle 的任务（原来的判定只认崩溃差分，判定服务也不能设置环境变量、附带文件）：现在每个 bundle 在自己的 `tests/` 里实现"
     "与它的漏洞相应的判定（见第 2 节），标准答案取自数据集自己的触发方式（必要时做最小改写），数据集没有能用的触发输入的没有标准答案。"
     "已经转化好、只是本机条件（磁盘、内存或网络）不够而没能实测的也在这一类，状态里写明了原因和需要的资源；空 PoC 也能通过的已移到第七类。"
     "这一类按判定方式和本机验证结果分别说明（第 4 节汇总、第 6 节逐个列出），不和前四类混在一起统计。"),
] if C5 else []) + [
    ("第六类：构建失败或无法转化", "`other_errors/`",
     "因原始数据的问题，`build.sh` 一定构建失败、暂时无法修复：注入的代码让构建本身崩溃、diff 改的是构建时才生成的文件、"
     "注入的代码不在被构建的程序里（两个版本的产物完全相同，task-server 镜像无法建立），或数据集有注入版的崩溃记录、但按它给的构建流程编不出注入版"
     "（原来在第三类、第四类）；以及原来没有生成 bundle、按第五类的方案也构建不了或转化不成有效任务（能构建但没有 PoV 能通过判定）的。"
     "**不要构建上传**。已经转化好、只是本机条件（磁盘、内存或网络）不够而没能实测的，留在原来的类别。"),
    ("第七类：潜在误报", "`PotentialFalsePositive/`",
     "第三类、第五类里空 PoC 也能通过判定的 bundle（自检 3 输出 PASS-DEGENERATE，2026-10-21 的要求）：判定会把不利用注入漏洞的提交判为成功。"
     "每个都用几个任意 PoC 实测过，分为“任意 PoC 都能通过”和“只有一部分任意 PoC 能通过”两种（第 4 节）。能构建、能推送，但不可用于 PoC 迭代。"),
]) + "\n")

md.append("## 4. 各类数量\n")
n_unc = sum(1 for r in R if not r["converted"] and r["path"] not in C5_SPECS)
md.append(("%d 个 bundle（1034 个任务中另有 %d 个没有生成 bundle，原因见 `newplatform_bundles/conversion_manifest.csv` 的 `review` 列）：\n"
           % (len(Q), n_unc)) if n_unc else "%d 个 bundle（1034 个任务都生成了 bundle）：\n" % len(Q))
statuses = ("pass", "pass-degenerate", "pass-no-gt", "fail", "not-built") + (("unverified",) if any(
    e["verification"] == "unverified" for e in Q.values()) else ())  # e.g. category-5 bundles that cannot be built here
# the PASS-DEGENERATE bundles self-checked again with arbitrary PoCs (any_poc.py): those that pass with any PoC
ANY_F = os.path.join(HERE, "verification", "any_poc.json")
ANY = json.load(open(ANY_F, encoding="utf-8")) if os.path.isfile(ANY_F) else None
ANY_COL = "其中：任意 PoC 都能通过（实测）"
any_cat = collections.Counter(Q[n]["category"] for n, e in (ANY or {}).get("bundles", {}).items()
                              if e.get("any_poc_passes") and Q.get(n, {}).get("verification") == "pass-degenerate")
AB = (ANY or {}).get("bundles", {})


def any_kind(n):
    """For a PASS-DEGENERATE bundle retested with arbitrary PoCs: "all", "some" or "untested"; else None."""
    if not ANY or Q[n]["verification"] != "pass-degenerate":
        return None
    e = AB.get(n) or {}
    return "untested" if not e.get("retested") else "all" if e["any_poc_passes"] else "some"


def any_group_note(names):
    """The summary table's note on a group of bundles: how they did with arbitrary PoCs."""
    k = collections.Counter(any_kind(n) for n in names if any_kind(n) and Q[n]["category"] != "第七类")
    parts = [("任意 PoV 都能通过 %d 个", "all"), ("只有部分任意 PoV 能通过 %d 个", "some"), ("本机未能重测 %d 个", "untested")]
    return "实测：" + "、".join(t % k[x] for t, x in parts if k[x]) if k else ""


def spaced(t):
    """t between Chinese text: a space only next to Latin letters, digits or code."""
    lat = lambda ch: ch.isascii() and not ch.isspace()
    return (" " if t and lat(t[0]) else "") + t + (" " if t and lat(t[-1]) else "")


def any_bundle_note(n):
    """The per-bundle table's note: what the arbitrary PoCs did."""
    kind = any_kind(n)
    if kind is None or Q[n]["category"] == "第七类":  # category 7's state says it already
        return ""
    if kind == "untested":
        return "实测任意 PoV：本机这次没能重新构建，未重测。"
    ins = AB[n]["inputs"]
    name = lambda k: ANY["inputs"].get(k, k)
    if kind == "all":
        return "实测任意 PoV：空 PoV、%s都通过，提交什么都能通过。" % "、".join(name(k) for k in ins)
    ok = [name(k) for k, x in ins.items() if x["passes"]]
    bad = [name(k) for k, x in ins.items() if not x["passes"]]
    return "实测任意 PoV：只有空 PoV%s能通过，%s不通过，不是提交什么都能通过。" % (
        " 和" + spaced("、".join(ok)) if ok else " ", spaced("、".join(bad)).lstrip())


def status_cells(get):
    out = []
    for s in statuses:
        out.append(get(s))
        if s == "pass-degenerate" and ANY:
            out.append(get(ANY_COL))
    return out


heads = status_cells(lambda s: s if s == ANY_COL else "本机验证：" + STATUS_ZH[s])
md.append(table(["分类", "目录", "数量"] + heads, [
    [SHOW.get(c, c), "`%s`" % folder_of[c], by_cat[c]] + status_cells(
        lambda s, c=c: any_cat[c] if s == ANY_COL else by_cat_status[(c, s)]) for c in CATS] +
    [["合计", "", len(Q)] + status_cells(
        lambda s: sum(any_cat.values()) if s == ANY_COL else sum(by_cat_status[(c, s)] for c in CATS))]) + "\n")
if ANY:
    deg = [n for n, e in Q.items() if e["verification"] == "pass-degenerate"]
    some = sorted(n for n in deg if AB.get(n, {}).get("retested") and not AB[n]["any_poc_passes"])
    gone = sorted(n for n in deg if not AB.get(n, {}).get("retested"))
    short = lambda n: n[len("cyberforge-"):-len("-poc-L1-oracle")]

    def partial_groups(names):
        """[(the arbitrary PoCs that passed, bundles)], the bundles grouped by which ones passed."""
        g = collections.OrderedDict()
        for n in names:
            ok = tuple(ANY["inputs"].get(k, k) for k, x in AB[n]["inputs"].items() if x["passes"])
            g.setdefault(ok, []).append(n)
        return sorted(g.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    unknown = collections.Counter(e["category"] for e in Q.values() if e["verification"] in ("not-built", "unverified"))
    md.append("“%s”：“通过但空输入也触发”的 %d 个 bundle（都在第七类）在本机重新构建，用几个任意的 PoV 代替标准答案再跑一遍自检"
              "（%s；命令行参数型换成%s），空 PoV 和这些 PoV 全部通过的才算。%s其余验证过的 bundle 都有不能通过的 PoV"
              "（空 PoV 或标准答案），不会出现提交什么都通过的情况；本机没建成或没验证的（%s）不知道。"
              "逐个结果在 `newplatform_bundles/conversion/verification/any_poc.json`。\n" % (
                  ANY_COL, len(deg),
                  "、".join(v for k, v in ANY["inputs"].items() if not k.startswith("any:argv")),
                  "、".join(v for k, v in ANY["inputs"].items() if k.startswith("any:argv")),
                  ("空 PoV 能通过、但不是任何 PoV 都能通过的 %d 个：%s。" % (len(some), "；".join(
                      "%s（%s）" % ("、".join(short(n) for n in ns), "任意 PoV 里只有%s能通过" % spaced("、".join(ok)) if ok else
                                   "任意 PoV 都不通过，只有空 PoV 能通过")
                      for ok, ns in partial_groups(some)))
                   if some else "") +
                  ("没能重新构建、未重测的 %d 个：%s。" % (len(gone), "、".join(short(n) for n in gone)) if gone else ""),
                  "、".join("%s %d 个" % (SHOW.get(c, c), unknown[c]) for c in CATS if unknown[c])))
md.append("按转换时的证据分级（tier：A = 有崩溃证据、harness 型；B = 有崩溃证据、命令行 / 程序型；C = 数据集里没有触发证据）：\n")
md.append(table(["分类", "A", "B", "C"], [[SHOW.get(c, c)] + [by_cat_tier[(c, t)] for t in "ABC"] for c in CATS]) + "\n")

# ---- the summary: what converted well, what still has a problem, who it comes from, what to do -------------
sys.path.insert(0, HERE)
import summary_groups as SG  # noqa: E402
UNC = json.load(open(os.path.join(HERE, "unconverted_review.json"), encoding="utf-8"))["tasks"]


def who(counter):
    return "、".join("%s %d" % (k, v) for k, v in counter.most_common()) if len(counter) > 1 else \
        (next(iter(counter)) if counter else "—")


def who_c5(sources):
    """A task's problem may be in both parties' files: count each party."""
    up = sum(1 for x in sources if SG.UP in x)
    team = sum(1 for x in sources if "提供数据的团队" in x)
    if not team:
        return SG.UP
    if not up:
        return "提供数据的团队"
    return "%s %d、提供数据的团队 %d（有的两者都有）" % (SG.UP, up, team) if up + team > len(sources) else \
        "%s %d、提供数据的团队 %d" % (SG.UP, up, team)


md.append("### 汇总：哪些转好了、哪些还有问题，问题出在哪里，怎么解决\n")
md.append("“问题出在”指原始数据里出问题的文件是谁提供的：**上游数据**是 [Cyb3rForge/CyberForge-projects]"
          "(https://github.com/Cyb3rForge/CyberForge-projects) 原有的文件（注入的 diff、exploit、sanitizer 报告、种子，本仓库的副本与上游完全相同）；"
          "**提供数据的团队**是他们新增或重新生成的文件（题面描述变体、hints.json、bug_report.txt、task_contract.json、60 个空的报告，见 "
          "`newplatform_bundles/conversion/upstream_comparison.md`、`upstream_diff.json`）；**本机环境**、**转换侧**不是原始数据的问题。"
          "第二类的一个 bundle 可能有几个问题，按问题分别计数；每个 bundle 的明细见第 6 节（“问题及影响”一栏的“来源”）。\n")
rows = [("第一类", "原始数据正常", by_cat["第一类"], "—", "无需处理", "可直接用于 PoC 迭代和轨迹生成")]
code_src = collections.defaultdict(collections.Counter)
groups = collections.OrderedDict()
group_names = {}
for name, e in sorted(Q.items()):
    c = e["category"]
    if c == "第一类":
        continue
    if c == "第二类" and e.get("codes"):
        for code in e["codes"]:
            code_src[code][(e.get("code_sources") or {}).get(code) or SG.UP] += 1
        continue
    g = SG.basis_row(c, e["basis"]) or (e["basis"], e.get("suggest") or e.get("fix") or "", e.get("status") or "")
    k = (c,) + g
    groups.setdefault(k, collections.Counter())[e.get("source_of_problem") or SG.UP] += 1
    group_names.setdefault(k, []).append(name)
for code, cnt in sorted(code_src.items(), key=lambda kv: -sum(kv[1].values())):
    problem, fix, state = SG.CODE_ROWS[code]
    rows.append(("第二类", problem, sum(cnt.values()), who(cnt), fix, state))
for c in ("第二类", "第三类", "待确认", "第六类"):
    for k, cnt in sorted(((k, v) for k, v in groups.items() if k[0] == c), key=lambda kv: -sum(kv[1].values())):
        note = any_group_note(group_names[k])
        rows.append((SHOW.get(c, c), k[1], sum(cnt.values()), who_c5(list(cnt.elements())) if c == "第六类" else who(cnt),
                     k[2], k[3] + ("（%s）" % note if note else "")))
c5_groups = collections.OrderedDict()
c5_names = {}
for name, e in sorted(C5.items()):
    k = (e.get("review") or "", SG.c5_state(e["verification"], e.get("unusable"), e.get("hardware")))
    c5_groups.setdefault(k, []).append(e.get("source_of_problem") or SG.UP)
    c5_names.setdefault(k, []).append(name)


C5_ORDER = list(SG.REVIEW_ROWS)
for (review, state), sources in sorted(c5_groups.items(), key=lambda kv: (C5_ORDER.index(kv[0][0]) if kv[0][0] in C5_ORDER
                                                                         else len(C5_ORDER), -len(kv[1]), kv[0][1])):
    note = any_group_note(c5_names[(review, state)])
    rows.append(("第五类", SG.REVIEW_ROWS.get(review, (review, ""))[0], len(sources), who_c5(sources),
                 SG.C5_FIX.get(review, ""), state + ("（%s）" % note if note else "")))
for k, cnt in sorted(((k, v) for k, v in groups.items() if k[0] == "第七类"), key=lambda kv: -sum(kv[1].values())):
    rows.append(("第七类", k[1], sum(cnt.values()), who_c5(list(cnt.elements())), k[2], k[3]))
unc = collections.Counter(v["category"] for k, v in UNC.items() if k not in C5_SPECS)
for cat, n in unc.most_common():
    problem, fix = SG.REVIEW_ROWS.get(cat, (cat, ""))
    rows.append(("未转换", problem, n, SG.UP, fix, "没有生成 bundle"))
md.append(table(["分类", "问题", "数量", "问题出在", "解决办法（已做 / 建议）", "现状"], rows) + "\n")
usable = by_cat["第一类"] + by_cat["第二类"]
c5_by = collections.Counter(SG.C5_SHORT["hardware" if e.get("hardware") else e["verification"]] for e in C5.values())
c5_hw = sum(1 for e in C5.values() if e.get("hardware"))
md.append("合计：1034 个任务里，**%d 个 bundle 可用于 PoC 迭代和轨迹生成**（第一类 %d、第二类 %d）；第三类 %d 个原始数据有严重问题"
          "（其中 %d 个没有标准答案）；第四类（待确认）%d 个%s；%s第六类 %d 个构建失败或无法转化（不要构建上传）；"
          "第七类 %d 个空 PoC 也能通过判定（潜在误报，其中 %d 个实测任意 PoC 都能通过）%s。"
          "除第六类外，其余 bundle 都能构建、能推送（第四类%s在本机没能验证构建）。\n"
          % (usable, by_cat["第一类"], by_cat["第二类"], by_cat["第三类"], nogt_cat["第三类"], by_cat["待确认"],
             "（其中 %d 个也没有标准答案）" % nogt_cat["待确认"] if nogt_cat["待确认"] else "",
             "第五类 %d 个（原来没有生成 bundle，现在按任务实现判定：%s）；" % (
                 by_cat["第五类"], "，".join("%s %d 个" % kv for kv in c5_by.most_common())) if C5 else "",
             by_cat["第六类"], by_cat["第七类"], any_cat["第七类"],
             "；另有 %d 个任务没有生成 bundle" % sum(unc.values()) if sum(unc.values()) else "；所有任务都生成了 bundle",
             "和第五类中本机条件不够的 %d 个" % c5_hw if c5_hw else ""))

md.append("## 5. 转换侧的问题（已改正，不计入原始数据问题）\n")
md.append(open(os.path.join(HERE, "conversion_fixes.md"), encoding="utf-8").read().strip() + "\n")

md.append("## 6. 原始数据有问题的 bundle\n")
md.append("第二类、第三类、第四类（待确认）、%s第六类、第七类的 bundle 逐个列在下面（第一类不列）。%s列的含义：" % (
    "第五类和" if C5 else "", "第五类的“分类”后是判定方式，“必要修改”的“已做”是现在的判定和标准答案。" if C5 else "") +
          "**转换后路径**相对 repo 根目录；**原始数据路径**是转换前的任务目录；"
          "**分类**后是简短依据；**问题及影响**说明问题的前因后果、为什么归到原始数据，以及对 PoC 迭代和轨迹质量的影响，"
          "最后的“来源”说明问题出在上游数据（Cyb3rForge/CyberForge-projects 原有的文件）还是提供数据的团队（他们新增或重新生成的文件）；**必要修改**分“已做”和"
          "“建议（未实施）”；**修改后状态**说明现在能否使用、还有哪些限制。每个 bundle 的机器可读版本在 "
          "`newplatform_bundles/conversion/quality.json`。\n")
HEAD = ["Bundle 名称", "转换后路径", "原始数据路径", "分类", "问题及影响", "必要修改", "修改后状态"]
SECTIONS = [("第二类", "第二类：原始数据轻微问题"), ("第三类", "第三类：原始数据严重问题"), ("待确认", "第四类：待确认")] + \
    ([("第五类", "第五类：按任务实现判定")] if C5 else []) + [("第六类", "第六类：构建失败或无法转化（other_errors/，不要构建上传）"),
                                                       ("第七类", "第七类：空 PoC 也能通过（PotentialFalsePositive/，潜在误报）")]
for i, (c, title) in enumerate(SECTIONS):
    title = "6.%d %s" % (i + 1, title)
    rows = []
    for name, e in sorted(Q.items()):
        if e["category"] != c:
            continue
        if e["fix"] in ("", "未修改。"):
            fix = "未做修改。"
        elif e["fix"].startswith(("无需修改", "报告无需修改", "题面未修改")):  # nothing changed, and why
            fix = e["fix"]
        else:
            fix = "已做：" + e["fix"]
        if e.get("suggest"):
            fix += "\n建议（未实施）：" + e["suggest"]
        rows.append((name, "%s%s" % (folder_of[c], name), e["source"], "%s：%s" % (SHOW.get(c, c), e["basis"]),
                     "问题：%s\n影响：%s\n来源：%s%s" % (e["problem"], e["impact"], e.get("source_of_problem") or "—",
                                                       "（%s）" % e["source_note"] if e.get("source_note") else ""),
                     fix, e["status"] + ("\n" + any_bundle_note(name) if any_bundle_note(name) else "")))
    md.append("### %s（%d 个）\n" % (title, len(rows)))
    md.append(table(HEAD, rows) + "\n")

md.append("## 7. 对分类标准和处理方案的建议\n")
env = [e for e in Q.values() if e["category"] == "待确认" and e["verification"] == "not-built"
       and e["basis"].startswith("本机未能完成构建")]
sugg = open(os.path.join(HERE, "suggestions.md"), encoding="utf-8").read().strip()
for k, v in {"N_ENV": len(env), "N_NET": sum(1 for e in env if "磁盘" not in e["problem"]),
             "N_DISK": sum(1 for e in env if "磁盘" in e["problem"]),
             "N_DEGEN": sum(1 for e in Q.values() if e["verification"] == "pass-degenerate"),
             # the arbitrary PoCs (any_poc.json): how many of them pass with whatever is submitted
             "ANY_SENTENCE": ("用几个任意的 PoV 实测，%d 个提交什么都能通过（第 4 节表里的“%s”一列）%s。" % (
                 sum(any_cat.values()), ANY_COL,
                 "，%d 个只有一部分任意 PoV 能通过" % len(some) if some else "") if ANY else ""),
             "DEGEN_SPLIT": "、".join("%s %d 个" % (SHOW.get(c, c), n) for c, n in sorted(collections.Counter(
                 e["category"] for e in Q.values() if e["verification"] == "pass-degenerate").items(),
                 key=lambda kv: CATS.index(kv[0]) if kv[0] in CATS else len(CATS))),
             # category 5, and the category-5 tasks that went to category 6
             "N_C56": sum(1 for e in Q.values() if e.get("how") == "c5" and e["category"] == "第六类"),
             "N_C6B": sum(1 for e in Q.values() if e.get("how") == "c5" and e["category"] == "第六类"
                          and e["basis"].startswith("第五类构建失败")),
             "N_C6U": sum(1 for e in Q.values() if e.get("how") == "c5" and e["category"] == "第六类"
                          and e["basis"].startswith("第五类无法转化")),
             "N_5": len(C5), "N_5P": sum(1 for e in C5.values() if e["verification"] == "pass"),
             "N_5G": sum(1 for e in C5.values() if e["verification"] == "pass-no-gt"),
             "N_5D": sum(1 for e in C5.values() if e["verification"] == "pass-degenerate"),
             # category 7, by the category it came from (quality.py seventh(): "原第三类" / "原第五类" in its basis)
             "N_7FROM5": sum(1 for e in Q.values() if e["category"] == "第七类" and "原第五类" in e["basis"]),
             "DEGEN_ORIGIN": "、".join("原%s %d 个" % (c, n) for c, n in sorted(collections.Counter(
                 re.search(r"原(第.类)", e["basis"]).group(1) for e in Q.values() if e["category"] == "第七类").items())),
             "N_5H": sum(1 for e in C5.values() if e.get("hardware")),
             "HW_TASKS": "、".join(sorted(e["source"].split("/projects/")[1].replace("/vulnerabilities/vulnerability_", " ")
                                         for e in C5.values() if e.get("hardware"))),
             "N_LFS": LFS["missing_objects"], "N_NOGT": N_NOGT, "NOGT_WHERE": NOGT_WHERE,
             "DISK_PROJECTS": "、".join("%s %d 个" % kv for kv in collections.Counter(
                 e["source"].split("/projects/")[1].split("/")[0] for e in env if "磁盘" in e["problem"]).most_common()),
             "NET_TASKS": "、".join(sorted(e["source"].split("/projects/")[1].replace("/vulnerabilities/vulnerability_", " ")
                                          for e in env if "磁盘" not in e["problem"]))}.items():
    sugg = sugg.replace("@@%s@@" % k, str(v))
md.append(sugg + "\n")
open(os.path.join(REPO, "README.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("README.md:", len(Q), "bundles", dict(by_cat))
