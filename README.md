# ChatNamer

**给每段对话，一个找得到的名字。**

修好的报错、聊过的方案、做到一半的小项目，都值得有个清楚的标题。ChatNamer 为 **ZCode、Codex、Qoder CN** 的本地对话整理日期与内容概括，让对话列表同时呈现时间和主题。下次回来，顺着标题接着聊。

[看看改名效果](#整理后是什么样) · [开始使用](#开始使用) · [详细用法与备份](docs/USAGE.md) · [反馈建议](https://github.com/Maneck007/ChatNamer/issues)

[![Checks](https://github.com/Maneck007/ChatNamer/actions/workflows/checks.yml/badge.svg)](https://github.com/Maneck007/ChatNamer/actions/workflows/checks.yml)

## 整理后是什么样

| 原来的标题 | 整理后 |
|---|---|
| `修复登录报错` | `20261029_修复登录报错` |
| `新对话`，首条需求是“请帮我整理项目README” | `20261030_整理项目README` |
| `20261028_整理安装说明` | 保留原名 |

*以上是命名规则示例，日期取会话开始日。已有好标题保留措辞；需要生成概括时，从首条可用用户文字中提取，也可导入自己精修的摘要。*

## 一套命名习惯，整理几个工具

- **按日期找，也按内容找。** 用 `日期_内容概括` 整理 ZCode、Codex、Qoder CN 的会话。
- **先预览，再批量改名。** 先检查原名与新名，确认后通过 `--apply` 执行，写入前保存备份。
- **给当前工作留出空间。** 默认保留最近 60 分钟有活动的会话，已符合格式的标题继续沿用。
- **本机运行，按需精修。** 默认使用本地规则，外部摘要文件可用于补充更贴合内容的概括。

运行环境：**Windows + Python 3.10+**，通过命令行使用。

## 开始使用

```powershell
git clone https://github.com/Maneck007/ChatNamer.git
cd ChatNamer
Copy-Item config.example.json config.json
```

打开 `config.json`，参照[路径说明](docs/USAGE.md#路径配置)填入本机位置，并将需要的平台设为 `"enabled": true`。

以 Codex 为例，先查看预览：

```powershell
python cli.py --platform codex --no-report
```

确认新标题符合预期，**关闭目标客户端**，再执行写入：

```powershell
python cli.py --platform codex --apply
```

首次可选择一个平台试用并检查结果。运行记录保存在本机 `records/`，包含原名与新名；更多平台选项、摘要导入和筛选规则见[详细用法](docs/USAGE.md)。

## 运行记录与备份

每个平台、每次执行都使用独立备份目录。长期使用时，可将 `backup_dir` 设置到自己的持久目录。

恢复采用整库备份还原，会覆盖备份之后的变更；恢复前先另存当前数据库。备份位置、恢复步骤、客户端版本适配及跨文件写入说明，统一列在[写入与备份](docs/USAGE.md#写入与备份)中。

## 反馈与参与

ChatNamer 来自日常整理 AI 对话的需要。欢迎在 [Issues](https://github.com/Maneck007/ChatNamer/issues) 分享你的命名习惯、平台适配需求，或按[贡献说明](CONTRIBUTING.md)提交改进。

[MIT 许可](LICENSE)。借助 AI 编程工具开发，由维护者审阅和验证。
