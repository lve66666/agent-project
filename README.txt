仓库地址：https://github.com/lve66666/agent-project

Pine Agent 是从零实现的本地 Coding Agent，通过 OpenAI 兼容 API 完成读代码、改文件、运行测试和根据失败结果继续修复。不使用 LangChain、LlamaIndex、OpenAI Agents SDK、AutoGen、CrewAI 等 Agent 框架，也不使用服务端代码执行或文件工具。

运行（Python 3.11+）：
1. PowerShell 设置：$env:OPENAI_API_KEY="你的密钥"；可选设置 OPENAI_BASE_URL、OPENAI_MODEL。
2. 根目录执行：$env:PYTHONPATH="src"；CLI 示例：python -m pine.cli "为 calculator.py 增加除零校验并运行测试" --workspace demo_project --yes；GUI：python -m pine.gui。
3. 离线测试：python -m unittest discover -s tests -v。每次运行的 JSONL trace 在 runs/。

特色功能：
- Plan Task 先只读查看文件，用户可编辑、批准或拒绝方案，批准后才允许修改和运行命令。
- 自行实现 AgentLoop、上下文裁剪、协议解析、工具注册/参数校验、错误处理、循环终止和 JSONL 审计。
- 六个本地工具：list_files、search_text、read_file、write_file、edit_file、run_command；edit_file 按精确文本替换，避免重写整个文件。
- write_file/edit_file 返回 unified diff，GUI 在写入前弹窗审批，拒绝则文件不变；摘要统计修改文件、命令、测试状态和失败次数。模型对 429、5xx、超时等临时错误有限退避重试；workspace 路径隔离，命令有确认、超时和输出上限，trace 脱敏。API key 只在进程内保存。

演示项目：web_demo 成绩统计网页；grade_demo 成绩模块；demo_project/Fibonacci 斐波那契任务。
