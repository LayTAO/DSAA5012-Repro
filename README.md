# DSAA5012-Repro

DSAA5012 课程论文复现项目：以 SIGMOD 2025 的 **Accelerating Core Decomposition in Billion-Scale Hypergraphs** 为主论文，以 VLDB 2023 的 **Neighborhood-based Hypergraph Core Decomposition** 为 baseline。

## 项目目标

- 在同一数据、预处理和运行环境下复现超图 core decomposition 实验。
- 先逐节点验证 core number 一致性，再比较运行时间与峰值内存。
- 将复现结果与主论文报告的结果对照，说明一致之处、差异及实验范围。

**当前状态：项目骨架已建立，尚未运行复现实验。** 上游代码版本已固定；SIGMOD 全文的实验图号、完整数据集清单及参数仍待逐项核对。

## 论文与数据

| 角色 | 论文 / 资源 | 代码 |
| --- | --- | --- |
| 主论文 | [SIGMOD 2025](https://doi.org/10.1145/3709656) | [unswdb/hyper-k-core](https://github.com/unswdb/hyper-k-core) |
| Baseline | [VLDB 2023](https://arxiv.org/abs/2301.06426) | [toggled/vldbsubmission](https://github.com/toggled/vldbsubmission) |
| 数据来源 | [Cornell / Austin R. Benson datasets](https://www.cs.cornell.edu/~arb/data/) | 具体版本需与主论文对齐 |

引用信息见 [references.bib](references.bib)，实验范围见 [docs/experiment-plan.md](docs/experiment-plan.md)。

## 快速开始

建议在 Linux 服务器运行正式实验。准备 Git、Python 3.8+、支持 OpenMP 的 C++ 编译器和 CMake；以下项目管理脚本只使用 Python 标准库。

```bash
# 下载两份作者代码并检出固定 commit；不运行下载的程序
python3 scripts/fetch_upstream.py

# 记录当前环境（结果默认不纳入 Git）
python3 scripts/capture_environment.py

# 以 Release 模式构建 SIGMOD 实现；默认使用 4 个编译任务
bash scripts/build_sigmod.sh
```

`configs/upstream.lock.json` 记录代码来源和完整 commit SHA。作者代码位于被 Git 忽略的 `external/`，其许可仍由各自仓库决定。下载脚本不会覆盖或切换已有的不同版本；若已有目录不匹配，会停止并提示。

baseline 的编译与正式运行命令将在核对作者脚本后加入统一实验入口；目前不要直接运行批量实验脚本。SIGMOD 的 `org` 操作会覆盖输入数据，必须在原始数据副本上进行。

## 目录结构

```text
configs/       固定的上游版本与后续实验配置
data/raw/      原始数据（忽略）
data/processed/统一预处理后的数据（忽略）
docs/          实验计划和复现说明
external/      按 lock 文件获取的作者代码（忽略）
notebooks/     后续分析与绘图 notebook
results/       环境记录、运行日志、原始结果和图表（默认忽略）
scripts/       获取代码、记录环境与构建脚本
src/           后续数据转换、校验器及实验适配代码
references.bib 论文引用
```

## 实验规范

1. 保留原始数据，记录来源、版本和校验值；不要混用 `full`、裁剪版本和投影图。
2. 对齐节点映射、重复记录处理和超边清洗规则；保存转换后的数据统计。
3. 主对比统一单线程；并行实验单独控制线程数与 CPU 绑定。
4. 分开记录数据读取、初始化、算法执行及整体进程耗时；明确峰值 RSS 的测量范围。
5. 每次运行保留算法版本、参数、重复编号、退出状态和原始日志；超时与内存不足单独记录。
6. 上游示例输出不能当作本项目实验结果；未复现的论文实验须在报告中明确列出。

## 推送到 GitHub

在 GitHub 创建一个名为 `DSAA5012-Repro` 的空仓库，不要额外初始化 README 或许可证，然后将下方的 `YOUR_GITHUB_USERNAME` 替换成你的用户名：

```bash
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/DSAA5012-Repro.git
git push -u origin main
```

本项目不包含 SSH 密钥、服务器账号、数据文件或已产生的实验结果。正式发布图表时，请选择要提交的文件，不要将整个原始结果目录强制加入 Git。
