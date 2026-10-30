# a2 命令完整参考

**`a2`（`~/.aria2/a2`，`~/.local/bin/a2` 是软链）只对资源做增删改查**：
增 `add` / 删 `rm` `purge` / 改 `pause` `resume` `concurrent` `up` `down` / 查 `ls` `st` `info` `files`。
搜索（`a2-search`）、落点（`a2-dest`，含 `check`）、资源校验（`a2-verify`）都在**技能层**，本节末尾各有一节。
aria2 的端口/密钥自动从 `~/.aria2/aria2.conf` 读取（`rpc-listen-port`、`rpc-secret`）；a2 自己的配置（目前只有服务名）在 `~/.aria2/a2.conf`；搜索站点在 `~/.aria2/search-sites.conf`。

## 0. 落点配置：`a2-dest`（技能层，不是 a2 的选项）

a2 自己**不决定任何落点**：`a2 add` 必须显式给 `--dir`。默认目录与分类子目录的这一层决策在这里：

```
a2-dest                   # 打印默认下载目录；首次运行按 OS 生成并写入 ~/.aria2/dest.conf
a2-dest check DIR         # 落点检查：挂载判据 + 建目录 + 剩余空间，打印绝对路径（下之前先跑）
a2-dest set DIR           # 改默认下载目录（持久化，后续沿用）
a2-dest media             # 打印媒体库根（未设置 = download-dir）
a2-dest media set DIR     # 单独指定媒体库根
a2-dest cat               # 打印配置文件路径与内容
a2-dest --json            # {"config":…,"download-dir":…,"media-root":…}
```

- 首次调用就落盘（`~/.aria2/dest.conf`，`A2_DEST_CONF` 可换路径），不会每次重新猜；
- 按 OS 生成默认值：macOS `~/Downloads`；Linux `XDG_DOWNLOAD_DIR`（读 `~/.config/user-dirs.dirs`，本地化后可能是 `~/下载`），退回 `~/Downloads`；Windows `%USERPROFILE%\Downloads`；
- 需要「电影 / 剧集 / 私藏」时由技能拼子目录（`$(a2-dest media)/Movies|TV|Private`），a2 不认识这些分类；
- 启动器 `start-aria2.sh` 会校验 `download-dir` 与 `media-root` 是否可用（盘没挂载就拒绝启动）；
- `check` 是**落点策略**的唯一入口（原来压在 a2 里）：目录不存在且会建在家目录所在那块盘上 → 拒绝
  （外接盘/网络盘没挂载的典型误写），`A2_ALLOW_CREATE=1` 放行；剩余 < `A2_MIN_FREE_GB`（默认 20）→ 拒绝。
  `a2 add` 自己不再做这些判断，只要求目录**已经存在**。

## 全局行为

- **gid 前缀**：所有接受 gid 的命令都支持 6 位以上前缀（如 `a2 info c44f16`）；`all` 表示全部任务。
- **空间/挂载检查不在 a2**：`a2 add` 只要求目录已存在；要检查盘在不在、够不够空间，先跑 `a2-dest check DIR`（见 §0）。
- **限速只对本次运行有效**：`a2 up/down` 改的是运行时全局选项，持久化需改 aria2.conf 后重启守护。

---

## 1. `a2 add` — 添加下载到指定目录（默认入口，可省略 add 字样）

```
a2 add --dir DIR [-p] [-o 文件名] <url|magnet|file.torrent|urls.txt> ...
```

选项：
| 选项 | 含义 |
|---|---|
| `--dir DIR` | **必填**：下到 DIR（**目录必须已存在**）。只负责下载，不改名、不搬动、不做分类 |
| `-p` / `--pause` | 加入后先暂停 |
| `-o 名字` | 指定保存文件名 |

行为：
- **不给 `--dir` 直接报错退出**，不会退回任何「默认库」或按名字猜目录；
- 目录不存在直接报错退出（不建目录、不判断盘、不算空间 —— 这些在 `a2-dest check`）；
- 已删除的落点参数（`-m` / `-t` / `-P` / `-flat` / `-d`）现在会报「已移除的选项」并提示改用 `--dir`；
- 落点的决策在技能层：基目录 `a2-dest`、分类子目录由技能拼（见 §0）；
- `--verify` 已移到技能层：现在用 `a2-verify <磁力|file.torrent>`（见 §2.5），a2 不再做资源判断。

