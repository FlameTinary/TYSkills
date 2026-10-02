# TYSkills

个人自用 skill 集合。每个 skill 都是一个自包含的 `SKILL.md` 包（附带 `scripts/`、`references/`、`assets/`），
谁支持 `SKILL.md` 这个约定，把技能目录放进它的本地技能目录就能用。

## 技能列表

| 技能 | 一句话说明 | 适用平台 |
|---|---|---|
| [aria2-rpc](skills/aria2-rpc/) | aria2 下载中枢：`a2` 高级封装 CLI，媒体下载自动分级入库、种子搜索入库、限速/暂停/继续、AList 网盘直链下载、一键部署为守护服务 | macOS / Linux / Windows(WSL、Git Bash) |
| [obsidian-para](skills/obsidian-para/) | Obsidian 知识库的 PARA（项目/领域/资源/归档）顾问与执行助手：归类决策树、目录结构规范、frontmatter 规范、4 套笔记模板 + 4 个成品 MOC、10 条 Dataview 查询、旧库迁移与复盘归档流程、库体检脚本 | macOS / Linux / Windows |
| [skill-sanitize](skills/skill-sanitize/) | 技能脱敏：审计技能里的本机痕迹（路径/用户名/主机名/密钥/代理/私有域名）、按类处置（删除/参数化/占位/留痕保留）、需要私有化的值改成用户自己的配置文件 | macOS / Linux / Windows |

## 怎么用

克隆后把 `skills/<技能名>/` 复制（或软链）到你所用 agent 的技能目录即可，例如
`~/.agents/skills/`、`~/.claude/skills/`、`~/.hermes/skills/<类别>/`：

```bash
git clone https://github.com/FlameTinary/TYSkills.git
cp -R TYSkills/skills/<技能名> ~/.agents/skills/     # 用 ln -s 则 git pull 后即最新版
```

Windows 把 `~` 换成 `%USERPROFILE%`。技能就是一个目录 + `SKILL.md`，不依赖安装器或账号。

## 目录结构

```
skills/
├── aria2-rpc/
│   ├── SKILL.md              # 技能主文件：决策规则、工作流、踩坑清单
│   ├── assets/               # 配置与服务定义模板（占位符由安装脚本替换）
│   ├── references/           # 分主题参考文档（命令详解、搜索源契约、排错、AList API 等）
│   └── scripts/              # 可执行程序：a2、裸 RPC 客户端、完成钩子、安装/启动脚本
├── obsidian-para/
│   ├── SKILL.md              # PARA 判断决策树、五种工作模式、frontmatter 规范、交付前验证
│   ├── assets/               # 4 套笔记模板（项目/领域/资源/归档）+ 4 个成品总览 MOC，复制入库即用
│   ├── references/           # 目录结构、命名与标签、MOC 与 Dataview、工作流与边界案例
│   └── scripts/scan_vault.py # 库体检：缺 frontmatter / 缺 type / 近空笔记 / Inbox 积压
└── skill-sanitize/
    ├── SKILL.md              # 脱敏流程、红线、分类处置表、验收清单
    ├── assets/               # 私有配置模板 + 配置加载器
    ├── references/           # 泄漏分类库、脱敏报告模板
    └── scripts/audit_skill.py# 审计器：本机痕迹 + 文件完整性，退出码可用作门禁
```

---

# aria2-rpc

## 简介

把 aria2 变成一个**开箱可用的下载中枢**。核心是一个 `a2` 命令行封装：aria2 本身只认 JSON-RPC，
`a2` 把它包装成分级入库的日常命令，并用完成钩子把下载好的媒体自动搬进媒体库。
a2 没覆盖的能力（`select-file` 按索引只下整季包里的部分集、`bt-metadata-only` 定制校验、
addTorrent 自定义选项）再回落到裸 aria2 JSON-RPC。

解决的具体问题：

