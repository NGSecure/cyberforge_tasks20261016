"""The groups of the repo README's summary table (make_root_readme.py): what the problem is, who it comes
from, what to do about it and what state the bundles are in. Rows of category 2 are per problem code
(quality.py); rows of categories 3 and 4 group the bundles by their basis; unconverted tasks by the
category of their review (unconverted_review.json)."""
import re

UP, TEAM, ENV, CONV = "上游数据", "提供数据的团队", "本机环境", "转换侧（判定规则）"

# category 2, by problem code: (problem, what was done / what to do, state)
CODE_ROWS = {
    "pov-not-trigger": ("数据集指定的 PoV（exploit_files/pov.bin）不触发：它不是 exploit 实际喂给 harness 的输入",
                        "已做：标准答案改用 exploit 在项目镜像里实际喂给 harness 的输入（只用于自检）。数据侧：上游按 exploit 实际运行的输入"
                        "重新导出 pov.bin；提供数据的团队生成的 hints.json 也把 pov.bin 记成了“成功的种子”，要一并改正", "可用"),
    "no-evidence": ("数据集缺少触发证据（sanitizer 报告为空或没有）",
                    "无需修改，以本机验证为准。数据侧：上游补上这些任务的 sanitizer 报告；提供数据的团队补的 60 个空报告应删掉或换成真实报告", "可用"),
    "lfs": ("标准答案只是 Git LFS 指针", "已做：按 SHA-256 从同一种子在其他任务里的副本还原。数据侧：上游把真实内容提交进仓库", "可用"),
    "report-not-own": ("sanitizer 报告是别的任务的（多个任务共用一份）", "无需修改，转换不依赖报告。数据侧：上游为每个任务单独生成报告", "可用"),
    "description-wrong": ("题面描述指错了位置", "已做：按数据集自己的报告改正（description_fixes.json，原文保留在 cyberforge_source.json）。"
                                         "数据侧：请生成描述的一方按实际崩溃位置重新生成描述变体", "可用"),
    "description": ("题面描述的漏洞类型与实际崩溃不符", "未修改（函数和文件仍指向注入位置）。建议统一改成实际崩溃类型；数据侧：生成描述时以 sanitizer 报告的崩溃类型为准",
                    "可用，agent 可能多走弯路"),
    "harness-injection": ("注入在 fuzz harness 自己的代码里，不在项目库代码里", "未修改。数据侧（上游）：把注入放进项目库代码；或在训练数据里单独标注",
                          "可用，作为真实漏洞的代表性差"),
    "constructed": ("exploit 的输入到不了注入的代码（格式不对）", "已做：按 exploit 的意图做最小修正（conversion/constructed/）。数据侧（上游）：修正 exploit", "可用"),
    "file-missing": ("触发文件没有随任务附带", "已做：从同项目其他任务找回同一文件。数据侧（上游）：打包时把种子放进任务目录", "可用"),
    "artifact-not-reproduce": ("fuzz 崩溃样本单独不复现", "已做：换成重跑 exploit 得到的输入。数据侧（上游）：保存能单独复现的输入", "可用"),
}

