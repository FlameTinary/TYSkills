---
name: aria2-rpc
description: aria2 下载中枢（a2 优先，macOS / Linux / Windows(WSL) 通用）。a2 只做两件事：**下载到你给的目录**（add --dir，可选 --verify 先验真做种）与**任务管理**（ls/st/info/files/pause/resume/rm/purge/up/down）。**搜索在本技能这一层**：a2-search 在你自己配置的站点里搜（site= HTML 结果页自动抽磁力 / site=cmd: 自写源），并支持 --discover 全网发现结果页（websearch= 可配任意搜索页），脚本不内置任何资源站；**落点也在本技能**：a2-dest 首次按 OS 生成默认下载目录并持久化，电影/剧集/私藏等子目录由技能决定。另含 AList 网盘全流程（install-alist.sh / setup-aliyun.sh / a2-ls / a2-alist / a2-alist-dir / a2-aliyun）、一键部署（install-a2.sh，自动按平台装服务：macOS launchd / Linux systemd --user / Windows 计划任务）。a2 未覆盖的能力——select-file 只下整季包里的部分集、bt-metadata-only 定制校验、addTorrent 自定义选项、按需字段查询——用裸 aria2 JSON-RPC（scripts/aria2_cli.py 或 curl）。当用户提到 aria2、a2、下载器、磁力/BT 下载、种子搜索、找资源/搜资源、AList、网盘直链、下载任务管理、限速/暂停/继续、默认下载目录/落点配置时使用。
---

# a2 + Aria2 RPC 下载中枢

**职责三分**，越界就会乱：
- **a2**：只下载（`add --dir …`，可选 `--verify` 先验真做种）和管任务，不搜索、不推断分类、不改名、不搬动；
- **a2-search（技能层）**：搜索。在你自己配置的站点里搜，并支持全网发现；不内置任何资源站；
- **本文件的工作流（技能层）**：落点决策（`a2-dest` + 分类子目录）、搜索策略、下载前后的检查。
**凡 a2 有子命令的操作一律用 a2；a2 没有的才用裸 RPC。**

## 1. 系统布局（先确认这些在）

| 路径 | 作用 |
|---|---|
| `~/.local/bin/a2` | a2 命令（软链 → `~/.aria2/a2`） |
| `~/.local/bin/a2-dest` | **落点配置命令（技能层）**：首次运行按 OS 生成默认下载目录并持久化；`set` 改默认值 |
| `~/.aria2/dest.conf` | 落点配置：`download-dir=` / `media-root=`。**a2 不读它**（a2 只认 `--dir`），skill 与启动器读 |
| `~/.aria2/aria2.conf` | **aria2** 的配置：RPC 端口、rpc-secret、BT/tracker（只放 aria2 认识的键） |
| `~/.local/bin/a2-search` | **搜索命令（技能层）**：在 `search-sites.conf` 的站点里搜，`--discover` 做全网发现 |
| `~/.aria2/search-sites.conf` | 搜索站点配置：`site=<名字>|<URL 模板>`、`site=<名字>|cmd:<命令>`、`websearch=<URL>`；**a2 不读** |
| `~/.aria2/a2.conf` | **a2 自己**的配置：目前只有服务名 `service`（搜索配置不在这个文件里） |
| `~/.aria2/start-aria2.sh` | 启动器：校验 `dest.conf` 里的落点目录可用（不存在且会建到系统盘上就拒绝启动）；终端/服务管理器/cron 统一入口 |
| 服务定义（守护进程） | macOS `~/Library/LaunchAgents/<服务名>.plist`（launchd）｜Linux `~/.config/systemd/user/<服务名>.service`（systemd --user）｜Windows 计划任务 / nssm —— 默认服务名 `com.example.aria2`，崩溃自动拉起 |

