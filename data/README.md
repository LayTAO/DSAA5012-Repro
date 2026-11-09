# 数据与结果归档

## 纳入 Git 的内容

[results/full-paper/](results/full-paper/) 保存最终小型归档。`archive-manifest.json` 记录 470 个文件的大小与 SHA256，总计 1,853,588 字节（不含清单本身）。

- `summary.json`：405 条记录、143 组配置的状态及统计。
- `final-comparison.json`：性能、消融、逐轮统计、过滤开销、规模、线程扩展及论文对照。
- `final-audit.json`：输入、二进制、完整输出校验记录和失败记录的最终审计。
- `table-5-comparison.json`：POW-S、POW-L 的表 5 对照。
- `input/`：重建上述汇总所需的逐次测量、配置快照、数据 manifest、校验及环境信息；`input/source-checksums.json` 固定本项目 49 个代码文件的 SHA256。

归档中 `${PROJECT_ROOT}` 与 `${ORIGINAL_PROJECT_ROOT}` 是路径占位符；完整 core CSV 和大型输入不在 Git 中。不能将这些 JSON 误认为原始超图数据。

## 服务器上的大型数据

当前正式目录为 `/data/taolei/DSAA5012-Repro-full`：

- `data/raw/`：原始下载或生成的数据，保留来源及校验记录。
- `data/processed/`：作者格式输入、节点映射、规模子集和数据统计。
- `results/`：各次运行日志、完整 core 输出及工作流记录。

早期 `/home/taolei/DSAA5012-Repro` 的结果仍保留，最终归档通过原路径引用这些记录。本地同名目录中的 `.gitkeep` 仅用于保留目录结构；不会把大型数据下载到本地。

## 输入与预处理

真实数据涵盖 HI、CO、GE、DB、DF、THS、AM、TAS、AMZ、SOA，来源与下载入口分别见 [Cornell 配置](../configs/cornell-datasets.json) 和 [扩展数据配置](../configs/extended-datasets.json)。以每份数据的 manifest 为准，区分公开版本、时间记录去重、单点超边移除及作者数组计数；这些数字与论文表 4 不一定相同。

POW-S 和 POW-L 使用作者公开的 `generateHypergraph_nbr_PowerLaw` 生成器，固定种子 **5012**。请求节点数和超边数分别为 60,000,000 / 60,000,000 和 1,100,000,000 / 1,100,000,000；参数见 [synthetic-profile.json](../configs/synthetic-profile.json)。生成后实际节点、超边统计独立保存在 manifest，不等同于请求参数。保留归档中的 `POW-S-approx`、`POW-L-approx` 标识以保持结果可追溯；未把重新生成的输入当作论文原始文件。

作者 `.hyp` 输入每行一条超边、节点 ID 用逗号分隔。原始下载文件不做就地覆盖；作者 `org` 操作只能针对处理副本。不同算法须使用对齐后的相同输入与节点映射。正式数据处理通过服务器保护入口执行，不能绕过该入口将临时文件写到根分区。
