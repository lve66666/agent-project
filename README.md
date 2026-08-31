# Pine Agent

Pine Agent 是一个从零实现的本地 Coding Agent。它通过 OpenAI 兼容的 Chat Completions API 完成“检查代码、修改文件、运行测试、根据结果继续修复”的多轮任务。项目不使用 LangChain、LlamaIndex、OpenAI Agents SDK、AutoGen、CrewAI 或其他 Agent 框架，也不依赖服务端托管的代码执行和文件工具。

## 已实现功能

- **CLI**：从终端提交任务，限制最大轮数和总时间，并输出停止原因、轮数和工具调用数。
- **桌面 GUI**：基于 Python 标准库 Tkinter，实时显示模型请求、工具调用、工具结果和错误；API 配置放在独立弹窗，主页不显示密钥。
- **Plan Mode**：`Plan Task` 先运行只读规划阶段，只能列出、搜索和读取文件；用户可以编辑、批准或拒绝方案，批准后才进入可修改文件和运行命令的执行阶段。
- **五个本地工具**：`list_files`、`search_text`、`read_file`、`write_file`、`run_command`。工具由本地注册表定义、校验参数并执行，模型不能直接访问文件系统或 shell。
- **安全边界**：所有文件路径必须位于指定 workspace；拒绝 `..`、`.git`、符号链接逃逸、二进制和超大文件。命令默认弹窗确认，且有工作目录限制、超时和输出上限。
- **可靠运行**：本地 `AgentLoop` 管理对话历史、工具结果回填、上下文预算、取消信号和终止条件。停止原因明确区分 `completed`、`max_turns`、`timeout`、`model_error`、`protocol_error` 和 `cancelled`。
- **可审计 trace**：每次运行在 `runs/` 生成 JSONL 事件，包括请求、回复、工具调用、工具结果和最终原因；敏感字段和 API key 会脱敏。

## 环境要求

Python 3.11+。运行时只使用标准库；模型服务需要一个 OpenAI 兼容接口。CLI 从环境变量读取连接信息：

```powershell
$env:OPENAI_API_KEY = "你的密钥"
$env:OPENAI_BASE_URL = "https://api.openai.com/v1" # 可选
$env:OPENAI_MODEL = "gpt-4.1-mini"                  # 可选
```

密钥不会写入源码、README、Git、trace 或视频。GUI 中填写的密钥只保存在当前进程内，关闭程序即丢弃。

## 运行

在仓库根目录执行：

```powershell
$env:PYTHONPATH = "src"
python -m pine.cli "为 calculator.py 增加除零校验并运行测试" `
  --workspace demo_project --max-turns 10 --max-seconds 180 --trace-dir runs --yes
```

不使用 `--yes` 时，每个 `run_command` 都会询问 `Allow command ...? [y/N]`。启动 GUI：

```powershell
$env:PYTHONPATH = "src"
python -m pine.gui
```

也可以安装为本地命令：`python -m pip install -e .`，之后使用 `pine` 和 `pine-gui`。

## 演示项目

- `web_demo/`：成绩统计网页（HTML/CSS/JavaScript），可计算平均分、最高分和及格人数，并用 `node --test web_demo/test_app.js` 验证。
- `grade_demo/`：Python 成绩统计模块，适合演示搜索逻辑、修复空列表异常和补充测试。
- `demo_project/Fibonacci/`：斐波那契数、列表和求和任务，适合演示多轮修改与错误校验。

运行离线测试：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
powershell -ExecutionPolicy Bypass -File tools/verify.ps1
```

## 设计重点

模型只决定下一步建议；`AgentLoop`、工具参数校验、工作区权限、上下文裁剪、循环终止、错误处理和 trace 都由本项目自行编写。工具结果作为 `tool` 消息进入下一轮，因此模型能依据测试失败继续修复；达到本地轮数或时间预算时，循环强制停止。详细流程见 [流程.md](流程.md)，架构说明见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。
