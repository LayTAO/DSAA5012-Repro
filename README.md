# DSAA5012-Repro

DSAA5012 课程论文复现项目：以 SIGMOD 2025 的 **Accelerating Core Decomposition in Billion-Scale Hypergraphs** 为主论文，以 VLDB 2023 的 **Neighborhood-based Hypergraph Core Decomposition** 为 baseline。

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
