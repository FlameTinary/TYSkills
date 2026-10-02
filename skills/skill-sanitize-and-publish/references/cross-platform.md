# 三平台可移植性规则（macOS / Linux / Windows）

目标：技能**默认**在这三平台可用。做不到时，在正文里明确写「只在 X 上可用」或给出平台分支，
不要让读者在另一个平台上撞到 ImportError。

## 1. Python 脚本

| 别用 | 原因 | 换成 |
|---|---|---|
| `fcntl`、`pty`、`termios`、`pwd`、`grp`、`crypt`、`resource` | Windows 原生 Python 没有这些模块（`ImportError` 直接崩） | 平台分支：`try: import fcntl / except ImportError: import msvcrt`；或 `psutil`（可选依赖） |
| `os.fork`、`os.killpg`、`os.setsid`、`os.getuid`、`signal.SIGKILL` | POSIX 专有 | `subprocess` + `Popen.terminate()`/`kill()`；`psutil.pid_exists` 判活 |
| 裸 `os.kill(pid, 0)` 判活 | Windows 语义不同 | `psutil.pid_exists` 或 `Popen.poll()` |
| 硬编码 `/tmp` | Windows 无此目录 | `tempfile.gettempdir()` / `tempfile.mkstemp()` |
| `open(path)` 不写编码 | Windows 默认 cp936/GBK，中文日志乱码 | `open(path, encoding="utf-8", errors="replace")` |
| `print` 含 emoji/框线字符 | Windows 传统控制台（cp936）报 `UnicodeEncodeError` | 纯 ASCII 输出；或 `PYTHONIOENCODING=utf-8` + `chcp 65001` 并写明前提 |
| `shutil.rmtree` 无 `ignore_errors` 删只读文件 | Windows 只读属性会失败 | `onerror=` 回调里 `os.chmod(p, stat.S_IWRITE)` 后重试 |
| 路径字符串拼接 `dir + "/" + name` | 分隔符、盘符 | `os.path.join` / `pathlib.Path` |
| `os.rename` 跨盘移动 | Windows 报 `OSError`（跨设备） | `shutil.move` / `os.replace`（同盘原子） |
| `argparse` 位置参数用 `/path` 风格 | Windows 用户不习惯但可用 | 无碍，但文档写清两种写法 |
| `subprocess` 传字符串命令 | 各平台 shell 不同 | `subprocess.run([...], shell=False)`；命令查找用 `shutil.which` |
| 依赖 `shell=True` 的管道 | 引号/转义规则不同 | 改 Python 实现，或明确要求 bash（并声明平台） |
| `python` / `pip` 命令名 | 部分系统只有 `python3` / `py -3` | 用 `python3`；或 `sys.executable` |

版本底线写 Python 3.8+ 时：不要用 `match`、`X | Y` 类型联合（运行时求值）、
`dict[str, int]` 注解（3.9+），要注解就 `from __future__ import annotations`。

## 2. Shell 脚本

**首选：把逻辑放进 Python**，shell 只做几行编排。真要写 shell：

- `#!/usr/bin/env bash`（别写 `#!/bin/bash`，macOS 与 NixOS 上会是老版本/不存在）。
- **macOS 自带 bash 3.2**：没有 `${var,,}`、`${var^^}`、关联数组、`mapfile`、`&>>`。
  要数组就用 POSIX 位置参数，或直接换 Python。
- `.sh` 文件必须 **LF** 行尾（CRLF 会让 `#!/usr/bin/env bash\r` 找不到解释器）。
- `sed -i`：BSD 必须带备份后缀（`sed -i '' -e …`），GNU 不接受空后缀 → 用 Python 改写文本。
- `readlink -f` / `realpath`：老 macOS 无 `-f`；`stat` 参数两边不同（`-f` vs `-c`）。
- `date -d`（GNU）vs `date -r`（BSD）→ 在 Python 里算时间。
- `grep -P`、`sed -r`、`sort -V`、`cp --parents` 都是 GNU 专有 → 换 Python。
- `mktemp`、`mktemp -d` 通用；`mktemp -p` 不是。
- 别假设 `brew` 在服务的 PATH 里（launchd/systemd --user 的 PATH 很窄），用绝对路径兜底寻找工具。
- `set -eu` 仍然推荐；`pipefail` 不是 POSIX（bash/zsh 有，dash 没有）。

