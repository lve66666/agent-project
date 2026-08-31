# 设计与运行机制

## Plan And Execute Mode

`planning.py` is a separate pre-execution stage. It sends the original task to the same model client with `tools=[]` and rejects a response that contains tool calls or no plan text. Therefore plan generation cannot use the local file, search, write, or command tools. The GUI presents this text in an editable modal. Only an explicit user approval starts `AgentLoop`; rejecting the dialog makes no workspace changes.

The approved plan is included with the original task as execution guidance, not as a new authorization mechanism. Tool schemas, workspace confinement, command confirmation, turn limits, time limits, context trimming, and error handling remain owned by the existing local execution loop. One JSONL trace records the planned-run lifecycle: `plan_requested`, `plan_created`, then `plan_approved` plus execution events, or `plan_rejected` with no execution events.

## 一次任务如何运行

```text
用户目标 -> CLI 建立 RunState -> ModelClient 请求模型
                                    |
                              文本完成？----是--> 写 trace，返回结果
                                    |
                               工具调用列表
                                    |
       ToolRegistry 验证名称/JSON 参数 -> Workspace 或 CommandRunner 本地执行
                                    |
                 ToolResult 追加至 history 和 trace -> 下一轮模型请求
```

`AgentLoop` 是单一状态机，而非递归调用。每轮先检查取消信号、最大轮数和总时间预算；再请求模型；若模型返回工具调用，就依序执行并把每一项结果作为 `tool` 消息回填；若模型返回最终文本则成功结束。模型协议错误、工具异常、预算耗尽、用户取消和网络失败都以不同原因结束，但都会得到可读摘要和轨迹。

`gui.py` 不是另一套 Agent。它将现有 `AgentLoop` 放入后台线程，并订阅其本地事件回调；主线程只负责渲染状态与命令确认弹窗。因此 CLI 和 GUI 共享同一套模型通信、工具验证、权限边界和终止逻辑。

## 自行实现的关键逻辑

这些不是调用 SDK 后自动获得的能力，实施时将由本项目编写并以单元测试证明：

| 模块 | 自行编写的逻辑 | 为什么需要它 |
| --- | --- | --- |
| `agent_loop.py` | `RunState` 状态转换、轮次/时间预算、工具结果回填、终止分类 | 防止模型无限循环，保证每次运行可解释。 |
| `tool_registry.py` | 工具 schema、参数 JSON 解码、类型与必填字段验证、分派、结构化错误 | 不信任模型给出的任意文本或任意函数名。 |
| `workspace.py` | `resolve()` 后的根目录包含性检查、文本/大小限制、原子写入 | `../`、符号链接等路径不能逃出用户指定项目。 |
| `command_runner.py` | subprocess 生命周期、超时、stdout/stderr 合并截断、退出码归一化 | 命令会卡住或失败，错误必须成为下一轮可用信息。 |
| `context.py` | 消息预算估计、工具结果局部压缩、保留集选择、早期段摘要和工具调用配对 | 原样累积历史会超出模型上下文且破坏调用协议。 |
| `trace.py` | JSONL 事件序列、敏感字段遮蔽、运行 ID、最终汇总 | 演示、调试和面试时能够还原“为何这么做”。 |

## 工具边界

当前提供五个工具：

- `list_files(path, depth)`：遍历工作区内的文本目录，跳过被忽略目录与超深路径。
- `read_file(path, start_line, end_line)`：读取 UTF-8 文本，返回行号并限制字节数。
- `write_file(path, content)`：仅写工作区普通文件，先创建父目录，再原子替换；不写二进制。
- `run_command(command, cwd, timeout_seconds)`：在工作区内运行；默认先征得交互确认，`--yes` 只用于演示；强制超时和输出上限。
- `search_text(query, path, max_results, use_regex)`：搜索工作区内 UTF-8 文本，跳过受保护目录、二进制和超大文件，并限制结果数量。

不在初版实现“任意 Python 执行”或远程文件服务。此取舍让安全策略、失败行为和面试讲解都保持清楚，同时足以完成真实的编辑-测试-修复任务。

## 可辩护的设计决策

### 工具结果局部压缩

`ContextWindow(max_tool_chars=8000)` 在按轮次裁剪前复制消息，并只对过大的 `tool` 消息做头尾保留。中间插入截断标记，保留 `tool_call_id` 和工具名称；原始 `AgentLoop` 历史与 JSONL trace 不变。这样单个 `read_file` 或 `run_command` 输出不会独占上下文，同时最近完整轮次仍按原协议成组保留。

1. 选择有限工具而非让模型直接获得 Python 能力：权限更小、审计更完整，也能明确展示本地工具层。
2. 选择顺序执行同一轮中的工具调用：后续调用不会与前一个写文件操作竞态，输出稳定，便于复现；性能不是本项目主目标。
3. 命令默认确认：模型生成的命令是建议，不是授权。演示时显式 `--yes`，使自动化意图可见。
4. 使用 JSONL 而不是数据库：单次运行可追加、可直接查看、依赖少，满足展示和故障复盘。
5. 先用假模型做循环测试：测试不依赖网络、密钥或模型随机性；端到端测试只验证集成，不承担核心正确性。

## 面试应能讲清楚的边界

模型决定“下一步建议”，但从不直接接触文件系统或 shell。它的工具调用只是经过协议解析的未可信输入；本地注册表验证后才执行。工具结果和失败文本回到下一轮消息中，因此模型能根据测试错误修正策略。循环由本地预算和终止条件控制，不由模型宣称“完成”之外的任何隐式机制控制。