可配置常量（环境变量覆盖）：目标盘最小剩余空间 `A2_MIN_FREE_GB`（默认 20，可 `A2_MIN_FREE_GB=5 a2 add …` 临时放宽）、
服务名 `A2_SERVICE`（默认 `com.example.aria2`）、落点配置路径 `A2_DEST_CONF`（默认 `~/.aria2/dest.conf`）、
站点配置路径 `A2_SITES_CONF`（默认 `~/.aria2/search-sites.conf`）、校验超时 `A2_VERIFY_TIMEOUT`（默认 90 秒）。
默认下载目录与媒体库根**不再走环境变量**：它们持久化在 `dest.conf`，用 `a2-dest set` / `a2-dest media set` 改
（`A2_DOWNLOAD_DIR` / `A2_MEDIA_ROOT` 只作为 AList 助手脚本的临时覆盖保留）。
落点可以在**任何**盘上（内置盘、外接盘、网络盘、Linux 的 `/mnt/…`、Windows 的 `D:\…`）。
启动器与 `a2 add` 用同一条跨平台判据检查目标目录：**家目录内**或**落在别的盘上**都直接放行；
只有「既不在家目录内、又会落在系统盘上」才拒绝（目录不存在且它的最近存在祖先与家目录同设备）——
这正是外接盘/网络盘没挂载、挂载点目录凭空消失的样子。确认就要那个位置：先 `mkdir -p`，
或用 `A2_ALLOW_CREATE=1`；想临时回退到系统盘的下载目录：`A2_FALLBACK_DIR=~/Downloads`。

## 2. 健康检查（动手前 3 秒）

```bash
a2 st            # 全局速率/任务数；RPC 不可用时它会给出对应平台的服务检查命令
# 守护是否在跑：macOS  launchctl list | grep aria2
#               Linux  systemctl --user status <服务名>
#               Windows  schtasks /Query /TN "<服务名>" /V
curl -s -o /dev/null -w "%{http_code}" http://localhost:5244   # AList（网盘下载才需要）应返回 200
```

## 3. 决策规则：a2 优先，裸 RPC 兜底

| 要做什么 | 用什么 |
|---|---|
| 下载链接/磁力/种子到指定目录（**落点必须先定好**，a2 只下不管分类） | `a2 add --dir <目录>` |
| 查/改默认下载目录（首次按 OS 生成） | `a2-dest` / `a2-dest set <目录>` / `a2-dest media […]` |
| 在**你配置的站点**里搜资源 | `a2-search <关键词>`（站点在 `search-sites.conf`，见 §5.2） |
| 不知道去哪搜 / 站点都不命中 | `a2-search --discover <关键词>` → 结果页链接交给 agent 的 web 工具 |
| 下载搜到的磁力（可选先验真做种） | `a2 add --dir <目录> --verify "<磁力>"` |
| 查看任务/单任务详情/任务内文件 | `a2 ls` / `a2 st` / `a2 info <gid>` / `a2 files <gid>` |
| 暂停/继续/移除/清空 | `a2 pause [force] <gid\|all>` / `a2 resume` / `a2 rm` / `a2 purge` |
| 上下行限速（本次运行有效） | `a2 up 1M` / `a2 down 0` |
| AList 安装 / 启动 / 云盘接入 / 验证 | `install-alist.sh` / `start-alist.sh` / `setup-aliyun.sh`（见 §5.4） |
| AList 网盘浏览/单文件下载/目录批量下载 | `a2-ls` / `a2-alist` / `a2-alist-dir` / `a2-aliyun` |
| **整季包里只下指定集**（select-file）、定制元数据校验、addTorrent 自定义选项、自定义全局选项 | **裸 RPC**（见 §5.3） |

原则：先翻 `a2 --help` 确认有没有对应子命令；没有 → `scripts/aria2_cli.py`（或直接 curl）；
RPC 报错先看 `~/.aria2/aria2.conf` 的端口/secret 是否被改。

## 4. a2 命令速查