## 3. 路径与文件名

- `~` 展开是 **shell** 的功能，不是程序的：写进配置文件的值要自己 `expanduser`。
  （真实事故：`dir=~/Downloads` 被当成字面量目录名，在启动目录下创建了一个叫 `~` 的文件夹。）
- Windows 保留名：`CON PRN AUX NUL COM1..9 LPT1..9`；禁止字符 `<>:"/\|?*`；结尾不能是点或空格。
- 路径长度：传统 Win32 API 上限 260 字符，长路径要 `\\?\` 前缀（Python 3.6+ 在注册表开启后支持）。
- macOS/Windows 文件系统大小写不敏感（APFS 默认、NTFS 默认）→ 别用大小写区分两个文件名。
- 路径里有空格 → 所有地方都要引号；在配置模板里给出带引号的写法示例。
- 磁盘空间检查、稀疏文件支持、`fsync` 行为都与文件系统相关（HFS+ 不支持稀疏文件 → `falloc` 真写零）。

## 4. 服务与自启

| 平台 | 机制 | 关键点 |
|---|---|---|
| macOS | `~/Library/LaunchAgents/<label>.plist`（launchd） | `plutil -lint` 校验；`KeepAlive`；PATH 极窄，工具要绝对路径；崩溃重启 |
| Linux | `~/.config/systemd/user/<unit>.service`（systemd --user） | `Restart=always`、`WantedBy=default.target`；开机常驻要 `loginctl enable-linger <user>` |
| Windows | 任务计划程序（`schtasks /Create`）或 nssm | 触发条件「登录时/启动时」，失败重启；没有 daemon 语义 |

- 被服务管理器拉起的进程**不要 `--daemon`/自己 fork**，否则父进程退出会被反复拉起。
- 服务里的日志路径、工作目录、环境变量都要显式写（不要依赖用户 shell 的 profile）。
- 模板化服务定义：用 `__HOME__` / `__LABEL__` 占位，由安装脚本按平台渲染（不要提交渲染后的文件）。

## 5. 锁、并发、原子写

- 跨进程互斥：POSIX `fcntl.flock(fd, LOCK_EX|LOCK_NB)` ↔ Windows `msvcrt.locking(fd, LK_NBLCK, 1)`；
  两者都没有时退化为「不加锁 + 超时」并在文档里写明假设（单机单进程）。
- 原子替换文件：`os.replace()` 三平台都可用（同盘）。
- 别用「文件不存在」当完成判据（控制文件、`.part` 后缀都是不可靠信号），用返回值/状态查询。

## 6. 网络

- `localhost` 在 Windows 上可能先解析到 IPv6 `::1`：服务只监听 `127.0.0.1` 时会连接失败。
  要么监听两栈，要么统一写 `127.0.0.1`。
- 首次监听端口时 Windows 防火墙会弹窗；无人值守场景要用 HTTP/本机回环并写进文档。
- 代理：不要写死。做成配置项（`PROXY`），默认空=直连；读环境变量时注意各家变量名
  （`HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`/`NO_PROXY`，Windows 上大小写不一致）。

## 7. 编码与文本

- 所有自己写出的文件显式 `encoding="utf-8"`，行尾显式选择（`newline="\n"` 生成跨平台文本）。
- 发布文本文件用 LF；`.gitattributes` 里给 `*.sh text eol=lf`、`*.py text eol=lf` 加保障。
- 不要在 SKILL.md 前加 BOM（会顶掉 frontmatter 的 `---`）。

## 8. 验证矩阵（能测就测，不能测就写清楚）

| 检查 | 怎么做 |
|---|---|
| Python 语法与导入 | `python3 -m py_compile *.py`；在 Windows 上装一次 Windows Python 跑 `import` |
| shell 语法 | `bash -n script.sh`；macOS 上额外用 bash 3.2（`/bin/bash`）过一遍 |
| 路径/占位 | 把配置指向一个带空格的中文目录名再跑一次 |
| 干净环境 | 删掉配置文件跑一次：应给出「去哪配」的可读报错，而不是崩栈 |
| 服务定义 | macOS `plutil -lint`；Linux `systemd-analyze --user verify`；Windows 用 `schtasks /Query` 复核 |
| 无法覆盖的平台 | 在 SKILL.md 里写明「未在 X 上验证/仅支持 WSL」，不要假装三平台都验过 |
