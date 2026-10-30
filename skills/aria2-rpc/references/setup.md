# a2 搭建与运维

平台：**macOS、Linux、Windows（WSL / Git Bash）** 都支持。Python 脚本三平台通用；
`*.sh` 需要 POSIX shell（Windows 原生请用 WSL，或 Git Bash + 计划任务）。

## 1. 依赖

| 依赖 | 用途 | macOS | Debian/Ubuntu | Fedora/Arch | Windows |
|---|---|---|---|---|---|
| aria2c | 下载引擎 | `brew install aria2` | `sudo apt install aria2` | `sudo dnf install aria2` / `sudo pacman -S aria2` | `winget install aria2.aria2` / `scoop install aria2` |
| python3 | a2 / a2-dest / a2-search / 搜索源脚本 | `brew install python3`（系统自带也可） | `sudo apt install python3` | `sudo dnf install python3` | WSL 自带；原生用 python.org 安装包 |
| curl | AList 助手、RPC 探活 | 系统自带 | `sudo apt install curl` | `sudo dnf install curl` | 系统自带（Win10+） |
| ffprobe (ffmpeg) | 可选：自己校验文件完整性（a2 不再调用） | `brew install ffmpeg` | `sudo apt install ffmpeg` | `sudo dnf install ffmpeg` | `winget install ffmpeg` / `scoop install ffmpeg` |
| AList + 云盘 | 网盘直链下载（可选） | 见 §5 | 同 | 同 | 同 |

搜索不需要额外依赖：站点配置见 `references/search-sites.md`（HTML 模式直接抓页面，cmd 模式是你的脚本）。

## 2. 一键部署（推荐）

```bash
bash scripts/install-a2.sh
# 换服务名（默认 com.example.aria2）：
A2_SERVICE=a2.你的名字 bash scripts/install-a2.sh
```

脚本幂等，重复运行安全，**绝不覆盖**已有 `aria2.conf`、`a2.conf` 与服务定义。做的事：

1. 依赖检查（aria2c/python3/curl），缺失时按平台给安装命令；
2. 建 `~/.aria2`，touch 空 `aria2.session` / `aria2.log`（session 文件不存在 aria2 会直接退出）；
3. 安装核心脚本：`a2`、`start-aria2.sh` → `~/.aria2/`，`a2-dest` / `a2-search` / `a2-verify` → `~/.local/bin`；
4. 首次运行 `a2-dest`：按当前 OS 生成默认下载目录并写入 `~/.aria2/dest.conf`（已存在则沿用，不覆盖用户改过的值）；
5. `~/.local/bin/a2` 软链到 `~/.aria2/a2`；AList 四件套复制到 `~/.local/bin`（不在 PATH 会给出提示）；
6. 搜索源脚本 `search-source-demo.py` / `search-source-template.py` → `~/.aria2/`，并生成 `search-sites.conf`（不覆盖已有的）；
7. 无 `aria2.conf` 时用模板生成（随机 `rpc-secret`，`__HOME__` 替换成实际家目录），并 `chmod 600`；
8. 无 `a2.conf` 时用模板生成（a2 专有配置：服务名）；
9. **按平台装服务**：macOS → launchd（`~/Library/LaunchAgents/<服务名>.plist`）并启动；
   Linux → systemd 用户服务（`~/.config/systemd/user/<服务名>.service`）`enable --now`；
   Windows → 打印计划任务 / nssm 的等价命令，可手动前台启动。最后验证 `a2 st`。

## 3. 手动部署（不跑安装脚本时）

```bash
# 三平台通用部分
mkdir -p ~/.aria2 ~/.local/bin
touch ~/.aria2/aria2.session ~/.aria2/aria2.log
cp scripts/a2 scripts/start-aria2.sh ~/.aria2/
cp scripts/a2-dest ~/.local/bin/ && chmod 755 ~/.local/bin/a2-dest
a2-dest >/dev/null            # 首次运行：按 OS 生成默认下载目录并持久化
cp scripts/search-source-demo.py scripts/search-source-template.py ~/.aria2/
# 搜索站点：assets/search-sites.conf.template → ~/.aria2/search-sites.conf（替换 __HOME__，然后填 site= 行）
ln -sf ~/.aria2/a2 ~/.local/bin/a2
# aria2.conf：assets/aria2.conf.template → ~/.aria2/aria2.conf，替换 __HOME__ 与 __RPC_SECRET__，然后 chmod 600
# a2.conf   ：assets/a2.conf.template      → ~/.aria2/a2.conf，  替换 __HOME__ 与 __LABEL__
```

