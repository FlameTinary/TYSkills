---
name: skill-sanitize-and-publish
description: "Use when sharing a skill: sanitize and make it portable."
version: 1.0.0
author: Shawn (FlameTinary), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [skills, sanitization, privacy, portability, publishing]
    category: software-development
    related_skills: [hermes-agent-skill-authoring, github]
---

# 技能脱敏与发布

把一个「只能在本机跑」的技能，变成「任何人 clone 下来就能用」的技能包：审计本机痕迹 →
按类处置（删除 / 参数化 / 占位）→ 私有值落用户配置文件 → 三平台可移植 → 写 README 与安装说明 →
发布到公开仓库。产物是 Hermes、Claude Code、Codex、OpenCode、OpenClaw 都能用的 SKILL.md 包 ——
安装方式就是把技能目录放进各 agent 的本地技能目录，不走任何官方商店或安装器。

本技能不含任何站点、私有服务或机器信息；审计词表由使用者维护（见「私有配置」）。

## When to Use

- 用户要把一个技能公开 / 分享 / 推到 GitHub / 发给别人
- 用户说「脱敏」「去掉本机信息」「去掉我机器上的东西」「让任何人都能用」
- 审查一个已经公开的技能里是否残留了本机内容
- 把一个只在 macOS 上验证过的技能改成 macOS/Linux/Windows 通用

Don't use for: 只在本机自用的技能（没有别人，就不用付出脱敏成本）；从零写新技能（用
`hermes-agent-skill-authoring`）；只是想 publish 一个已经干净的仓库（直接用 `github` 技能）。

## 红线（不可协商）

1. **不做「看起来脱敏」**：凡是能唯一指认你这个人或你所用机器的字符串，一律处置——包括
   用户名、主机名、家目录、外接盘卷标、局域网 IP、私有域名、个人服务名、邮箱、机器状态叙述。
2. **秘密是删除 + 轮换，不是脱敏**：凭据一旦进过公开仓库就视为已泄漏；改文件不算修复，
   必须去源头轮换（token 吊销、密码改掉、密钥重签）。
3. **要私有化的走配置文件**，不写死、不猜默认：没有配置时给出可读报错或安全降级，
   绝不静默用某个「作者机器上成立」的值。
4. **三平台是默认要求**，除非用户明确只要一个平台：脚本不用单边选项、不用 POSIX 专有 API、
   不硬编码临时目录（细节见 `references/cross-platform.md`）。
5. **审计脚本要跑，不靠眼睛**：`scripts/audit_skill.py` 退出码非零就是还没脱敏完。

## 分类处置表

| 类别 | 典型内容 | 处置 |
|---|---|---|
| 秘密 | token、password、私钥、refresh_token、Cookie、Authorization 值、含密码的 URL | 删；改环境变量或配置文件；提醒轮换 |
| 身份 | 家目录路径、用户名、主机名、卷标（/Volumes/X）、邮箱、局域网 IP | 改 `~` / `expanduser` / `%USERPROFILE%` / 占位符 |
| 私有设施 | 私有域名、个人服务名、本机代理端口、NAS/设备品牌、私有站点名 | 改通用占位；需要保留则做成配置项 |
| 通用但被写死 | 端口号、盘符、包管理器命令、平台服务命令 | 保留（属公共知识），但确认是软件默认值而不是你改过的 |
| 个人叙述 | 「本机实测（含个人环境描述）」「我的盘」「我司」 | 改中性表述；经验值可以留，去掉指认性 |

判断口径：**这条信息在别人的机器上是否同样成立？** 成立 → 通用知识，留；不成立 → 本机内容，处置。

## 私有配置模式

要私有化的东西（路径、端口、密钥、站点命令、盘位）一律进配置文件，不留在代码里。

- 位置：`~/.<skill名>/<skill名>.conf`（Windows 为 `%USERPROFILE%\.<skill名>\<skill名>.conf`），
  只提交 `assets/<skill名>.conf.template`，真实 conf 写进 `.gitignore`。
- 优先级：**命令行参数 > 环境变量 > 配置文件 > 内置默认**。
- 读取：用 `assets/conf_loader.py`（仅标准库、三平台通用，`${VAR:-default}` 展开、`~` 展开）。
- 生成：安装脚本首次运行时从模板生成，并随机化 secret；POSIX 下 `chmod 600`。
- 报错：缺配置时报「缺什么、去哪配、模板在哪」，**不回显密钥**。

模板见 `assets/private.conf.template`，模板里的键名就是给用户填的契约。

## 流程

1. **冻结现状**。确认技能目录可写、改动可追溯（是 git 仓库就先提交，或先 `cp -R` 一份）。
   完成判据：`git status --short` 为空（或只有你有意保留的改动）。
2. **跑审计**。`terminal(command="python3 <技能目录>/scripts/audit_skill.py <技能目录> --report 报告.md")`。
   完成判据：拿到分级清单 + 报告文件；`high` 全在明处。
   把自己机器的专属词补进去：`--terms ~/.config/skill-sanitize/local-terms.txt`，一行一词
   （用户名、主机名、域名、站点名、盘标、设备名）——通用规则抓不到的用词表兜底。
3. **分类处置**。逐条 high/medium 决定：删除 / 参数化 / 占位 / 保留并写理由。同一根因只处理一次，
   但要替换**所有**出现处（用 `--json` 聚合，别按输出前几条手改）。
   完成判据：报告里每条都有处置结论。
4. **落地配置**。凡是「作者机器上的值」都迁到 conf 模板 + loader，脚本改成读配置。
   完成判据：没有配置文件时脚本给出可读报错且不崩；复制模板即可跑通。
