# 排错与「用血换来的事实」

这些坑都是实测踩出来的，按主题分组。**每条都给了判据与处置**，别凭"看起来像"下结论。
极少数与某个平台强绑定的经验会明确标注（macOS 备注 / Linux 备注）。
先做 3 秒健康检查：`a2 st`（RPC 是否活着）、服务是否在跑（macOS `launchctl list | grep aria2`，
Linux `systemctl --user status <服务名>`，Windows `schtasks /Query /TN "<服务名>" /V`）、`a2 ls`（任务是否还在）。

## 1. 路径与配置键（启动即失败）

| 现象 | 原因 / 处置 |
|---|---|
| 进程启动后立刻退出 1，日志里 `Exception: [Logger.cc:73] 打开文件 … 失败` 或 `download_helper.cc:563 … aria2.session 失败` | `log` / `dir` / `input-file` 指向的路径不存在。**这些是致命错误不是警告**：先把文件/目录建出来（`install-a2.sh` 会 `touch` 空 `aria2.session`、`aria2.log`） |
| 下载落到了奇怪的 `~/` 目录 | **aria2 不展开 `~`**（实测）：`dir=~/Downloads` 会创建一个字面量 `~/` 目录（相对守护进程的 cwd）。conf 里一律写绝对路径（模板用 `__HOME__` 占位，安装脚本替换） |
| `[WARN] Unknown option: bt-listen-port` | 1.37 没有这个选项：BT 端口是 `listen-port`，DHT 是 `dht-listen-port`。写了未知键只会 WARN 然后被无视 —— 手写 conf 前先核对：`aria2c --help=#all \| grep -oE '\-\-[a-z0-9-]+' \| sed 's/^--//' \| sort -u` 与 conf 的键做 diff |
| 手工跑 `aria2c <url> --dir <某处>` 秒退，什么都没下 | 裸 `aria2c` 会自动读 `~/.aria2/aria2.conf`，而 RPC 端口已被守护进程占着 → `IPv4 RPC: failed to bind TCP port` → exit 1；你那行的 `--dir` 根本没生效（后来出现的下载其实是守护进程按 conf 下的）。要用 `a2 add`，或 `--no-conf` + 另一个 `--rpc-listen-port` |
| `rpc-secret` 会不会被别人读到 | conf 里是明文密钥：`chmod 600 ~/.aria2/aria2.conf`（install-a2.sh 已做；Windows 上注意 `%USERPROFILE%\.aria2\aria2.conf` 的 ACL，别放在共享目录） |

## 2. 守护进程与服务管理（launchd / systemd / 计划任务）

- **「自动拉起」+ `--daemon=true` = 重启循环**：daemon 化会 fork 后退出，服务管理器（macOS `KeepAlive`、
  Linux `Restart=always`）看到进程没了就反复拉起。必须前台跑（`--daemon=false`）
- 查/重启/停止：
  - macOS：`launchctl print gui/$(id -u)/<服务名>` / `launchctl kickstart -k gui/$(id -u)/<服务名>` / `launchctl bootout gui/$(id -u)/<服务名>`
  - Linux：`systemctl --user status|restart|stop <服务名>`，日志 `journalctl --user -u <服务名> -f`
    （服务器上没登录也要常驻：`loginctl enable-linger $USER`）
  - Windows：计划任务 `schtasks /Query /End /Run /TN "<服务名>"`，或用 nssm 包成服务后在「服务」里管理
- **重启守护后的 5–10 分钟里 RPC 可能时通时断**：进程在重新校验/保存几十 GB 的种子（磁盘满速、进程处于 `U` 状态），
  `aria2.getGlobalStat` 会先应答、然后超时几分钟、再自己恢复。**别再 kill**——处于不可中断 I/O 的进程也杀不掉。
  重启前先 `aria2.saveSession`，任务的进度不会丢
- **RPC 端口被占、服务显示反复失败（macOS `last exit code = 1`）**：上一个进程卡在 `fsync`（磁盘回写），
  它还占着端口，每次拉起都 `failed to bind TCP port`。要么等回写排空（macOS `iostat -d diskN` / Linux `iostat`、`iotop` 观察），
  要么临时改 `rpc-listen-port` 先把服务救回来
- 在受限环境里（某些 agent / CI 网关）`launchctl bootstrap`、`systemctl --user` 可能被拦住 —— 这种情况把命令交给用户在自己的终端跑