```bash
a2-dest                                   # 默认下载目录（首次运行按 OS 生成并持久化）
a2-dest set <目录>                        # 改默认下载目录（持久化，后续沿用）
a2-dest media                             # 媒体库根（未设置 = 默认下载目录）
a2-dest media set <目录>                  # 单独指定媒体库根
a2 add --dir <目录> [--verify] [-p] [-o 文件名] <url|magnet|file.torrent|urls.txt> ...
a2-search <关键词> [--pages N] [--min-seeds N] [--res 1080p] [--prefer 组A,组B] [--all] [--json]
a2-search --discover <关键词> [--json]        # 全网发现：列出结果页链接
a2-search sites                               # 列出已配置的站点/搜索源
a2 ls [-a]   a2 st   a2 info <gid>   a2 files <gid>
a2 pause [force] <gid|all>   a2 resume <gid|all>   a2 rm <gid|all>   a2 purge
a2 up <rate|0>   a2 down <rate|0>
a2-ls <AList路径>   a2-alist <AList路径> [输出目录]   a2-alist-dir <AList目录> [输出目录] [过滤]
```

要点（坑都在这里）：
- **落点必须显式**：`a2 add` 不带 `--dir` 直接报错。a2 不推断分类、不进暂存区、不改名、不搬动——文件就落在你给的目录里。
- **搜索不在 a2 里**：`a2 find` / `a2 grab` 已移除，执行时会打印新用法。搜索用 `a2-search`（§5.2），
  它同样做过滤与排序：电影分类全留、剧集必须命中「整季/全集」且排除单集 SxxExx、噪音（3D/SBS/Hindi/FLAC/电子书）剔除，`--all` 全关。
- **`--verify` 是下载控制**（bt-metadata-only，最长 `A2_VERIFY_TIMEOUT` 秒）：搜索结果页标的做种数会撒谎，
  拿不到元数据就跳过该条。不想等就别加这个参数。
- **站点由使用者配置**：`~/.aria2/search-sites.conf` 里一行一个 `site=`；不内置任何资源站。
  站点改版导致抓不到时，换 URL、换站点，或写成 `cmd:` 源自己解析（契约见 `references/search-sites.md`）。
- **a2-search 不做缓存/序号**：它每次直接抓（`--pages` 翻页），磁力随 `--json` 一起给出，选哪条由 agent/用户决定。
- **限速只对本次运行有效**：持久化改 conf 后重启服务（macOS `launchctl kickstart -k gui/$(id -u)/<服务名>`；Linux `systemctl --user restart <服务名>`）。

## 5. 核心工作流

### 5.1 落点决策 + 下载

**决策顺序（技能这一层，a2 完全不参与）**：

1. 基目录 = `a2-dest`（首次运行按当前 OS 生成：macOS `~/Downloads`、Linux 遵循 XDG `XDG_DOWNLOAD_DIR`（本地化后可能叫 `~/下载`）、Windows `%USERPROFILE%\Downloads`），持久化在 `~/.aria2/dest.conf`；
2. 媒体库根 = `a2-dest media`（未单独设置时等于基目录）；
3. 需要分类时由**本技能**决定子目录：电影 → `<媒体库根>/Movies`，剧集 → `<媒体库根>/TV`，私藏 → `<媒体库根>/Private`，普通文件 → 基目录；
4. 把选好的目录传给 a2：`a2 add --dir <该目录> <输入>`。

```bash
a2-dest                                     # 看默认下载目录（首次会自动生成并落盘）
a2-dest set /Volumes/磁盘/Downloads          # 改默认（持久化，后续下载沿用）
a2-dest media set /Volumes/磁盘/media         # 媒体库根单独指定

DEST=$(a2-dest); MEDIA=$(a2-dest media)
mkdir -p "$MEDIA/Movies" "$MEDIA/TV" "$MEDIA/Private"   # 分类子目录由 skill 负责建

a2 add --dir "$DEST" "https://example.com/x.zip"         # 普通文件 → 默认下载目录
a2 add --dir "$MEDIA/TV" "magnet:?xt=urn:btih:…"          # 剧集 → 子目录由 skill 选
a2 add --dir "$MEDIA/Movies" -o "某电影.mkv" "https://…"  # -o 只改文件名，不改目录
a2 ls; a2 st
```

