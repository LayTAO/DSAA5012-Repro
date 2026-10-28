# 结果目录

此目录目前没有实验结果。运行产物默认被 Git 忽略，避免误提交大型日志或把示例输出当作实测结果。

建议每批实验建立独立运行目录，包含环境快照、完整命令、原始日志、结构化测量和生成的图表。公开报告所需的小型结果可在审核后选择性加入版本控制。

`python3 scripts/capture_environment.py` 默认生成 `environment.json`；正式运行时使用 `--output results/<run-id>/environment.json` 保留各批次的独立记录。
