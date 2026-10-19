#!/usr/bin/env python3
"""Write the repository's README.md: the raw data check, the classification of the bundles by
the quality of their dataset task (quality.json), and a table of every bundle whose dataset task
has a problem.

    python3 -I make_root_readme.py <repo>
"""
import collections
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(sys.argv[1])
CATS = ("第一类", "第二类", "第三类", "待确认")
STATUS_ZH = {"pass": "通过", "pass-degenerate": "通过但空输入也触发", "fail": "不通过", "not-built": "本机未建成",
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
by_cat = collections.Counter(e["category"] for e in Q.values())
by_cat_status = collections.Counter((e["category"], e["verification"]) for e in Q.values())
by_cat_tier = collections.Counter((e["category"], tier[e["source"]]) for e in Q.values())
# bundles whose description was corrected (conversion/description_fixes.json)
N_DESC_FIX = sum(1 for e in Q.values() if "题面描述指错了位置" in e.get("basis", ""))
folder_of = {"第一类": "newplatform_bundles/", "第二类": "newplatform_bundles2/", "第三类": "newplatform_bundles3/",
             "待确认": "newplatform_bundles3/"}

# ---- the raw data: where it is, and whether it changed since it was uploaded ----------------------
DATA = "cyberforge_tasks20261016"
log = git("log", "--format=%h %ad %s", "--date=format:%Y-%m-%d %H:%M", "--", DATA).splitlines()
upload = git("log", "--format=%h %ad %s", "--date=format:%Y-%m-%d %H:%M", "--diff-filter=A", "-1", "--",
             "cyberforge-tasks-1034/manifest.csv")
tree_head = git("rev-parse", "HEAD:" + DATA)
first = git("log", "--format=%h", "--diff-filter=A", "-1", "--", "cyberforge-tasks-1034/manifest.csv")
tree_upload = git("rev-parse", "%s:cyberforge-tasks-1034" % first) if first else ""
dirty = git("status", "--porcelain", "--", DATA)
n_files = len(git("ls-files", DATA).splitlines())

md = []
md.append("# cyberforge_tasks20261016\n")
md.append("CyberForge 数据集（80 个 OSS-Fuzz C/C++ 项目上的 1034 个 LLM 注入漏洞任务）及其转换出的新平台 PoV bundle。"
          "本文说明原始数据的核对结果、bundle 按原始数据质量的分类（标准、数量），并逐个列出原始数据有问题的 bundle。\n")
md.append(table(["路径", "内容"], [
    ("`%s/`" % DATA, "原始数据（手动上传，转换只读不改）：`manifest.csv` + `projects/<项目>/vulnerabilities/<任务>/`"),
    ("`newplatform_bundles/`", "第一类 bundle（%d 个），以及三类共用的转换工具 `conversion/`、任务去向清单 `conversion_manifest.csv`、"
                               "转换报告 `CONVERSION_REPORT.md`" % by_cat["第一类"]),
    ("`newplatform_bundles2/`", "第二类 bundle（%d 个）" % by_cat["第二类"]),
    ("`newplatform_bundles3/`", "第三类（%d 个）和待确认（%d 个）bundle" % (by_cat["第三类"], by_cat["待确认"])),
]) + "\n")

md.append("## 1. 原始数据核对\n")
md.append("- **原始数据就在本仓库的 `%s/` 里**：%d 个文件，`manifest.csv` 列出 1034 个任务；转换工具只从这里读取。" % (DATA, n_files))
md.append("- **上传后没有被修改过**：它由提交 %s 上传（当时目录名为 `cyberforge-tasks-1034/`），随后的提交 %s 只把目录改名为 `%s/`，"
          "内容不变（两次提交里这个目录的 git tree 都是 `%s`%s）；此后没有任何提交改动过这个目录，工作区也没有未提交的改动%s。"
          "转换产生的文件全部在三个 `newplatform_bundles*/` 目录里。"
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
          "其中 9 个任务的崩溃种子就在缺的里面，没有生成 bundle，其余缺的是不进入 bundle 的语料。"
          "缺失清单：`newplatform_bundles/conversion/lfs_objects/missing.json`。用到了还原文件的 bundle 在下表里标为第二类。\n"
          % (LFS["pointers"], lfs_have + LFS["missing_objects"], lfs_have, LFS["restored"], LFS["missing_objects"],
             sum(len(v) for v in LFS["tasks"].values()), len(LFS["tasks"])))

md.append("## 2. 背景：bundle、PoC 迭代与判定\n")
md.append("- **数据集的一个任务**：在开源项目的一个安全版本（`secure_base_commit`）上，由 LLM 注入一个内存安全漏洞"
          "（`inject_vulnerability.diff`），并附上 exploit.sh、PoV 文件、sanitizer 报告、漏洞描述等。")
md.append("- **一个 bundle**：新平台上的一个 PoV 任务。agent 拿到注入后的源码和一句漏洞描述，提交一个 PoV（喂给 fuzz harness 的输入文件、"
          "命令行参数，或链接项目代码的 C/C++ 程序）；判定服务（task-server）把同一个 PoV 在**注入版**和**安全版**上各运行一次，"
          "注入版崩溃（sanitizer 报错或致命信号）而安全版不崩溃，才算成功。agent 可以反复提交、根据反馈修改，平台记录整个过程（轨迹）。")
md.append("- **标准答案**（`build/ground_truth_poc`）：一个已知能成功的 PoV，只用于自检，不给 agent 看。")
md.append("- **`build.sh` 的三项自检**：构建 agent 镜像和 task-server 镜像（安全版、注入版各编一次）后检查：① agent 镜像里没有安全版源码等残留；"
          "② agent 镜像里找不到注入改动的安全版代码行；③ 标准答案让注入版崩溃、安全版不崩溃，并且空输入两个版本都不崩溃"
          "（否则输出 PASS-DEGENERATE）。")
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
     "数据集里没有只让注入版崩溃的输入（exploit 的输入不触发、报告用的输入没保存、报告是别的程序或别的任务的、安全版也崩溃），"
     "注入的代码不在被测程序里或让构建失败，注入的漏洞不依赖输入（空输入就触发，PASS-DEGENERATE）或实际走不到（只在内存分配失败时），"
     "漏洞版只表现为超时；修复需要重新构造 PoV 或重新设计注入，或者修复后仍会明显影响轨迹质量。"),
    ("待确认", "`newplatform_bundles3/`",
     "无法确定：本机没能构建（需要公网、磁盘不够），或者原因不能确定在原始数据（例如数据集有注入版的崩溃记录、但按它给的构建流程编不出注入版；"
     "判定规则本身的限制）。"),
]) + "\n")

