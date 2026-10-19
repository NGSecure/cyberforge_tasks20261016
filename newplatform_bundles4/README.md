# CyberForge → 新平台 bundles（第四类：待确认）

本目录是 CyberForge 数据集（`../cyberforge_tasks20261016/`）转换出的 65 个**第四类（待确认）** bundle：无法确定原始数据是否有问题。原因有两种：

- **本机没能构建**：构建要用的磁盘超出了本机的配额，或者构建时要下载的东西本机下载不到。在磁盘充足、能直接访问公网的机器上运行 `build.sh`，三项自检通过后可按数据集证据归入第一或第二类，不通过的归入第三类。其中 2 个没有标准答案（数据集的崩溃种子只是 Git LFS 指针，上游就缺），构建后只做不依赖标准答案的自检（输出 `PASS-NO-GROUND-TRUTH`），通过后归第三类。
- **不能断定是原始数据的问题**：例如数据集有注入版的崩溃记录，但按它给的构建流程编不出注入版；或者是判定规则本身的限制。repo 根目录 `README.md` 的表里给出了原因和建议的处理办法。

每个 bundle 的原因、已做的修改和建议见 repo 根目录 `README.md` 的 6.3 节（机器可读：`../newplatform_bundles/conversion/quality.json`，也写在每个 bundle 的 `cyberforge_source.json` 的 `quality` 里）。

```bash
bash newplatform_bundles4/<bundle>/build.sh     # 公网：构建镜像 + 3 项阻塞式自检；通过后再推送
```

第一类在 `../newplatform_bundles/`，第二类在 `../newplatform_bundles2/`，第三类在 `../newplatform_bundles3/`。转换方法和验证情况见 `../newplatform_bundles/README.md`、`../newplatform_bundles/CONVERSION_REPORT.md`，每个任务的去向见 `../newplatform_bundles/conversion_manifest.csv`。
