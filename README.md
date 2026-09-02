# Design Asset Organizer

一个面向长期素材管理的图片重命名 Skill。它会分析图片的视觉内容，生成统一、可搜索的中文文件名，帮助你以后直接在 Windows、macOS 或素材库中按关键词找到图片。

## 命名方式

统一使用 5–8 个关键词，并按以下顺序组织：

`主体＊用途/场景＊风格＊色调＊核心视觉元素＊构图＊补充关键词＊中文LOGO/品牌名.原扩展名`

示例：

`金融＊KV＊科技＊蓝紫＊玻璃圆环＊中心透视＊未来感.jpg`

全角 `＊` 可作为文件名字符在 Windows 和 macOS 中使用，也让关键词边界清晰。Skill 会保留 `.jpg`、`.jpeg`、`.png` 或 `.webp` 原扩展名。

## 安装

将整个 `design-asset-organizer` 文件夹放入 Codex 的 Skill 目录：

- Windows：`%USERPROFILE%\.codex\skills\design-asset-organizer`
- macOS / Linux：`~/.codex/skills/design-asset-organizer`

重新打开 Codex 后即可使用。

## 使用

上传单张或多张图片：

```text
$design-asset-organizer 请按上传顺序为这些图片生成可搜索的中文文件名。
```

处理本地文件夹并实际改名：

```text
$design-asset-organizer 请分析 D:\素材\科技 中的图片并直接重命名，保留回退清单。
```

批量建议会保持输入顺序：

```text
01｜IMG_0234.jpg → 金融＊KV＊科技＊蓝紫＊玻璃圆环＊中心透视＊未来感.jpg
02｜IMG_0235.png → 人物＊人物介绍＊毛玻璃＊红白＊半透明卡片＊左右构图＊基金经理.png
```

## 安全改名

项目包含跨平台辅助脚本 `scripts/apply_rename_plan.py`：

- 默认只预览，不修改文件；
- 拒绝覆盖同名文件；
- 保留源扩展名；
- 批量交换名称时使用临时名，避免互相覆盖；
- 执行后生成 JSON 回退清单。

Skill 会在用户明确要求实际改名时调用它。你也可以单独运行：

```text
python scripts/apply_rename_plan.py rename-plan.json
python scripts/apply_rename_plan.py rename-plan.json --apply
python scripts/apply_rename_plan.py --rollback rename-manifest-20260902-120000.json --apply
```

改名计划格式：

```json
{
  "renames": [
    {
      "source": "D:/素材/IMG_0234.jpg",
      "target": "金融＊KV＊科技＊蓝紫＊玻璃圆环＊中心透视＊未来感.jpg"
    }
  ]
}
```

## 项目结构

```text
design-asset-organizer/
├── SKILL.md
├── agents/openai.yaml
├── references/naming-rules.md
├── scripts/apply_rename_plan.py
└── tests/test_apply_rename_plan.py
```

详细命名词库和规则见 `references/naming-rules.md`。