- **自动分级入库**：按标题判断电影/剧集，下载落 `.incoming` 暂存区，完成后经 `ffprobe` 校验再搬进 `${A2_MEDIA_ROOT}/{Movies,TV}`，并清洗文件名（去站点广告，不动 `SxxExx`/年份/分辨率）。
- **搜索 → 校验 → 入库**：`a2 find` 调你自配的搜索源，`a2 grab` 先做真做种校验（源标的做种数会撒谎）再下载，按那一行的分类落库。
- **整季包只下缺的集**：已有 E01/E03/E06，只补 E02/E04/E05，不重复下 12GB（裸 RPC `select-file`）。
- **网盘直链下载**：AList 接入阿里云盘等，`a2-alist` / `a2-alist-dir` 拉直链交给 aria2。
- **一键部署为守护进程**：macOS launchd / Linux systemd --user / Windows 计划任务，崩溃自动拉起，配置模板由脚本按平台与 `$HOME` 渲染。
- **本技能不含任何站点**：搜索源由使用者在 `~/.aria2/a2.conf` 里配置一条命令（`tor-source-cmd=`），脚本不内置、不硬编码任何站点。

不适用：非 aria2 的下载方式（yt-dlp、浏览器下载、纯 HTTP 脚本）、qBittorrent/Transmission 生态、需要图形界面的场景。

## 依赖

- 必需：`aria2c`（aria2 1.36+）、`python3`（3.8+）、`curl`
- 强烈建议：`ffprobe`（ffmpeg 自带）—— 入库前的媒体完整性校验，缺了会静默关掉整套校验
- 可选：`alist` 二进制（仅网盘下载需要，`scripts/install-alist.sh` 可自动装）

## 安装

### 1. 把技能放进 agent 的本地技能目录

安装方式见文首「安装到各个 agent」——把 `skills/aria2-rpc/` 复制或软链到
`~/.agents/skills/`、`~/.claude/skills/`、`~/.hermes/skills/<类别>/` 任一处即可，
不需要安装器或账号。

### 2. 一键部署 aria2 + a2

```bash
cd TYSkills/skills/aria2-rpc
bash scripts/install-a2.sh
```

脚本是幂等的（重复运行安全，已有配置一律不覆盖），它会：

1. 检查 `aria2c` / `python3` / `curl`，缺失时按平台打印安装命令；
2. 建 `~/.aria2/`，并 `touch` 空 `aria2.session` / `aria2.log`（aria2 对不存在的路径会直接 exit 1）；
3. 按平台渲染配置与服务定义模板（`__HOME__` / `__RPC_SECRET__` / `__LABEL__` 占位符替换）：
   macOS → `~/Library/LaunchAgents/com.example.aria2.plist`（launchd，KeepAlive）
   Linux → `~/.config/systemd/user/com.example.aria2.service`（systemd --user，Restart=always）
   Windows → 打印计划任务 / nssm 的等价命令；
4. 装 `a2` 等命令到 `~/.local/bin`，媒体库 `~/media/{Movies,TV,Private}` 与暂存区 `~/media/.incoming/*`。

**换机器必改的常量**（环境变量覆盖，或改 `install-a2.sh` 顶部）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `A2_MEDIA_ROOT` | `~/media` | 媒体库根目录，可放任意盘（外接盘、`/mnt/...`、`D:\...`） |
| `A2_DOWNLOAD_DIR` | `~/Downloads` | 普通文件的下载目录 |
| `A2_MIN_FREE_GB` | `20` | 目标盘最小剩余空间，不足则拒绝任务（可临时 `A2_MIN_FREE_GB=5 a2 add ...`） |
| `A2_SERVICE` | `com.example.aria2` | 服务名（launchd 标签 / systemd unit / 计划任务名） |

媒体库可以放在**任何**盘上。启动器与 `a2 add` 用同一条跨平台判据检查目标目录：
在家目录内、或落在别的盘上 → 放行；只有「既不在家目录内、又会落到系统盘上」才拒绝
（这正是外接盘/网络盘没挂载的样子）。确认就要那个位置：先 `mkdir -p` 或用 `A2_ALLOW_CREATE=1`。

### 3. 健康检查（动手前 3 秒）

```bash
a2 st                                              # 全局速率/任务数；RPC 不通会给平台对应的服务检查命令
launchctl list | grep aria2                        # macOS 守护是否在跑
systemctl --user status com.example.aria2          # Linux
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5244   # AList（网盘下载才需要）应返回 200
```

## 使用方法

### 下载媒体（自动分级入库）

```bash
a2 add "magnet:?xt=urn:btih:..."           # 名字像剧集 → TV；像电影(年份+1080p) → Movies；完成后钩子搬进媒体库
a2 add "https://example.com/x.mkv" -t      # 强制当剧集
a2 add "https://example.com/x.zip"         # 普通文件 → ${A2_DOWNLOAD_DIR:-~/Downloads}
a2 add -d /path/to/raw "magnet:..."    # -d 直达指定目录：不经暂存区、钩子不碰、不改名
a2 ls                                      # 任务列表；a2 st 看速率；a2 info <gid> / a2 files <gid> 看详情
```

