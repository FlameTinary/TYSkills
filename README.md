# TYSkills

个人自用 skill 集合。每个 skill 都是一个自包含的 `SKILL.md` 包（附带 `scripts/`、`references/`、`assets/`），
**安装方式就是把技能目录复制（或软链）到 agent 的本地技能目录**，不需要发布到任何商店、不需要安装器：
Hermes Agent、Claude Code、Codex、OpenCode、OpenClaw 都按同一个约定扫描本地目录里的 `SKILL.md`。

## 技能列表

| 技能 | 一句话说明 | 适用平台 |
|---|---|---|
| [aria2-rpc](skills/aria2-rpc/) | aria2 下载中枢：`a2` 高级封装 CLI，媒体下载自动分级入库、种子搜索入库、限速/暂停/继续、AList 网盘直链下载、一键部署为守护服务 | macOS / Linux / Windows(WSL、Git Bash) |
| [skill-sanitize-and-publish](skills/skill-sanitize-and-publish/) | 技能脱敏与发布：审计本机痕迹（路径/用户名/密钥/代理/私有域名）、按类处置、私有值落用户配置文件、三平台可移植、写 README 与五 agent 安装说明 | macOS / Linux / Windows |

## 安装到各个 agent（本地目录，复制或软链）

```bash
git clone https://github.com/FlameTinary/TYSkills.git
SKILL=aria2-rpc        # 换成要装的那个技能名（另一项：skill-sanitize-and-publish）

# 通用目录：Codex / OpenCode / OpenClaw 都会读它
mkdir -p ~/.agents/skills
cp -R "TYSkills/skills/$SKILL" ~/.agents/skills/

# Claude Code / OpenCode
mkdir -p ~/.claude/skills
ln -s "$PWD/TYSkills/skills/$SKILL" ~/.claude/skills/"$SKILL"

# Hermes Agent（类别目录按需换：software-development / media / …）
mkdir -p ~/.hermes/skills/software-development
ln -s "$PWD/TYSkills/skills/$SKILL" ~/.hermes/skills/software-development/"$SKILL"

# OpenClaw / OpenCode 的全局目录（可选；~/.agents/skills 已覆盖，放这里也行）
mkdir -p ~/.config/opencode/skills ~/.openclaw/skills
```

也可以每个目录都用符号链接，`git pull` 之后即是最新版。
Windows 把 `~` 换成 `%USERPROFILE%`（PowerShell：`$env:USERPROFILE`），
软链需要开发者模式，不满足就用 `Copy-Item -Recurse` 复制。
各家读取的完整目录清单见 [skills/skill-sanitize-and-publish/references/agent-install.md](skills/skill-sanitize-and-publish/references/agent-install.md)。

## 目录结构

```
skills/
├── aria2-rpc/
│   ├── SKILL.md              # 技能主文件：决策规则、工作流、踩坑清单
│   ├── assets/               # 配置与服务定义模板（占位符由安装脚本替换）
│   ├── references/           # 分主题参考文档（命令详解、搜索源契约、排错、AList API 等）
│   └── scripts/              # 可执行程序：a2、裸 RPC 客户端、完成钩子、安装/启动脚本
└── skill-sanitize-and-publish/
    ├── SKILL.md              # 脱敏与发布流程、红线、验收清单
    ├── assets/               # 私有配置模板 + 三平台配置加载器
    ├── references/           # 泄漏分类库、五 agent 安装路径、可移植性规则、报告模板
    └── scripts/audit_skill.py# 审计器：泄漏 + 可移植性 + frontmatter，退出码可作 CI 门禁
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

# skill-sanitize-and-publish

## 简介

把「只能在本机跑」的技能，变成「任何人拿到就能用」的技能包。四件事：

1. **审计**：`scripts/audit_skill.py` 扫全目录，按 high/medium/low 分级报出本机痕迹与不可移植写法 ——
   家目录路径、用户名、主机名、外接盘卷标、局域网 IP、私有域名、个人服务名、令牌/密码/私钥/邮箱、
   写死的代理端口、GNU/BSD 单边选项、`fcntl` 这类 POSIX 专有 API、frontmatter 格式问题
   （技能名与目录名不一致、小于 57 字符窗口里没有触发词、BOM/CRLF）。
2. **按类处置**：每条命中给出四种处置之一 —— 删除（秘密）、参数化（本机特有的值）、占位（示例值）、
   保留并写理由（公共知识，如 AList 默认端口 5244）。处置记录留在报告里。
3. **私有值落配置文件**：要私有化的东西（路径、端口、密钥、搜索源命令、代理）迁到
   `~/.<技能名>/<技能名>.conf`，只提交 `*.conf.template`；配 `assets/conf_loader.py` 读取，
   优先级 命令行参数 > 环境变量 > 配置文件 > 内置默认；没有配置文件时给出「缺什么、去哪配」的报错。
4. **可移植与发布**：脚本按 macOS / Linux / Windows 三平台收口，写 README 与五大 agent 的
   **本地安装目录**（复制或软链即可用，不走任何商店），再从远端核实发布结果。

不适用：只在本机自用的技能（不必付出脱敏成本）；从零写新技能（这不是写技能的模板）。

## 依赖

- `python3`（3.8+，仅标准库；三平台通用）
- 可选：`gh`（发布到 GitHub 时用）、`git`

## 安装

与其它技能相同：把 `skills/skill-sanitize-and-publish/` 复制/软链到 agent 的本地技能目录。
它是纯 Python + Markdown，无第三方依赖，`audit_skill.py` 也可以脱离 agent 单独当命令行工具用。

## 使用方法

```bash
# 审计一个技能目录（退出码 0 = 没有达到 --fail-level 的问题）
python3 scripts/audit_skill.py /path/to/skill

# 更严：medium 也算失败；输出 JSON 便于聚合；顺手写一份处置报告
python3 scripts/audit_skill.py /path/to/skill --fail-level medium --json --report 脱敏报告.md

# 补上只有你知道的专属词（用户名、主机名、域名、站点名、盘标），一行一词
python3 scripts/audit_skill.py /path/to/skill --terms ~/.config/skill-sanitize/local-terms.txt
```

- 默认还会拿**本机**的用户名与主机名当判据（`--no-host-facts` 关闭）。
- 文档里必须保留的反面示例，用 `audit-skip: 理由`（行级）或 `audit-skip-file: 理由`（文件级，前 8 行内）
  就地记账；理由会进报告，不算静默跳过。
- 报告内含命中原文，**只留本地或私有仓库**。
- `assets/private.conf.template` 是给被脱敏技能用的配置模板；
  `assets/conf_loader.py` 是可直接抄走的三平台配置加载器。

## 参考文档

| 文件 | 内容 |
|---|---|
| `references/leak-taxonomy.md` | 泄漏分类库：每类长什么样、为什么算泄漏、怎么改（含 before/after） |
| `references/agent-install.md` | Hermes / Claude Code / Codex / OpenCode / OpenClaw 的本地技能目录与 frontmatter 差异 |
| `references/cross-platform.md` | 三平台可移植性规则（shell、Python、路径、服务管理、文件锁、编码） |
| `references/report-template.md` | 脱敏报告模板（交付给用户看的处置清单） |

## 免责声明

本仓库内容为工具链的自动化封装、运维便利与技能脱敏/发布流程，**不包含、不内置、不推荐任何内容站点**。
`aria2-rpc` 的搜索源由使用者自行配置，请遵守你所在地区的法律法规与版权规定，仅用于你有权下载的内容。
技能中的示例路径、主机名、服务名、令牌一律为占位符，不含作者机器的真实信息。

## License

MIT
