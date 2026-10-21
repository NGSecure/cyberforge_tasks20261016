# CyberForge → 新平台 bundles（第六类：构建失败或无法转化）

本目录是 CyberForge 数据集（`../cyberforge_tasks20261016/`）转换出的 28 个**第六类** bundle：因为原始数据的问题，`build.sh` **一定会构建失败**，或者 bundle 虽然能构建、但**转化不成有效任务**（没有任何 PoV 能通过判定），暂时无法修复。**不要构建上传**；放在这里只是为了保留转换结果和问题记录。（已经转化好、只是本机硬件不够而没能实测的不在这里，留在原来的类别。）

原因有三种，都在原始数据里：

- **注入让构建失败**：注入的代码让构建本身崩溃，或 diff 改的是构建时才生成的文件（干净源码里没有它，补丁打不上）；或注入的代码不在任何被构建的程序里，两个版本的构建产物完全相同，task-server 镜像（要比较两个版本的产物）无法建立。原来在第三类。
- **数据集有注入版的崩溃记录，但按它给的构建流程编不出注入版**：原来在第四类（待确认）。repo 根目录 `README.md` 第 6 节的表里给出了预计能解决的最小改动（对构建流程的少量偏离）；如果接受，可以改动后重新转换、验证，再归入相应的类。
- **原来没有生成 bundle、按第五类的方案也救不了**：注入的代码不在被构建的程序里、让漏洞版编译不过，或项目本身在数据集的镜像里就构建不了（构建失败）；或者能构建、但注入只是注释或死代码、改动走不到或没有可观察的效果、注入是加固而不是漏洞、需要判定环境给不了的权限或资源（没有 PoV 能通过判定）。

每个 bundle 的问题、影响和建议见 repo 根目录 `README.md` 第 6 节的第六类表（机器可读：`../newplatform_bundles/conversion/quality.json`，也写在每个 bundle 的 `cyberforge_source.json` 的 `quality` 里）。

第一类在 `../newplatform_bundles/`，第二类在 `../newplatform_bundles2/`，第三类在 `../newplatform_bundles3/`，第四类（待确认）在 `../newplatform_bundles4/`，第五类在 `../newplatform_bundles5/`，第七类在 `../PotentialFalsePositive/`。转换方法和验证情况见 `../newplatform_bundles/README.md`、`../newplatform_bundles/CONVERSION_REPORT.md`，每个任务的去向见 `../newplatform_bundles/conversion_manifest.csv`。
