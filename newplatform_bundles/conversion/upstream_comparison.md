# 原始数据与上游 CyberForge-projects 的对比

- 上游：<https://github.com/Cyb3rForge/CyberForge-projects>，`main` 分支 `9e09f49`（2026-08-04，“README: link the teacher-trajectory datasets and CyberForge repos”）。
- 本仓库的原始数据：`cyberforge_tasks20261016/`，即提交 `e997c5df`（2026-10-16 上传）里的 `cyberforge-tasks-1034/`。
- 比较方法：两边的 git tree 按路径逐个比较文件的 blob 哈希（内容相同则哈希相同）；与上游不同的文件，再在上游全部 66 个提交、15 个分支里按内容查找来源。LFS 指针按其中记录的 SHA-256 和大小核对。

## 1. 对应关系

- 原始数据就是上游 `main` 里**有任务的 80 个项目**（放到 `projects/` 下），加一个 `manifest.csv`。上游另有 20 个没有任务的项目目录（binutils、ffmpeg、qemu 等）和仓库根目录的 README、LICENSE、`.github/`，没有带过来。
- 1034 个任务一个不差（FZ 643、WF_RAG 220、WF_LLM 171），没有增删任务。
- 与上游 `main` 最接近：80 个项目里上游 `main` 的文件全部在原始数据里，36621 个内容完全相同；上游更早的提交（例如发布前的 `af0e78d` / 分支 `cyberforge_full_data`）相同的文件更少。

## 2. 提供数据的团队改了什么

原始数据共 43674 个文件：

| 类别 | 文件数 | 说明 |
|---|---|---|
| 与上游完全相同 | 36621 | 注入的 diff、exploit 文件（exploit.sh、pov.bin、fuzz 结果等）、上游已有的 sanitizer 报告、vulnerability_metadata.json、vuln_description.md、各项目的 setup/、unit_tests/ 都没有改动 |
| 新增任务元数据 | 3626 | 给缺这些文件的任务补了 bug_report.txt（726）、hints.json（726）、bug_description_variants.json（725）、bug_description_validation.json（725）、task_contract.json（724）：上游的 391 个 WF 任务都没有这些文件，FZ 任务里也有约 335 个没有。task_contract.json 里的工作区路径是 `/home/rzcai/disk1/mythos_research/CyberForge/collect_trace/workspaces/…`，bug_description_variants.json 标着 `"generated": true`，看起来是用他们的 CyberForge collect_trace 流程生成的 |
| 新增空的 sanitizer_report.txt | 60 | 上游这 60 个任务没有报告，补的是空文件 |
| 新增 manifest.csv | 1 | 任务清单（seq、type、project、vuln、path、cwe、severity） |
| 修改任务元数据 | 554 | 143 个 FZ 任务的 bug_description_variants.json（上游是空列表，改成 3 条生成的描述）、148 个 bug_description_validation.json、263 个 task_contract.json（重新生成：工作区路径、任务编号改成 FZ_n 等） |
| 修改种子文件 | 2812 | 上游这些文件只是 Git LFS 指针，他们换成了同一个种子在别的任务里的真实文件（同项目 1692 个、其他项目 1118 个）。其中 2796 个与指针记录的 SHA-256 和大小一致；**16 个不一致**：serenity FZ_5、FZ_9、FZ_16、FZ_17 的 `gsub_tail_*.bin`，是按文件名从别的任务拷来的同名文件，内容不是原来的（这 16 个文件都不是任何 bundle 的标准答案） |
| 删除 | 0 | — |

对转换的影响：

- agent 看到的题面取自 bug_description_variants.json，其中 868 个任务（725 + 143）的描述是这个团队生成的。转换中改正过的 8 个“指错了位置”的题面，有 7 个出自这些生成的描述（quickjs FZ_3/12/15/21/25、grok WF_RAG_1、h3 WF_LLM_2）；其中 grok WF_RAG_1、h3 WF_LLM_2 上游自己的 vuln_description.md 写的位置是对的。另一个（bluez FZ_1）是上游原有的描述，但上游的 vuln_description.md 同样写对了。
- 726 个任务的 hints.json（“成功的种子”等）是这个团队生成的；转换不直接相信它，标准答案都经过实测。第二类里“数据集指定的 PoV 不触发”的 43 个 bundle，数据集指定的 PoV 都是 exploit_files/pov.bin：这个文件是上游原有的，但不是 exploit 在项目镜像里实际喂给 harness 的输入；这个团队生成的 hints.json 也把它记成了“成功的种子”。

## 3. Git LFS 是怎么回事

