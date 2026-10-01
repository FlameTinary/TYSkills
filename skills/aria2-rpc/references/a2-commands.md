# a2 命令完整参考

a2 主程序：`~/.aria2/a2`（`~/.local/bin/a2` 是软链）。aria2 的端口/密钥自动从 `~/.aria2/aria2.conf` 读取（`rpc-listen-port`、`rpc-secret`）；a2 自己的配置（搜索源、服务名）在 `~/.aria2/a2.conf`。

## 全局行为

- **gid 前缀**：所有接受 gid 的命令都支持 6 位以上前缀（如 `a2 info c44f16`）；`all` 表示全部任务。
- **空间保护**：加任务时目标盘剩余 < `A2_MIN_FREE_GB`（默认 20 GB）直接拒绝；`A2_MIN_FREE_GB=5 a2 add ...` 临时放宽。
- **限速只对本次运行有效**：`a2 up/down` 改的是运行时全局选项，持久化需改 aria2.conf 后重启守护。

---

## 1. `a2 add` — 添加下载（默认入口，可省略 add 字样）

```
a2 add [-p] [-m|-t|-P|-flat|-d 目录] [-o 文件名] <url|magnet|file.torrent|urls.txt> ...
```

选项：
| 选项 | 含义 |
|---|---|
| `-p` / `--pause` | 加入后先暂停 |
| `-m` / `--movie` | 强制当电影 → `${A2_MEDIA_ROOT}/Movies` |
| `-t` / `--tv` | 强制当剧集 → `${A2_MEDIA_ROOT}/TV` |
| `-P` / `--private` | 强制当私藏 → `${A2_MEDIA_ROOT}/Private`（不看名字；成人/私藏资源用这个） |
| `-d DIR` | 指定任意保存目录：直接落 DIR，不经暂存区、不自动改名/入库、钩子不碰 |
| `-flat` | 强制落 aria2.conf 的 `dir`（不进媒体库） |
| `-o 名字` | 指定保存文件名 |

路由规则（`-d` 优先级最高，其次强制分类，然后看名字）：
- 名字命中剧集正则（`S01E02`、`1x02`、`第03集`、`第二季`、`第1-4季`、`全24集`、`合集`、`Season 1`、`EP 3`，
  以及**只写季号的整季包**如 `Show S01 COMPLETE 1080p`）→ 剧集；
- 否则含年份/1080p/2160p/BluRay/WEB-DL 等质量词或视频扩展名 → 电影；
- 都不是 → 普通下载落 conf 的 `dir`（默认 `~/Downloads`，可用 `A2_DOWNLOAD_DIR` 覆盖）；
- 磁力/种子没带名称 → `.incoming/_unsorted`，下载完钩子按实际文件名判断再入库。
- 目标目录不可用时拒绝加任务（跨平台判据：目录不存在且会被建到系统盘上 —— 通常是外接盘/网络盘没挂载）；目标盘剩余不足阈值也拒绝（见 §9 的 `A2_MIN_FREE_GB`）。

输入形式：URL、磁力、本地 `.torrent` 文件、文本文件（每行一个链接，`#` 注释）。

## 2. `a2 find` — 搜索（源由你自己配置）

```
a2 find <关键词> [--pages N] [--min-seeds N] [--res 1080p] [--prefer 组A,组B] [--all] [--refresh] [--json]
```

- **a2 不内置任何种子站/索引站**：`a2 find` 调用 `~/.aria2/a2.conf` 里 `tor-source-cmd=` 配置的
  「搜索源命令」（临时换源：`A2_TOR_CMD='…' a2 find …`）。源把结果以 JSON 打到 stdout，
  契约、字段别名、示例脚本见 `references/tor-source.md`；随附 `tor-source-demo.py`（离线自测）与
  `tor-source-template.py`（接入骨架）
