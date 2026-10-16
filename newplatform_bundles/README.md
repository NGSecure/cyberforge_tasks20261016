# CyberForge → 新平台 bundles

本目录是 `cyberforge_tasks20261016/`（CyberForge 数据集）转换出的新平台 bundle，与原数据集分开存放，原数据未做任何修改。

- `cyberforge-<project>-<fz|wf-rag|wf-llm>-<n>-poc-L1-oracle/`：462 个 bundle（数据集中的 tier-A 任务，每个任务一个）
- `conversion_manifest.csv`：全部 1034 个任务的去向（tier、原因、对应 bundle、harness、标准答案来源等）
- `CONVERSION_REPORT.md`：转换方法、分级统计、发现的问题
- `conversion/`：转换工具（`SKILL.md` 说明原理与流程；`classify.py`、`scan_snapshots.py`、`convert.py`、`validate.py`、`templates/`；`snapshot_scan/` 是各基础镜像快照层的扫描结果；`records.json` 是分级结果）

## 每个 bundle 的使用（与 ARVO bundle 相同的两步）

```bash
docker login                                    # Docker Hub 匿名拉取有限流
bash <bundle>/build.sh                          # 公网：构建 main + task-server 镜像，并跑 3 项阻塞式自检
bash <bundle>/push.sh                           # 上传网络：推送镜像并回填 task.toml [environment]
```

`build.sh` 只有在三项自检全部通过时才会打印 `PASS`：

1. agent 镜像里没有干净源码、git 历史、`/opt/src_snapshot.tar`（安全版源码快照）及其他快照残留；
2. agent 镜像里找不到注入改动的"安全版"代码行（防止通过对比源码得到答案）；
3. 标准答案 PoC 在漏洞版上崩溃、在安全版上不崩溃（差分判定成立）。

自检 3 失败说明该任务的标准答案在重建的镜像里无法复现，**不要推送**，记录下来即可（详见 `CONVERSION_REPORT.md`）。

## bundle 结构

```
instruction.md  task.toml  build.sh  push.sh  cyberforge_source.json(来源与证据)
environment/    Dockerfile(agent 沙箱) docker-compose.yaml submit.sh description.txt
                task-server/{Dockerfile, task_server.py, judge.json}
tests/          test.sh verify.py            (与 ARVO bundle 相同)
solution/       solve.sh                     (标准答案；>256KB 时从 task-server /solve 取)
build/          inject_vulnerability.diff ground_truth_poc setup/ snapshot_residue.txt secure_lines.txt
                (构建输入，含机密，不会进入 agent 镜像)
```