输入形式：URL、磁力、本地 `.torrent` 文件、文本文件（每行一个链接，`#` 注释）。

## 2. `a2-search` — 搜索（技能层，不是 a2 的子命令）

`a2 find` / `a2 grab` 已移除：搜索不在 a2 里。完整契约（HTML 抽取规则、cmd 源字段表、全网发现、排查）
见 **`references/search-sites.md`**，这里只列形状：

```
a2-search <关键词> [--pages N] [--min-seeds N] [--res 1080p] [--prefer 组A,组B] [--all]
                   [--json] [--site 名字] [--timeout S]
a2-search --discover <关键词> [--json]     # 全网发现：结果页链接（配合 agent 的 web 工具）
a2-search sites                            # 列出已配置的站点/搜索源
```

- 站点在你自己的 `~/.aria2/search-sites.conf` 里配置：`site=<名字>|<URL 模板>`（HTML，自动抽磁力）
  或 `site=<名字>|cmd:<命令>`（自写源，输出 JSON 行）；`websearch=` 供 `--discover` 用；
- 过滤/排序在搜索侧：电影分类全留、剧集要「整季/全集」且不是单集、噪音剔除，`--all` 全关；
  `--res` / `--min-seeds`（seeds 未知的行不参与）/ `--prefer` 可叠加；
- **没有缓存、没有序号**：磁力随 `--json` 给出，选中后 `a2-verify` 校验、`a2-dest check` 定落点、`a2 add` 下载。

## 2.5 `a2-verify` — 资源校验（技能层）

```
a2-verify <磁力|file.torrent> [--timeout S] [--json]
```

bt-metadata-only：临时往 aria2 加一个「只要元数据」的任务（占一个下载槽、落 `A2_VERIFY_DIR`），
从 DHT 拿真实元数据 → 解析出文件数与总大小 → 删任务、删产物。**退出码 0 = 可下，1 = 拿不到**；
`--json` 时 stdout 只有一行 JSON（`{"ok":…,"name":…,"bytes":…,"files":…,"has_extras":…}`），拿不到也照样输出。
`.torrent` 文件会先算出 info 段 sha1（原字节，不重编码）再当磁力校验。
RPC 复用 a2 主程序里的实现（同一个 conf/端口/密钥），所以没有第二份 RPC 客户端。

## 3. 任务查看


```
a2 ls          # 活动+等待（默认）；a2 ls -a 含已结束
a2 ls --name 片段   # 按任务名过滤（可叠加 -a，用来"找正在下/已下好的那个"）
a2 st          # 全局：下载/上传速率、活动/等待/已结束任务数
a2 info <gid>  # 单任务：状态/大小/速率/连接数/做种数/错误码/目录/文件
a2 files <gid> # 任务内文件列表（BT 显示种子内全部文件，含未选中的）
```

BT 任务 `files[0]` 可能是 RARBG.txt 之类小文件，`ls` 显示种子名而不是第一个文件（看 `bittorrent.info.name`）。

## 4. 任务控制

```
a2 pause [force] <gid|all>     # force = 立即中断当前分片
a2 resume <gid|all>
a2 rm <gid|all>                # 移除任务（不删已下文件；已结束的顺带清结果）
a2 purge                       # 清空已结束列表
```

## 4.5 改并发任务数（本次运行有效）

```
a2 concurrent      # 查当前 max-concurrent-downloads
a2 concurrent 5    # 改成 5（>=1 的整数）
```

持久化：改 conf 的 `max-concurrent-downloads` 后重启服务。

## 5. 限速（本次运行有效）

```
a2 up 1M     # 上传限速
a2 down 0    # 0 = 不限速
```

## 6. AList 网盘助手（`a2-ls` / `a2-alist` / `a2-alist-dir` / `a2-aliyun`）

