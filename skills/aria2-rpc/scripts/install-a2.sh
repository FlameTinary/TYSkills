#!/usr/bin/env bash
# =============================================================
# a2（aria2 高级封装）一键部署脚本 —— macOS / Linux / Windows(WSL、Git Bash)
# 幂等：重复运行安全；已有配置（aria2.conf、a2.conf、服务定义）一律不覆盖。
# 用法: bash scripts/install-a2.sh
# 依赖: aria2c、python3、curl
# 服务名: 默认 com.example.aria2（macOS 服务名 / Linux systemd unit 名 / Windows 计划任务名），
#         用 A2_SERVICE=a2.aria2 之类换成自己的
# 平台适配：
#   macOS  → 安装 launchd 用户服务（~/Library/LaunchAgents/<服务名>.plist）并启动
#   Linux  → 安装 systemd 用户服务（~/.config/systemd/user/<服务名>.service）并 enable --now
#   Windows(Git Bash/MSYS) → 不自动装服务，打印计划任务/nssm 的等价命令，可手动前台启动
# =============================================================
set -eu

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"     # 技能根目录
ARIA2_DIR="$HOME/.aria2"
BIN_DIR="$HOME/.local/bin"
SERVICE="${A2_SERVICE:-com.example.aria2}"

case "$(uname -s 2>/dev/null || echo unknown)" in
  Darwin)                         PLAT=mac ;;
  Linux)                          PLAT=linux ;;
  MINGW*|MSYS*|CYGWIN*|Windows*)  PLAT=windows ;;
  *)                              PLAT=other ;;
esac

echo "== a2 一键部署（平台: ${PLAT}，技能目录: ${SKILL_DIR}，服务名: ${SERVICE}）"

# ---------- 0) 依赖检查（按平台给安装命令） ----------
missing=""
for c in aria2c python3 curl; do
  command -v "$c" >/dev/null 2>&1 || missing="$missing $c"
done
if [ -n "$missing" ]; then
  echo "缺少依赖:$missing —— 安装方式：" >&2
  case "$PLAT" in
    mac)     echo "  macOS:  brew install aria2 python3   (curl 系统自带)" >&2 ;;
    linux)   echo "  Debian/Ubuntu:  sudo apt install aria2 python3 curl" >&2
             echo "  Fedora/RHEL:    sudo dnf install aria2 python3 curl" >&2
             echo "  Arch:           sudo pacman -S aria2 python curl" >&2 ;;
    windows) echo "  Windows: winget install aria2.aria2  或  scoop install aria2 python" >&2 ;;
    *)       echo "  请用你系统的包管理器安装 aria2、python3、curl" >&2 ;;
  esac
  exit 1
fi

# ---------- 1) 目录与必存空文件（aria2.session 不存在时 aria2 会直接报错退出） ----------
mkdir -p "$ARIA2_DIR" "$BIN_DIR"
touch "$ARIA2_DIR/aria2.session" "$ARIA2_DIR/aria2.log"

# ---------- 2) 核心脚本：a2 主程序 + 落点配置 + 启动器 ----------
install -m 755 "$SKILL_DIR/scripts/a2"             "$ARIA2_DIR/a2"
install -m 755 "$SKILL_DIR/scripts/start-aria2.sh" "$ARIA2_DIR/start-aria2.sh"
install -m 755 "$SKILL_DIR/scripts/a2-dest"        "$BIN_DIR/a2-dest"
install -m 755 "$SKILL_DIR/scripts/a2-search"      "$BIN_DIR/a2-search"
echo "已安装核心脚本 -> $ARIA2_DIR/{a2,start-aria2.sh} + $BIN_DIR/{a2-dest,a2-search}"
# 落点配置：首次运行按 OS 生成默认下载目录（已存在则沿用，不覆盖用户改过的值）
"$BIN_DIR/a2-dest" >/dev/null
echo "默认下载目录 -> $("$BIN_DIR/a2-dest")（改：a2-dest set <目录>）"

# ---------- 3) a2 软链进 PATH（本体在 ~/.aria2/a2，软链到 ~/.local/bin/a2） ----------
ln -sf "$ARIA2_DIR/a2" "$BIN_DIR/a2"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "提示: $BIN_DIR 不在 PATH 里，把下面一行加进 shell 启动脚本（~/.bashrc / ~/.zshrc / ~/.profile）："
     echo "      export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

# ---------- 4) AList 网盘助手（需另行部署 AList 并挂载云盘） ----------
for s in a2-ls a2-alist a2-alist-dir a2-aliyun; do
  install -m 755 "$SKILL_DIR/scripts/$s" "$BIN_DIR/$s"
done
echo "已安装 AList 助手 -> $BIN_DIR/{a2-ls,a2-alist,a2-alist-dir,a2-aliyun}"

# ---------- 5) 搜索站点配置 + 源骨架（a2-search 用；站点由你自己填） ----------
install -m 755 "$SKILL_DIR/scripts/search-source-demo.py"     "$ARIA2_DIR/search-source-demo.py"
install -m 755 "$SKILL_DIR/scripts/search-source-template.py" "$ARIA2_DIR/search-source-template.py"
echo "已安装搜索源脚本 -> $ARIA2_DIR/{search-source-demo.py,search-source-template.py}"
if [ -f "$ARIA2_DIR/search-sites.conf" ]; then
  echo "search-sites.conf 已存在，跳过（站点就配在这里）"
else
  sed -e "s|__HOME__|$HOME|g" \
      "$SKILL_DIR/assets/search-sites.conf.template" > "$ARIA2_DIR/search-sites.conf"
  echo "已生成 search-sites.conf -> $ARIA2_DIR/search-sites.conf（填 site= 行之后 a2-search 才有站点可搜）"
fi