## 3. 完成判据、控制文件与会话

1. **永远不要用「有没有 `<条目>.aria2` 控制文件」判断是否下完**。conf 的 `force-save=true`
   让已完成的控制文件**永久残留**，而且完成时 aria2 的顺序是「下载完成 → 保存片段文件 → 执行 on-download-complete」，
   所以钩子被调用时控制文件一定还在。判据只能是 RPC：`completedLength == totalLength > 0`
   （`on-complete.py` / `a2 sweep` 就是这么做的）
2. 完成的任务在 `force-save=true` 下**还会被写回 session**：入库之后要 `aria2.removeDownloadResult` + `saveSession`，
   否则下次重启把已经入库的几十 GB 再下一遍
3. **清空 session 后又"回来"了**：正在退出的守护进程会在你截断之后又保存一次。顺序是
   `aria2.purgeDownloadResult` + `aria2.saveSession` + 重新读文件确认（`wc -c` 与 `a2 ls -a` 各看一次）
4. **不要在下任务运行时 `rm` 它的 `.aria2` 控制文件**：日志会出现
   `DefaultBtProgressInfoFile.cc … Failed to write into the segment file …`。正确顺序是 `a2 rm <gid>` → `a2 purge` → 再删文件

## 4. 磁盘、文件系统与假死

- **不支持稀疏文件的外接盘要把 `file-allocation` 设成 `none`**（macOS 备注：HFS+ 就不支持稀疏文件）：
  这类盘上 `falloc` 会真的把 100 GB 写满零，外接硬盘持续满速写很久（表现为"盘凭空少了 100 GB"）。
  APFS / ext4 / XFS / NTFS 上 `falloc` 才是真分配
- **磁盘写满会把 aria2 卡死在内核 fsync 上**（macOS 用 `sample <pid> 3` 看，Linux 用 `gdb -p <pid>` 或看
  `D` 状态）能看到卡在 `MultiDiskAdaptor::flushOSBuffers`/`fsync`，日志里常有
  `FileAllocationCommand.cc … F_PREALLOCATE … No space left on device`。
  这种进程不可中断（杀不掉）又占着 RPC 端口 → 服务管理器反复 respawn，全部 `failed to bind port`。
  处置：先腾空间，再 `: > ~/.aria2/aria2.session`，最后重启服务
- 另一处假死是 `pause` 撞在 ~97% 上，卡在 `DefaultBtProgressInfoFile::save()` 的 `rename()`
- 预防：`file-allocation=none`、`enable-mmap=false`（mmap 脏页回写会拖长 fsync）、`auto-save-interval=300`、别把盘写满（见下）
- **默认的空间保护**：`a2 add` 在目标盘剩余 < `A2_MIN_FREE_GB`（默认 20 GB）时拒绝加任务，
  并在路由提示里给出剩余空间；临时放宽 `A2_MIN_FREE_GB=5 a2 add …`
- 外接盘上文件"虚大"是正常的（高位分片零填充），**真实进度看 RPC 的 `completedLength`**，别看 `ls` 的大小
- macOS 备注：想在线检查媒体盘又不想停正在播的服务，`diskutil verifyVolume <挂载点>` 可以**在线**做
  （它会退回 `fsck_hfs -fn -l -x`）；要停别的 launchd 服务得 `launchctl bootout` 那个 job，`pkill` 只会被 respawn
  （Linux 上对应做法：`umount` 前先 `fuser -m`/`lsof` 确认没有进程占用）

## 5. 日志

- `log-level=info` 会**每 peer 每 piece 写一行**：实测把内部盘吃掉 23.7 GB，而且大到 `grep` 看起来像卡住。
  aria2 不自带轮转 —— 保持 `log-level=warn`，`console-log-level=warn`
- 需要排查时临时改 `info` 再重启服务；查完改回 **并** 重启（截断日志本身立刻生效，改等级必须重启）
- 截断一个正在写的文件是安全的（fd 是 append 模式）
- Linux 上 unit 日志单独存在 journal 里：`journalctl --user -u <服务名>`；Windows 计划任务看不到 stdout 时，
  用 `--log=/绝对路径/aria2.log` 落文件最省事

## 6. BT / 磁力

