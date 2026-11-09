# 运行结果

正式实验队列已经结束，最终统计为 **405 条记录：382 成功、11 超时、9 内存限制、3 崩溃**。完整结果说明见 [docs/experiment-results.md](../docs/experiment-results.md)。

## 如何查看

可直接从 Git 获取的小型结果保存在 [data/results/full-paper/](../data/results/full-paper/)，而非本目录。其 `summary.json`、`final-comparison.json` 和 `final-audit.json` 分别提供统计、论文比较及审计记录。`input/` 保留重建统计所需的测量和配置，原始失败记录没有删除。

服务器 `/data/taolei/DSAA5012-Repro-full/results/` 保存完整日志及 core CSV，主要运行目录为 `full-workflow-001`、`full-real-001`、`full-synthetic-small001`、`full-synthetic-large001` 和 `final-audit-001`。早期 `paper-*` 结果在原目录保留并纳入最终汇总。

本地 `reports/full-comparison/` 是报告生成工作副本；`reports/ieee-reproduction/` 保存最终 IEEE 报告及源文件。历史 `reports/history-pilot/` 与 `reports/paper-comparison/` 保留此前试跑和核心实验材料，不能与最终全量统计重复相加。

## 新运行与重建

本目录的运行产物默认被 Git 忽略。重新汇总或绘图使用新的输出目录，例如 `results/review/`；不要覆盖 `data/results/full-paper/` 的已审计快照。重跑正式实验前核对工作流、PID 及输入/二进制 SHA，不能重复启动活跃实验，也不能覆盖旧日志。

每次正式尝试保留命令、输入及二进制标识、重复编号、时间/内存限制、退出状态、原始日志与校验信息。超时、内存限制、崩溃和校验不一致必须单列；只有重复次数完整且通过校验的成功组才提供均值。
