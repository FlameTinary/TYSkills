# TYSkills

个人自用 skill 集合。每个 skill 都是一个自包含的 `SKILL.md` 包（附带 `scripts/`、`references/`、`assets/`），
谁支持 `SKILL.md` 这个约定，把技能目录放进它的本地技能目录就能用。

本文件只做**集合级索引**：整体说明、技能列表、目录结构、克隆与安装方式。每个技能的详细说明
（简介、依赖、安装、使用方法、避坑、参考文档）在**该技能目录自己的 `README.md`** 里，点下表「详细说明」列即可。

## 技能列表

| 技能 | 一句话说明 | 适用平台 | 详细说明 |
|---|---|---|---|
| [aria2-rpc](skills/aria2-rpc/) | aria2 下载中枢：`a2` 高级封装 CLI，媒体下载自动分级入库、种子搜索入库、限速/暂停/继续、AList 网盘直链下载、一键部署为守护服务 | macOS / Linux / Windows(WSL、Git Bash) | [README](skills/aria2-rpc/README.md) |
| [obsidian-para](skills/obsidian-para/) | Obsidian 知识库的 PARA（项目/领域/资源/归档）顾问与执行助手：归类决策树、目录结构规范、frontmatter 规范、4 套笔记模板 + 4 个成品 MOC、10 条 Dataview 查询、旧库迁移与复盘归档流程、库体检脚本 | macOS / Linux / Windows | [README](skills/obsidian-para/README.md) |
| [skill-sanitize](skills/skill-sanitize/) | 技能脱敏：审计技能里的本机痕迹（路径/用户名/主机名/密钥/代理/私有域名）、按类处置（删除/参数化/占位/留痕保留）、需要私有化的值改成用户自己的配置文件 | macOS / Linux / Windows | [README](skills/skill-sanitize/README.md) |

## 怎么用

克隆后把 `skills/<技能名>/` 复制（或软链）到你所用 agent 的技能目录即可，例如
`~/.agents/skills/`、`~/.claude/skills/`、`~/.hermes/skills/<类别>/`：

```bash
git clone https://github.com/FlameTinary/TYSkills.git
cp -R TYSkills/skills/<技能名> ~/.agents/skills/     # 用 ln -s 则 git pull 后即最新版
```

Windows 把 `~` 换成 `%USERPROFILE%`。技能就是一个目录 + `SKILL.md`，不依赖安装器或账号。
每个技能自己的 `README.md` 里还有各自的前置依赖与初始化步骤（部署服务、放模板、写配置）。

## 目录结构

```
skills/
├── aria2-rpc/
│   ├── README.md             # 本技能完整说明：简介 / 依赖 / 安装 / 使用方法 / 参考文档
│   ├── SKILL.md              # 技能主文件：决策规则、工作流、踩坑清单（agent 读这个）
│   ├── assets/               # 配置与服务定义模板（占位符由安装脚本替换）
│   ├── references/           # 分主题参考文档（命令详解、搜索源契约、排错、AList API 等）
│   └── scripts/              # 可执行程序：a2、裸 RPC 客户端、完成钩子、安装/启动脚本
├── obsidian-para/
│   ├── README.md             # 本技能完整说明：简介 / 依赖 / 安装 / 使用方法 / 参考文档
│   ├── SKILL.md              # PARA 判断决策树、五种工作模式、frontmatter 规范、交付前验证
│   ├── assets/               # 4 套笔记模板（项目/领域/资源/归档）+ 4 个成品总览 MOC，复制入库即用
│   ├── references/           # 目录结构、命名与标签、MOC 与 Dataview、工作流与边界案例
│   └── scripts/scan_vault.py # 库体检：缺 frontmatter / 缺 type / 近空笔记 / Inbox 积压
└── skill-sanitize/
    ├── README.md             # 本技能完整说明：简介 / 依赖 / 使用方法 / 参考文档
    ├── SKILL.md              # 脱敏流程、红线、分类处置表、验收清单
    ├── assets/               # 私有配置模板 + 配置加载器
    ├── references/           # 泄漏分类库、脱敏报告模板
    └── scripts/audit_skill.py# 审计器：本机痕迹 + 文件完整性，退出码可用作门禁
```

每个技能目录里两个文件的分工：

- `SKILL.md` —— 给 agent 读：触发条件、判断规则、工作流、踩坑清单，决定技能被正确调用。
- `README.md` —— 给人读：这个技能解决什么问题、要装什么、怎么用、什么场景不适用。

## 免责声明

本仓库内容为工具链的自动化封装、运维便利与技能脱敏/发布流程，**不包含、不内置、不推荐任何内容站点**。
`aria2-rpc` 的搜索源由使用者自行配置，请遵守你所在地区的法律法规与版权规定，仅用于你有权下载的内容。
技能中的示例路径、主机名、服务名、令牌一律为占位符，不含作者机器的真实信息。

## License

MIT