前置：AList 服务在 `http://localhost:5244`；管理员密码读 `~/.alist/admin_password.txt`（没有则交互输入）；已挂载阿里云盘（AliyundriveOpen 驱动）。

| 命令 | 作用 |
|---|---|
| `a2-ls [路径]` | 列出目录/文件（默认 `/`），目录在前、文件带大小 |
| `a2-alist "路径" [输出目录]` | 单文件：AList 取直链 → `a2 add --dir 输出目录`（默认 `a2-dest`） |
| `a2-alist-dir "目录" [输出目录] [过滤]` | 目录批量：逐个取直链加入 a2（默认 `a2-dest`，过滤如 `*.mkv`） |
| `a2-aliyun "路径" [输出目录]` | 阿里云盘文件直链下载（密码同样读密码文件，不写死在脚本里） |

AList 本身的安装/阿里云盘接入见本技能 `references/install-guide.md`（安装）、`references/aliyun-driver.md`（阿里云盘驱动）、`references/alist-api.md`（API），脚本为 `scripts/install-alist.sh` 与 `scripts/setup-aliyun.sh`。

## 7. 环境变量（可覆盖默认行为）

| 变量 | 默认 | 作用 |
|---|---|---|
| `A2_SITES_CONF` | ~/.aria2/search-sites.conf | **a2-search** 的站点配置（a2 不读） |
| `A2_SEARCH_TIMEOUT` | 20 | 单次抓取超时（秒）；cmd 源上限是它的 3 倍 |
| `A2_SEARCH_PROXY` | 空 | 给抓取指定代理，如 `http://127.0.0.1:7897` |
| `A2_SEARCH_DEBUG` | 空 | 1=打印完整 cmd 源命令（可能含 token，谨慎） |
| `A2_VERIFY_TIMEOUT` | 90 | `a2-verify` 的元数据校验超时（秒） |
| `A2_VERIFY_DIR` | ~/.aria2/tor-cache | 校验任务临时目录（别指向媒体库目录） |
| `A2_RC` | ~/.aria2/a2.conf | a2 自己的配置文件 |
| `A2_CONF` | ~/.aria2/aria2.conf | aria2 配置（端口/密钥/下载目录的来源） |
| `A2_SERVICE` | a2.conf 的 `service=` | 服务名（launchd / systemd unit / Windows 计划任务；只影响提示信息） |
| `A2_SECRET` | conf 的 `rpc-secret` | RPC 密钥覆盖 |
| `A2_MIN_FREE_GB` | 20 | **a2-dest check** 的剩余空间阈值（0=不检查；a2 add 不再判断） |
| `A2_ALLOW_CREATE` | 空 | 1 = 允许 **a2-dest check** 把目录建在系统盘上 |
| `A2_DEST_CONF` | ~/.aria2/dest.conf | 落点配置文件（`a2-dest` 与启动器读；a2 不读） |
| `A2_MEDIA_ROOT` | `a2-dest media` | **仅 AList 助手脚本**的临时覆盖；常驻值请用 `a2-dest media set` |
| `A2_DOWNLOAD_DIR` | `a2-dest` | **仅 AList 助手脚本**的临时覆盖；常驻值请用 `a2-dest set` |
| `A2_ARIA2` | `command -v aria2c` | aria2c 可执行文件路径（服务管理器 PATH 里找不到时指定绝对路径） |
| `A2_FALLBACK_DIR` | 空 | 落点目录不可用时临时回退的下载目录（不设则拒绝启动） |

## 8. 与裸 RPC 的分工（a2 不覆盖才走 RPC）

a2 是"常用操作的封装"，以下能力它没暴露，需要 `scripts/aria2_cli.py` 或直接 curl（端口取 conf 的 `rpc-listen-port`）：
- `select-file`：整季包只下指定集（见 SKILL.md §5.3 完整示例）；
- `bt-metadata-only` + `bt-save-metadata`：定制元数据预校验（`a2-verify` 已封装一版）；
- `aria2.addTorrent` 传自定义 options；
- `aria2.changeGlobalOption`：限速之外的全局选项；
- 按需字段的 `tellStatus` / `getGlobalStat` / `getFiles`。