### 配好搜索源 → 搜索 → 入库

搜索源要自己配一条命令（本技能不内置站点）：

```bash
# ~/.aria2/a2.conf
#   tor-source-cmd=<你的搜索源命令>     # 命令里可用 {query}/{page} 占位符，或读 A2_QUERY/A2_PAGE/A2_PAGES
# 想先离线跑通流程（不联网）：
#   tor-source-cmd=python3 ~/.aria2/tor-source-demo.py

a2 find "关键词 压制组" --res 1080p        # 关键词语言跟着你的源站点走
a2 find 关键词 --json                      # 调源时先看这条：字段到底有没有被认出来
a2 find 关键词 --all                       # 搜单集（默认只留整季/全集，排除单集 SxxExx）
a2 grab 1,3,5                              # 按显示的序号入库（可多个/区间 2-4），默认先做真做种校验
```

搜索源命令的 JSON 字段契约、写自己的源、排查：见 `references/tor-source.md`。

### 任务管理 / 限速 / 收尾

```bash
a2 pause [force] <gid|all>   a2 resume <gid|all>   a2 rm <gid|all>   a2 purge
a2 up 1M      # 上行限速（本次运行有效）
a2 down 0     # 下行不限速；持久化要改 conf 后重启服务
a2 sweep      # 暂存区里已完成但钩子没搬的条目 → 经 ffprobe 校验后入库
```

### AList 网盘下载

```bash
bash scripts/install-alist.sh        # 装到 ~/.local/bin/alist，管理员密码存 ~/.alist/admin_password.txt
~/.alist/start-alist.sh              # 启动，验证 curl http://localhost:5244 返回 200
bash scripts/setup-aliyun.sh "<refresh_token>"   # 接入阿里云盘（token 获取见 references/aliyun-driver.md）

a2-ls /aliyun                                    # 列目录，能列出即就绪
a2-alist "/aliyun/某电影/xx.mp4"                 # 单文件下载
a2-alist-dir "/aliyun/剧集" ~/media/TV "*.mkv"   # 目录批量下载
```

直链约 15 分钟有效期，取到后尽快交给 `a2`（连接建立后过期不影响）。

### 整季包只下缺的集（裸 RPC）

`select-file` 是 1-based 索引，配合 `bt-metadata-only` 先拉元数据列出文件索引再选择性下载，
完整可粘贴脚本见 `SKILL.md` §5.3。

### 故障排查

```bash
a2 find 报「没有配置搜索源」        → 在 ~/.aria2/a2.conf 填 tor-source-cmd
a2 find 报源失败/超时/非 JSON       → 源的问题：单独跑那条命令；A2_TOR_DEBUG=1 看完整命令与 stderr
a2 报 RPC 不可用                    → 确认守护在跑（launchctl / systemctl / schtasks），重启后 a2 st 复验
任务 0 速度 / 卡在元数据            → 公共 BT 冷门资源正常；查 ~/.aria2/aria2.log
磁盘没满但 RPC 假死、服务反复重启   → 进程卡在 fsync 且占着端口；腾空间 → : > ~/.aria2/aria2.session → 重启服务
```

其余分类见 `SKILL.md` §7 与 `references/troubleshooting.md`。

## 已知事实（血泪清单，节选）

- aria2 不展开 `~`：conf 里 `dir=~/Downloads` 会创建字面量 `~/` 目录，必须写绝对路径。
- 服务管理器下不能开 `--daemon=true`（fork 后父进程退出 → KeepAlive/Restart 反复拉起）。
- 完成判据只能是 RPC（`completedLength == totalLength > 0`），不能看 `.aria2` 控制文件是否存在。
- 完成的任务要 `removeDownloadResult` + `saveSession`，否则重启会把已入库的大种子再下一遍。
- 不支持稀疏文件的外接盘（如 HFS+）必须 `file-allocation=none`，否则 `falloc` 真会写满零、盘写满后进程卡在内核 fsync 上杀不掉。
- `log-level=info` 会按 peer×piece 写日志吃光磁盘且 aria2 不自带轮转，保持 `warn`。
- aria2 用 HTTP 400 + JSON 体表达 RPC 错误，要读 `HTTPError.read()` 里的 `error.message`。