md.append("## 4. 各类数量\n")
md.append("%d 个 bundle（1034 个任务中另有 %d 个没有生成 bundle，原因见 `newplatform_bundles/conversion_manifest.csv` 的 `review` 列）：\n"
          % (len(Q), len(R) - n_conv))
statuses = ("pass", "pass-degenerate", "fail", "not-built")
md.append(table(["分类", "目录", "数量"] + ["本机验证：" + STATUS_ZH[s] for s in statuses], [
    [c, "`%s`" % folder_of[c], by_cat[c]] + [by_cat_status[(c, s)] for s in statuses] for c in CATS] +
    [["合计", "", len(Q)] + [sum(by_cat_status[(c, s)] for c in CATS) for s in statuses]]) + "\n")
md.append("按转换时的证据分级（tier：A = 有崩溃证据、harness 型；B = 有崩溃证据、命令行 / 程序型；C = 数据集里没有触发证据）：\n")
md.append(table(["分类", "A", "B", "C"], [[c] + [by_cat_tier[(c, t)] for t in "ABC"] for c in CATS]) + "\n")

md.append("## 5. 转换侧的问题（已改正，不计入原始数据问题）\n")
md.append(open(os.path.join(HERE, "conversion_fixes.md"), encoding="utf-8").read().strip() + "\n")

md.append("## 6. 原始数据有问题的 bundle\n")
md.append("第二类、第三类和待确认的 bundle 逐个列在下面（第一类不列）。列的含义：**转换后路径**相对 repo 根目录；**原始数据路径**是转换前的任务目录；"
          "**分类**后是简短依据；**问题及影响**说明问题的前因后果、为什么归到原始数据，以及对 PoC 迭代和轨迹质量的影响；**必要修改**分“已做”和"
          "“建议（未实施）”；**修改后状态**说明现在能否使用、还有哪些限制。每个 bundle 的机器可读版本在 "
          "`newplatform_bundles/conversion/quality.json`。\n")
HEAD = ["Bundle 名称", "转换后路径", "原始数据路径", "分类", "问题及影响", "必要修改", "修改后状态"]
for c, title in (("第二类", "6.1 第二类：原始数据轻微问题"), ("第三类", "6.2 第三类：原始数据严重问题"), ("待确认", "6.3 待确认")):
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
        rows.append((name, "%s%s" % (folder_of[c], name), e["source"], "%s：%s" % (c, e["basis"]),
                     "问题：%s\n影响：%s" % (e["problem"], e["impact"]), fix, e["status"]))
    md.append("### %s（%d 个）\n" % (title, len(rows)))
    md.append(table(HEAD, rows) + "\n")

md.append("## 7. 对分类标准和处理方案的建议\n")
env = [e for e in Q.values() if e["category"] == "待确认" and e["verification"] == "not-built"
       and e["basis"].startswith("本机未能完成构建")]
sugg = open(os.path.join(HERE, "suggestions.md"), encoding="utf-8").read().strip()
for k, v in {"N_ENV": len(env), "N_NET": sum(1 for e in env if "磁盘" not in e["problem"]),
             "N_DISK": sum(1 for e in env if "磁盘" in e["problem"]),
             "N_DEGEN": sum(1 for e in Q.values() if e["verification"] == "pass-degenerate"),
             "N_LFS": LFS["missing_objects"]}.items():
    sugg = sugg.replace("@@%s@@" % k, str(v))
md.append(sugg + "\n")
open(os.path.join(REPO, "README.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("README.md:", len(Q), "bundles", dict(by_cat))
