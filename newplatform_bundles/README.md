# CyberForge → 新平台 bundles

`cyberforge_tasks20261016/`（CyberForge 数据集）转换出的新平台 bundle，与原数据集分开存放，原数据未做任何修改。本目录放 A 类 bundle，以及三类共用的转换工具、清单和报告。

## 目录

转换结果分在 repo 根目录下三个平级的目录里：

| 目录 | bundle 数 | 内容 |
|---|---|---|
| `newplatform_bundles/`（本目录，A 类） | 741 | 有崩溃证据；PoV 是喂给 OSS-Fuzz harness 的一个输入文件（`/out/<harness> <poc>`），与 ARVO bundle 同一范式 |
| `newplatform_bundles2/`（B 类） | 64 | 有崩溃证据；PoV 交给项目自己的程序：CLI 的输入文件 / 标准输入 / 命令行参数（29 个），或者是一个链接项目代码的 C/C++ 程序（35 个） |
| `newplatform_bundles3/`（C 类） | 95 | 数据集里没有触发证据（报告为空、报告里没有崩溃、超时、或报告与 exploit.sh 自己的判定条件矛盾）。标准答案没有经过验证，以 `build.sh` 自检 3 为准；其中 63 个是 harness 型，32 个是 CLI / 程序型 |

A 类 bundle 的位置与上一版相同（本目录下的 `cyberforge-*`），但和 B、C 一起按新模板重新生成了：镜像标签升为 `v0.0.2`，判定服务做了隔离（原因见 `CONVERSION_REPORT.md` 4.7），已推送过旧版本的请用新版本替换。

本目录还有（三个目录共用）：

- `conversion_manifest.csv`：全部 1034 个任务的去向（tier、是否转换、所在目录、bundle、PoV 类型、原因、标准答案来源等）。另有 134 个任务没有生成 bundle，逐个人工复核过，原因记录在这里的 `review`、`review_note` 列（exploit 根本没有执行注入的代码、行为差异型 oracle、只跑单元测试、触发输入没有保存或是空文件等，见 `CONVERSION_REPORT.md` 第 5 节）
- `CONVERSION_REPORT.md`：转换方法、分级统计、验证情况、发现的问题
- `conversion/`：转换工具（`SKILL.md` 说明原理与流程）。`replay_exploits.py`、`replay_deep.py` 负责重放 exploit 并记录它实际运行的命令和输入，`report_inputs.py` 从镜像里取出报告指明崩溃的项目文件，`classify.py`、`deep_recipe.py`、`convert.py`、`validate.py`、`scan_snapshots.py` 和 `templates/` 负责分级与生成。`replay/`、`replay_deep/` 是两种重放的记录，`report_inputs/` 是从镜像源码快照里取出的、报告指明崩溃的项目文件，`snapshot_scan/` 是基础镜像快照层的扫描结果，`records.json` 是分级结果，`unconverted_review.json` 是未转换任务的人工复核

## 每个 bundle 的使用（与 ARVO bundle 相同的两步）

```bash
bash newplatform_bundles/<bundle>/build.sh      # 公网：构建 main + task-server 镜像，并跑 3 项阻塞式自检
bash newplatform_bundles/<bundle>/push.sh       # 上传网络：推送镜像并回填 task.toml [environment]
```

B、C 类同样用法（`newplatform_bundles2/<bundle>/`、`newplatform_bundles3/<bundle>/`）。

Docker Hub 匿名拉取每小时约 100 次。`build.sh` 拉不到基础镜像时，会改从 `mirror.gcr.io` 拉同一个 digest，内容完全相同；也可以先 `docker login`。

`build.sh` 只有在三项自检全部通过时才会打印 `PASS`：

1. agent 镜像里没有干净源码、git 历史、`/opt/src_snapshot.tar`（安全版源码快照）及其他快照残留；
2. agent 镜像里找不到注入改动的"安全版"代码行（防止通过对比源码得到答案）；
3. 标准答案在漏洞版上触发、在安全版上不触发（差分判定成立）。

自检 3 失败说明这个任务的标准答案在重建的镜像里无法复现，**不要推送**，记录下来即可。C 类出现这种情况属于预期。

## bundle 结构

```
instruction.md  task.toml  build.sh  push.sh  cyberforge_source.json(来源、证据、PoV 类型)
environment/    Dockerfile(agent 沙箱) docker-compose.yaml submit.sh description.txt
                task-server/{Dockerfile, task_server.py, judge.json, cf_delta.py}
tests/          test.sh verify.py            (与 ARVO bundle 相同)
solution/       solve.sh                     (标准答案；>256KB 时从 task-server /solve 取)
build/          inject_vulnerability.diff ground_truth_poc setup/ snapshot_residue.txt secure_lines.txt
                aux/（仅 CLI / 程序型：exploit 的命令行用到的其他文件）
                (构建输入，含机密，不会进入 agent 镜像)
```

两类 bundle 的 agent 沙箱、`tests/`、`submit.sh` 和 task-server 接口完全相同，区别只在 task-server 怎么运行 PoV：

- **harness 型**（A 类，以及部分 C 类）：`judge.json` 记录 harness 名，判定为 `/out/<harness> <poc>`；
- **CLI / 程序型**（B 类，以及部分 C 类）：`judge.json` 记录 exploit 实际运行的命令（`conversion/replay_deep.py` 在项目真实镜像里重放 exploit.sh 录下来的），判定时用 PoV 替换 exploit 自己的输入再跑一遍。程序型 PoV 是一个 C/C++ 源文件，按 exploit 的编译命令编译、运行；只有栈里经过注入改动所在文件的 sanitizer 报告才算触发。

两类 task-server 都把安全版和漏洞版放在同一路径下：每次运行前把该版本特有的文件复制到位，大小、权限、mtime 都一致。PoV 进程以每次新建的无权限用户身份运行，没有网络，读不到标准答案和判定配置；它在一次运行里留下的进程和文件，会在下一次运行前全部清掉。`/verify` 对两个版本的运行顺序随机。
