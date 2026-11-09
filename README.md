# DSAA5012-Repro

DSAA5012 课程论文复现项目。主论文为 SIGMOD 2025 的 **Accelerating Core Decomposition in Billion-Scale Hypergraphs**；VLDB 2023 的 **Neighborhood-based Hypergraph Core Decomposition** 提供 Local-core-OPTIV baseline。

- 主论文：[DOI 10.1145/3709656](https://doi.org/10.1145/3709656)，[作者代码](https://github.com/unswdb/hyper-k-core)。
- Baseline：[arXiv:2301.06426](https://arxiv.org/abs/2301.06426)，[作者代码](https://github.com/toggled/vldbsubmission)。
- 上游固定版本见 [configs/upstream.lock.json](configs/upstream.lock.json)，引用见 [references.bib](references.bib)。

## 最终实验状态

全部计划记录已于 2026-11-07 结束，最终审计于 2026-11-08 完成。共 **405/405 条记录**：393 次正式计时尝试及 12 次确定性逐轮计数观测。结果为 **382 条成功、11 条超时、9 条内存限制、3 条崩溃**；143 组配置中 135 组具有完整、成功且通过校验的结果。

覆盖论文图 4–11 和表 5：10 个真实数据集的性能与过滤实验、4 个数据集的规模实验，以及 AMZ、SOA、POW-L 的 1–64 线程实验。所有配置均有终止记录；失败配置没有补成成功数值，也没有只选成功重复计算均值。

在两种方法均完成的 9 个真实数据集上，HyperCD* 相对 VLDB baseline 的记录总时间加速比为 **4.65–9.28×**。计时口径、未成功配置、论文对照及差异见 [实验结果](docs/experiment-results.md)；实验设置与运行入口见 [实验协议](docs/experiment-plan.md)。

## 文件位置

- `src/`、`scripts/`：C++ 适配器、正确性检查、数据处理、实验调度、汇总与绘图代码。
- `configs/`：方法映射、数据来源、上游版本及实验参数。
- [data/results/full-paper/](data/results/full-paper/)：纳入 Git 的完整小型结果归档，含配置快照、逐次记录、校验信息、统计与论文比较 JSON。
- `data/raw/`、`data/processed/`、`external/`、`build/`：服务器上的原始数据、处理后输入、固定版本作者代码和二进制；大型内容不提交 Git。
- `results/`：服务器原始运行目录；本地说明见 [results/README.md](results/README.md)。
- `reports/`：本地报告、图表及报告源文件。新增报告按 `.gitignore` 排除；历史已跟踪的实验材料仍保留。

最终 IEEE 报告位于本地 `reports/ieee-reproduction/DSAA5012-IEEE-Reproduction-Report.pdf`，LaTeX 主文件为同目录 `main.tex`，使用 **XeLaTeX** 编译。此报告不随新的代码提交上传。

## 本地核查已归档结果

Python 3.10+ 即可运行测试与重新汇总，不需要下载大型输入或连接服务器。在仓库根目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B scripts/summarize_full_results.py data/results/full-paper/input   --output results/review/summary.json
```

重新汇总只写入 `results/review/`，保留归档快照。输出应包含 `recorded_trial_records: 405`、`pending_trial_records: 0` 及上述状态计数。若本地已有 Matplotlib，可生成图表：

```bash
MPLCONFIGDIR="$PWD/.runtime/matplotlib" python3 -B scripts/plot_full_results.py   results/review/summary.json --input data/results/full-paper/input   --output results/review
```

## 服务器运行约定

正式工作目录为 `/data/taolei/DSAA5012-Repro-full`，所有数据、构建、缓存、临时文件及结果均放在该目录。服务器写入必须经 `scripts/run_on_server.sh`，由存储保护脚本检查工作目录所在设备与 `/` 不同。保留 `/home/taolei/DSAA5012-Repro` 中早期结果。

完整队列已有终态，不需要为查看结果再次启动。重新执行前先检查 PID、运行状态和输入版本；新机器还需准备固定版本作者代码、输入及二进制，详见实验协议。
