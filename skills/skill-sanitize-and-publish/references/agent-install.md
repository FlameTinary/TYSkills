# 五大 agent 的安装路径与格式差异

**安装方式只有一种：把技能目录复制（或软链）到 agent 的本地技能目录即可，不需要发布到任何商店、
不需要安装器、不需要联网注册。** 各家都只是「按目录扫描 SKILL.md」，放进去即被发现。
本文只回答「放哪个目录」和「frontmatter 要满足什么」，不涉及任何官方技能市场/仓库。

以下路径来自各家官方文档（校对时间见文末），只列**用户级**位置；项目级位置一并给出。
一份合格的技能包应当同时满足这五家的共同要求，差异部分靠「加法」而非「替换」处理。

## 一句话结论

| agent | 用户级安装位置 | 备注 |
|---|---|---|
| Hermes Agent | `~/.hermes/skills/<类别>/<名字>/SKILL.md` | 也支持 `~/.hermes/profiles/<profile>/skills/`；用 `skill_manage` 创建 |
| Claude Code | `~/.claude/skills/<名字>/SKILL.md` | 项目级 `.claude/skills/`；支持 `/技能名` 直接调用 |
| Codex CLI | `~/.agents/skills/<名字>/SKILL.md` | 另读 `$CWD/.agents/skills`、`$REPO_ROOT/.agents/skills`、`/etc/codex/skills`；跟随符号链接 |
| OpenCode | `~/.config/opencode/skills/<名字>/SKILL.md` | 同时读 `~/.claude/skills/` 与 `~/.agents/skills/` |
| OpenClaw | `~/.openclaw/skills/<名字>/SKILL.md`（共享位置）或 `<workspace>/skills/<名字>/` | 也读 `~/.agents/skills/`、`<workspace>/.agents/skills/`；分组布局下 SKILL.md 出现在任意层都认 |

**通用搬运位置**：`~/.agents/skills/<名字>/` 同时被 Codex、OpenCode、OpenClaw 读取；
`~/.claude/skills/<名字>/` 同时被 Claude Code、OpenCode 读取。
所以最省事的安装指引是：

```bash
git clone <仓库>
# 三合一（Codex / OpenCode / OpenClaw）
mkdir -p ~/.agents/skills && cp -R <仓库>/skills/<名字> ~/.agents/skills/
# Claude Code / OpenCode
mkdir -p ~/.claude/skills && cp -R <仓库>/skills/<名字> ~/.claude/skills/
# Hermes
mkdir -p ~/.hermes/skills/<类别> && cp -R <仓库>/skills/<名字> ~/.hermes/skills/<类别>/
# 或者全部用符号链接，git pull 即更新：
#   ln -s "$PWD/<仓库>/skills/<名字>" ~/.agents/skills/<名字>
```

Windows 上把 `~` 换成 `%USERPROFILE%`（PowerShell：`$env:USERPROFILE`），用 `Copy-Item -Recurse`
或 `New-Item -ItemType SymbolicLink`（符号链接需要开发者模式或管理员权限；不满足就用复制）。

## frontmatter：取五家交集，差异用加法

共同必需（少一个就有 agent 不加载）：

```yaml
---
name: my-skill            # ^[a-z0-9]+(-[a-z0-9]+)*$，≤64 字符，且必须等于所在目录名
description: "一句话，说明能力与触发场景。"
---
```

各家可选项（**可以都写上**，互不冲突）：

| 字段 | 谁在用 | 说明 |
|---|---|---|
| `license` | OpenCode 识别；其余忽略 | `MIT` 之类 |
| `compatibility` | OpenCode 识别 | 兼容性说明字符串 |
| `version` / `author` / `platforms` | Hermes 生态惯例 | 语义化版本、作者、适用平台 |
| `allowed-tools` | Claude Code | 如 `Bash(${CLAUDE_SKILL_DIR}/scripts/run.sh *)`、`Read Grep` |
| `disable-model-invocation` | Claude Code / OpenClaw | `true` 时不自动进上下文，只作 `/命令` |
| `user-invocable` | OpenClaw | 默认 `true`，是否暴露为斜杠命令 |
| `homepage` | OpenClaw（macOS UI 显示） | 项目主页 URL |
| `metadata.hermes.{tags,related_skills,category}` | Hermes Agent | 分类与技能索引 |
| `metadata.openclaw.{os,requires,always,emoji,primaryEnv}` | OpenClaw | gating：`requires.bins/env/config` 不满足则不加载 |

