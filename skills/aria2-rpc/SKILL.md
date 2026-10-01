---
name: aria2-rpc
description: aria2 下载中枢（a2 优先，macOS / Linux / Windows(WSL) 通用）。以 a2（aria2 高级封装 CLI）为第一入口：媒体下载自动分级入库（add）、任务管理（ls/st/info/files/pause/resume/rm/purge）、限速（up/down）、暂存区收尾（sweep）、搜索入库（find/grab，**站点由使用者在 ~/.aria2/a2.conf 里自行配置命令，脚本不内置任何站点**）、AList 网盘全流程（install-alist.sh / setup-aliyun.sh / a2-ls / a2-alist / a2-alist-dir / a2-aliyun）、一键部署（install-a2.sh，自动按平台装服务：macOS launchd / Linux systemd --user / Windows 计划任务，含配置模板与搜索源示例脚本）。a2 未覆盖的能力——select-file 按索引只下整季包里的部分集、bt-metadata-only 定制校验、addTorrent 自定义选项、按需字段查询——再用裸 aria2 JSON-RPC（scripts/aria2_cli.py 或直接 curl）。当用户提到 aria2、a2、下载器、磁力/BT 下载、种子搜索下载、AList、网盘直链下载、下载任务管理、下载限速/暂停/继续时使用。
---

# a2 + Aria2 RPC 下载中枢

a2 是 aria2 的完整封装：下载自动分级入库、搜索源按需接入、网盘直链、暂存区收尾。
**凡 a2 有子命令的操作一律用 a2；a2 没有的才用裸 RPC。**
本技能不含任何具体站点：搜索源（`a2 find` 用）由使用者在 `~/.aria2/a2.conf` 里配置一条命令即可。

## 1. 系统布局（先确认这些在）

| 路径 | 作用 |
|---|---|
| `~/.local/bin/a2` | a2 命令（软链 → `~/.aria2/a2`） |
| `~/.aria2/aria2.conf` | **aria2** 的配置：RPC 端口、rpc-secret、BT/tracker、钩子（只放 aria2 认识的键） |
| `~/.aria2/a2.conf` | **a2 自己**的配置：搜索源 `tor-source-cmd`、服务名 `service` |
| `~/.aria2/on-complete.py` | 下载完成钩子：`.incoming` 暂存区媒体自动搬进媒体库 |
| `~/.aria2/nameclean.py` | 入库文件名清洗（去站点广告，不动 SxxExx/年份/分辨率） |
| `~/.aria2/start-aria2.sh` | 启动器：校验媒体库目录可用（不存在且会建到系统盘上就拒绝启动）；终端/服务管理器/cron 统一入口 |
| 服务定义（守护进程） | macOS `~/Library/LaunchAgents/<服务名>.plist`（launchd）｜Linux `~/.config/systemd/user/<服务名>.service`（systemd --user）｜Windows 计划任务 / nssm —— 默认服务名 `com.example.aria2`，崩溃自动拉起 |
| `${A2_MEDIA_ROOT}/{Movies,TV,Private}` | 媒体库（默认 `~/media`，可在任意盘上：`/mnt/xxx/media`、`D:\media` 都行；安装脚本会建好这三个子目录） |
| `${A2_MEDIA_ROOT}/.incoming/{Movies,TV,Private,_unsorted}` | 下载中暂存区（完成后钩子搬走） |