服务定义按平台二选一（模板里的 `__HOME__` / `__LABEL__` 都要替换）：

```bash
# --- macOS（launchd 用户服务）---
sed -e "s|__LABEL__|<你的服务名>|g" -e "s|__HOME__|$HOME|g" \
    assets/com.example.aria2.plist.template > ~/Library/LaunchAgents/<你的服务名>.plist
plutil -lint ~/Library/LaunchAgents/<你的服务名>.plist      # 先校验 XML
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<你的服务名>.plist

# --- Linux（systemd 用户服务）---
mkdir -p ~/.config/systemd/user
sed -e "s|__LABEL__|<你的服务名>|g" -e "s|__HOME__|$HOME|g" \
    assets/a2.service.template > ~/.config/systemd/user/<你的服务名>.service
systemctl --user daemon-reload && systemctl --user enable --now <你的服务名>
loginctl enable-linger "$USER"        # 可选：没登录也让它常驻

# --- Windows ---
# A) 计划任务（登录自启）：
#    schtasks /Create /TN "<服务名>" /SC ONLOGON /TR "wsl.exe -e sh -lc \"~/.aria2/start-aria2.sh --daemon=false\""
# B) nssm 包成服务：nssm install <服务名> <aria2c.exe 路径> --conf-path=%USERPROFILE%\.aria2\aria2.conf
```

两个配置文件的分工：**aria2.conf** 只放 aria2 认识的键（端口、密钥、目录、BT 参数）；
**a2.conf** 放 a2 专有配置（目前只有服务名）——写进 aria2.conf 只会换来每次启动的 `[WARN] Unknown option` 刷屏；
搜索站点在 `search-sites.conf`，落点在 `dest.conf`，两者 a2 都不读。

## 4. 落点与空间保护

落点是**显式**的：`a2 add --dir DIR`，a2 不改名、不搬动、不建暂存区。

```
a2-dest            # 默认下载目录（首次按 OS 生成：macOS ~/Downloads、Linux XDG、Windows %USERPROFILE%\Downloads）
a2-dest set DIR    # 改默认（持久化到 ~/.aria2/dest.conf）
a2-dest media      # 媒体库根（未设置 = 默认下载目录）
```

- 「电影 / 剧集 / 私藏」这类子目录由**技能**拼：`$(a2-dest media)/Movies`、`/TV`、`/Private`（需要就 `mkdir -p`）；
- 落点可以放在**任何**盘上：内置盘、外接盘、网络盘、Windows 的 `D:\media`、Linux 的 `/mnt/xxx/media` 都行；
- `a2-dest check DIR` 与启动器用同一条跨平台判据检查目标目录：**家目录内**、**落在别的盘上**都放行；
  只有「既不在家目录内、又会落在系统盘上」才拒绝（外接盘/网络盘没挂载时挂载点目录会凭空消失）。
  确认就要那个位置：先 `mkdir -p`，或设 `A2_ALLOW_CREATE=1`；
- `A2_MIN_FREE_GB`（默认 20）是 `a2-dest check` 的余量阈值，不足直接拒绝（`0`＝不检查）。
  `a2 add` 只要求目录已存在，不再做这两项判断。

## 5. AList 接入（可选，网盘下载用）

完整指南分三份：`references/install-guide.md`（AList 安装）、`references/aliyun-driver.md`（云盘驱动）、`references/alist-api.md`（AList API）。

1. 安装：`bash scripts/install-alist.sh`（AList 到 `~/.local/bin/alist`，数据 `~/.alist`，密码存 `~/.alist/admin_password.txt`，
   建议 `chmod 600`）；启动 `~/.alist/start-alist.sh`；验证 `curl http://localhost:5244` 返回 200。
2. 云盘（以阿里云盘为例）：在 https://alist.nn.ci/tool/aliyundrive/request.html 扫码拿 refresh_token，
   然后 `bash scripts/setup-aliyun.sh "<refresh_token>"`；或 Web UI 手动加存储（驱动 **AliyundriveOpen**、
   挂载 `/aliyun`、根文件夹 root；勿用旧版 Aliyundrive 驱动）。
3. `a2-ls /aliyun` 能列出即就绪；存储状态应显示 **work**。
4. refresh_token 失效表现为 `failed to refresh token`，重新扫码后重存（AList 会自动续期）。
5. 助手脚本的密码统一从 `~/.alist/admin_password.txt` 读（没有文件则交互输入）——
   **不要把密码写进脚本或命令行**，命令行参数会出现在 `ps` 输出里。

## 6. 搜索站点配置（a2-search 用）

