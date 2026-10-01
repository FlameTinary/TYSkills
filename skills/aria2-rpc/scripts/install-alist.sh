#!/bin/bash
# AList 安装脚本（macOS / Linux / Windows(Git Bash、MSYS)，都无需 sudo）
# 安装到 ~/.local/bin，数据目录 ~/.alist

set -e

INSTALL_DIR="$HOME/.local/bin"
DATA_DIR="$HOME/.alist"

echo "=== AList 安装脚本 ==="

# 平台与架构（按 uname 判断，不假设系统）
case "$(uname -s)" in
  Darwin)                PLATFORM="darwin" ;;
  Linux)                 PLATFORM="linux" ;;
  MINGW*|MSYS*|CYGWIN*)  PLATFORM="windows" ;;
  *) echo "不支持的平台: $(uname -s)（可手动从 GitHub Releases 下载）" >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64|amd64)   ARCH="amd64" ;;
  arm64|aarch64)  ARCH="arm64" ;;
  *) echo "不支持的架构: $(uname -m)" >&2; exit 1 ;;
esac
if [ "$PLATFORM" = "windows" ]; then BIN_NAME="alist.exe"; PKG_EXT="zip"; else BIN_NAME="alist"; PKG_EXT="tar.gz"; fi
BIN="$INSTALL_DIR/$BIN_NAME"
echo "平台: $PLATFORM/$ARCH"

# 创建目录
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR"

# 获取最新版本号
echo "正在获取最新版本..."
LATEST=$(curl -sL https://api.github.com/repos/AlistGo/alist/releases/latest | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
echo "最新版本: $LATEST"

# 下载
DOWNLOAD_URL="https://github.com/AlistGo/alist/releases/download/${LATEST}/alist-${PLATFORM}-${ARCH}.${PKG_EXT}"
echo "下载地址: $DOWNLOAD_URL"

WORK="$(mktemp -d)"
cd "$WORK"
curl -L -o "alist-pkg.${PKG_EXT}" "$DOWNLOAD_URL"

# 解压安装（Windows 包是 zip）
if [ "$PKG_EXT" = "zip" ]; then
  unzip -o "alist-pkg.${PKG_EXT}" >/dev/null
else
  tar -xzf "alist-pkg.${PKG_EXT}"
fi
mv -f "$BIN_NAME" "$BIN"
chmod +x "$BIN"
cd "$HOME" && rm -rf "$WORK"

echo "已安装到: $BIN"
"$BIN" version

# 生成管理员密码
echo ""
echo "正在初始化管理员账号..."
cd "$DATA_DIR"
"$BIN" admin random --data "$DATA_DIR" 2>&1 | tee "$DATA_DIR/admin_password.txt"
chmod 600 "$DATA_DIR/admin_password.txt" 2>/dev/null || true

# 创建启动脚本
cat > "$DATA_DIR/start-alist.sh" << 'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
PID_FILE="$HOME/.alist/alist.pid"

if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "AList 已在运行，PID: $(cat $PID_FILE)"
    echo "访问地址: http://localhost:5244"
    exit 0
fi

cd "$HOME/.alist"
nohup "$HOME/.local/bin/__BIN__" server --data "$HOME/.alist" > "$HOME/.alist/alist.log" 2>&1 &
echo $! > "$PID_FILE"
sleep 2
echo "AList 已启动，PID: $(cat $PID_FILE)"
echo "访问地址: http://localhost:5244"
EOF

# 创建停止脚本
cat > "$DATA_DIR/stop-alist.sh" << 'EOF'
#!/bin/bash
PID_FILE="$HOME/.alist/alist.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "AList 已停止（PID: ${PID}）"
    fi
    rm -f "$PID_FILE"
else
    pkill -f "alist server" && echo "AList 已停止" || echo "AList 未在运行"
fi
EOF

# heredoc 是不插值的，这里把二进制名（Windows 是 alist.exe）填进启动脚本
sed -i.bak "s|__BIN__|$BIN_NAME|g" "$DATA_DIR/start-alist.sh" 2>/dev/null || \
  perl -pi -e "s|__BIN__|$BIN_NAME|g" "$DATA_DIR/start-alist.sh"
rm -f "$DATA_DIR/start-alist.sh.bak"
chmod +x "$DATA_DIR/start-alist.sh" "$DATA_DIR/stop-alist.sh"

# 确保 PATH 配置（按存在的 shell 启动文件写，不假设一定是 zsh）
for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile"; do
    [ -e "$rc" ] || continue
    grep -q '.local/bin' "$rc" 2>/dev/null && continue
    printf '%s\n' 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
    echo "已添加 PATH 到 $(basename "$rc")"
done

echo ""
echo "=== 安装完成 ==="
echo "启动服务: ~/.alist/start-alist.sh"
echo "访问地址: http://localhost:5244"
echo "密码文件: $DATA_DIR/admin_password.txt"