- **上游自己就只有指针**：上游 `main` 里有 6749 个文件只是 LFS 指针（2164 个不同内容），都在 exploit_files/ 下（6655 个在 generated_inputs/）。
- **上游从来没有启用 LFS**：全部 66 个提交、15 个分支里都没有 `.gitattributes`。这些指针是被当成普通文本文件提交进去的，所以 GitHub 网页上看到的就是三行指针文本；通过 GitHub 的 LFS 下载地址（media.githubusercontent.com）也取不到内容（返回 404）。
- **从加入 FZ 任务起就是指针**：只有 `main` 和 `cyberforge_full_data` 两个分支有 generated_inputs；指针是在加入 FZ 任务的提交 `af0e78d`（2026-07-06）里一起进来的，之后一直如此。也就是说，上游作者把这些文件拷进来时，它们在来源处就已经只是 LFS 指针：这种三行指针只会由 Git LFS（或兼容 LFS 的仓库，例如 Hugging Face 的数据集仓库）生成，说明拷贝的来源用 LFS 管理这些文件，而拷贝时没有取到内容；真实内容从来没有进过这个仓库。
- **这些种子当时是有真实内容的**：上游的生成框架（CyberForge 的 `src/vuljector/run_fuzz_poc.py`）把每次生成的种子按内容的 SHA-256 命名（`seed_<sha256>`）存进运行目录 `runs/fuzz_poc/_curated/`，后来的任务再从这里取种子（`curated_seed_<sha256>`）。上游的 6749 个指针文件里，3436 个文件名带着这个 SHA-256，而且全都正好等于指针记录的 SHA-256（文件名带 SHA-256 的 9502 个真实文件，也全都等于内容的 SHA-256）：这些种子在生成时就是指针记录的那份真实内容，只是后来存进仓库时只剩下了指针。框架仓库本身没有用 LFS（169 个提交里都没有 `.gitattributes`），它的 `.gitignore` 还排除了运行目录 `runs/`，所以这些种子的真实内容只在作者本地。
- **哪些文件成了指针，看不出按类型的规律**：上游 421 个有 generated_inputs 的 FZ 任务里，207 个是真实文件和指针混在一起（没有一个任务全是指针），这些任务分属 45 个项目，其中 32 个有指针；各种命名的种子（`curated_seed_<sha256>`、`poc_orig_*`、`poc_trim_*` 和其他）都有 22%–29% 是指针；.bin、.png、.zip 等同一种扩展名既有真实文件也有指针，内容已知的指针里既有二进制也有文本。所以不是某一类文件被设成了 LFS，而是上游拼装数据集时，有一部分文件只拿到了指针。
- **有的种子在生成数据时就已经是指针**：jq FZ_1 的 sanitizer_report.txt（与上游相同）是数据集自己那次 fuzz 运行的输出，其中有 126 处 jq 报错的内容就是 `version https://git-lfs…`，说明那次运行喂给 jq 的种子就是指针文本。
- **能找回的都找回了**：同一个种子常常在一个任务里是真实文件、在另一个任务里是指针。上游 `main` 内部能这样找到真实内容的有 3659 个指针文件（672 个内容）：提供数据的团队补对了 2796 个，转换时按 SHA-256 又补了 862 个，剩下 1 个是补错的那 16 个之一（serenity FZ_5 的 `gsub_tail_ff.bin`，正确内容其实就在同一任务的 `reproducer.bin` 里）；上游发布前的分支 `cyberforge_full_data` 里还有 2 个内容（在发布前的清理中被删掉的文件里），也已补上。
- **剩下的上游里没有**：把上游全部历史（66 个提交、15 个分支，共 28482 个不同的文件内容）逐个比对（大小一致的再算 SHA-256），剩下的 1481 个内容（3073 个文件）一个都没有；补错的 16 个 serenity 文件里，也只有上面那 1 个的正确内容在上游。有 9 个任务的崩溃种子就在缺的里面；用指针文本本身当输入在这些任务里实测（能构建的 7 个），都不触发，所以它们需要的是原始内容。
- **数目对得上**：上游的 2164 个指针内容 = 上游 `main` 里有真实副本的 672 个 + 发布前分支里的 2 个 + 仍缺的 1481 个 + 只出现在补错的 serenity 文件里、同样找不到的 9 个。
- **Hugging Face 上的副本也只有指针**：上游 README 链接的 Hugging Face 数据集 `AmL-hug/cyberforge-projects`（2026-08-04 发布，提交 `02d0191c`）是 100 个项目各一个 tar.gz，解开就是 GitHub `main` 上同一棵目录树（40178 个文件），6749 个指针文件原样在里面，缺的 1481 个内容一个都没有。同一作者的两个教师轨迹数据集（agent 修补漏洞、构造 PoC 的对话记录）里，agent 打印或写出的字节只对上了 11 个很小的内容（1–71 字节），都不是崩溃种子。还可能有原始内容的只剩上游作者本地的运行目录（CyberForge 框架 <https://github.com/vuljector/CyberForge> 的 `runs/fuzz_poc/_curated/`，那里的种子按 SHA-256 命名，正好能和指针对上）。
- **处理决定（2026-10-19）**：缺的内容几乎都是不进 bundle 的语料，agent 看不到、判定也不用，不影响 PoC 轨迹，所以不再找回（轨迹里出现过的、或只有 1–3 字节可以穷举出来的少数小文件也没有补进来）。崩溃种子缺内容的 9 个任务照常转成 bundle，但没有标准答案、不做“标准答案只让漏洞版崩溃”的自检：本机验证过的 7 个归第三类，serenity FZ_16、FZ_17 本机磁盘不够、没能构建，暂在第四类（见 repo 根目录 `README.md`）。
