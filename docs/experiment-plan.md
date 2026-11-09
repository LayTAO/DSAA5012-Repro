# 实验协议与执行入口

本文记录论文图表、实验配置、测量口径及正确性验证方法。完整执行命令见 [README 快速启动](../README.md#快速启动)，结果分析见 [experiment-results.md](experiment-results.md)。

## 方法与版本

以 SIGMOD 2025 的 HyperCD 系列为主，VLDB 2023 的 Local-core-OPTIV 为 baseline。同一输入及节点映射下比较两套实现，并保留作者自身的计时口径。

- SIGMOD 上游：`unswdb/hyper-k-core`，commit `db709d81c3da8fff410c6b4f4aa2932883a227ee`。
- VLDB 上游：`toggled/vldbsubmission`，commit `ea540958c176058b44830960753d854017719be2`。
- 方法映射：[methods.json](../configs/methods.json)；项目代码指纹：[source-checksums.json](../data/results/full-paper/input/source-checksums.json)。

## 论文图表与已执行范围

- **图 4–6**：HI、CO、GE、DB、DF、THS、AM、TAS、AMZ、SOA 的总时间、执行时间和进程峰值 RSS，比较 HyperCD 系列与 VLDB baseline。
- **图 7**：DF、THS、TAS、AMZ 的逐轮计算节点数，比较 HyperCD*、RUC、LB、SUC。
- **图 8**：过滤策略消融，比较 LB、RUC、HyperCD* 及 baseline；真实及合成输入的失败配置均保留。
- **图 9**：RUC 过滤时间占执行时间的比例；10 个真实数据集及 POW-S 有成功结果，POW-L 的统计运行超时。
- **图 10**：AMZ、TAS、SOA、AM 按 20%、40%、60%、80%、100% 超边规模运行 HyperCD*。
- **图 11**：AMZ、SOA、POW-L 分别使用 1、2、4、8、16、32、64 个 CPU 线程；POW-L 的 1 线程组超时。
- **表 5**：POW-S、POW-L 的算法时间、内存及论文数据对照，记录公开生成器参数和实际输入统计。

图号对应关系与原文数字/图读数保存在 `configs/paper-*.json` 及最终归档中。配置快照中的早期规划备注不代表当前完成状态；以最终审计和结果汇总为准，不回改历史配置。

## 重复、时间、内存与计量

正式计时配置各尝试 **3 次**，共 393 条。另有 12 条 LB/RUC/SUC 的确定性逐轮计数观测，共计 405 条。仅对规定重复全部成功且完整输出校验通过的组计算算术平均；一条成功、两条超时的组也不提供成功样本均值。

单次正式运行墙钟超时为 **21,600 秒（6 小时）**。扩展批次设置 **500 GiB 的 RLIMIT_AS 虚拟地址空间上限**，这与峰值 RSS 或机器物理内存不是同一个指标。复用早期 HI、CO、DB 核心结果的上限为 32 GiB，AM 为 128 GiB；保留每条记录的真实限制，不声称全部批次内存上限相同。

SIGMOD 的作者计时使用墙钟，baseline 的作者计时使用 CPU 时钟；图表中的记录总时间为作者初始化时间加算法执行时间。进程墙钟另存，不能与该总时间混用。峰值 RSS 使用 GNU time 的整个进程峰值；统计插桩运行与核心性能计时分开。

主对比为单线程，线程扩展单独运行并记录线程数和 CPU 绑定。实验服务器为双路 AMD EPYC 7543、64 个物理核/128 个逻辑线程、约 1007.7 GiB 内存、Ubuntu 22.04、GCC 11.4。硬件与论文机器不同，绝对时间不能解释为相同硬件的精确复测。

## 数据与正确性

真实数据公开版本、预处理及计数差异见 [data/README.md](../data/README.md) 和各输入 manifest。POW-S/POW-L 使用作者公开生成器和固定种子 5012，参数见 [synthetic-profile.json](../configs/synthetic-profile.json)，实际统计与论文表 4 分列。

先用小图 oracle 检查强诱导超图语义，再对适配器的完整节点 ID/core 输出进行对比。运行时完整输出的 SHA 与参考记录比较；最终审计另查 CSV 存在和大小，没有第二次重读全部巨大 CSV 计算 SHA。超时、内存限制和崩溃记录不会被标记为通过正确性验证。

## 执行命令

[README 快速启动](../README.md#快速启动) 按顺序给出项目获取、依赖准备、作者代码下载、四个构建入口、小图验证、真实数据处理、正式队列、审计和图表导出的完整命令。

`run_full_workflow.py` 依赖已准备的十个真实输入、二进制及 HI/CO/DB/AM 的 `paper-*-001` 核心批次；对应前置步骤不能省略。数据与结果目录名由 `configs/full-datasets.json` 和运行器共同确定。

单独运行扩展阶段时，现有入口如下。下列命令对应完整工作流内部步骤，不能在同一队列活跃时再启动一遍：

```bash
bash scripts/run_on_server.sh python3 scripts/prepare_full_inputs.py scales AMZ TAS SOA AM
bash scripts/run_on_server.sh python3 scripts/run_extended_suite.py \
  --phase real --run-id 001 --timeout 21600 --memory-gib 500

bash scripts/run_on_server.sh python3 scripts/prepare_full_inputs.py synthetic POW-S-approx
bash scripts/run_on_server.sh python3 scripts/run_extended_suite.py \
  --phase synthetic --datasets POW-S-approx --run-id small001 \
  --timeout 21600 --memory-gib 500

bash scripts/run_on_server.sh python3 scripts/prepare_full_inputs.py synthetic POW-L-approx
bash scripts/run_on_server.sh python3 scripts/run_extended_suite.py \
  --phase synthetic --datasets POW-L-approx --run-id large001 \
  --timeout 21600 --memory-gib 500
```

方法参数、重复次数和线程列表由配置/运行器定义；以独立 run ID 执行的自定义实验不自动纳入固定全量导出。复现相同实验集合时保持上述批次名称和参数。