# categories 2 (manual review), 3, 4 and 6, by basis: (category, regex, problem, what to do, state)
BASIS_ROWS = [
    ("第二类", r"不稳定", "触发偶尔不稳定", "平台正式使用前对 /verify 连续跑 3 次，只保留结果一致的；数据侧（上游）：检查注入是否引入了非确定性", "可用，需多次验证"),
    ("第二类", r"构建脚本", "项目自带的构建脚本在编完 fuzzer 后失败（与注入无关）", "已做：按数据集的做法，只要 fuzzer 编出来就继续；数据侧（上游）：修构建脚本", "可用"),
    ("第三类", r"^空输入就能触发", "注入的漏洞不依赖输入：空输入就触发（PASS-DEGENERATE）", "数据侧（上游）：重新设计注入，让漏洞依赖输入内容；否则剔除", "不可用于 PoC 迭代"),
    ("第三类", r"^崩溃种子只有 Git LFS 指针", "崩溃种子只有 Git LFS 指针，没有标准答案",
     "已做：照常转成 bundle，不做标准答案自检（自检 3 只检查判定）。数据侧（上游）：向上游作者要 runs/fuzz_poc/_curated/ 里的原始种子，"
     "放进 conversion/lfs_objects/ 重新转换即可补上", "能构建、能判定；能否触发未验证"),
    ("第三类", r"报告是别的任务的", "报告是别的任务的，本任务的注入按 exploit 运行不崩溃", "数据侧（上游）：重新设计注入（现在多半只改变报错信息），并为每个任务单独生成报告", "不可用"),
    ("第三类", r"崩溃依赖 fuzz 过程", "崩溃依赖 fuzz 过程，没有单个输入能复现", "数据侧（上游）：保存能单独复现的崩溃输入；或用定向 fuzz 补一个（新标准答案不来自原始数据，需单独标注）", "不可用"),
    ("第三类", r"安全版也崩溃|上游 bug|安全版本身", "安全版也崩溃：崩溃来自项目本身的 bug，不是注入的", "数据侧（上游）：换注入点或换没有这个 bug 的安全版本", "不可用"),
    ("第三类", r"注入的代码不在|diff 是坏的|让构建本身崩溃|构建时生成的文件|两个版本构建完全相同", "注入本身有问题：不在被测程序里，或 diff 坏了（注入版编译不过，构建照常完成）",
     "数据侧（上游）：重新做注入", "能构建、能推送；不可用于 PoC 迭代"),
    ("第三类", r"内存分配失败", "注入的漏洞只在内存分配失败时才走到", "数据侧（上游）：重新设计注入", "不可用"),
    ("第三类", r"判定方向相反", "判定方向相反（安全版“崩溃”，或漏洞版只是返回值不同）", "数据侧（上游）：重新设计 exploit 或注入", "不可用"),
    ("第三类", r"只打印结论|作者自写的程序|exploit 自己拷贝|行为差异型", "exploit 没有真正触发注入的代码（只打印结论、崩溃来自 exploit 自己的程序、行为差异型）",
     "数据侧（上游）：重写 exploit；否则剔除", "不可用"),
    ("第三类", r"超时", "漏洞版只表现为超时", "判定只认崩溃：剔除，或重新设计注入", "不可用"),
    ("第三类", r"泄漏|内存超限", "证据只是很小的泄漏，或是 libFuzzer 读输入时的内存超限，与项目代码无关", "数据侧（上游）：重新设计注入或重新生成证据", "不可用"),
    ("第三类", r"不触发|没有保存|到不了|没有触发证据", "数据集没有能触发的输入（PoV、exploit 的输入不触发，报告用的输入没有保存）",
     "数据侧（上游）：重跑数据集的流水线并保存崩溃输入；或用定向 fuzz / 人工构造 PoV（新标准答案不来自原始数据，需单独标注）", "不可用（缺可用 PoV）"),
    ("待确认", r"^本机未能完成构建", "本机没能构建：磁盘配额不够（arrow 是本机的 GitHub 代理不放行它要下载的依赖）",
     "在磁盘充足（100 GB 以上）、能直连公网的机器上运行 build.sh；三项自检通过后按数据集证据归第一或第二类", "待验证"),
    ("待确认", r"编不出注入版", "数据集有注入版的崩溃记录，但按它的构建流程编不出注入版",
     "数据侧（上游）：修正注入或构建流程；README 表里给出了预计能解决的最小改动，需要决定是否接受", "待决定"),
    ("待确认", r"转换侧限制", "判定规则认不出宏里的注入", "转换侧：为这个任务单独设定判定规则", "待处理"),
    ("第六类", r"让构建本身崩溃|构建时生成的文件|两个版本构建完全相同", "注入让构建失败：注入的代码让构建本身崩溃、diff 改的是构建时才生成的文件，"
     "或注入的代码不在被构建的程序里（两个版本的产物完全相同，task-server 镜像无法建立）", "数据侧（上游）：重新做注入", "构建会失败，不要构建上传"),
    ("第六类", r"编不出注入版", "数据集有注入版的崩溃记录，但按它的构建流程编不出注入版",
     "数据侧（上游）：修正注入或构建流程；第 6 节的表里给出了预计能解决的最小改动，接受后可重新转换、验证", "构建会失败，暂不构建上传"),
    ("第六类", r"^第五类构建失败", "原来没有生成 bundle、按第五类的方案也构建不了：注入的代码不在被构建的程序里（两个版本的产物完全相同）、"
     "diff 让漏洞版编译不过，或项目本身在数据集的镜像里就构建不了（open62541）",
     "数据侧（上游）：重新做注入；open62541 还要修好项目在镜像里的构建", "构建会失败，不要构建上传"),
    ("第六类", r"^第五类无法转化", "原来没有生成 bundle、按第五类的方案也转化不成有效任务：能构建，但没有 PoV 能通过判定"
     "（注入只是注释或死代码、改动走不到或没有可观察的效果、注入是加固而非漏洞、需要判定环境给不了的权限或资源）",
     "数据侧（上游）：重新设计注入；否则剔除", "不要上传"),
]

