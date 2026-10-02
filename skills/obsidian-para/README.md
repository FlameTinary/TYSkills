# obsidian-para

> 本技能是 [TYSkills](../../README.md) 技能集合的一部分：把本目录复制或软链到你的 agent 技能目录即可使用，
> 不需要安装器或账号。仓库级的技能列表与目录结构见主 README。

## 简介

把 PARA 方法论（Tiago Forte：**P**rojects 项目 / **A**reas 领域 / **R**esources 资源 / **A**rchives 归档）
落成**能直接执行**的 Obsidian 库顾问与操作助手。它不陪你讨论方法论，而是给判断、给结构、
给可以直接粘贴的模板、MOC 和 Dataview 查询。

解决的具体问题：

- **归类决策**：30 秒口诀 + 决策树（有 deadline → Project；长期要操心 → Area；只是存着 → Resource；
  已结束 → Archive；拿不准 → Inbox），并覆盖读书笔记、课程、健身、备考、副业等边界案例。
- **目录规范**：`01-Projects/ 02-Areas/ 03-Resources/ 04-Archives/ 99-Inbox/` 加 `Templates/ MOC/ Assets/`，
  含「什么时候**不**建文件夹」的判据——优先 MOC + 标签 + Dataview，解决不了再建目录。
- **frontmatter 规范**：`type / status / due / area / tags / created / modified` 的取值语义，
  以及各类型特有字段（Project 的 `goal` / `done-criteria`、Area 的 `review-cycle`、Resource 的 `source` / `author`、
  Archive 的 `archived-date` / `archive-reason`）。
- **成品模板即用**：4 套笔记模板（项目 / 领域 / 资源 / 归档）+ 4 个总览 MOC（Home / Projects / Areas / Resources），
  复制进库即生效，不需要照着文档手搓。
- **Dataview 查询库**：进行中项目、本周到期、搁置项目、已完成待归档、三个月没动过的资源、
  Area 页内的本领域项目与资源等 10 条查询。
- **库体检**：`scripts/scan_vault.py` 扫一遍报出缺 frontmatter、缺 `type`、近空笔记、`99-Inbox/` 积压，
  迁移前后各跑一次可以看数字是否下降。
- **迁移与复盘流程**：旧库迁移 5 步、每周 / 每月复盘清单、项目归档 5 步、搁置与放弃的区别。

不适用：非 Obsidian 的笔记体系（Notion / Logseq / 语雀 / Evernote）、不认同 PARA 的分类法
（Zettelkasten 卡片盒、纯按文件类型或按年份归档）、以及没有 frontmatter / Dataview 能力的纯 Markdown 编辑器。

## 依赖

- 必需：`python3`（3.8+，仅标准库）—— 只有库体检脚本需要；其余部分是文档、模板与查询
- 强烈建议：Obsidian + **Dataview** 插件（成品 MOC 与模板里的自动汇总全靠它）；
  Obsidian 核心**「模板」插件**（模板中的 `{{title}}`、`{{date:YYYY-MM-DD}}` 由它渲染，不要手改成字面文本）
- 可选：Templater（更强的模板能力）、Web Clipper（网页剪藏直接进 Inbox）—— 两者都不是必需

## 安装

把 `skills/obsidian-para/` 复制或软链到 agent 的技能目录即可（见仓库主 README 的「怎么用」）。
对已有的库，只需要把模板与 MOC 复制进去：

```bash
cd TYSkills/skills/obsidian-para
cp -R assets/templates/* "<你的库>/Templates/"
cp -R assets/moc/*       "<你的库>/MOC/"
```

然后在 Obsidian 里做三件事：设置 → 核心插件 → 模板，指定 `Templates/`；
设置 → 文件与链接 → 附件默认路径设为 `Assets/`；第三方插件里安装 Dataview。

## 使用方法

### 库体检（动手前先看现状）

```bash
python3 scripts/scan_vault.py /path/to/vault   # 顶层结构、各分区计数、缺 frontmatter / 缺 type / 近空 / Inbox 积压
python3 scripts/scan_vault.py                  # 不传路径 = 当前目录
```

### 交给 agent 的典型请求

```
这几篇笔记该归 P/A/R/A 哪一类？（附标题清单）
把这个项目的 frontmatter 补全，并放进 01-Projects/
我这个库想从零搭 PARA 结构，给我目录 + 模板 + MOC
周日复盘：清空 Inbox，过一遍 Projects 的状态
把做完的项目按 5 步归档
体检报告出来了，给我整理建议
```

### 工作模式索引（`SKILL.md` §4）

| 模式 | 任务 |
|---|---|
| A | 从零搭建 / 迁移库（建空壳 → 复制模板与 MOC → 旧笔记先进 Inbox → 批量归类） |
| B | 笔记归类与 frontmatter（单篇给结论 + 完整 frontmatter；批量只出 `笔记 / 类别 / 路径 / 备注` 表格） |
| C | 生成模板 / MOC（从 `assets/` 复制成品，不手写改写结构） |
| D | 复盘 / 归档（周月清单、项目归档 5 步） |
| E | 库体检（跑 `scan_vault.py` 并给整理建议） |

## 已知事实（避坑清单）

- 图片 / 附件在 Markdown 里用**相对路径**（`../../../Assets/images/...`）；`/Assets/...` 这种根路径 Obsidian 不解析。
- 文件夹是物理位置，MOC 是逻辑地图。想用目录做「分类」时，先用 MOC + 标签 + Dataview，解决不了再建目录。
- 标签只做属性标记（来源 / 状态 / 优先级）；`#工作 #生活` 这类与目录重复的第二套分类体系会让决策成本翻倍。
- 文件夹最多 2 级嵌套，标签最多 2 级。
- 搁置 ≠ 放弃：`on-hold` / `dormant` 只改 `status`，不移动文件；彻底不做才移进 `04-Archives/`。
- frontmatter 必须是标准 YAML（`---` 分隔）；被外部转换器改坏（`---` 变 `***`、`[[` 被转义成 `\[\[`）时要全文修复。

## 参考文档

| 文件 | 内容 |
|---|---|
| `references/directory-structure.md` | 目录结构规范：各 PARA 目录定义与示例、辅助目录、何时建 / 不建文件夹 |
| `references/naming-and-tags.md` | 命名规范、推荐与禁用标签清单、链接 / 标签 / Dataview / frontmatter 的选择 |
| `references/moc-and-dataview.md` | MOC 设计、Dataview 前置准备、10 条通用查询 |
| `references/workflows.md` | 新建笔记判断流程、迁移 5 步、周 / 月复盘清单、归档流程、边界案例、避坑指南 |
| `assets/templates/` | 4 套笔记模板（项目 / 领域 / 资源 / 归档） |
| `assets/moc/` | 4 个成品总览 MOC（Home / Projects / Areas / Resources） |
| `scripts/scan_vault.py` | 库体检脚本 |

## 免责声明

本技能只提供工具与流程，不包含、不内置、不推荐任何内容站点或第三方服务凭据。
技能中的示例路径、主机名、服务名、令牌一律为占位符，不含作者机器的真实信息。

## License

MIT
