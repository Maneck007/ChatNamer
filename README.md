# ChatNamer

**聊过的好思路，别再翻半天。**

那次修好的报错、讨论过的方案、做到一半的小项目，都还在聊天记录里。可标题只剩“新对话”，或者几个看不出区别的名字。

ChatNamer 给 **ZCode、Codex、Qoder CN** 的本地对话补上日期和内容概括。下次回来，先看标题，就能多一点找到它的线索。

[看看改名效果](#整理后是什么样) · [开始使用](#开始使用) · [详细用法与备份](docs/USAGE.md) · [反馈建议](https://github.com/Maneck007/ChatNamer/issues)

[![Checks](https://github.com/Maneck007/ChatNamer/actions/workflows/checks.yml/badge.svg)](https://github.com/Maneck007/ChatNamer/actions/workflows/checks.yml)

## 整理后是什么样

| 原来的标题 | 整理后 |
|---|---|
| `修复登录报错` | `20261029_修复登录报错` |
| `新对话`，首条需求是“请帮我整理项目README” | `20261030_整理项目README` |
| `20261028_整理安装说明` | 已符合格式，保持不变 |

*以上是命名规则示例，日期取会话开始日。默认保留已有好标题的措辞；需要生成概括时，从首条可用用户文字中提取，不会通读整段对话。*

## 把整理聊天记录，变成一件可检查的小事

- **几个工具，一套命名习惯。** 支持 ZCode、Codex、Qoder CN，用 `日期_内容概括` 统一整理。
- **先看结果，再决定改不改。** 默认预览；只有加上 `--apply` 才写入，写入前备份。
- **正在聊的，先留着。** 默认跳过最近 60 分钟有活动的会话，也跳过已经符合格式的标题。
- **不必再接一个模型服务。** 默认在本机按规则整理，不调用云端模型；想自己精修概括，也能导入外部摘要。

目前是 **Windows / Python 3.10+ 的命令行工具**，需要手动配置路径。Claude 桌面端暂不支持。

## 开始使用

```powershell
git clone https://github.com/Maneck007/ChatNamer.git
cd ChatNamer
Copy-Item config.example.json config.json
```

打开 `config.json`，核对本机路径，只把准备试用的平台改为 `"enabled": true`。示例配置默认全部关闭；[路径填写说明](docs/USAGE.md#路径配置)在这里。

以 Codex 为例，先预览：

```powershell
python cli.py --platform codex --no-report
```

确认列表里的新标题符合预期，**关闭目标客户端**，再执行写入：

```powershell
python cli.py --platform codex --apply
```

第一次建议只选一个平台试用并检查结果。运行记录保存在本机 `records/`，可以查看原名与新名。其他平台、摘要导入和筛选规则见[详细用法](docs/USAGE.md)。

## 备份和恢复要知道的事

这会修改客户端的本地数据。每个平台、每次执行都有独立备份，默认放在系统临时目录；长期使用建议把 `backup_dir` 设置到持久目录。

当前没有一键撤销，整库恢复会覆盖备份之后的其他变更。客户端升级也可能改变数据结构。执行前请读[写入与备份说明](docs/USAGE.md#写入与备份)，其中包含恢复步骤和跨文件写入的限制。

## 反馈与参与

ChatNamer 来自日常整理 AI 对话的需要，目前仍在早期。欢迎在 [Issues](https://github.com/Maneck007/ChatNamer/issues) 分享你遇到的命名难题，或按[贡献说明](CONTRIBUTING.md)改进它；请勿附带私人对话或数据库。

[MIT 许可](LICENSE)。借助 AI 编程工具开发，由维护者审阅和验证。