# ---------- 6) aria2.conf + a2.conf：不存在才生成（绝不覆盖已有配置） ----------
if [ -f "$ARIA2_DIR/aria2.conf" ]; then
  echo "aria2.conf 已存在，跳过（如需变更请手动编辑 $ARIA2_DIR/aria2.conf）"
else
  SECRET="$(openssl rand -hex 16 2>/dev/null || echo "a2_$(date +%s)_secret")"
  sed -e "s|__RPC_SECRET__|$SECRET|g" -e "s|__HOME__|$HOME|g" \
      "$SKILL_DIR/assets/aria2.conf.template" > "$ARIA2_DIR/aria2.conf"
  echo "已生成 aria2.conf（rpc-secret 已随机生成并写进文件，注意保密）"
fi
chmod 600 "$ARIA2_DIR/aria2.conf"        # 里面有 rpc-secret：同机其他用户不该读到

if [ -f "$ARIA2_DIR/a2.conf" ]; then
  echo "a2.conf 已存在，跳过（搜索源就配在这里）"
else
  sed -e "s|__LABEL__|$SERVICE|g" -e "s|__HOME__|$HOME|g" \
      "$SKILL_DIR/assets/a2.conf.template" > "$ARIA2_DIR/a2.conf"
  echo "已生成 a2.conf -> $ARIA2_DIR/a2.conf（a2 自己的配置：搜索源、服务名）"
fi

# ---------- 7) 守护服务：按平台安装（已存在则不覆盖） ----------
case "$PLAT" in
  mac)
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST="$PLIST_DIR/$SERVICE.plist"
    mkdir -p "$PLIST_DIR"
    if [ ! -f "$PLIST" ]; then
      sed -e "s|__LABEL__|$SERVICE|g" -e "s|__HOME__|$HOME|g" \
          "$SKILL_DIR/assets/com.example.aria2.plist.template" > "$PLIST"
      echo "已安装 launchd 服务定义 -> $PLIST"
    else
      echo "launchd 服务定义已存在，跳过 -> $PLIST"
    fi
    launchctl load -w "$PLIST" 2>/dev/null || true
    launchctl kickstart -k "gui/$(id -u)/$SERVICE" 2>/dev/null || \
      echo "提示: launchctl kickstart 失败，服务可能刚装载，稍后会自动拉起"
    ;;
  linux)
    UNIT_DIR="$HOME/.config/systemd/user"
    UNIT="$UNIT_DIR/$SERVICE.service"
    mkdir -p "$UNIT_DIR"
    if [ ! -f "$UNIT" ]; then
      sed -e "s|__LABEL__|$SERVICE|g" -e "s|__HOME__|$HOME|g" \
          "$SKILL_DIR/assets/a2.service.template" > "$UNIT"
      echo "已安装 systemd 用户服务 -> $UNIT"
    else
      echo "systemd 服务已存在，跳过 -> $UNIT"
    fi
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user daemon-reload 2>/dev/null || true
      systemctl --user enable --now "$SERVICE" 2>/dev/null || \
        echo "提示: systemctl --user enable --now $SERVICE 失败 —— 看 systemctl --user status $SERVICE"
      echo "日志: journalctl --user -u $SERVICE -f"
    else
      echo "提示: 没找到 systemctl（容器/精简系统？）—— 手动前台启动：$ARIA2_DIR/start-aria2.sh --daemon=false"
    fi
    ;;
  windows)
    echo "Windows: 脚本与配置已就绪，但守护进程需要你自己注册（任选其一）"
    echo "  A) 计划任务（登录自启，无需额外工具）："
    echo "     schtasks /Create /TN \"$SERVICE\" /SC ONLOGON /RL LIMITED \\"
    echo "       /TR \"%USERPROFILE%\\\\.aria2\\\\start-aria2.sh --daemon=false\""
    echo "     （走 WSL 时改成：wsl.exe -e sh -lc \"~/.aria2/start-aria2.sh --daemon=false\"）"
    echo "  B) nssm（把命令包成 Windows 服务）：nssm install $SERVICE <aria2c.exe> --conf-path=..."
    echo "  临时前台跑：bash \"$ARIA2_DIR/start-aria2.sh\" --daemon=false"
    ;;
  *)
    echo "提示: 未识别的平台 —— 服务需要你自己托管。前台运行命令："
    echo "      $ARIA2_DIR/start-aria2.sh --daemon=false"
    ;;
esac

# ---------- 8) 验证 ----------
sleep 2
echo "== 验证 =="
curl -s -o /dev/null -w "AList  http:%{http_code}\n" http://localhost:5244 --max-time 3 || true
a2 st 2>/dev/null || echo "RPC 未就绪：确认守护进程在跑（macOS: launchctl print gui/$(id -u)/${SERVICE}｜Linux: systemctl --user status ${SERVICE}），并检查 $ARIA2_DIR/aria2.conf"
cat <<EOF
== 完成。常用命令：
     a2 st / a2 ls / a2-dest / a2-dest set <目录>
     a2 add --dir "$(${BIN_DIR}/a2-dest)" "<磁力或链接>"      # 落点必须显式给
   搜索在 skill 层（a2 不内置任何站点）：先在 $ARIA2_DIR/search-sites.conf 里加
     site=<名字>|<URL 模板>          或   site=<名字>|cmd:<命令>
   然后 a2-search <关键词> → a2 add --dir <目录> --verify "<磁力>"。
   想先跑通流程（离线、不联网）：site=本地演示|cmd:python3 $ARIA2_DIR/search-source-demo.py
   契约与示例见 references/search-sites.md。
   服务名是 ${SERVICE}；想换：A2_SERVICE=a2.其他名字 bash scripts/install-a2.sh
   （服务定义已存在时不会被覆盖，需先删掉旧的再重跑。）
EOF