完整 15 条见 `SKILL.md` §6，逐条附带复现背景的版本在 `references/troubleshooting.md`。

## 参考文档

| 文件 | 内容 |
|---|---|
| `references/a2-commands.md` | a2 全部子命令逐一详解（参数/示例/坑） |
| `references/tor-source.md` | 搜索源契约：配置、JSON 字段表与别名、写自己的源、排查 |
| `references/troubleshooting.md` | 排错分类表与「用血换来的事实」 |
| `references/setup.md` | 搭建部署（macOS/Linux/Windows）、服务管理、媒体落点、维护 |
| `references/install-guide.md` | AList 手动安装指南 |
| `references/aliyun-driver.md` | 阿里云盘 AliyundriveOpen 驱动配置 |
| `references/alist-api.md` | AList API 参考（登录 / fs 列表与直链 / 存储管理 / 状态码） |
| `references/api_reference.md` | aria2 JSON-RPC 完整方法参考 |

---

# obsidian-para

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

把 `skills/obsidian-para/` 复制或软链到 agent 的技能目录即可（见文首「怎么用」）。
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

---

# skill-sanitize

## 简介

把一个技能里**属于某台机器、属于作者本人**的内容清干净，让它「换一台机器、换一个人，照样能用」。
四件事：

1. **审计**：`scripts/audit_skill.py` 扫全目录，按 high/medium/low 分级报出本机痕迹 ——
   家目录路径、用户名、主机名、外接盘卷标、局域网 IP、私有域名、个人服务名、真实邮箱，
   以及令牌/密码/私钥/refresh_token/Cookie/含密码的 URL、写死的代理端口，
   并顺带检查脱敏改写有没有把文件改坏（frontmatter 起止、BOM/CRLF）。
   默认还会拿**本机**的用户名与主机名当判据。
2. **按类处置**：每条命中给出四种处置之一 —— 删除（秘密）、参数化（本机特有的值）、占位（示例值）、
   保留并写理由（公共知识，如 AList 默认端口 5244）。处置记录留在报告里。
3. **私有值落配置文件**：要私有化的东西（路径、端口、密钥、站点命令、代理）迁到
   `~/.<技能名>/<技能名>.conf`，只提交 `*.conf.template`；配 `assets/conf_loader.py` 读取，
   优先级 命令行参数 > 环境变量 > 配置文件 > 内置默认；没有配置文件时给出「缺什么、去哪配」的报错。
4. **留痕**：文档里必须保留的反面示例用 `audit-skip: 理由` 就地记账；报告归档在本地。

技能边界：**只做脱敏**。跨平台适配、给其他 agent 打包安装、发布到仓库都不归它管。

## 依赖

- `python3`（3.8+，仅标准库），也可以脱离 agent 单独当命令行工具用

## 使用方法

```bash
# 审计一个技能目录（退出码 0 = 没有达到 --fail-level 的问题）
python3 scripts/audit_skill.py /path/to/skill

# 更严 + 输出 JSON 便于聚合 + 顺手写一份处置报告
python3 scripts/audit_skill.py /path/to/skill --fail-level medium --json --report 脱敏报告.md

# 补上只有你知道的专属词（用户名、主机名、域名、站点名、盘标），一行一词
python3 scripts/audit_skill.py /path/to/skill --terms ~/.config/skill-sanitize/local-terms.txt
```

- 报告内含命中原文，**只留本地或私有仓库**。
- `assets/private.conf.template` 是给被脱敏技能用的配置模板；
  `assets/conf_loader.py` 是可直接抄走的配置加载器。

## 参考文档

| 文件 | 内容 |
|---|---|
| `references/leak-taxonomy.md` | 泄漏分类库：每类长什么样、为什么算泄漏、怎么改（含 before/after） |
| `references/report-template.md` | 脱敏报告模板（交付给用户看的处置清单） |

## 免责声明

本仓库内容为工具链的自动化封装、运维便利与技能脱敏/发布流程，**不包含、不内置、不推荐任何内容站点**。
`aria2-rpc` 的搜索源由使用者自行配置，请遵守你所在地区的法律法规与版权规定，仅用于你有权下载的内容。
技能中的示例路径、主机名、服务名、令牌一律为占位符，不含作者机器的真实信息。

## License

MIT
