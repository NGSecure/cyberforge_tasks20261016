# CyberForge → 新平台 bundles（C 类）

本目录是 CyberForge 数据集（`../cyberforge_tasks20261016/`）中 C 类任务转换出的 88 个新平台 bundle：harness 型 57 个，CLI / 程序型 31 个。

**这些任务在数据集里没有触发证据**（`sanitizer_report.txt` 为空、报告里没有崩溃、只有超时、报告与 exploit.sh 自己的判定条件矛盾，或报告来自另一个程序）。bundle 里的标准答案就是数据集的 PoV 或重放 exploit 得到的输入，但没有任何记录证明它能触发漏洞。`build.sh` 的自检 3（标准答案在漏洞版上触发、在安全版上不触发）是唯一的把关：不通过的不要推送，预计会有相当一部分不通过。每个 bundle 的 `cyberforge_source.json` 里 `ground_truth_evidence` 写明了原因。

```bash
bash newplatform_bundles3/<bundle>/build.sh     # 公网：构建镜像 + 3 项阻塞式自检
bash newplatform_bundles3/<bundle>/push.sh      # 上传网络：推送镜像并回填 task.toml
```

A 类在 `../newplatform_bundles/`，B 类在 `../newplatform_bundles2/`。转换方法、验证结果和发现的问题见 `../newplatform_bundles/README.md`、`../newplatform_bundles/CONVERSION_REPORT.md`，每个任务的去向见 `../newplatform_bundles/conversion_manifest.csv`。