可配置常量（环境变量覆盖，换机器必改）：媒体库根 `A2_MEDIA_ROOT`（默认 `~/media`）、
默认下载目录 `A2_DOWNLOAD_DIR`（默认 `~/Downloads`）、目标盘最小剩余空间 `A2_MIN_FREE_GB`（默认 20，
可 `A2_MIN_FREE_GB=5 a2 add …` 临时放宽）、服务名 `A2_SERVICE`（默认 `com.example.aria2`）。
媒体库可以放在**任何**盘上（内置盘、外接盘、网络盘、Linux 的 `/mnt/…`、Windows 的 `D:\…`）。
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
| 下载链接/磁力/种子（自动分级入库、-d 直达、-m/-t/-P/-flat 强制分类） | `a2 add` |
| 搜索（源由你在 a2.conf 里配置） | `a2 find` |
| 按搜索结果入库（先 bt-metadata-only 校验真做种，再下载） | `a2 grab <序号>` |
| 查看任务/单任务详情/任务内文件 | `a2 ls` / `a2 st` / `a2 info <gid>` / `a2 files <gid>` |
| 暂停/继续/移除/清空 | `a2 pause [force] <gid\|all>` / `a2 resume` / `a2 rm` / `a2 purge` |
| 上下行限速（本次运行有效） | `a2 up 1M` / `a2 down 0` |
| 暂存区已完成但钩子没搬的条目 → 入库 | `a2 sweep` |
| AList 安装 / 启动 / 云盘接入 / 验证 | `install-alist.sh` / `start-alist.sh` / `setup-aliyun.sh`（见 §5.4） |
| AList 网盘浏览/单文件下载/目录批量下载 | `a2-ls` / `a2-alist` / `a2-alist-dir` / `a2-aliyun` |
| **整季包里只下指定集**（select-file）、定制元数据校验、addTorrent 自定义选项、自定义全局选项 | **裸 RPC**（见 §5.3） |

原则：先翻 `a2 --help` 确认有没有对应子命令；没有 → `scripts/aria2_cli.py`（或直接 curl）；
RPC 报错先看 `~/.aria2/aria2.conf` 的端口/secret 是否被改。

## 4. a2 命令速查

```bash
a2 add [-p] [-m|-t|-P|-flat|-d 目录] [-o 文件名] <url|magnet|file.torrent|urls.txt> ...
a2 find <关键词> [--pages N] [--min-seeds N] [--res 1080p] [--prefer 组A,组B] [--all] [--refresh] [--json]
a2 grab <序号|标题片段|infohash|磁力> [-t|-m|-P|-flat|-d 目录] [-p] [-o 文件名] [--no-verify]
a2 ls [-a]   a2 st   a2 info <gid>   a2 files <gid>
a2 pause [force] <gid|all>   a2 resume <gid|all>   a2 rm <gid|all>   a2 purge
a2 up <rate|0>   a2 down <rate|0>
a2 sweep
a2-ls <AList路径>   a2-alist <AList路径> [输出目录]   a2-alist-dir <AList目录> [输出目录] [过滤]
```