# unconverted tasks, by review category: (problem, what to do)
REVIEW_ROWS = {
    "behavioral": ("行为差异型 oracle：两个版本输出不同，但都不崩溃", "需要支持“输出差异”判定的平台；或重新设计注入使其崩溃"),
    "technical": ("exploit 自己构建程序或容器、要联网、从附带的数据文件读 payload、依赖环境变量，或 payload 是 GB 级文件，判定服务无法照做",
                  "改写 exploit，使 PoV 是一个可提交的输入；或扩展判定，支持环境变量和附带文件"),
    "unit-test": ("触发靠项目自带的单元测试或测试程序，没有攻击者提供的输入", "改写 exploit，改为给 harness 或项目程序的输入；否则剔除"),
    "fake-exploit": ("exploit 根本没有执行注入的代码（grep 源码、打印伪造的 sanitizer 报告、制造无关的崩溃）", "重新生成 exploit；否则剔除"),
    "weak-oracle": ("只有超时、数据竞争或超大输入导致的 OOM，判定区分不了两个版本", "剔除，或重新设计注入"),
    "lost-input": ("有崩溃证据、harness 已知，但触发崩溃的输入没有保存", "重跑数据集的流水线并保存崩溃输入；或用定向 fuzz 补一个"),
    "candidates": ("exploit 依次试几个输入，没有记录是哪一个触发的（实测都不触发）", "重跑并记录触发的输入"),
    "race": ("exploit 依赖与 harness 同时运行的后台进程，单个输入复现不了", "剔除，或重新设计成单个输入可复现"),
    "no-evidence": ("报告为空，输入是随机的或有多个，没有可用的标准答案", "重跑数据集的流水线并保存输入"),
    "empty-input": ("数据集里触发崩溃的输入是空文件（任何空文件都能通过）", "重新设计注入"),
}


def basis_row(category, basis):
    for cat, rx, problem, fix, state in BASIS_ROWS:
        if cat == category and re.search(rx, basis):
            return problem, fix, state
    return None


# category 5, by the verification here: the state column of the summary table
C5_STATE = {"pass": "可用（本机验证：标准答案按本任务的规则通过）", "pass-no-gt": "能构建、能判定；没有标准答案，能否触发未验证",
            "pass-degenerate": "空 PoV 也通过，不可用于 PoC 迭代", "fail": "本机验证没有通过", "not-built": "本机没能构建，待验证",
            "unverified": "待验证", "stale": "待重验"}


C5_HARDWARE = "已转化；本机条件不够（磁盘、内存或网络），未实测"


def c5_state(status, unusable="", hardware=""):
    if unusable:
        return "不可用（原因见第 6.4 节）"
    return C5_HARDWARE if hardware else C5_STATE.get(status, status)


# the same, short, for the totals sentence
C5_SHORT = {"pass": "可用", "pass-no-gt": "没有标准答案、能否触发未验证", "pass-degenerate": "空 PoV 也通过",
            "hardware": "已转化但本机条件不够、没能实测"}


# category 5, by the reason the task had no bundle before (unconverted_review.json): what its bundle does now
C5_FIX = {
    "behavioral": "已做：按输出差分或输出匹配判定（两个版本各运行，比较退出状态、输出或留下的文件），PoV 交给项目的程序，"
                  "或交给 exploit 自己的测试程序（改为从 PoV 读输入）",
    "technical": "已做：判定端在两个构建里编译 exploit 自己的程序（改为从 PoV 读输入）；PoV 可以是带环境变量和附带文件的 tar 包；"
                 "exploit 私自构建的程序换成构建产出的同一程序；要联网的允许本机套接字并由判定端启动 exploit 的应答程序",
    "unit-test": "已做：把单元测试的触发步骤写成 driver（从 PoV 读参数），或直接运行项目的程序和测试程序，按崩溃、输出差分或输出匹配判定；"
                 "标准答案取自测试用例",
    "fake-exploit": "已做：按注入的代码选 harness 或写 driver 判定（崩溃、输出差分、输出匹配或超时）；数据集没有真正触发的输入，多数没有标准答案",
    "weak-oracle": "已做：按超时差分、libFuzzer 内存超限的输出匹配，或判定端固定 ASan 分配上限后的崩溃差分判定",
    "lost-input": "已做：标准答案取自同项目其他任务里同一崩溃的样本或转换重放录到的输入，崩溃差分",
    "candidates": "已做：逐个实测 exploit 试过的输入，选出触发的作标准答案；按崩溃或输出匹配判定",
    "race": "已做：用确定性的输入或判定端预置的文件代替与 harness 并发的后台进程，崩溃差分",
    "no-evidence": "已做：按 exploit 的输入构造标准答案、按输出匹配判定，或说明为什么不可用",
    "empty-input": "已做：照常转换，标准答案是空文件（任何输入都触发）",
}