判分类的依据（只在 skill 侧，脚本里没有）：标题命中 `S01E02` / `1x02` / `第03集` / `第二季` / `全24集` / `合集` /
`Season 2` / 只写季号的整季包（`Show S01 COMPLETE 1080p`）→ 剧集；含年份或 `1080p/2160p/BluRay/WEB-DL` → 电影；
其余落默认下载目录。拿不准就问用户，别猜。

**a2 侧只有这些参数**：`--dir`（必填）、`-p`（加入后暂停）、`-o`（文件名）。输入类型仍是
`url | magnet | file.torrent | urls.txt`（每行一个链接，`#` 注释）。空间不足（`A2_MIN_FREE_GB`）会拒绝加任务。

### 5.2 搜索：找资源是本技能的活，a2 只管下

`a2 find` / `a2 grab` 已移除。找资源按这个顺序来（便宜 → 贵）：

1. **配置站点（首选，最快）**——`~/.aria2/search-sites.conf`：
   - `site=<名字>|<搜索结果页 URL 模板>`：脚本自己抽 `magnet:` 链接、标题、体积、做种数；
   - `site=<名字>|cmd:<命令>`：你自己写源，把 JSON 行打到 stdout（字段表见 `references/search-sites.md`）；
   - 模板占位符 `{query}`（URL 编码后关键词）、`{page}`（页码）。
2. **全网发现**——`a2-search --discover "<关键词>"` 调配置里的 `websearch=` 通用搜索页，列出结果页链接；
   再用 agent 自己的 web 搜索/抓取工具打开这些页面找磁力（这步不需要也不会自动下载）。
3. **问用户**——用户常用的站/私有 API 比任何猜测都准；问到了就写进 `search-sites.conf`，下次直接命中。

```bash
a2-search sites                                  # 先看有哪些站点可用
a2-search "关键词 压制组" --res 1080p              # 在配置站点里搜（默认过滤见 §4）
a2-search 关键词 --json | jq '.[0].magnet'        # 拿完整磁力（选哪条自己定）
a2-search --discover "关键词"                     # 站点都不命中时：先找页面
a2 add --dir "$(a2-dest media)/TV" --verify "<磁力>"   # 落点 + 先验真做种再下
```

要点：
- **过滤规则在搜索侧**：电影分类全留；剧集必须命中整季/全集且不是单集；噪音剔除；`--all` 关掉全部过滤。
  分辨率 `--res`、做种阈值 `--min-seeds`（seeds 未知的行不参与，HTML 页常见）、压制组优先 `--prefer` 都可叠加。
- **搜索结果可不可信看 `--verify`**：`a2 add --verify` 用 bt-metadata-only 从 DHT 拉真实元数据，拉不到就跳过。
- **站点抓不到 ≠ 没资源**：HTML 模式只认页面里的 `magnet:` 链接；结果页是 JS 渲染时，改用 `cmd:` 源
  （自己请求 API/解析），或换站点。`A2_SEARCH_PROXY=http://127.0.0.1:7897` 可给抓取指定代理。
- **不要手写搜索**：先看 `a2-search sites` 与 `search-sites.conf`，再考虑全网发现；同一关键词别反复翻 10 页。