5. **可移植性收口**。按 `references/cross-platform.md` 过一遍脚本，重跑审计。
   完成判据：`high` = 0；`medium` 每条都有理由；`--fail-level high` 退出码 0。
6. **写 README 与安装说明**。简介（做什么/不做什么/依赖）、安装、用法、排错、免责声明，
   以及五大 agent 的**本地技能目录**（照抄 `references/agent-install.md`，别现编路径）。
   完成判据：README 里有「把目录放到哪里 + 第一分钟怎么跑通」的完整路径；
   写法是「复制/软链到目录」，不是「去某商店安装」。
7. **发布并从远端核实**。`gh repo create <名字> --public --source . --remote origin` → `git push`。
   完成判据（必须回读远端，不是本地自述）：`gh repo view <owner>/<repo> --json visibility,defaultBranchRef`
   与 `gh api repos/<owner>/<repo>/git/trees/<branch>?recursive=1` 的文件数与本地一致、
   README blob 大小与本地文件一致。

## 「保留」要留痕：audit-skip 豁免

审计器会命中文档里的**反面示例**和规则定义本身（示例磁力、`example` 占位、正则字面量）。
这类内容不要为了通过审计而删改，而是就地记账：

```markdown
<!-- audit-skip-file: 本文档是反面示例库，表内字面量是教学用的错误写法 -->   # 文件级（前 8 行内）
… `rpc-secret=abcd1234` …            <!-- audit-skip: 报告模板里的虚构示例值 -->   # 行级
```

- 两种标记都必须写理由；理由会出现在文本输出、`--json` 的 `exemptions` 和报告里，可追溯、可复核。
- 豁免**不等于静默跳过**：它只是把「保留」这个决定显式化。真实值仍然要处置。
- 报告文件本身含命中原文 → 只留在本地或私有仓库，不要提交到公开仓库（工具会再提醒一次）。

## Quick Reference

```bash
# 审计（退出码 0 = 达到 --fail-level 的问题数为 0）
python3 scripts/audit_skill.py <技能目录> [<技能目录2> ...] \
        [--json] [--terms 词表文件] [--report 报告.md] [--fail-level high] [-q]

# 技能包必须满足的共同格式（五 agent 通用）
#   目录名 == frontmatter name，^[a-z0-9]+(-[a-z0-9]+)*$，≤64 字符
#   SKILL.md 全大写、frontmatter 从字节 0 起、description 前 57 字符自带触发
```

## Pitfalls

1. **只改 SKILL.md**。同一个路径值在 `scripts/`、`references/`、`assets/` 里通常还有 4~5 份，
   漏一个等于没做。用 `--json` 按规则聚合后全量替换。
2. **把示例改成另一个本机值**（比原样更糟）。示例一律用 `example.com` / `example.invalid` /
   `<占位>` / `com.example.<服务>`。
3. **过度脱敏**。把软件默认端口（5244、6800）、公知上游 URL、标准路径（`/opt/homebrew`）也删掉 →
   文档失去可操作性。默认值是公共知识，保留并对齐官方文档。
4. **忘了 git 历史**。提交者姓名/邮箱、旧提交里的密钥、`.git/logs` 都是泄漏面。已推送过的秘密
   必须轮换；作者身份按用户意愿换（noreply 邮箱）后再推。
5. **折叠计数**：审计输出对同一规则有折叠上限，看 `--json` 的汇总数字，不要以为前 5 条就是全部。
6. **平台盲区**：在 macOS/Linux 上 import 成功的脚本，到 Windows Python 上会因为 `fcntl`/`pty`
   直接崩。审计会标 `posix-only-api`，要么加平台分支（`msvcrt`/`psutil`），要么在技能里写清只支持 WSL。
7. **编码**：Windows 编辑器保存过会带 BOM/CRLF，frontmatter 的 `---` 就不在字节 0，某些 agent 直接不加载。

## Verification

- [ ] `python3 scripts/audit_skill.py <技能目录>` 退出码 0（`high` 为 0），或每条 high 都有书面理由
- [ ] 全目录搜不到：用户名、主机名、家目录、卷标、私有域名、局域网 IP、令牌/密码/邮箱
- [ ] 五 agent 通用格式：SKILL.md 全大写、`name` == 目录名、name 正则合规、description ≤57 字符内自带触发
- [ ] 无配置文件时脚本给出可读报错；复制 `*.conf.template` 后可跑通
- [ ] README 覆盖简介 / 安装（五 agent 本地目录，复制或软链）/ 用法 / 排错 / 免责
- [ ] 远端核实过：仓库可见性、文件数一致、README 大小一致
- [ ] 脱敏报告留档，可追溯每条处置决定

## 参考

| 文件 | 内容 |
|---|---|
| `references/leak-taxonomy.md` | 泄漏分类库：每类长什么样、怎么改（含 before/after） |
| `references/agent-install.md` | Hermes / Claude Code / Codex / OpenCode / OpenClaw 的安装路径与 frontmatter 差异 |
| `references/cross-platform.md` | 三平台可移植性规则（shell、Python、路径、服务管理、文件锁） |
| `references/report-template.md` | 脱敏报告模板（交付给用户看的处置清单） |
| `assets/private.conf.template` | 私有配置模板（复制到 `~/.<skill>/<skill>.conf`） |
| `assets/conf_loader.py` | 三平台配置加载器（仅标准库），直接抄进被脱敏的技能 |
| `scripts/audit_skill.py` | 审计器：泄漏 + 可移植性 + frontmatter 格式，退出码可用作 CI 门禁 |
