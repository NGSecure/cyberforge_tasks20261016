# CyberForge → 新平台 bundles（第七类：潜在误报）

本目录是 CyberForge 数据集（`../cyberforge_tasks20261016/`）转换出的 87 个**第七类** bundle（原第三类 80 个、原第五类 7 个，2026-10-21 的要求）：本机验证时 `build.sh` 的自检 3 输出 `PASS-DEGENERATE`，也就是**提交一个空的 PoC 也会被判定为成功**（空文件；命令行参数型是不带参数）。判定会把不利用注入漏洞的提交判为成功，在这些任务上的“成功”可能是误报，**不可用于 PoC 迭代和轨迹生成**；只用于不看判定结果的用途（例如代码理解、定位）时可以保留。

每个 bundle 都在本机重新构建，用几个任意的 PoC 代替标准答案再跑了一遍自检（1 字节 `A`、64 字节随机数据、4096 字节随机数据、1024 字节全零；命令行参数型换成 4 组任意参数）：

- **任意 PoC 都能通过**（67 个）：空 PoC 和这几个任意 PoC 全部通过，提交什么都判为成功，注入的漏洞不依赖输入（多在任何输入都会走到的路径上，例如初始化代码）；
- **只有一部分任意 PoC 能通过**：例如只有很短的输入能触发（注入删掉了 harness 的长度检查），或只有空 PoC 能通过（空参数走到了注入改动的分支）。判定不会把所有提交都判为成功，但空提交就能通过，同样不需要利用注入的漏洞。

每个 bundle 属于哪一种、哪些任意 PoC 通过了，见 repo 根目录 `README.md` 第 4 节和第 6 节的第七类表（机器可读：`../newplatform_bundles/conversion/verification/any_poc.json`、`../newplatform_bundles/conversion/quality.json`，也写在每个 bundle 的 `cyberforge_source.json` 的 `quality` 里）。问题都在原始数据（注入的设计），解决办法是上游重新设计注入、让漏洞依赖输入内容，否则剔除。

这一类都能构建、能推送（三项自检都通过，自检 3 输出 `PASS-DEGENERATE`）：

```bash
bash PotentialFalsePositive/<bundle>/build.sh     # 公网：构建镜像 + 3 项自检（自检 3 输出 PASS-DEGENERATE）
bash PotentialFalsePositive/<bundle>/push.sh      # 上传网络：推送镜像并回填 task.toml
```

第一类在 `../newplatform_bundles/`，第二类在 `../newplatform_bundles2/`，第三类在 `../newplatform_bundles3/`，第四类（待确认）在 `../newplatform_bundles4/`，第五类在 `../newplatform_bundles5/`，第六类在 `../other_errors/`。转换方法和验证情况见 `../newplatform_bundles/README.md`、`../newplatform_bundles/CONVERSION_REPORT.md`，每个任务的去向见 `../newplatform_bundles/conversion_manifest.csv`。
