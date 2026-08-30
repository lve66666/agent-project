# Pine Agent

一个从零实现的命令行编程智能体。它调用兼容 OpenAI 工具调用协议的模型，但由本项目自行管理上下文、工具执行、循环、错误和审计记录；不使用任何 Agent 框架或托管代码/文件工具。

项目尚处于设计阶段。开发顺序、验收条件和当前状态见 [docs/PROGRESS.md](docs/PROGRESS.md)；设计理由见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 目标体验

用户在目标项目目录执行 `pine "为 calculator.py 添加输入校验，并运行测试"`。Agent 搜索/读取仓库、提出或直接执行受允许的工具调用、查看测试结果并在有限轮次内给出结果和可复查的本地轨迹。

## 约束

- Python 3.11+，运行时仅使用标准库；命令行基于标准库 `argparse`。
- API 凭据仅从环境变量读取；绝不写入日志、Git 或演示视频。
- 文件工具限定在显式的 workspace 根目录；命令工具有超时、输出上限和确认策略。
- 每次运行写入本地 JSONL 事件轨迹，包含模型请求摘要、工具请求、工具结果和终止原因。

## 立即开始

按 [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) 的 P0--P6 实施。每完成一个检查点，运行 `powershell -ExecutionPolicy Bypass -File tools/status.ps1` 查看计划、Git 和远端状态；再用 `tools/checkpoint.ps1` 创建小而可解释的提交。交付前运行 `tools/verify.ps1`。远端配置后检查点脚本才会推送，避免误推送。
