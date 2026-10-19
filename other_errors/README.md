# CyberForge → 新平台 bundles（第六类：确定会构建失败）

本目录是 CyberForge 数据集（`../cyberforge_tasks20261016/`）转换出的 5 个**第六类** bundle：因为原始数据的问题，`build.sh` **一定会构建失败**，暂时无法修复。**不要构建上传**；放在这里只是为了保留转换结果和问题记录。

原因有两种，都在上游数据（注入的 diff 和数据集声明的构建流程）里：

- **注入让构建失败**：注入的代码让构建本身崩溃，或 diff 改的是构建时才生成的文件（干净源码里没有它，补丁打不上）；或注入的代码不在任何被构建的程序里，两个版本的构建产物完全相同，task-server 镜像（要比较两个版本的产物）无法建立。原来在第三类。
- **数据集有注入版的崩溃记录，但按它给的构建流程编不出注入版**：原来在第四类（待确认）。repo 根目录 `README.md` 第 6 节的表里给出了预计能解决的最小改动（对构建流程的少量偏离）；如果接受，可以改动后重新转换、验证，再归入相应的类。

每个 bundle 的问题、影响和建议见 repo 根目录 `README.md` 第 6 节的第六类表（机器可读：`../newplatform_bundles/conversion/quality.json`，也写在每个 bundle 的 `cyberforge_source.json` 的 `quality` 里）。

第一类在 `../newplatform_bundles/`，第二类在 `../newplatform_bundles2/`，第三类在 `../newplatform_bundles3/`，第四类（待确认）在 `../newplatform_bundles4/`。转换方法和验证情况见 `../newplatform_bundles/README.md`、`../newplatform_bundles/CONVERSION_REPORT.md`，每个任务的去向见 `../newplatform_bundles/conversion_manifest.csv`。
