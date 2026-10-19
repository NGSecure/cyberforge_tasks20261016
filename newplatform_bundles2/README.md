# CyberForge → 新平台 bundles（第二类）

本目录是 CyberForge 数据集（`../cyberforge_tasks20261016/`）转换出的 117 个**第二类**新平台 bundle：原始数据（数据集任务本身）有轻微问题，已经做了少量修改，或者不修改也不影响轨迹质量；在本机三项自检全部通过，可以用于 PoC 迭代和轨迹生成。

常见的问题：数据集指定的 PoV 文件不能触发（标准答案换成了数据集里另一个能触发的输入，例如 exploit 实际喂给 harness 的输入）、触发文件没有随任务附带（从同项目其他任务找回）、标准答案只是 Git LFS 指针（上游就缺内容，按 SHA-256 还原）、exploit 的输入格式不对（按它的意图做了最小修正，见 `../newplatform_bundles/conversion/constructed/`）、数据集缺少触发证据或报告是别的任务的（以本机验证为准）、题面描述的漏洞类型不准、题面描述指错了位置（已按数据集自己的报告改正，原文保存在 `cyberforge_source.json` 的 `description.original`）；另有少数注入在 fuzz harness 自己的代码里、或触发偶尔不稳定。除改正题面描述的以外，修改只涉及标准答案（只用于自检，不给 agent 看）；判定方式都没有改。每个 bundle 的问题、修改和影响见 repo 根目录 `README.md` 的 6.1 节。

```bash
bash newplatform_bundles2/<bundle>/build.sh     # 公网：构建镜像 + 3 项阻塞式自检
bash newplatform_bundles2/<bundle>/push.sh      # 上传网络：推送镜像并回填 task.toml
```

第一类在 `../newplatform_bundles/`，第三类和待确认在 `../newplatform_bundles3/`。分类标准见 repo 根目录 `README.md`；转换方法和验证情况见 `../newplatform_bundles/README.md`、`../newplatform_bundles/CONVERSION_REPORT.md`，每个任务的去向见 `../newplatform_bundles/conversion_manifest.csv`。
