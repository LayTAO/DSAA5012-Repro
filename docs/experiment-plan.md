# 实验协议与执行入口

本文记录最终执行的范围与口径，替代早期骨架计划。全部尝试已结束，最终状态及异常见 [experiment-results.md](experiment-results.md)，机器可读结果见 [summary.json](../data/results/full-paper/summary.json)。

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

## 服务器执行入口

正式目录固定为 `/data/taolei/DSAA5012-Repro-full`。服务器所有写入必须通过下述入口，并由 `server_env.sh` 验证项目与 `/` 位于不同设备，将缓存及临时文件重定向到项目 `.runtime/`。

```bash
cd /data/taolei/DSAA5012-Repro-full
bash scripts/run_on_server.sh COMMAND [ARGUMENTS...]
```

新环境需要 Git、Python 3.10+、C++20/OpenMP 编译器及 GNU time 等运行工具。准备顺序为：固定上游版本（`fetch_upstream.py`）→ 主适配器（`build_drivers.sh`）→ 扩展与数据工具（`build_extended.sh`、`build_data_tools.sh`）→ 数据下载/转换及小图检查 → 正式队列。所有步骤都经上述入口执行；本项目不自动安装系统软件。

`run_full_workflow.py` 不是空仓库的一键下载命令：它要求已准备好的真实输入、二进制与先前核心批次；随后生成规模输入，执行真实扩展、POW-S、POW-L 阶段，按检查点继续。运行前核对 `status.json`、`workflow.pid`、各阶段 `running.json` 与实际进程，不重复启动已有任务、不改变活跃输入和二进制。

当前队列已经结束。查看或复算结果使用 [README 的本地汇总命令](../README.md#本地核查已归档结果)，不需要重新启动服务器实验。远程小型导出使用 `sync_full_results.py`；完整 core CSV 和大型输入继续留在服务器。