- 源非零退出 / 超时 / 输出不是 JSON，都会**明确报错并以非零码退出**，绝不会伪装成「没有结果」
- 默认过滤（只看标题/分类文本，与用哪个源无关）：电影分类全留（单片没有「整季」概念）；
  剧集分类必须命中「整季/全集」且**不是单集 SxxExx**；噪音（3D/SBS/Hindi/多语/FLAC/电子书）剔除；
  `--all` 放宽到全部分类（含单集，噪音词仍剔除）
- 源没给分类时 a2 按标题推断（`S01E02`/`S01`/`第N季`/`全N集`/`合集`/`Season N` → TV；年份或 `1080p` 等 → Movies）
- 结果按做种数排序，`--prefer` 里的压制组排最前
- **缓存** `~/.aria2/find-cache.json`（v4：按 源指纹+关键词+页数 分键，默认 15 分钟内复用，`--refresh` 强制重抓）；
  只存源返回的**原始行**，所以换过滤参数不会互相污染；缓存里**不写源命令原文**（可能带 token），只写指纹与打码标签
- `--json` 打印规范化后的行 —— 调源时最好用这个看字段到底有没有被认出来
- 缓存位置可用 `A2_FIND_CACHE` 覆盖（测试/多实例）；`A2_TOR_DEBUG=1` 会打印完整源命令与源 stderr

## 3. `a2 grab` — 按搜索结果入库

```
a2 grab <序号|标题片段|infohash|磁力> [-t|-m|-P|-flat|-d 目录] [-p] [-o 名字] [--no-verify]
```

- 序号支持 `1,3,5` 与 `2-4`，按最近一次 find 的**视图**（过滤+排序后）取。
- 也可以给标题片段（匹配标题或详情页 URL 子串）、infohash（32/40 位，缓存里有现成磁力就用，没有就自己拼）或完整磁力。
- **默认先做真做种校验**：bt-metadata-only 从 DHT 拉真实元数据（`A2_TOR_VERIFY_TIMEOUT` 秒，默认 90），校验通过才入库；拉不到说明真没人做种（源的 seeds 数会撒谎），换一条或用 `--no-verify` 强下。
- 校验产物落 `~/.aria2/tor-cache`（绝不能落 `.incoming`，会触发入库钩子）。
- **落库分类**：没显式给 `-m/-t/-P/-d` 时跟随那一行的分类（源的分类，或按标题推断的分类），
  所以整季包不会因为磁力里的 `dn=` 被简写而落进普通下载目录；校验拿到的真实种子名优先用于分类。

## 4. 任务查看

```
a2 ls          # 活动+等待（默认）；a2 ls -a 含已结束
a2 st          # 全局：下载/上传速率、活动/等待/已结束任务数
a2 info <gid>  # 单任务：状态/大小/速率/连接数/做种数/错误码/目录/文件
a2 files <gid> # 任务内文件列表（BT 显示种子内全部文件，含未选中的）
```

BT 任务 `files[0]` 可能是 RARBG.txt 之类小文件，`ls` 显示种子名而不是第一个文件（看 `bittorrent.info.name`）。

## 5. 任务控制

```
a2 pause [force] <gid|all>     # force = 立即中断当前分片
a2 resume <gid|all>
a2 rm <gid|all>                # 移除任务（不删已下文件；已结束的顺带清结果）
a2 purge                       # 清空已结束列表
```

## 6. 限速（本次运行有效）

```
a2 up 1M     # 上传限速
a2 down 0    # 0 = 不限速
```

## 7. `a2 sweep` — 手动收尾入库

把 `.incoming` 里 aria2 认定「数据完整」、但钩子没搬走的条目，经 ffprobe 校验后搬进媒体库（用 `nameclean` 清洗文件名），并清理残留 `.aria2` 控制文件与 BT 元数据文件。
- 完成判据**只信 RPC**（completedLength==totalLength），不看 `.aria2` 控制文件（conf 里 force-save=true 会让已完成任务的控制文件永久残留）。
- RPC 不可用时降级为离线模式（只做 ffprobe 守卫，并明确警告）。
- 已存在同名目标会追加时间戳后缀，不覆盖。

## 8. AList 网盘助手（`a2-ls` / `a2-alist` / `a2-alist-dir` / `a2-aliyun`）

