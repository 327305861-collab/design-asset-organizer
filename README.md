# 图片素材命名 · Design Asset Organizer

让 AI 看图，为设计素材生成统一、可搜索的中文文件名；支持安全批量改名和回退。

`金融＊KV＊科技＊蓝紫＊玻璃圆环＊中心透视＊未来感.jpg`

支持 JPG、JPEG、PNG、WebP，保留原扩展名和图片内容。使用全角 `＊`，兼容 Windows 文件名。

## 先选一种用法

| 需求 | 环境要求 |
| --- | --- |
| 上传图片，只要命名建议 | 能看图并读取 Skill 的 AI 工具；不需要 Python |
| 实际改名本地文件夹中的图片 | 本地 Codex、看图能力、素材目录读写权限、Python 3.9+ |

改名脚本只用 Python 标准库，不需要 pip、额外 API Key 或图片识别服务。识图由 AI 工具完成，其账户和模型要求仍由该工具决定。云端会话不能直接处理你电脑上未上传或未连接的文件。

## 安装到 Codex（推荐）

### 方法一：手动复制，不需要 Python

下载本仓库 ZIP 并解压。找到**直接包含 `SKILL.md` 的文件夹**，复制并命名为 `design-asset-organizer`，放到：

- Windows：`%USERPROFILE%\.agents\skills\design-asset-organizer`
- macOS / Linux：`~/.agents/skills/design-asset-organizer`
- 仅当前项目：`<项目>/.agents/skills/design-asset-organizer`

最终应直接存在 `design-asset-organizer/SKILL.md`，以及 `agents/`、`references/` 和 `scripts/`。不要多套一层 `design-asset-organizer-main`，不要只复制 `SKILL.md`。

更新前把旧版移到技能目录之外。旧版装在 `.codex/skills` 且可用的，可继续使用；迁移时保留一份有效安装，避免同名副本。

新建 Codex 聊天，输入 `$design-asset-organizer`。未出现时重启 Codex，检查 Skill 是否被禁用。当前官方目录见 [OpenAI 技能文档](https://learn.chatgpt.com/docs/build-skills)。

### 方法二：安装器

在解压后的目录执行，任选本机可用的一种：

```sh
python install.py
python3 install.py
py -3 install.py
```

默认安装到 `~/.agents/skills/design-asset-organizer`。更新用 `--replace`；旧版自动移到技能扫描目录之外的 `skill-backups`，不覆盖原始材料。安装器不会安装 Python、修改系统 PATH 或联网。

```sh
python install.py --replace
python install.py --dest "/absolute/project/.agents/skills/design-asset-organizer"
```

`--dest` 是完整技能目录，包含最后一级 `design-asset-organizer`。多个 Python 并存时，让 Codex 使用它确认可运行的解释器。

## 使用

上传图片后：

```text
$design-asset-organizer 请按上传顺序为这些图片生成可搜索的中文文件名，只给建议。
```

实际改名（换成自己的路径）：

```text
$design-asset-organizer 请分析 D:\素材\科技 中的图片并直接重命名，不处理子文件夹，保留改名计划和回退清单。
```

回退：

```text
$design-asset-organizer 请使用这份 rename-manifest-xxx.json 回退上次的改名。
```

相同名称会跳过；不同图片命名相同时，先添加区分词或编号。看不到的图片应明确列出，不依据旧文件名猜图。

## 排查“用不了”

| 现象 | 处理方式 |
| --- | --- |
| 找不到 Skill | 检查目录层级、完整文件、新建聊天/重启，以及是否被禁用 |
| python 找不到或无法启动 | 试 python3 --version 或 py -3 --version，或使用宿主已配置的 Python 3.9+；没有则先用命名建议模式 |
| can't open file ... scripts/apply_rename_plan.py | 使用已安装 Skill 的绝对脚本路径，不能假设当前项目就是技能目录 |
| 能命名但不能实际改名 | 确认是本地会话、目录已获读写授权、文件未被占用；建议不代表已改名 |
| 看不到 WebP 或本地图片 | 使用宿主的预览工具或临时转换预览，保留原图；无法查看时上传可查看的图片 |
| 目标已存在 | 为目标换一个未占用的名称，脚本拒绝覆盖 |
| 清单状态不是 applied | 可能执行中断或已回退，先检查实际文件位置，不直接改状态重试 |

诊断命令（换成本机真实绝对路径；路径含空格时保留引号）：

```sh
python "/absolute/skill/scripts/doctor.py"
python "/absolute/skill/scripts/doctor.py" --folder "/absolute/assets"
```

诊断只读、不联网、不上传图片。输出包含本地路径，发给别人前可遮去用户名。

## 手动调用脚本

保存 UTF-8 JSON 计划。相对 source 按**计划文件所在目录**解析，也可用绝对路径：

```json
{"renames": [{"source": "IMG_0234.jpg", "target": "金融＊KV＊科技＊蓝紫＊玻璃圆环＊中心透视＊未来感.jpg"}]}
```

```sh
python "/absolute/skill/scripts/apply_rename_plan.py" "/absolute/rename-plan.json"
python "/absolute/skill/scripts/apply_rename_plan.py" "/absolute/rename-plan.json" --apply
python "/absolute/skill/scripts/apply_rename_plan.py" --rollback "/absolute/rename-manifest-xxx.json" --apply
```

默认只预览。执行前先写恢复清单，成功后标记 applied；回退完成标记 rolled_back，避免重复回退。保留计划和清单，避免多个程序同时改名同一批图片。断电、强制退出或硬盘故障后，可能需要依据清单人工恢复。

macOS / Linux 的安全改名使用文件系统硬链接：exFAT、FAT 或部分共享盘可能不支持，此时脚本会报错并尝试恢复；请在支持硬链接的本地文件系统上操作，或仅使用命名建议模式。

## 其他 AI 工具与英文用户

这是 Markdown 指令和 Python 辅助脚本组成的 Skill，不是可双击的独立应用。支持该格式、看图和文件访问的其他 Agent，可按其自身文档安装完整文件夹；**尚未实测这些宿主，兼容性待确认**。普通聊天工具可结合命名规则和上传图片给出建议，本地改名则需文件执行能力。

English: Generate searchable Chinese filenames for design images. Copy the complete skill folder to `~/.agents/skills/design-asset-organizer`, then invoke `$design-asset-organizer` with images in Codex. Naming suggestions do not require Python. Local renaming requires Python 3.9+ and folder access. Helpers use the standard library; no pip packages or separate API key are needed.

## 开发验证与分发

```sh
python -m unittest discover -s tests -v
python tools/build_package.py
```

生成 `dist/design-asset-organizer.zip`，包含正确的顶层技能目录，不含缓存和用户改名记录。GitHub Actions 配置了 Windows、macOS、Linux 和 Python 3.9/3.12 测试；是否通过，以实际运行记录为准。
