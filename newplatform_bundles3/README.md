# CyberForge → 新平台 bundles（第三类与待确认）

本目录是 CyberForge 数据集（`../cyberforge_tasks20261016/`）转换出的 289 个 bundle，**不应直接用于 PoC 迭代和轨迹生成**：

- **第三类（170 个）：原始数据有严重问题**。数据集里没有只让注入版崩溃的输入（exploit 的输入不触发、报告用的输入没保存、报告是别的程序或别的任务的、安全版也崩溃）、注入的代码不在被测程序里或让构建失败、注入的漏洞不依赖输入（空输入就触发，`build.sh` 输出 `PASS-DEGENERATE`）、漏洞版只表现为超时等。修复需要重新构造 PoV 或重新设计注入。
- **待确认（119 个）**：本机没能构建（需要公网、磁盘不够），或者不能断定是原始数据的问题（例如数据集有注入版的崩溃记录，但按它给的构建流程编不出注入版；判定规则的限制）。在能访问公网、磁盘充足的机器上运行 `build.sh`，三项自检通过后可按数据集证据归入第一或第二类。

每个 bundle 属于哪一类、问题的前因后果、已做的修改和建议见 repo 根目录 `README.md` 的 6.2、6.3 节（机器可读：`../newplatform_bundles/conversion/quality.json`，也写在每个 bundle 的 `cyberforge_source.json` 的 `quality` 里）。

```bash
bash newplatform_bundles3/<bundle>/build.sh     # 公网：构建镜像 + 3 项阻塞式自检（第三类通常不通过，不要推送）
```

第一类在 `../newplatform_bundles/`，第二类在 `../newplatform_bundles2/`。转换方法和验证情况见 `../newplatform_bundles/README.md`、`../newplatform_bundles/CONVERSION_REPORT.md`，每个任务的去向见 `../newplatform_bundles/conversion_manifest.csv`。
