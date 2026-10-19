# CyberForge → 新平台 bundles（第三类）

本目录是 CyberForge 数据集（`../cyberforge_tasks20261016/`）转换出的 184 个**第三类** bundle：**原始数据有严重问题**，不应直接用于 PoC 迭代和轨迹生成。

数据集里没有只让注入版崩溃的输入（exploit 的输入不触发、报告用的输入没保存、报告是别的程序或别的任务的、安全版也崩溃）、注入的代码不在被测程序里、注入的漏洞不依赖输入（空输入就触发，`build.sh` 输出 `PASS-DEGENERATE`）、漏洞版只表现为超时等。修复需要重新构造 PoV 或重新设计注入。其中 7 个没有标准答案：数据集的崩溃种子只是 Git LFS 指针（上游就缺），按 2026-10-19 的决定照常转成 bundle，`build.sh` 不做标准答案自检、自检 3 只检查判定（输出 `PASS-NO-GROUND-TRUTH`），`solution/solve.sh` 只说明没有参考 PoV；它们能构建、能判定，但能否被输入触发没有验证。

每个 bundle 属于哪一类、问题的前因后果、已做的修改和建议见 repo 根目录 `README.md` 的 6.2 节（机器可读：`../newplatform_bundles/conversion/quality.json`，也写在每个 bundle 的 `cyberforge_source.json` 的 `quality` 里）。

这一类都能构建、能推送：自检 3 已知不通过的 97 个，`build.sh` 照常构建两个镜像，自检 3 打印说明后正常结束（最后一行是 `BUILT …`），镜像可以推送；它们能用来做什么、不能用来做什么见 repo 根目录 `README.md` 第 6 节。确定会构建失败的（注入让构建失败、两个版本的产物完全相同）已移到 `../other_errors/`（第六类）。

```bash
bash newplatform_bundles3/<bundle>/build.sh     # 公网：构建镜像 + 3 项自检（已知不通过的打印说明后以 BUILT 结束；
                                                #   没有标准答案的 7 个输出 PASS-NO-GROUND-TRUTH）
bash newplatform_bundles3/<bundle>/push.sh      # 上传网络：推送镜像并回填 task.toml
```

第一类在 `../newplatform_bundles/`，第二类在 `../newplatform_bundles2/`，第四类（待确认）在 `../newplatform_bundles4/`，第六类在 `../other_errors/`。转换方法和验证情况见 `../newplatform_bundles/README.md`、`../newplatform_bundles/CONVERSION_REPORT.md`，每个任务的去向见 `../newplatform_bundles/conversion_manifest.csv`。
