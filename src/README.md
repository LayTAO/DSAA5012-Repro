# 项目代码

本目录提供调用固定版本作者实现的 C++ 适配器，以及独立的小图正确性参考实现。作者完整代码由 [fetch_upstream.py](../scripts/fetch_upstream.py) 按 [upstream.lock.json](../configs/upstream.lock.json) 获取到 `external/`，不复制进本目录。

## C++ 入口

- `drivers/sigmod.cpp`：SIGMOD 核心方法的统一运行、计量和 core CSV 导出。
- `drivers/vldb.cpp`：VLDB Local-core-OPTIV baseline 的计量及输出适配。
- `drivers/sigmod_extended.cpp`：逐轮/过滤统计和 1–64 线程并行入口。
- `drivers/generate_synthetic.cpp`：作者合成数据生成器的固定种子入口。
- `drivers/sample_sizes.cpp`：规模实验的数据抽样入口。
- `drivers/audit_hypergraph.cpp`：大型输入结构与统计核查。
- `drivers/metrics.h`：共同的计量输出辅助代码。

[configs/methods.json](../configs/methods.json) 固定方法与参数映射：`0` 为 HyperCD*（LB + RUC），`1` 为仅 RUC，`2` 为仅 LB，`3` 为 HyperCD+，`4` 为 HyperCD，`5` 为 HyperCD++（SUC）；VLDB baseline 参数为 `OPTIV`。

## 正确性与实验调度

`repro/oracle.py` 针对小输入独立计算强诱导超图的邻域 core number，默认最多 128 个节点；它用于正确性验证，不作为性能 baseline。完整输出的节点 ID 与 core 值检查见 [validate_cores.py](../scripts/validate_cores.py)，测试位于 [tests/](../tests/)。

数据下载、转换、构建、队列、汇总及绘图脚本位于 [scripts/](../scripts/)。`build_drivers.sh` 构建主适配器，`build_extended.sh` 构建统计/并行及生成器，`build_data_tools.sh` 构建规模抽样和审计工具。需要 Linux、Python 3.10+、支持 C++20/OpenMP 的编译器；正式服务器构建必须经 `run_on_server.sh`。

固定种子及统计插桩的派生源码在 `build/extended/generated/` 生成，相关变更与 SHA 记录在 setup 结果中，不直接改写已固定的作者源文件。实验所用本项目代码的 SHA 清单见 [source-checksums.json](../data/results/full-paper/input/source-checksums.json)。