| 现象 | 原因 / 处置 |
|---|---|
| 任务自己停了，RPC 显示 `errorCode=7`（未完成的下载），进度冻在 0 B/s | `bt-stop-timeout` 把它掐了。300 秒对公共 tracker 太激进（实测一个 100 GB 的包在 13 MB 处被停）。**保持 `bt-stop-timeout=0`**，让卡住的任务自己挂着，用 `a2 pause` / `a2 rm` 手动处理 |
| 空闲时 `lsof` 看不到 BT 监听端口 | BT 端口是**懒绑定**的，有任务时才出现（Windows 用 `netstat -ano \| findstr <端口>`）。不要因此"修"配置 |
| `seed-time=0` 与 `seed-ratio` | 设了 `seed-time` 后，到时间或到比率**任一**满足就停止做种（man 页），所以 `seed-ratio` 基本是死配置。不想做种就 `seed-time=0` |
| 上传占满上行 | 保留 `max-overall-upload-limit`（模板给 2M）。它是全局选项，也能运行时改：`aria2.changeGlobalOption {"max-overall-upload-limit":"2M"}` |
| 冷门资源一直 0 速度 | 公共 BT 的正常现象，`bt-stop-timeout=0` 时不会自停。用 `a2 grab` 的元数据校验判断"到底有没有人在做种" |

## 7. 入库与媒体库

- **完成判据只信 RPC**（见 §3.1）。钩子 `on-complete.py` 只有在任务目录位于 `<媒体库根>/.incoming/` 下才动作，
  普通下载静默跳过
- **ffprobe 守卫**：入库前会用 ffprobe 解析条目里最大的视频文件，解析不了（如 `moov atom not found` 的截断 mp4）
  就留在暂存区不动。**服务管理器拉起的进程 PATH 很窄**（macOS launchd 里没有 Homebrew，Linux systemd --user
  里通常没有 `/usr/local/bin`，Windows 计划任务里更是空的）—— 脚本在 PATH 之外还会去常见安装位置兜底找
  ffprobe；只用 `shutil.which` 会静默关掉整个校验
- **并发**：两个任务同一秒完成会让 aria2 并发调两次钩子，靠 `flock ~/.aria2/move.lock` 串行化；
  日志里出现"另一个钩子实例还在忙"是正常跳过。（Windows 上 `flock` 不可用时钩子会退化为单实例串行，仍是安全的）
- **文件没入库**：先 `a2 sweep`（它用同一套 RPC 判据 + ffprobe 守卫）；看 `~/.aria2/move.log`；
  条目既不在"活动/等待"也不在"已结束"列表（结果被清/守护重启过）时，宁可留着让人看一眼，也不要猜
- **文件名清洗** `nameclean.py`：入库时去掉站点广告（网址、`【…发布…】`、`地址发布页` 之类），
  绝不动 `SxxExx` / `第N季` / 年份 / `1080p` / `x265` 这些刮削要用的信息；目录内部也洗（最多两层）
- 媒体库根由 `A2_MEDIA_ROOT`（默认 `~/media`；Windows 上可写 `D:\media`）决定，含 `Movies` / `TV` / `Private`
  三个子目录；下载先落 `A2_MEDIA_ROOT/.incoming/{Movies,TV,Private,_unsorted}`

## 8. RPC 与 a2 本身

- **aria2 用 HTTP 400 + JSON 体表达 RPC 错误**：只捕获通用异常会得到没有信息量的
  `HTTP Error 400: Bad Request`，正确做法是读 `HTTPError.read()` 里的 `error.message`
  （`scripts/aria2_cli.py` 与 `a2` 都已处理）
- `a2` 的端口/密钥来自 `~/.aria2/aria2.conf`（`rpc-listen-port` / `rpc-secret`），所以不用手动传；
  要临时覆盖用 `A2_SECRET`，要指向另一份配置用 `A2_CONF`
- `a2` 的专有配置（`find` 的搜索源、服务名）在 `~/.aria2/a2.conf`，**不要写进 aria2.conf**
  （aria2 会为未知键打 `[WARN] Unknown option` 刷屏）
- 服务名默认 `com.example.aria2`：安装时用 `A2_SERVICE=a2.<你的名字> bash scripts/install-a2.sh` 换掉；
  `a2.conf` 里的 `service=` 保持同一个名字，a2 报错时给的提示命令才是对的
  （Windows 计划任务名可以不带点，例如 `a2`）
