# a2 搭建与运维

平台：**macOS、Linux、Windows（WSL / Git Bash）** 都支持。Python 脚本三平台通用；
`*.sh` 需要 POSIX shell（Windows 原生请用 WSL，或 Git Bash + 计划任务）。

## 1. 依赖

| 依赖 | 用途 | macOS | Debian/Ubuntu | Fedora/Arch | Windows |
|---|---|---|---|---|---|
| aria2c | 下载引擎 | `brew install aria2` | `sudo apt install aria2` | `sudo dnf install aria2` / `sudo pacman -S aria2` | `winget install aria2.aria2` / `scoop install aria2` |
| python3 | a2 / 钩子 / 清洗 / 搜索源脚本 | `brew install python3`（系统自带也可） | `sudo apt install python3` | `sudo dnf install python3` | WSL 自带；原生用 python.org 安装包 |
| curl | AList 助手、RPC 探活 | 系统自带 | `sudo apt install curl` | `sudo dnf install curl` | 系统自带（Win10+） |
| ffprobe (ffmpeg) | 入库前完整性校验（强烈建议） | `brew install ffmpeg` | `sudo apt install ffmpeg` | `sudo dnf install ffmpeg` | `winget install ffmpeg` / `scoop install ffmpeg` |
| AList + 云盘 | 网盘直链下载（可选） | 见 §5 | 同 | 同 | 同 |

搜索源不需要额外依赖：源是你自己的脚本/命令，见 `references/tor-source.md`。

## 2. 一键部署（推荐）

```bash
bash scripts/install-a2.sh
# 换服务名（默认 com.example.aria2）：
A2_SERVICE=a2.你的名字 bash scripts/install-a2.sh
```

脚本幂等，重复运行安全，**绝不覆盖**已有 `aria2.conf`、`a2.conf` 与服务定义。做的事：

1. 依赖检查（aria2c/python3/curl；ffprobe 缺失仅警告），缺失时按平台给安装命令；
2. 建 `~/.aria2`，touch 空 `aria2.session` / `aria2.log` / `move.log` / `move.lock`（session 文件不存在 aria2 会直接退出）；
3. 建媒体库目录 `$A2_MEDIA_ROOT/{Movies,TV,Private,.incoming/…}` —— 但如果该路径会被创建到系统盘上
   （外接盘/网络盘没挂载时的典型表现）就跳过并提示，避免误在系统盘上铺一套目录；
4. 安装核心脚本：`a2`、`nameclean.py`、`on-complete.py`、`start-aria2.sh` → `~/.aria2/`；
5. `~/.local/bin/a2` 软链到 `~/.aria2/a2`；AList 四件套复制到 `~/.local/bin`（不在 PATH 会给出提示）；
6. 搜索源脚本 `tor-source-demo.py` / `tor-source-template.py` → `~/.aria2/`；
7. 无 `aria2.conf` 时用模板生成（随机 `rpc-secret`，`__HOME__` 替换成实际家目录），并 `chmod 600`；
8. 无 `a2.conf` 时用模板生成（a2 专有配置：搜索源、服务名）；
9. **按平台装服务**：macOS → launchd（`~/Library/LaunchAgents/<服务名>.plist`）并启动；
   Linux → systemd 用户服务（`~/.config/systemd/user/<服务名>.service`）`enable --now`；
   Windows → 打印计划任务 / nssm 的等价命令，可手动前台启动。最后验证 `a2 st`。

## 3. 手动部署（不跑安装脚本时）

```bash
# 三平台通用部分
mkdir -p ~/.aria2 ~/.local/bin
touch ~/.aria2/aria2.session ~/.aria2/aria2.log ~/.aria2/move.log ~/.aria2/move.lock
cp scripts/a2 scripts/nameclean.py scripts/on-complete.py scripts/start-aria2.sh ~/.aria2/
cp scripts/tor-source-demo.py scripts/tor-source-template.py ~/.aria2/
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
**a2.conf** 放 a2 专有配置（搜索源、服务名）——写进 aria2.conf 只会换来每次启动的 `[WARN] Unknown option` 刷屏。

## 4. 媒体落点与空间保护

```
${A2_MEDIA_ROOT}/{Movies,TV,Private}                        # 媒体库根（默认 ~/media）
${A2_MEDIA_ROOT}/.incoming/{Movies,TV,Private,_unsorted}    # 下载中的暂存区（隐藏目录）
aria2.conf 的 dir（默认 ~/Downloads）                        # 普通文件（zip/pdf/…）与 -flat 的落点
```

- `a2 add` 按名字把任务路由进暂存子目录，完成后 `on-complete.py` 搬进对应库目录并清名；
- 媒体库可以放在**任何**盘上：内置盘、外接盘、网络盘、Windows 的 `D:\media`、Linux 的 `/mnt/xxx/media` 都行；
- 启动器与 `a2 add` 会用同一条跨平台判据检查目标目录：**家目录内**、**落在别的盘上**都放行；
  只有「既不在家目录内、又会落在系统盘上」才拒绝（外接盘/网络盘没挂载时挂载点目录会凭空消失）。
  确认就要那个位置：先 `mkdir -p`，或设 `A2_ALLOW_CREATE=1`；
- `A2_MIN_FREE_GB`（默认 20）是目标盘最低余量，不足直接拒绝加任务。

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

## 6. 搜索源配置（a2 find 用）

```bash
# ~/.aria2/a2.conf 里一行：
tor-source-cmd=python3 ~/.aria2/tor-source-demo.py      # 离线自测（不联网，先跑通流程）
```

契约、字段表、示例脚本、排查：`references/tor-source.md`。
没配之前 `a2 find` 会打印配置步骤并以非零码退出 —— 不会假装"没有结果"。

## 7. 守护进程与服务管理

服务名默认 `com.example.aria2`（安装时用 `A2_SERVICE` 换）。三平台的共同要点：

- **必须走 `start-aria2.sh`**：它校验媒体库目录是否可用（不存在且会被建到系统盘上就拒绝启动），
  媒体库根与默认下载目录分别由 `A2_MEDIA_ROOT`（默认 `~/media`）与 `A2_DOWNLOAD_DIR`（默认 `~/Downloads`）配置。
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
三平台都有 `~/.aria2/aria2.log` 与 `~/.aria2/move.log`。
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

完整表（路径、服务管理、fsync 假死、日志、BT、入库、RPC 各主题）见 **`references/troubleshooting.md`**。
先记这四条：

| 现象 | 处理 |
|---|---|
| `a2` 报 RPC 不可用 | 确认守护在跑（macOS `launchctl print gui/$(id -u)/<服务名>`；Linux `systemctl --user status <服务名>`；Windows `schtasks /Query /TN "<服务名>" /V`），再核对 conf 的 `rpc-listen-port` |
| 加任务被拒：媒体库/目标目录不可用 | 外接盘/网络盘没挂载；挂载后重试，或 `A2_ALLOW_CREATE=1`（确实要放系统盘时） |
| 加任务被拒：目标盘剩余不足 | `A2_MIN_FREE_GB=5 a2 add …` 临时放宽，或清理磁盘 |
| `.incoming` 里文件不入库 | 完成判据是 RPC 不是控制文件；`a2 sweep` 手动收尾；看 `~/.aria2/move.log` |
