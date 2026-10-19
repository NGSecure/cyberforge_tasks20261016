# CyberForge → 新平台 bundles（第一类）

`../cyberforge_tasks20261016/`（CyberForge 数据集）转换出的新平台 bundle，与原数据集分开存放，原数据未做任何修改。bundle 按**原始数据（数据集任务本身）的质量**分在 repo 根目录下四个平级的目录里；本目录放**第一类**，以及各类共用的转换工具、清单和报告。分类标准、各类数量和每个原始数据有问题的 bundle 的说明见 repo 根目录的 `README.md`。

## 目录

| 目录 | bundle 数 | 内容 |
|---|---|---|
| `newplatform_bundles/`（本目录） | 522 | 第一类：原始数据正常，本机三项自检全部通过，可直接用于 PoC 迭代和轨迹生成 |
| `newplatform_bundles2/` | 125 | 第二类：原始数据有轻微问题（已做少量修改，或不修改也不影响轨迹质量），本机三项自检全部通过 |
| `newplatform_bundles3/` | 183 | 第三类：原始数据有严重问题，不应用于 PoC 迭代 |
| `newplatform_bundles4/` | 73 | 第四类（待确认）：本机没能构建，或不能断定是原始数据的问题 |

四个目录的 bundle 结构和用法完全相同；PoV 有两种形态：harness 型（喂给 OSS-Fuzz harness 的一个输入文件，810 个）和 CLI / 程序型（交给项目自己的程序：CLI 的输入文件、标准输入或命令行参数，或者是一个链接项目代码的 C/C++ 程序，93 个）。所有 bundle 都按当前模板生成（镜像标签 `v0.0.2`，判定服务做了隔离，原因见 `CONVERSION_REPORT.md` 4.7），已推送过旧版本的请用新版本替换。

本目录还有（四个目录共用）：

- `conversion_manifest.csv`：全部 1034 个任务的去向（tier、是否转换、所在目录、分类 `quality` / `quality_basis`、bundle、PoV 类型、原因、标准答案来源、验证结果等）。另有 131 个任务没有生成 bundle，逐个人工复核过，原因记录在这里的 `review`、`review_note` 列（exploit 根本没有执行注入的代码、行为差异型 oracle、只跑单元测试、触发输入没有保存或是空文件等，见 `CONVERSION_REPORT.md` 第 5 节）
- `CONVERSION_REPORT.md`：转换方法、统计、验证情况、发现的问题
- `conversion/`：转换工具（`SKILL.md` 说明原理与流程）。`replay_exploits.py`、`replay_deep.py` 负责重放 exploit 并记录它实际运行的命令和输入，`report_inputs.py` 从镜像里取出报告指明崩溃的项目文件，`select_candidates.py` 在重建的漏洞版上实际运行 exploit 的候选输入、找出触发的那一个，`classify.py`、`deep_recipe.py`、`convert.py`、`validate.py`、`scan_snapshots.py` 和 `templates/` 负责分级与生成，`verify_bundles.py`（及 `verify_diag.py`、`verify_exploit.py`）在本机实际构建和验证，`choose_gt.py` 按验证结果选标准答案，`quality.py` 按原始数据质量分类（`quality.json`，人工复核在 `quality_review.json`），`make_root_readme.py` 写 repo 根目录的 `README.md`。`replay/`、`replay_deep/` 是两种重放的记录，`report_inputs/` 是从镜像源码快照里取出的、报告指明崩溃的项目文件，`constructed/` 是按 exploit 意图修正过的输入（附说明），`candidates/` 是候选输入的实测结果，`snapshot_scan/` 是基础镜像快照层的扫描结果，`verification/` 是本机验证的记录，`records.json` 是分级结果，`unconverted_review.json` 是未转换任务的人工复核

## 每个 bundle 的使用（与 ARVO bundle 相同的两步）

```bash
bash newplatform_bundles/<bundle>/build.sh      # 公网：构建 main + task-server 镜像，并跑 3 项阻塞式自检
bash newplatform_bundles/<bundle>/push.sh       # 上传网络：推送镜像并回填 task.toml [environment]
```

另外三个目录同样用法（`newplatform_bundles2/<bundle>/`、`newplatform_bundles3/<bundle>/`、`newplatform_bundles4/<bundle>/`）。

Docker Hub 匿名拉取每小时约 100 次。`build.sh` 拉不到基础镜像时，会改从 `mirror.gcr.io` 拉同一个 digest，内容完全相同；也可以先 `docker login`。

`build.sh` 只有在三项自检全部通过时才会打印 `PASS`：

1. agent 镜像里没有干净源码、git 历史、`/opt/src_snapshot.tar`（安全版源码快照）及其他快照残留；
2. agent 镜像里找不到注入改动的"安全版"代码行（防止通过对比源码得到答案）；
3. 标准答案在漏洞版上触发、在安全版上不触发（差分判定成立），并且空输入两个版本都不触发（否则打印 `PASS-DEGENERATE`：任何提交都能通过）。

自检 3 失败说明这个任务的标准答案在重建的镜像里无法复现，**不要推送**，记录下来即可。第一、二类在本机全部通过；第三类和待确认出现失败属于预期（原因见 repo 根目录 `README.md` 的表）。

## bundle 结构

```
instruction.md  task.toml  build.sh  push.sh  cyberforge_source.json(来源、证据、PoV 类型、分类)
environment/    Dockerfile(agent 沙箱) docker-compose.yaml submit.sh description.txt
                task-server/{Dockerfile, task_server.py, judge.json, cf_delta.py}
tests/          test.sh verify.py            (与 ARVO bundle 相同)
solution/       solve.sh                     (标准答案；>256KB 时从 task-server /solve 取)
build/          inject_vulnerability.diff ground_truth_poc setup/ snapshot_residue.txt secure_lines.txt
                aux/（仅 CLI / 程序型：exploit 的命令行用到的其他文件）
                (构建输入，含机密，不会进入 agent 镜像)
```

两类 bundle 的 agent 沙箱、`tests/`、`submit.sh` 和 task-server 接口完全相同，区别只在 task-server 怎么运行 PoV：

- **harness 型**：`judge.json` 记录 harness 名，判定为 `/out/<harness> <poc>`；
- **CLI / 程序型**：`judge.json` 记录 exploit 实际运行的命令（`conversion/replay_deep.py` 在项目真实镜像里重放 exploit.sh 录下来的），判定时用 PoV 替换 exploit 自己的输入再跑一遍。程序型 PoV 是一个 C/C++ 源文件，按 exploit 的编译命令编译、运行；只有栈里经过注入改动所在文件的 sanitizer 报告才算触发（sanitizer 打印不出源码位置的栈帧，判定服务用 llvm-symbolizer 补上；程序 abort 时也打印栈）。

两类 task-server 都把安全版和漏洞版放在同一路径下：每次运行前把该版本特有的文件复制到位，大小、权限、mtime 都一致。PoV 进程以每次新建的无权限用户身份运行，没有网络，读不到标准答案和判定配置；它在一次运行里留下的进程和文件，会在下一次运行前全部清掉。`/verify` 对两个版本的运行顺序随机。