```bash
# ~/.aria2/search-sites.conf（模板 assets/search-sites.conf.template）
site=某站|https://example.org/search?q={query}&page={page}   # HTML 结果页，自动抽 magnet
site=本地演示|cmd:python3 ~/.aria2/search-source-demo.py      # 离线自测（不联网，先跑通流程）
websearch=https://www.bing.com/search?q={query}               # 全网发现（--discover）
```

`a2-search sites` 看已配置的源；`a2-search <关键词>` 搜；`a2-search --discover <关键词>` 只列结果页链接。
契约、字段表、示例脚本、排查：`references/search-sites.md`。
没配站点时 `a2-search` 会打印配置步骤并非零退出 —— 不会假装"没有结果"。

## 7. 守护进程与服务管理

服务名默认 `com.example.aria2`（安装时用 `A2_SERVICE` 换）。三平台的共同要点：

- **必须走 `start-aria2.sh`**：它校验落点目录是否可用（不存在且会被建到系统盘上就拒绝启动），
  目录取自 `~/.aria2/dest.conf` 的 `download-dir` / `media-root`（`a2-dest` 维护）。
  终端 / 服务管理器 / cron 都走它，行为才一致。
- **必须前台运行**（`--daemon=false`）：daemon 化会 fork 后退出，服务管理器会当成崩溃无限重启。
- 崩溃自动拉起：macOS `KeepAlive=true`（`ThrottleInterval` ≥ 10 秒）；Linux `Restart=always` + `RestartSec=10`；
  Windows 计划任务可设「失败后重启」。

```bash
# macOS
launchctl print gui/$(id -u)/<服务名>            # 查状态
launchctl kickstart -k gui/$(id -u)/<服务名>     # 重启（改 conf/脚本后用它）
launchctl bootout  gui/$(id -u)/<服务名>         # 停止并卸载

# Linux
systemctl --user status <服务名>                 # 查状态
systemctl --user restart <服务名>                # 重启
systemctl --user stop <服务名>                   # 停止
journalctl --user -u <服务名> -f                 # 看 unit 日志

# Windows（计划任务）
schtasks /Query /TN "<服务名>" /V                # 查状态
schtasks /End /TN "<服务名>" && schtasks /Run /TN "<服务名>"   # 重启
```

日志：macOS `~/.aria2/launchd.out.log` / `launchd.err.log`；Linux `journalctl --user -u <服务名>`；
三平台都有 `~/.aria2/aria2.log`。
重启守护后头几分钟 RPC 可能时断时续（进程在重新校验/保存大任务）——**别反复 kill**，见 `references/troubleshooting.md` §2。

## 8. 维护要点

- **tracker 列表**：conf 里的 `bt-tracker` 建议定期从公开 trackerslist 项目更新 best trackers，改后重启服务
- **日志**：平时 `log-level=warn`；排查时临时 `info` 并重启，查完改回 —— `info` 会按 peer×piece 写，实测涨到 23.7 GB
- **session**：`aria2.session` 每 30s 保存；`a2 rm` 后会自动 `saveSession`；完成的任务要 `removeDownloadResult`，否则重启会重下
- **空间**：不是所有文件系统都支持稀疏文件（典型是 macOS 的 HFS+、部分网络文件系统），"表面大小"会提前撑满；
  真实进度以 RPC `completedLength` 为准
- **完成判据**：永远用 RPC（`completedLength == totalLength`），不要看 `.aria2` 控制文件在不在
- **改动生效**：conf/脚本改完必须重启服务（见 §7）；`a2 up/down` 的限速只对本次运行有效

## 9. 故障排查

完整表（路径、服务管理、fsync 假死、日志、BT、落点、RPC 各主题）见 **`references/troubleshooting.md`**。
先记这四条：

| 现象 | 处理 |
|---|---|
| `a2` 报 RPC 不可用 | 确认守护在跑（macOS `launchctl print gui/$(id -u)/<服务名>`；Linux `systemctl --user status <服务名>`；Windows `schtasks /Query /TN "<服务名>" /V`），再核对 conf 的 `rpc-listen-port` |
| `a2-dest check` 报落点不可用 | 外接盘/网络盘没挂载；挂载后重试，或 `A2_ALLOW_CREATE=1`（确实要放系统盘时） |
| `a2-dest check` 报剩余不足 | `A2_MIN_FREE_GB=5 a2-dest check …` 临时放宽，或清理磁盘 |
| `a2 add` 报「缺少目标目录/目录不存在」 | 先 `a2-dest check <目录>`（会建目录并检查），再把返回的路径给 `--dir` |