### 5.3 整季包只下缺的集（select-file，裸 RPC）
场景：本地已有 E01/E03/E06，整季包里有全部 6 集，只想补 E02/E04/E05，不重复下载已存在的 12GB。
```bash
# 1) 先搜到目标行，拿到它的磁力
a2-search "关键词" --all --json
# 2) 拉元数据拿文件索引（1-based）：bt-metadata-only 落到 ~/.aria2/tor-cache
python3 - <<'PY'
import importlib.machinery, importlib.util, json, os, re, subprocess, time
loader = importlib.machinery.SourceFileLoader("a2mod", os.path.expanduser("~/.aria2/a2"))
spec = importlib.util.spec_from_loader("a2mod", loader)
a2 = importlib.util.module_from_spec(spec); loader.exec_module(a2)
cache_dir = os.path.expanduser("~/.aria2/tor-cache")
rows = json.loads(subprocess.check_output(["a2-search", "关键词", "--all", "--json"], text=True))
magnet = [r for r in rows if "关键词" in r["title"]][0]["magnet"]
ih = re.search(r"btih:([0-9a-fA-F]{40})", magnet).group(1).lower()
gid = a2.rpc("aria2.addUri", [[magnet], {"bt-metadata-only": "true", "bt-save-metadata": "true",
                                        "seed-time": "0", "dir": cache_dir}])
while a2.rpc("aria2.tellStatus", [gid, ["status"]])["status"] in ("active", "waiting"):
    time.sleep(3)
d = a2.tor_bdecode(open(os.path.join(cache_dir, ih + ".torrent"), "rb").read())
info = d[b"info"]
for i, f in enumerate(info.get(b"files") or [info], 1):
    print(i, b"/".join(f.get(b"path", [b"?"])).decode("utf-8", "replace"),
          f.get(b"length", info.get(b"length")))
# 3) 只下目标索引（先下到临时目录，确认完整再自己搬进媒体库）
gid = a2.rpc("aria2.addUri", [[magnet], {"dir": os.path.expanduser("~/Downloads/.tmp"),
                                        "select-file": "10,12,13", "seed-time": "0",
                                        "max-connection-per-server": "16", "split": "16"}])
# 4) 完成后自己校验（ffprobe）并搬进 $(a2-dest media) 对应目录，清理临时目录
PY
```
要点：`select-file` 是 1-based 索引；`dir` 传临时目录（a2/守护进程都不会替你搬文件）；
完成判据用 `aria2.tellStatus` 的 completedLength==totalLength，**不要看 `.aria2` 控制文件**（见 §6）。

### 5.4 AList 网盘下载（安装 → 接入 → 直链下载）

**① 安装 AList（首次）**
```bash
bash scripts/install-alist.sh     # 装到 ~/.local/bin/alist，密码存 ~/.alist/admin_password.txt
~/.alist/start-alist.sh           # 启动；验证 curl http://localhost:5244 返回 200
```
手动安装与目录结构见 references/install-guide.md。

**② 接入云盘（以阿里云盘 AliyundriveOpen 为例）**
```bash
# 先在 https://alist.nn.ci/tool/aliyundrive/request.html 用手机 App 扫码拿 refresh_token
bash scripts/setup-aliyun.sh "<refresh_token>"
# 或 Web UI：管理 → 存储 → 添加 → 驱动 AliyundriveOpen、挂载路径 /aliyun、根文件夹ID root
```
驱动参数与 token 失效排查见 references/aliyun-driver.md。

**③ 验证 + 下载**
```bash
a2-ls /aliyun                                        # 能列出即就绪
a2-alist "/aliyun/某电影/xx.mp4"                     # 单文件 → $(a2-dest)
a2-alist "/aliyun/某电影/xx.mp4" "$(a2-dest media)/Movies"
a2-alist-dir "/aliyun/剧集" "$(a2-dest media)/TV" "*.mkv"
```
前置：AList 在 localhost:5244、管理员密码在 `~/.alist/admin_password.txt`（建议 `chmod 600`）、已挂载云盘。
直链有约 15 分钟有效期，获取后尽快 `a2 add --dir …`（下载开始后过期不影响已建立连接）；API 细节见 references/alist-api.md。

## 6. 不可协商的事实（每条都踩过）

