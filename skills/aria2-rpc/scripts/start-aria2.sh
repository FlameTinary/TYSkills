#!/bin/sh
# aria2 启动器（服务管理器 / 终端 / cron 都用它，保证各条启动路径行为一致）
# 平台：macOS、Linux、WSL、Git Bash 等有 sh 的环境都可用（Windows 原生建议走 WSL）
#   1) 校验目标目录可用 —— 目录不存在、且会被创建在系统盘上（外接盘/网络盘没挂载的典型表现）
#      就拒绝启动，避免把几十 GB 悄悄写进系统盘。确认要建在系统盘上：设 A2_ALLOW_CREATE=1
#      临时回退（只用系统盘的下载目录）：A2_FALLBACK_DIR=~/Downloads
#   2) 媒体库根 / 默认下载目录由 A2_MEDIA_ROOT（默认 ~/media）/ A2_DOWNLOAD_DIR（默认 ~/Downloads）配置
#   3) 自测不可用分支：A2_MEDIA_ROOT=/不存在的挂载点/媒体 ./start-aria2.sh
set -u

CONF=${A2_CONF:-$HOME/.aria2/aria2.conf}
ARIA2=${A2_ARIA2:-$(command -v aria2c 2>/dev/null || true)}
MEDIA_ROOT=${A2_MEDIA_ROOT:-$HOME/media}
DOWNLOAD_DIR=${A2_DOWNLOAD_DIR:-$HOME/Downloads}
FALLBACK=${A2_FALLBACK_DIR:-}

case "${1:-}" in
  --version|-v|--help|-h)
    [ -n "$ARIA2" ] && exec "$ARIA2" "$@"
    echo "aria2: 找不到 aria2c" >&2
    exit 127
    ;;
esac

if [ ! -f "$CONF" ]; then
  echo "aria2: 找不到配置文件 ${CONF}（先跑 install-a2.sh，或用 A2_CONF 指定）" >&2
  exit 78
fi

if [ -z "$ARIA2" ] || [ ! -x "$ARIA2" ]; then
  echo "aria2: 找不到可执行的 aria2c（装好 aria2 后重试，或用 A2_ARIA2 指定绝对路径）" >&2
  exit 127
fi

# 目标目录可用性（跨平台：不依赖任何固定的挂载点前缀）
dir_ok() {
  [ -d "$1" ] && [ -w "$1" ] && return 0
  [ "${A2_ALLOW_CREATE:-0}" = "1" ] && return 0
  command -v python3 >/dev/null 2>&1 || return 0     # 没 python3 就不做该判断（a2 本身也依赖 python3）
  python3 - "$1" <<'PY'
import os, sys
p = os.path.abspath(os.path.expanduser(sys.argv[1]))
home = os.path.abspath(os.path.expanduser("~"))
if p == home or p.startswith(home.rstrip(os.sep) + os.sep):
    sys.exit(0)
anc = p
while not os.path.exists(anc):
    parent = os.path.dirname(anc)
    if not parent or parent == anc:
        break
    anc = parent
if not os.path.exists(anc):
    sys.stderr.write("路径所在位置不可用（盘符/挂载点不存在）：%s\n" % p)
    sys.exit(1)
try:
    if os.stat(anc).st_dev != os.stat(home).st_dev:
        sys.exit(0)
except OSError:
    sys.exit(0)
sys.stderr.write("%s 不存在，且会被创建到系统盘上（外接盘/网络盘多半没挂载）。\n" % p)
sys.stderr.write("  确认要建在系统盘上：mkdir -p '%s'，或设 A2_ALLOW_CREATE=1。\n" % p)
sys.exit(1)
PY
}

if ! dir_ok "$MEDIA_ROOT"; then
  if [ -n "$FALLBACK" ]; then
    echo "aria2: 媒体库 ${MEDIA_ROOT} 当前不可用 —— 本次回退到 ${FALLBACK}（临时模式，接好盘后请重启）" >&2
    exec "$ARIA2" --conf-path="$CONF" --dir="$FALLBACK" "$@"
  fi
  echo "aria2: 媒体库 ${MEDIA_ROOT} 当前不可用，拒绝启动（避免写进系统盘）。" >&2
  echo "       接好盘后重试；确需临时用系统盘：A2_FALLBACK_DIR=$DOWNLOAD_DIR $0" >&2
  exit 78
fi

exec "$ARIA2" --conf-path="$CONF" "$@"
