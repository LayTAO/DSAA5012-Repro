# DSAA5012-Repro

## Accelerating Core Decomposition in Billion-Scale Hypergraphs

本仓库复现 SIGMOD 2025 论文 **Accelerating Core Decomposition in Billion-Scale Hypergraphs**，使用 VLDB 2023 的 **Neighborhood-based Hypergraph Core Decomposition** 中的 Local-core-OPTIV 作为 baseline。项目调用固定版本的作者 C++ 实现，提供数据预处理、正确性验证、性能比较、过滤消融、规模扩展和 CPU 并行实验。

[主论文](https://doi.org/10.1145/3709656) · [SIGMOD 作者代码](https://github.com/unswdb/hyper-k-core) · [Baseline 论文](https://arxiv.org/abs/2301.06426) · [VLDB 作者代码](https://github.com/toggled/vldbsubmission) · [实验设置](docs/experiment-plan.md) · [详细结果](docs/experiment-results.md)

## 方法

- **HyperCD***：组合 lower-bound filtering（LB）与 recalculation-unnecessary checking（RUC），对应参数 `0`。
- **过滤对照**：仅 RUC（`1`）、仅 LB（`2`）、HyperCD+（`3`）、HyperCD（`4`）、HyperCD++ / SUC（`5`）。
- **Local-core-OPTIV**：VLDB 2023 作者实现，对应参数 `OPTIV`。

方法映射见 [configs/methods.json](configs/methods.json)，两份作者代码的完整 commit SHA 见 [configs/upstream.lock.json](configs/upstream.lock.json)。

## 环境依赖

- Linux，Python 3.10+，Git，支持 C++20 与 OpenMP 的 `g++`。
- GNU `time`、`sort`、`timeout`、`taskset`，以及 Python `venv`/`pip`。
- 绘图需要 Matplotlib 和 NumPy；下面的命令将它们安装在项目虚拟环境中。
- 本次实验环境：Ubuntu 22.04、GCC 11.4、双路 AMD EPYC 7543，共 64 个物理核 / 128 个逻辑线程、约 1007.7 GiB 内存。实验使用 CPU，不需要 GPU。
- 正式计时每组 3 次，每次最长 6 小时。扩展实验的虚拟地址空间上限为 500 GiB；早期核心批次的限制见[实验设置](docs/experiment-plan.md#重复时间内存与计量)。POW-L 生成前脚本要求项目分区至少有 800 GiB 可用空间。

## 快速启动

以下为全新 Linux 项目的完整执行顺序，命令中的项目路径与现有全流程审计脚本一致。系统工具需预先可用；本流程不安装系统软件。完成首次克隆后，服务器操作均经 `run_on_server.sh` 执行。

### 1. 获取项目

在服务器终端执行；已有仓库时直接进入该目录。

```bash
cd /data/taolei
test "$(stat -c %d .)" != "$(stat -c %d /)" || exit 1
git clone https://github.com/LayTAO/DSAA5012-Repro.git DSAA5012-Repro-full
cd /data/taolei/DSAA5012-Repro-full
```

以下各步骤都在仓库根目录执行。

### 2. 准备依赖与固定版本作者代码

```bash
bash scripts/run_on_server.sh python3 -m venv .venv
bash scripts/run_on_server.sh .venv/bin/python -m pip install matplotlib numpy
bash scripts/run_on_server.sh python3 scripts/fetch_upstream.py
bash scripts/run_on_server.sh python3 scripts/capture_environment.py \
  --output results/setup/environment.json
```

### 3. 编译与小图验证

原生工具用于 `org` / `sortEV` 预处理；主适配器用于核心对比，扩展适配器用于统计、并行和合成输入。

```bash
bash scripts/run_on_server.sh bash scripts/build_native.sh
bash scripts/run_on_server.sh bash scripts/build_drivers.sh
bash scripts/run_on_server.sh bash scripts/build_extended.sh
bash scripts/run_on_server.sh bash scripts/build_data_tools.sh

bash scripts/run_on_server.sh python3 -B -m unittest discover -s tests -v
bash scripts/run_on_server.sh python3 scripts/check_upstream.py \
  --random-cases 100 --seed 5012 --output results/correctness-002
bash scripts/run_on_server.sh python3 scripts/check_extended.py \
  --output results/extended-correctness-002
bash scripts/run_on_server.sh python3 scripts/check_data_tools.py \
  --output results/data-tools-check-001
```

三个验证脚本使用新的输出目录；若目录已存在，先查看原有结果，不覆盖原记录。

### 4. 下载与预处理十个真实数据集

```bash
# HI、GE、DF：下载 Cornell 原始数据并完成格式转换、org 和排序。
bash scripts/run_on_server.sh python3 scripts/prepare_cornell.py HI
bash scripts/run_on_server.sh python3 scripts/prepare_cornell.py GE
bash scripts/run_on_server.sh python3 scripts/prepare_cornell.py DF

# CO、DB、AM：获取 VLDB 作者数据归档，再分别预处理。
bash scripts/run_on_server.sh python3 scripts/fetch_data.py baseline
bash scripts/run_on_server.sh python3 scripts/prepare_author_data.py CO
bash scripts/run_on_server.sh python3 scripts/prepare_author_data.py DB
bash scripts/run_on_server.sh python3 scripts/prepare_author_data.py AM

# THS、TAS、SOA、AMZ：下载扩展数据并预处理。
bash scripts/run_on_server.sh python3 scripts/fetch_extended_data.py THS TAS SOA AMZ
bash scripts/run_on_server.sh python3 scripts/prepare_extended_data.py THS TAS SOA AMZ
```

下载文件保存在 `data/raw/`，处理后输入与 manifest 保存在 `data/processed/`。`configs/full-datasets.json` 指定每个实验使用的目录。CO 使用 VLDB 作者归档，不能用另一份 Cornell CO 输入替换同一配置。

### 5. 运行核心对比及完整扩展实验

```bash
# 首先生成完整队列需要复用的四个核心批次。
bash scripts/run_on_server.sh python3 scripts/run_paper_batch.py \
  --datasets HI CO DB AM --run-id 001

# 顺序执行规模输入准备、真实数据实验、POW-S 和 POW-L 实验。
bash scripts/run_on_server.sh python3 scripts/run_full_workflow.py

# 队列结束后检查输入、二进制、重复次数、完整输出记录及失败记录。
bash scripts/run_on_server.sh python3 scripts/audit_final_results.py
```

`run_paper_batch.py` 拒绝覆盖已有输出。`run_full_workflow.py` 使用检查点和互斥锁；单项算法超时/失败会保留状态，脚本或环境错误会使队列停止并留下诊断。完整队列包含长时间和大内存实验，需要持续运行的终端会话。

POW-S / POW-L 使用作者公开的 `generateHypergraph_nbr_PowerLaw` 生成器，种子为 **5012**；参数记录于 [configs/synthetic-profile.json](configs/synthetic-profile.json)。原始及处理后输入的实际统计保存在 manifest 中。

### 6. 导出结果与生成图表

下面的命令在服务器项目内生成小型结果包、图 4–11、表 5 和 Markdown 比较报告，输出目录为 `results/reproduced/`。

```bash
bash scripts/run_on_server.sh .venv/bin/python - <<'PYRESULTS'
import json
from pathlib import Path
import shutil
import subprocess
import sys

out = Path('results/reproduced')
inputs = out / 'input'
inputs.mkdir(parents=True, exist_ok=True)
package = json.loads(subprocess.check_output(
    [sys.executable, 'scripts/export_full_results.py'], text=True))
for name, content in package.items():
    target = (inputs / name).resolve()
    if not target.is_relative_to(inputs.resolve()):
        raise ValueError('Unexpected export path: ' + name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')

shutil.copyfile('results/final-audit-001/audit.json', out / 'final-audit.json')
subprocess.run([sys.executable, 'scripts/summarize_full_results.py',
                str(inputs), '--output', str(out / 'summary.json')], check=True)
subprocess.run([sys.executable, 'scripts/plot_full_results.py',
                str(out / 'summary.json'), '--input', str(inputs),
                '--output', str(out)], check=True)
subprocess.run([sys.executable, 'scripts/finalize_report.py', str(out)], check=True)
PYRESULTS
```

对应输出：`summary.json`（分组测量）、`final-comparison.json`（结构化比较）、`final-report.md`（结果分析）、`figure-4` 至 `figure-11` 的 PNG/SVG，以及 `table-5.png` / `table-5.svg`。

## 主要实验结果

以下均为本项目实测数据，来源为 [final-comparison.json](data/results/full-paper/final-comparison.json)。成功计时配置取 3 次算术平均；总时间为作者初始化时间加算法执行时间，进程峰值 RSS 单独记录。SIGMOD 作者计时为墙钟，VLDB 作者计时为 CPU 时钟，不能把表中比值解释为严格同一端到端时钟的加速比。

### 核心性能

| 数据集 | HyperCD* 总时间 (s) | HyperCD* 执行时间 (s) | VLDB 总时间 (s) | 时间比 VLDB / HyperCD* | HyperCD* 峰值 RSS (MiB) |
| :-- | --: | --: | --: | --: | --: |
| HI | 0.120 | 0.035 | 0.838 | 6.99× | 44.17 |
| CO | 0.655 | 0.522 | 3.042 | 4.65× | 16.58 |
| GE | 0.941 | 0.370 | 6.967 | 7.41× | 104.07 |
| DB | 2.418 | 1.135 | 19.946 | 8.25× | 208.51 |
| DF | 2.573 | 1.236 | 20.320 | 7.90× | 219.41 |
| THS | 14.583 | 9.320 | 135.367 | 9.28× | 543.50 |
| AM | 20.746 | 5.784 | 122.856 | 5.92× | 1891.19 |
| TAS | 18.739 | 16.429 | 98.711 | 5.27× | 425.77 |
| AMZ | 502.636 | 51.779 | 2488.760 | 4.95× | 1252.15 |
| SOA | 552.612 | 7.810 | 内存限制 | — | 791.13 |

在两种方法均完成的 9 个数据集上，总时间比为 **4.65–9.28×**。SOA 的 baseline 触发内存限制，未给出时间均值或加速比。不同硬件、公开输入版本及计量口径的影响见[结果分析](docs/experiment-results.md)。

数据集缩写：HI = History，CO = Congress-bills，GE = Geology，DB = DBLP，DF = DBLP-FULL，THS = Threads-stack-overflow，AM = Aminer，TAS = Tags-stack-overflow，AMZ = Amazon，SOA = Stack-overflow-answers。

### 过滤策略与规模扩展

组合 LB + RUC 在 10 个真实输入中的 **8 个**具有比仅 LB、仅 RUC 都短的执行时间；DF 上仅 RUC 略快，SOA 上仅 LB 和仅 RUC 都略快。POW-S 上组合策略也没有取得最短执行时间，因此结果不支持“组合过滤在所有输入上都最快”。

真实数据的 RUC 耗时占执行时间比例为 **8.71%–22.99%**，该比例来自独立统计运行。AMZ、TAS、SOA、AM 的 20%–100% 规模实验全部有测量结果；SOA 的增长明显快于超边比例增长，不能把所有曲线概括为线性。完整逐轮统计、过滤消融和规模数值见[详细结果](docs/experiment-results.md)。

### CPU 并行扩展

| 数据集 | 1 线程总时间 (s) | 64 线程总时间 (s) | 相对 1 线程加速 |
| :-- | --: | --: | --: |
| AMZ | 561.111 | 16.747 | 33.51× |
| SOA | 519.922 | 10.901 | 47.69× |
| POW-L | 超时 | 875.790 | — |

并行表使用同一并行实现的 1 线程结果作分母。POW-L 的 1 线程组超时，不使用另一顺序实现的耗时替代分母；2–64 线程结果保存在比较 JSON 中。

### 大规模输入

| 输入 | HyperCD* 初始化 (s) | HyperCD* 执行 (s) | HyperCD* 总时间 (s) | 峰值 RSS (GiB) |
| :-- | --: | --: | --: | --: |
| POW-S | 1210.88 | 132.32 | 1343.21 | 10.30 |
| POW-L | 17206.13 | 1486.66 | 18692.80 | 205.34 |

这些输入使用作者公开生成器及本项目记录的参数生成，实际规模与论文表 4 分列。对应原论文时间、数据统计及差异分析见 [table-5-comparison.json](data/results/full-paper/table-5-comparison.json) 和[详细结果](docs/experiment-results.md#pow-s--pow-l-与论文比较)。

## 数据与代码

- `src/`：算法适配器、数据工具及小图 oracle；`scripts/`：下载、构建、运行、校验、汇总和绘图入口。
- `configs/`：固定版本、方法映射、数据来源与实验参数。
- `data/results/full-paper/`：随仓库提供的小型结果与配置快照；[data/README.md](data/README.md) 说明归档内容和大型数据位置。
- `data/raw/`、`data/processed/`：运行时产生的原始数据与处理后超图，大型输入不放入 Git。
- `docs/experiment-plan.md`：实验设置；`docs/experiment-results.md`：各实验结果和差异分析。

## 引用

论文 BibTeX 见 [references.bib](references.bib)。本仓库是课程复现项目；作者原始实现的许可分别由对应上游仓库规定。

README 结构参考 [Papers with Code 的公开研究代码模板](https://github.com/paperswithcode/releasing-research-code/blob/master/templates/README.md)，将训练/评估部分调整为超图算法的构建、验证与复现实验。
