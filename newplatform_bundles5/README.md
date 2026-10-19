# CyberForge → 新平台 bundles（第五类：按任务实现判定）

本目录是 CyberForge 数据集（`../cyberforge_tasks20261016/`）转换出的 108 个**第五类** bundle。这些任务以前没有生成 bundle：原来的判定只认“注入版崩溃、安全版不崩溃”，判定服务也不能给 PoV 设置环境变量、附带文件。平台最终运行 bundle 自己的 `tests/test.sh` 检查 agent 迭代出的 PoV，完全按它的结果判定（2026-10-19 的说明），所以这些任务改为在各自的 `tests/` 里实现相应的判定逻辑。

- **判定规则**在 `tests/oracle.json`，`tests/test.sh` 把每次提交发给 task-server 的 `/verify`（它在注入版、安全版上分别运行 PoV，报告每次运行的结果），再由 `tests/verify.py` 按规则判定（规则本身是 `tests/cf_oracle.py`，task-server 的自检用同一份）：
  - `crash`：注入版报 sanitizer 错误或因致命信号退出，安全版不会；
  - `output-diff`：逻辑漏洞，注入版对 PoV 的可观察行为（退出状态、输出，必要时还有指定的输出文件）每次都与安全版不同，安全版重复运行结果一致（进程号、地址、时刻、运行目录不算差别）；
  - `match`：注入版的输出里出现项目代码打印的特定内容，安全版没有；
  - `timeout`：注入版在时限内跑不完，安全版能跑完（各运行两次）。
- **PoV 的形式**（`environment/task-server/judge.json` 的 `pov_kind`）：fuzz harness 的输入文件、项目程序的输入文件 / 标准输入 / 命令行参数、链接项目代码的 C/C++ 程序（只用于 `crash` 规则：程序能自己分辨两个版本，不能用输出差别判定），以及两种新形式：
  - `archive`：一个 tar 包，含输入文件 `input`、环境变量 `env`（每行 `NAME=value`；动态链接器、glibc 分配器、`PATH` 和 sanitizer 的变量不能设置）和输入或变量用到的其他文件；
  - `driver`：数据集 exploit 自己的测试程序，只改成从 PoV 文件读取原来写死的输入（数据集没有这样的程序时，是我们按注入的代码写的 driver），task-server 用两个版本各编译一次；源码放在 agent 的 `/workspace/` 里。
- **标准答案**都来自数据集（exploit 的输入、参数、环境变量或文件，必要时做最小改写，写在 `cyberforge_source.json` 里）；数据集没有能用的触发输入的任务没有标准答案，`build.sh` 的自检 3 只检查判定本身（输出 `PASS-NO-GROUND-TRUTH`）。

每个 bundle 的原因、判定方式和本机验证结果见 repo 根目录 `README.md` 的第 6 节（机器可读：`../newplatform_bundles/conversion/quality.json`、`../newplatform_bundles/conversion/c5_specs.json`，也写在每个 bundle 的 `cyberforge_source.json` 的 `quality`、`category5` 里）。

本机实测：100 个构建成功，自检 3 按本任务的规则通过（`PASS` 83 个；没有标准答案、只检查判定本身的 `PASS-NO-GROUND-TRUTH` 10 个；空 PoV 也通过的 `PASS-DEGENERATE` 7 个，只能当退化任务看待）。另有 8 个已经转化好，只是本机条件（磁盘、内存或网络）不够而没能实测，留在本目录，状态里写明了原因和需要的资源，需要在条件足够的机器上运行 `build.sh` 验证。原来的 131 个任务里，构建不了（注入的代码不在被构建的程序里、diff 让漏洞版编译不过、项目本身在镜像里构建不了）或转化不成有效任务（能构建，但没有 PoV 能通过判定）的 23 个已放到 `../other_errors/`（第六类），不要构建上传。每个 bundle 的情况见 repo 根目录 `README.md` 第 6 节。

```bash
bash newplatform_bundles5/<bundle>/build.sh     # 公网：构建镜像 + 3 项自检（自检 3 按本任务的规则）
bash newplatform_bundles5/<bundle>/push.sh      # 上传网络：推送镜像并回填 task.toml
```

第一类在 `../newplatform_bundles/`，第二类在 `../newplatform_bundles2/`，第三类在 `../newplatform_bundles3/`，第四类（待确认）在 `../newplatform_bundles4/`，第六类在 `../other_errors/`。转换方法和验证情况见 `../newplatform_bundles/README.md`、`../newplatform_bundles/CONVERSION_REPORT.md`，每个任务的去向见 `../newplatform_bundles/conversion_manifest.csv`。
