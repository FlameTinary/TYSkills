# aria2-rpc

> 本技能是 [TYSkills](../../README.md) 技能集合的一部分：把本目录复制或软链到你的 agent 技能目录即可使用，
> 不需要安装器或账号。仓库级的技能列表与目录结构见主 README。

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

安装方式见仓库主 README 的「怎么用」——把 `skills/aria2-rpc/` 复制或软链到
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

## 免责声明

本技能为 aria2 的自动化封装与运维便利，**不包含、不内置、不推荐任何内容站点**。
搜索源由使用者自行配置，请遵守你所在地区的法律法规与版权规定，仅用于你有权下载的内容。
技能中的示例路径、主机名、服务名、令牌一律为占位符，不含作者机器的真实信息。

## License

MIT