1. **坏路径是致命错误**：`log`/`dir`/`input-file` 指向不存在的路径时 aria2 直接 exit 1（`打开文件 … 失败`），
   所以 `install-a2.sh` 会先 touch 空的 `aria2.session` / `aria2.log`。
2. **aria2 不展开 `~`**：`dir=~/Downloads` 会创建一个字面量 `~/` 目录（实测）。conf 里写绝对路径。
3. **`bt-listen-port` 不是真选项**（1.37）：BT 端口是 `listen-port`，DHT 是 `dht-listen-port`；写错只有一行 WARN。
4. **服务管理器下不能 `--daemon=true`**：fork 后父进程退出 → launchd 的 `KeepAlive` / systemd 的 `Restart=always` / 计划任务会反复拉起。必须前台跑。
5. **BT 端口懒绑定**：空闲时 `lsof` 看不到监听端口是正常的，有任务才出现。
6. **完成判据只能是 RPC**（`completedLength == totalLength > 0`）。`force-save=true` 让已完成的 `.aria2` 控制文件
   永久残留 ——「没有控制文件才算下完」从来就不成立。
7. **完成的任务要 `removeDownloadResult` + `saveSession`**：否则重启会把已经下好的大种子再下一遍。
8. **别在下任务运行时删 `.aria2`**：会出现 `Failed to write into the segment file`。顺序是 `a2 rm` → `a2 purge` → 再删文件。
9. **`log-level=info` 会吃掉磁盘**（按 peer×piece 写，实测 23.7 GB）且 aria2 不自带轮转：保持 `warn`。
10. **重启守护后 5–10 分钟 RPC 可能时断时续**（进程在重新校验/保存大任务、磁盘满速）：别反复 kill，
    处于不可中断 I/O 的进程也杀不掉；重启前先 `aria2.saveSession`。
11. **不支持稀疏文件的外接盘必须 `file-allocation=none`**（macOS 的 HFS+ 是典型；APFS / ext4 / XFS / NTFS 正常）：
    `falloc` 真的会写满零。盘写满会让 aria2 卡在内核 fsync 上（macOS `sample <pid>`，Linux 看进程 `D` 状态），
    进程杀不掉又占着 RPC 端口 → 服务管理器反复 respawn。
12. **aria2 用 HTTP 400 + JSON 体表达 RPC 错误**：只捕通用异常会得到没信息量的 `HTTP Error 400: Bad Request`，
    要读 `HTTPError.read()` 里的 `error.message`（`a2` 与 `aria2_cli.py` 都已处理）。
13. **两个配置文件的键别串门**：aria2 的键写进 `a2.conf` 会失效，a2 的键写进 `aria2.conf` 会换来
    `[WARN] Unknown option` 刷屏。

## 7. 故障排查速查

| 现象 | 处理 |
|---|---|
| `a2` 报 RPC 不可用 | 确认守护在跑（macOS `launchctl print gui/$(id -u)/<服务名>`；Linux `systemctl --user status <服务名>`；Windows `schtasks /Query /TN "<服务名>" /V`），重启后 `a2 st` 复验 |
| `a2-search` 说「还没有配置站点」 | 在 `~/.aria2/search-sites.conf` 加 `site=` 行，见 references/search-sites.md |
| `a2-search` 抓到 0 条磁力 | 结果页可能改版/是 JS 渲染：换站点 URL、改 `cmd:` 源，或 `--discover` 找别的页 |
| `a2-search` 报 cmd 源失败/超时/非 JSON | 源的问题，不是脚本：先单独跑那条命令；`A2_SEARCH_DEBUG=1` 打印完整命令 |
| `a2 add --verify` 一直跳过 | DHT 上没有节点给元数据（真没人做种）；换一条，或去掉 `--verify` 强下 |
| 任务 0 速度 / 卡在元数据 | 公共 BT 冷门资源正常；`bt-stop-timeout=0` 不会自停；查 `~/.aria2/aria2.log`（需细查临时改 `info` 并重启） |
| `a2 add` 报「缺少目标目录」 | a2 不推断落点：`a2 add --dir "$(a2-dest)" …`；要换默认值就 `a2-dest set <目录>` |
| 目标盘空间不足被拒 | `A2_MIN_FREE_GB=5 a2 add …` 临时放宽；或清理磁盘 |
| 下载失败看似全挂 | 先确认不是 `bt-stop-timeout` 误设；errorCode=7 = 未完成数据 |
| 外接盘文件「虚大」 | 不支持稀疏文件的文件系统（如 HFS+）零填充占块；真实进度以 RPC completedLength 为准 |
| 播不了的视频 | 截断的容器（ffprobe 报 `moov atom not found`）：a2 已不做入库校验，自己 `ffprobe <文件>` 确认后重下 |
| 磁盘没满但 RPC 假死、服务反复重启 | 进程卡在 fsync 并占着端口（macOS `sample <pid>`、Linux 看 `D` 状态确认）；先腾空间 → `: > ~/.aria2/aria2.session` → 重启服务 |
| 其余（路径与配置键、日志、会话、RPC、BT） | `references/troubleshooting.md` 有完整分类表 |

