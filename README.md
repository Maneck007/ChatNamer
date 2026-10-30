# ChatNamer

把 ZCode、Codex、Qoder CN 的本地对话标题整理为 `yyyymmdd_内容概括`。日期取会话开始日，使用本机时区；已有标题优先保留措辞，只添加日期前缀。

这是从个人日常使用中整理出来的实验性工具，目前以 Windows、Python 3.10+ 为使用环境。Claude 桌面端适配器仅提示当前不支持，不改写其云端标题。

## 开始使用

```powershell
git clone https://github.com/Maneck007/ChatNamer.git
cd ChatNamer
Copy-Item config.example.json config.json
```

打开 `config.json`，核对数据库路径，把需要的平台设置为 `"enabled": true`。示例配置默认关闭所有平台。路径支持 `~` 和 Windows 环境变量，例如 `%APPDATA%`；ZCode 的 `tasks_index` 可能位于你自定义的数据目录，必须填写实际位置。

先预览，再决定是否执行：

```powershell
python cli.py --platform codex --no-report
python cli.py --platform codex --apply
```

省略 `--platform` 会处理配置中启用的全部平台；也可使用 `--platform zcode,codex`。运行记录保存在 `records/`，包含原名与新名，请留在本机。

## 命名与摘要

- 最近 60 分钟有活动的会话跳过，窗口可在配置中调整。
- 已符合格式的标题跳过；不确定的标题留待人工整理。
- 启发式摘要来自首条可用用户文本，不等同于模型理解完整对话。
- 外部摘要可用 `python cli.py --apply --summaries summaries.json` 导入，格式为 `{"codex": {"会话ID": "新的概括"}}`。
- `--export-pending pending.json` 导出待整理清单；请先检查内容，再决定是否交给其他工具。

## 写入与备份

| 平台 | 写入位置 | 范围 |
|---|---|---|
| ZCode | CLI `session` + UI 索引 `tasks` | 包含 Fork，排除内部子代理 |
| Codex | `state_5.sqlite` 的 `threads.name` + `session_index.jsonl` | 包含归档与 `agent_created_thread`，排除 guardian/subagent |
| Qoder CN | `main.sqlite` 的 `chat_sessions.title` | 排除已删除会话 |
| Claude 桌面端 | 不写入 | 当前不支持 |

`--apply` 才写入，写前通过 SQLite backup API 备份。每个平台、每次执行使用独立备份目录，默认在系统临时目录的 `ChatNamer_backups/` 下；长期使用建议配置 `backup_dir` 到自己的持久目录。

ZCode 两库在同一 SQLite ATTACH 事务中更新，缺少 UI 记录或标题已经变化时撤销本批修改，并复核两库结果。两库使用 WAL 时，突然断电仍不具备跨文件原子提交保证。Codex 的数据库和 JSONL 索引也不是一个原子事务。首次使用先关闭目标客户端，选择一个平台试用并检查结果。

恢复时先关闭目标客户端，找到对应运行目录的 `.bak`，将备份恢复到配置中的原数据库位置；Codex 还需恢复对应的 `session_index.jsonl`。当前没有自动撤销命令。

## 自动运行与限制

公开版提供手动 CLI，不会安装开机任务、客户端钩子或云端模型调用。可在确认预览结果后自行配置系统计划任务。个人环境中的 ZCode SessionStart 钩子曾未触发，因此本项目不把它作为可靠的默认安装方式。

客户端升级可能改变私有数据库结构。结构不兼容会报错，退出码为非零；请停止写入并提交已脱敏的版本信息和错误。异常退出留下 `.lock` 时，确认没有 ChatNamer 进程后再删除它。

## 开发

```powershell
python -m unittest discover -s tests -v
```

测试使用临时数据库，不接触你的真实对话。支持 `.jsonl.zst` 的 Codex 历史内容提取时，可选安装 `zstandard`；其他功能使用 Python 标准库。

问题和建议请提交到 [Issues](https://github.com/Maneck007/ChatNamer/issues)。[MIT 许可](LICENSE)。本项目借助 AI 编程工具开发，由维护者审阅和验证。
