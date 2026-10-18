# CyberForge → 新平台 bundles（B 类）

本目录是 CyberForge 数据集（`../cyberforge_tasks20261016/`）中 B 类任务转换出的 61 个新平台 bundle：数据集有崩溃证据，但 PoV 不是喂给 fuzz harness 的输入，而是交给项目自己的程序。

- CLI 型 26 个：PoV 是 CLI 的输入文件、标准输入或命令行参数（每行一个）；
- 程序型 35 个：PoV 是一个 C/C++ 源文件，按数据集 exploit 的编译命令链接项目代码后运行。

判定用的命令是在项目真实镜像里重放数据集的 exploit.sh 记录下来的，写在每个 bundle 的 `instruction.md`（给 agent 看）和 `environment/task-server/judge.json` 里。用法与 A 类相同：

```bash
bash newplatform_bundles2/<bundle>/build.sh     # 公网：构建镜像 + 3 项阻塞式自检
bash newplatform_bundles2/<bundle>/push.sh      # 上传网络：推送镜像并回填 task.toml
```

A 类在 `../newplatform_bundles/`，C 类在 `../newplatform_bundles3/`。转换方法、验证结果和发现的问题见 `../newplatform_bundles/README.md`、`../newplatform_bundles/CONVERSION_REPORT.md`，每个任务的去向见 `../newplatform_bundles/conversion_manifest.csv`。