注意事项：

- **OpenCode 只认** `name` / `description` / `license` / `compatibility` / `metadata`，其余忽略；
  它要求 `metadata` 是「字符串→字符串」的表，所以想同时喂 Hermes 的嵌套 `metadata.hermes` 时，
  要么接受 OpenCode 忽略它，要么把 Hermes 需要的元信息压成扁平键。
- **OpenClaw 跟随 AgentSkills 规范**：frontmatter 先按 YAML 解析，失败再退回单行解析器；
  嵌套 `metadata` 会被扁平化成 JSON 字符串再按 JSON5 解析，所以 `metadata.openclaw` 的块状写法它是认的。
- **`name` 必须等于目录名**（OpenCode 硬要求，其他家跟随），否则改名而不是改文档。
- **`description` 前 57 字符必须自带触发信息**：Hermes 的技能索引在这个窗口截断，
  Claude Code 也主要靠它决定是否加载（把「做什么 + 何时用」放前面，别把技能名重复一遍）。
- **正文里引用技能自己的文件**：Claude Code 用 `${CLAUDE_SKILL_DIR}/scripts/...`，
  OpenClaw 用 `{baseDir}/...`；要跨家通用就写相对路径（`scripts/foo.sh`）并在正文说明
  「相对技能目录解析」。

## 各家的额外机制（打包时按需写进 README）

- **Hermes Agent**：技能可带 `references/`、`scripts/`、`templates/`；插件机制支持注册工具/斜杠命令（见 `hermes-plugin-authoring`）。用户级技能用 `skill_manage(action='create')` 落盘。
- **Claude Code**：项目技能放 `.claude/skills/`；`/技能名` 直接调用；技能变更后需新会话生效。
- **Codex CLI**：从 `$CWD` 向上扫到仓库根，逐级收集 `.agents/skills`；同名的两份技能都会出现在选择器里（不合并）；把技能目录放进 `~/.agents/skills/`（或项目的 `.agents/skills/`）即可，无需打包。另有 `$CODEX_HOME/skills`（默认 `~/.codex/skills`）被 OpenClaw 文档提到是 Codex 的原生目录。
- **Windows 上的三平台注意点**：目录名不要用空格/中文以外的怪字符；软链需要开发者模式，不满足就直接复制。
- **OpenCode**：项目级从 `$CWD` 向上走到 git worktree 根，沿途收集 `.opencode/skills`、`.claude/skills`、`.agents/skills`；未知 frontmatter 字段忽略。
- **OpenClaw**：技能根按优先级：个人库 → `<workspace>/skills` → `<workspace>/.agents/skills` → `~/.agents/skills` → `<state-dir>/skills`（默认 `~/.openclaw/skills`）→ workshop 技能 → 内置 → `skills.load.extraDirs`。**分组布局下 `SKILL.md` 出现在任意层（最多 6 层）都会被认成同名技能**，所以 `~/.openclaw/skills/<你的分组>/<技能名>/SKILL.md` 一样能用。技能没被加载时用 `openclaw skills check` 排查（只读诊断，不是安装命令）。

## 文档出处（校对用）

- Hermes Agent 技能与插件：https://hermes-agent.nousresearch.com/docs
- Claude Code 技能：https://code.claude.com/docs/en/skills
- Codex 技能：https://developers.openai.com/codex/skills （仓库内 `openai/codex:docs/skills.md` 是跳转指针）
- OpenCode 技能：https://opencode.ai/docs/skills/
- OpenClaw 技能：https://docs.openclaw.ai/tools/skills
- AgentSkills 规范：https://agentskills.io/specification

> 路径与字段会随版本变。写进 README 前重跑一次 `web_search` / `web_extract` 核对；
> 拿不准就按「五家交集 + 通用目录 `~/.agents/skills`」写，别现编路径。
> 只需要「放进去能用」，不需要任何账号、注册、安装器或官方商店流程。
