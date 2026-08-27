# 项目计划

## 1. 范围与成功标准

交付一个可在本机工作目录中完成真实小型编程任务的 CLI Agent，而不是现成产品的 UI 包装。模型只负责生成下一步的自然语言或结构化工具调用；本地程序负责工具定义和执行、状态保存、上下文裁剪、循环停止、错误恢复和安全边界。

最小演示任务：在一个 `calculator` 示例项目中，Agent 读取失败测试，修改实现，运行 `pytest`，处理一次失败反馈，并报告变更和验证结果。演示必须使用独立的临时工作目录，不能让 Agent 修改本项目或用户主目录。

完成判据：

1. 用户可用一条 CLI 命令运行，凭据通过 `OPENAI_API_KEY` 和可选 `OPENAI_BASE_URL`、`OPENAI_MODEL` 提供。
2. Agent 能调用 `list_files`、`read_file`、`write_file`、`run_command`，并拒绝越出工作区的路径。
3. 工具调用、异常、轮数耗尽和用户中止都有明确、可测试的终止结果和 JSONL 轨迹。
4. 单元测试用假模型覆盖循环而不产生 API 费用；集成演示只在用户提供密钥后运行。
5. README.txt 不超过 1000 汉字，视频不超过 2 分钟/200 MB，仓库公开且在截止前停止推送。

## 2. 技术方案

选用 Python 3.11+、`argparse`、`pathlib`、`subprocess`、`json` 等标准库及轻量 HTTP 客户端 `httpx`。不引入 LangChain、LlamaIndex、OpenAI Agents SDK、AutoGen、CrewAI 或任何 Agent 框架。即使模型端支持 tool calling，也只把它视作 JSON 通信格式；工具注册、参数验证、执行与结果回填均在本地实现。

建议目录：

```text
src/pine/
  cli.py             # 参数、交互和退出码
  agent_loop.py      # 核心状态机
  model_client.py    # OpenAI 兼容 HTTP 请求与响应归一化
  protocol.py        # 消息、工具调用、运行结果数据类型
  context.py         # 历史预算、裁剪与摘要策略
  tool_registry.py   # 工具 schema、分派和参数校验
  workspace.py       # 路径解析、文件读写、大小限制
  command_runner.py  # 进程、超时、截断与退出码
  trace.py           # JSONL 事件审计
tests/
  test_loop.py test_workspace.py test_tools.py test_context.py
demo_project/
docs/ tools/
```

## 3. 里程碑与提交

| 检查点 | 内容 | 验收 | 建议提交信息 |
| --- | --- | --- | --- |
| P0 | 仓库、文档、忽略规则、状态脚本 | `status.ps1` 正确报告无远端 | `docs: add project plan and tracking` |
| P1 | 配置、协议模型、CLI 骨架 | 缺少密钥时给出明确错误 | `feat: add CLI and configuration` |
| P2 | 本地文件工具与工作区边界 | 越界、二进制和大文件测试通过 | `feat: add sandboxed file tools` |
| P3 | 命令工具、超时、输出截断、确认 | 超时与非零退出码可复现 | `feat: add guarded command runner` |
| P4 | 模型客户端、工具 schema 与循环 | 假模型驱动多轮工具链测试通过 | `feat: implement agent loop` |
| P5 | 上下文预算、摘要、轨迹和恢复 | 长历史裁剪不破坏协议 | `feat: add context and trace handling` |
| P6 | 端到端 demo、安全审计、文档 | 真实任务录屏成功，测试全绿 | `docs: finalize demo and submission guide` |

每个检查点只做一件可验证的事，测试与实现同提交；通过后立即推送一个不可改写的提交。不要等到项目结束才一次性推送，也不要在已推送历史上 rebase 或 force-push。

## 4. 进度节奏

以 2026-09-02 24:00（北京时间）为硬截止。先完成 P0--P4 获得可演示 MVP，再用 P5 增强可靠性，最后留出至少半天录制、压缩、检查提交物。每天开始更新 `docs/PROGRESS.md` 的“本次计划”，每完成一项更新状态、证据和 commit；每天结束执行一次 `tools/status.ps1` 并确认远端同步。

## 5. 风险与取舍

| 风险 | 处理 |
| --- | --- |
| API 或模型不稳定 | 抽象 `ModelClient`，单元测试全部使用脚本化假模型；保留清晰网络错误。 |
| shell 有破坏性 | 默认需要确认；P3 只允许在 workspace 内启动，超时杀掉进程，记录命令。 |
| 上下文超限 | 保留系统提示、最新用户目标、未完成工具调用和最近结果；将早期完成段压缩为摘要。 |
| 为做功能而使用框架 | 依赖清单仅保留 HTTP 客户端和测试工具；每个关键模块写清自己实现的职责。 |
| 截止前仓库历史薄弱 | 每个 P 阶段一次独立推送，提交消息描述行为和测试证据。 |