## 8. 文件一览

| 文件 | 作用 |
|---|---|
| `scripts/a2` | 主程序（add + 任务管理 + `--verify` 真做种校验；不搜索） |
| `scripts/a2-search` | **搜索**（技能层）：配置站点（HTML/命令两种）里搜、过滤排序、`--discover` 全网发现 |
| `scripts/search-source-demo.py` | 离线自测 cmd 源（不联网，验证「搜 → 选 → 下」流程） |
| `scripts/search-source-template.py` | 接入自己站点的 cmd 源骨架 |
| `scripts/aria2_cli.py` | 裸 RPC 客户端（a2 没覆盖的能力；端口/密钥自动读 conf） |
| `scripts/a2-dest` | **落点配置**（技能层）：首次按 OS 生成默认下载目录、持久化、读取/修改（`--json` 供脚本用） |
| `tests/` | `python3 -m unittest discover -s tests`（add/--verify、已删参数、a2-dest、a2-search 解析与过滤） |
| `scripts/start-aria2.sh` | 启动器：校验 `dest.conf` 里落点目录可用（跨平台判据）+ 统一启动路径 |
| `scripts/install-a2.sh` | 一键部署（幂等；按平台装 launchd / systemd / 计划任务服务） |
| `scripts/install-alist.sh` / `scripts/setup-aliyun.sh` | AList 安装 / 云盘接入 |
| `scripts/a2-ls` / `a2-alist` / `a2-alist-dir` / `a2-aliyun` | AList 网盘助手四件套 |
| `assets/aria2.conf.template` / `assets/a2.conf.template` | 配置模板（`__HOME__` / `__RPC_SECRET__` / `__LABEL__` 由安装脚本替换） |
| `assets/com.example.aria2.plist.template`（macOS）/ `assets/a2.service.template`（Linux） | 服务定义模板 |

## 9. 参考文件

- `references/a2-commands.md` — a2 全部子命令逐一详解（参数/示例/坑）
- `references/search-sites.md` — **搜索站点契约**：HTML/cmd 两种源、字段表与别名、全网发现、排查
- `references/troubleshooting.md` — 排错与「用血换来的事实」（路径/服务管理/磁盘/日志/BT/落点/RPC）
- `references/setup.md` — 搭建部署（macOS/Linux/Windows）、服务管理、落点配置、维护要点
- `references/install-guide.md` — AList 手动安装指南（下载/初始化/启动/目录结构）
- `references/aliyun-driver.md` — 阿里云盘 AliyundriveOpen 驱动配置（token/参数/验证/排查）
- `references/alist-api.md` — AList API 参考（登录/fs 列表与直链/存储管理/状态码）
- `references/api_reference.md` — aria2 JSON-RPC 完整方法参考
