# 实时进度

最后更新：2026-08-27

## 当前状态

| 检查点 | 状态 | 可验证证据 | 下一步 |
| --- | --- | --- | --- |
| P0 工程计划与跟踪 | 已完成 | 计划文档与状态脚本；`d7984ea` | 配置公开 `origin` 并推送已有检查点 |
| P1 CLI 与配置 | 已完成 | `python -m unittest discover -s tests -v`：3 项通过 | 实现受限工作区文件工具及越界测试 |
| P2 文件工具 | 已完成 | `unittest`：8 项通过，符号链接测试因系统权限跳过 | 实现命令超时、输出截断和确认策略 |
| P3 命令工具 | 已完成 | `unittest`：11 项通过，1 项符号链接权限跳过 | 实现工具 schema、模型协议解析和 Agent 循环 |
| P4 Agent 循环 | 已完成 | `unittest`：15 项通过，FakeModel 覆盖多轮工具调用 | 实现上下文裁剪、JSONL 轨迹和敏感信息脱敏 |
| P5 上下文与轨迹 | 已完成 | `unittest`：24 项通过，1 项符号链接权限跳过；新增工具结果局部压缩测试 | 准备 calculator 演示、README.txt 和提交物检查 |
| P6 演示与提交 | 进行中 | `tools/verify.ps1`：21 项通过；CLI/GUI 共用 AgentLoop；README.txt 792 字符 | 用真实 API 在 demo_project 录制视频并填写仓库地址 |

## 本次计划

增加 `search_text` 工具和 Tkinter GUI：GUI 复用 AgentLoop，显示本地执行事件并对命令提供确认弹窗；待运行真实 API 演示、录制视频并生成姓名.zip。

## 更新规则

完成一个检查点时：更新本表的状态、填写提交短哈希与测试命令，再运行 `tools/status.ps1`。状态只能是“未开始 / 进行中 / 已完成 / 阻塞”；“已完成”必须带可复现证据。