要点（坑都在这里）：
- **add 默认落点**：名字像剧集（S01E02/1x02/第03集/整季/合集/Season 2/**只写季号的整季包如 `Show S01 COMPLETE 1080p`**…）
  → `.incoming/TV`→完成后自动入库 `${A2_MEDIA_ROOT}/TV`；像电影/含年份+1080p → `${A2_MEDIA_ROOT}/Movies`；
  普通文件 → `aria2.conf` 的 `dir`（默认 `~/Downloads`）；裸磁力无名称 → `.incoming/_unsorted`，下载完按真实文件名判断。
- **`-d` 直达**：落用户指定目录，不经暂存区、钩子不碰、不会被改名（适合自定义位置；媒体库根目录慎用）。
- **find 默认过滤**：电影分类全留；剧集必须命中「整季/全集」且排除单集 SxxExx；噪音（3D/SBS/Hindi/FLAC/电子书）剔除。
  搜单集要加 `--all`。源没给分类时按标题推断。**源挂掉/超时/输出不是 JSON 会明确报错，不会显示成「没有结果」。**
- **grab 默认先做真做种校验**（bt-metadata-only，最长 `A2_TOR_VERIFY_TIMEOUT` 秒）：源标的做种数会撒谎，
  校验不过就换一条或用 `--no-verify` 强下。落库分类跟随那一行的分类（源的分类或标题推断），
  所以整季包不会因为磁力 `dn=` 被简写而落错库。
- **find/grab 依赖缓存** `~/.aria2/find-cache.json`（v4：按 源指纹+关键词+页数 分键）：`grab <序号>` 取的是最近一次
  find 的**视图**（过滤+排序后），15 分钟内复用，`--refresh` 强制重抓；缓存里不写源命令原文（可能带 token）。
- **限速只对本次运行有效**：持久化改 conf 后重启服务（macOS `launchctl kickstart -k gui/$(id -u)/<服务名>`；Linux `systemctl --user restart <服务名>`）。

## 5. 核心工作流

### 5.1 下载媒体（自动入库）
```bash
a2 add "magnet:?xt=urn:btih:..."          # 剧集/电影自动分级，完成后钩子搬进媒体库
a2 add "https://example.com/x.mkv" -t     # 强制当剧集
a2 add "https://example.com/x.zip"        # 普通文件 → ${A2_DOWNLOAD_DIR:-~/Downloads}
a2 ls                                     # 看进度；a2 st 看速率
```

### 5.2 配好搜索源 → 搜索 → 入库
```bash
# 一次性配置（契约详见 references/tor-source.md）：在 ~/.aria2/a2.conf 里写
#   tor-source-cmd=<你的搜索源命令>        # 命令里可用 {query}/{page} 占位符，或用 A2_QUERY/A2_PAGE/A2_PAGES
# 想先离线跑通流程（不联网）：
#   tor-source-cmd=python3 ~/.aria2/tor-source-demo.py
a2 find "关键词 压制组" --res 1080p        # 关键词语言跟着你的源站点走
a2 find 关键词 --json                     # 调源时先看这条：字段到底有没有被认出来
a2 grab 1,3,5                             # 按显示的序号（可多个/区间 2-4）入库
```

### 5.3 整季包只下缺的集（select-file，裸 RPC）
场景：本地已有 E01/E03/E06，整季包里有全部 6 集，只想补 E02/E04/E05，不重复下载已存在的 12GB。
```bash
# 1) 先 a2 find 拿到目标行（grab 的缓存里有它的磁力）
a2 find "关键词" --all
# 2) 拉元数据拿文件索引（1-based）：bt-metadata-only 落到 ~/.aria2/tor-cache
python3 - <<'PY'
import importlib.machinery, importlib.util, json, os, re, time
loader = importlib.machinery.SourceFileLoader("a2mod", os.path.expanduser("~/.aria2/a2"))
spec = importlib.util.spec_from_loader("a2mod", loader)
a2 = importlib.util.module_from_spec(spec); loader.exec_module(a2)
cache = json.load(open(os.path.expanduser("~/.aria2/find-cache.json")))
cache_dir = os.path.expanduser("~/.aria2/tor-cache")
row = [r for r in (cache.get("view") or cache.get("rows") or []) if "关键词" in r["title"]][0]
magnet = row["magnet"]
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
# 3) 只下目标索引（下到自定义临时目录，避开 .incoming 以免钩子误搬）
gid = a2.rpc("aria2.addUri", [[magnet], {"dir": os.path.expanduser("~/Downloads/.tmp"),
                                        "select-file": "10,12,13", "seed-time": "0",
                                        "max-connection-per-server": "16", "split": "16"}])
# 4) 完成后把文件搬进 ${A2_MEDIA_ROOT} 对应目录 + ffprobe 校验 + 清理临时目录
PY
```
要点：`select-file` 是 1-based 索引；BT 任务下载目录不要落在 `.incoming`（完成钩子只认暂存区，落别处安全）；
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
a2-alist "/aliyun/某电影/xx.mp4"                     # 单文件 → ${A2_DOWNLOAD_DIR:-~/Downloads}
a2-alist "/aliyun/某电影/xx.mp4" ${A2_MEDIA_ROOT:-~/media}/Movies
a2-alist-dir "/aliyun/剧集" ${A2_MEDIA_ROOT:-~/media}/TV "*.mkv"
```
前置：AList 在 localhost:5244、管理员密码在 `~/.alist/admin_password.txt`（建议 `chmod 600`）、已挂载云盘。
直链有约 15 分钟有效期，获取后尽快 `a2 add`（下载开始后过期不影响已建立连接）；API 细节见 references/alist-api.md。

### 5.5 手动收尾（钩子漏搬时）
```bash
a2 sweep    # 把 .incoming 里 aria2 认定完整、但钩子没搬的条目经 ffprobe 校验后入库，并清理残留控制文件
```

## 6. 不可协商的事实（每条都踩过）

1. **坏路径是致命错误**：`log`/`dir`/`input-file` 指向不存在的路径时 aria2 直接 exit 1（`打开文件 … 失败`），
   所以 `install-a2.sh` 会先 touch 空的 `aria2.session` / `aria2.log`。
2. **aria2 不展开 `~`**：`dir=~/Downloads` 会创建一个字面量 `~/` 目录（实测）。conf 里写绝对路径。
3. **`bt-listen-port` 不是真选项**（1.37）：BT 端口是 `listen-port`，DHT 是 `dht-listen-port`；写错只有一行 WARN。
4. **服务管理器下不能 `--daemon=true`**：fork 后父进程退出 → launchd 的 `KeepAlive` / systemd 的 `Restart=always` / 计划任务会反复拉起。必须前台跑。
5. **BT 端口懒绑定**：空闲时 `lsof` 看不到监听端口是正常的，有任务才出现。
6. **完成判据只能是 RPC**（`completedLength == totalLength > 0`）。`force-save=true` 让已完成的 `.aria2` 控制文件
   永久残留，而且钩子被调用时控制文件一定还在 ——「没有控制文件才算下完」从来就不成立。
7. **完成的任务要 `removeDownloadResult` + `saveSession`**：否则重启会把已经入库的大种子再下一遍。
8. **别在下任务运行时删 `.aria2`**：会出现 `Failed to write into the segment file`。顺序是 `a2 rm` → `a2 purge` → 再删文件。
9. **`log-level=info` 会吃掉磁盘**（按 peer×piece 写，实测 23.7 GB）且 aria2 不自带轮转：保持 `warn`。
10. **重启守护后 5–10 分钟 RPC 可能时断时续**（进程在重新校验/保存大任务、磁盘满速）：别反复 kill，
    处于不可中断 I/O 的进程也杀不掉；重启前先 `aria2.saveSession`。
11. **不支持稀疏文件的外接盘必须 `file-allocation=none`**（macOS 的 HFS+ 是典型；APFS / ext4 / XFS / NTFS 正常）：
    `falloc` 真的会写满零。盘写满会让 aria2 卡在内核 fsync 上（macOS `sample <pid>`，Linux 看进程 `D` 状态），
    进程杀不掉又占着 RPC 端口 → 服务管理器反复 respawn。
12. **aria2 用 HTTP 400 + JSON 体表达 RPC 错误**：只捕通用异常会得到没信息量的 `HTTP Error 400: Bad Request`，
    要读 `HTTPError.read()` 里的 `error.message`（`a2` 与 `aria2_cli.py` 都已处理）。
13. **ffprobe 要按绝对路径兜底找**：钩子由服务管理器拉起，PATH 很窄（launchd 里没有 Homebrew，systemd --user 里常没有 `/usr/local/bin`，Windows 计划任务里基本是空的）；只用 `shutil.which` 会静默关掉整套校验。
14. **两个配置文件的键别串门**：aria2 的键写进 `a2.conf` 会失效，a2 的键写进 `aria2.conf` 会换来
    `[WARN] Unknown option` 刷屏。

## 7. 故障排查速查

| 现象 | 处理 |
|---|---|
| `a2` 报 RPC 不可用 | 确认守护在跑（macOS `launchctl print gui/$(id -u)/<服务名>`；Linux `systemctl --user status <服务名>`；Windows `schtasks /Query /TN "<服务名>" /V`），重启后 `a2 st` 复验 |
| `a2 find` 说「没有配置搜索源」 | 在 `~/.aria2/a2.conf` 填 `tor-source-cmd=`，见 references/tor-source.md |
| `a2 find` 报源失败/超时/输出不是 JSON | 源的问题，不是 a2：先在终端单独跑那条命令；`A2_TOR_DEBUG=1` 打印完整命令与源 stderr |
| 任务 0 速度 / 卡在元数据 | 公共 BT 冷门资源正常；`bt-stop-timeout=0` 不会自停；查 `~/.aria2/aria2.log`（需细查临时改 `info` 并重启） |
| 目标盘空间不足被拒 | `A2_MIN_FREE_GB=5 a2 add …` 临时放宽；或清理磁盘 |
| `.incoming` 里文件不入库 | 判据是 RPC 不是控制文件；`a2 sweep` 手动收尾，或查 `~/.aria2/move.log` |
| 下载失败看似全挂 | 先确认不是 `bt-stop-timeout` 误设；errorCode=7 = 未完成数据 |
| 外接盘文件「虚大」 | 不支持稀疏文件的文件系统（如 HFS+）零填充占块；真实进度以 RPC completedLength 为准 |
| 库里有播不了的视频 | 截断的容器（ffprobe `moov atom not found`）被搬进来了 —— 钩子与 `a2 sweep` 的 ffprobe 守卫就是防这个 |
| 磁盘没满但 RPC 假死、服务反复重启 | 进程卡在 fsync 并占着端口（macOS `sample <pid>`、Linux 看 `D` 状态确认）；先腾空间 → `: > ~/.aria2/aria2.session` → 重启服务 |
| 其余（路径与配置键、日志、会话、RPC、入库、BT） | `references/troubleshooting.md` 有完整分类表 |

## 8. 文件一览

| 文件 | 作用 |
|---|---|
| `scripts/a2` | 主程序（add/sweep/find/grab/ls/st/info/files/pause/resume/rm/purge/up/down + 搜索源调用） |
| `scripts/tor-source-demo.py` | 离线自测搜索源（不联网，验证 find/grab 流程） |
| `scripts/tor-source-template.py` | 接入自己站点的搜索源骨架 |
| `scripts/aria2_cli.py` | 裸 RPC 客户端（a2 没覆盖的能力；端口/密钥自动读 conf） |
| `scripts/on-complete.py` / `scripts/nameclean.py` | 完成钩子 + 文件名清洗（入库用，共用一套规则） |
| `scripts/start-aria2.sh` | 启动器：校验目标目录可用（跨平台判据）+ 统一启动路径 |
| `scripts/install-a2.sh` | 一键部署（幂等；按平台装 launchd / systemd / 计划任务服务） |
| `scripts/install-alist.sh` / `scripts/setup-aliyun.sh` | AList 安装 / 云盘接入 |
| `scripts/a2-ls` / `a2-alist` / `a2-alist-dir` / `a2-aliyun` | AList 网盘助手四件套 |
| `assets/aria2.conf.template` / `assets/a2.conf.template` | 配置模板（`__HOME__` / `__RPC_SECRET__` / `__LABEL__` 由安装脚本替换） |
| `assets/com.example.aria2.plist.template`（macOS）/ `assets/a2.service.template`（Linux） | 服务定义模板 |

## 9. 参考文件

- `references/a2-commands.md` — a2 全部子命令逐一详解（参数/示例/坑）
- `references/tor-source.md` — **搜索源契约**：配置、JSON 字段表与别名、写自己的源、排查
- `references/troubleshooting.md` — 排错与「用血换来的事实」（路径/服务管理/磁盘/日志/BT/入库/RPC）
- `references/setup.md` — 搭建部署（macOS/Linux/Windows）、服务管理、媒体落点、维护要点
- `references/install-guide.md` — AList 手动安装指南（下载/初始化/启动/目录结构）
- `references/aliyun-driver.md` — 阿里云盘 AliyundriveOpen 驱动配置（token/参数/验证/排查）
- `references/alist-api.md` — AList API 参考（登录/fs 列表与直链/存储管理/状态码）
- `references/api_reference.md` — aria2 JSON-RPC 完整方法参考
