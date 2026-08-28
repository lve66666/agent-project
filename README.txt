仓库地址：https://github.com/lve66666/agent-project

项目：Pine Agent，一个从零实现的命令行编程智能体。它通过 OpenAI 兼容模型 API 完成真实的“读文件、修改代码、运行测试、根据失败结果继续修复”任务。

运行（Python 3.11+）：
1. 在 PowerShell 设置凭据：$env:OPENAI_API_KEY="你的密钥"；可选设置 OPENAI_BASE_URL、OPENAI_MODEL。
2. 在仓库根目录执行：$env:PYTHONPATH="src"；python -m pine.cli "为 calculator.py 增加除零校验并运行测试" --workspace demo_project --yes。
3. 运行记录写入 runs/ 下的 JSONL 文件；使用 python -m unittest discover -s tests -v 运行离线测试。

特色与设计：
- 不使用任何 Agent 框架或运行时第三方依赖；本地自行实现模型协议解析、工具注册与参数校验、循环终止、上下文裁剪、错误处理和 JSONL 审计。
- 仅提供 list_files、read_file、write_file、run_command 四个工具。所有路径必须位于 workspace；命令有确认、超时和输出上限。
- 模型只提出下一步建议，不能直接访问文件或 shell；本地状态机决定是否执行并在达到轮数/时间预算时停止。

安全：密钥只从环境变量读取，不写入仓库、轨迹或视频。演示使用独立 demo_project 目录；提交截止后不再推送。