前置：AList 服务在 `http://localhost:5244`；管理员密码读 `~/.alist/admin_password.txt`（没有则交互输入）；已挂载阿里云盘（AliyundriveOpen 驱动）。

| 命令 | 作用 |
|---|---|
| `a2-ls [路径]` | 列出目录/文件（默认 `/`），目录在前、文件带大小 |
| `a2-alist "路径" [输出目录]` | 单文件：AList 取直链 → `a2 add -d 输出目录` |
| `a2-alist-dir "目录" [输出目录] [过滤]` | 目录批量：逐个取直链加入 a2（默认输出 `${A2_DOWNLOAD_DIR:-~/Downloads}`，过滤如 `*.mkv`） |
| `a2-aliyun "路径" [输出目录]` | 阿里云盘文件直链下载（密码同样读密码文件，不写死在脚本里） |

AList 本身的安装/阿里云盘接入见本技能 `references/install-guide.md`（安装）、`references/aliyun-driver.md`（阿里云盘驱动）、`references/alist-api.md`（API），脚本为 `scripts/install-alist.sh` 与 `scripts/setup-aliyun.sh`。

## 9. 环境变量（可覆盖默认行为）

| 变量 | 默认 | 作用 |
|---|---|---|
| `A2_TOR_CMD` | a2.conf 的 `tor-source-cmd` | 搜索源命令（临时换源，优先级最高） |
| `A2_TOR_TIMEOUT` | 60 | 单次调用源命令的超时（秒） |
| `A2_TOR_CACHE_TTL` | 900 | find 缓存有效期（秒） |
| `A2_TOR_VERIFY_TIMEOUT` | 90 | grab 元数据校验超时（秒） |
| `A2_TOR_CACHE_DIR` | ~/.aria2/tor-cache | 元数据校验产物目录（**不能**指向 .incoming） |
| `A2_TOR_DEBUG` | 空 | 1=打印完整源命令与源 stderr（命令可能含 token，谨慎） |
| `A2_FIND_CACHE` | ~/.aria2/find-cache.json | 搜索缓存文件（测试/多实例） |
| `A2_RC` | ~/.aria2/a2.conf | a2 自己的配置文件 |
| `A2_CONF` | ~/.aria2/aria2.conf | aria2 配置（端口/密钥/下载目录的来源） |
| `A2_SERVICE` | a2.conf 的 `service=` | 服务名（launchd / systemd unit / Windows 计划任务；只影响提示信息） |
| `A2_SECRET` | conf 的 `rpc-secret` | RPC 密钥覆盖 |
| `A2_MIN_FREE_GB` | 20 | 目标盘最小剩余空间阈值 |
| `A2_MEDIA_ROOT` | ~/media | 媒体库根目录（含 Movies/TV/Private；可在任意盘，Windows 可写 `D:\\media`） |
| `A2_DOWNLOAD_DIR` | ~/Downloads | 普通文件与 AList 直链的默认下载目录 |
| `A2_ARIA2` | `command -v aria2c` | aria2c 可执行文件路径（服务管理器 PATH 里找不到时指定绝对路径） |
| `A2_ALLOW_CREATE` | 空 | 1=允许把目标目录创建在系统盘上（默认拒绝，防止外接盘没挂载时误写） |
| `A2_FALLBACK_DIR` | 空 | 媒体库不可用时临时回退的下载目录（不设则拒绝启动） |

## 10. 与裸 RPC 的分工（a2 不覆盖才走 RPC）

a2 是"常用操作的封装"，以下能力它没暴露，需要 `scripts/aria2_cli.py` 或直接 curl（端口取 conf 的 `rpc-listen-port`）：
- `select-file`：整季包只下指定集（见 SKILL.md §5.3 完整示例）；
- `bt-metadata-only` + `bt-save-metadata`：定制元数据预校验；
- `aria2.addTorrent` 传自定义 options；
- `aria2.changeGlobalOption`：限速之外的全局选项；
- 按需字段的 `tellStatus` / `getGlobalStat` / `getFiles`。
