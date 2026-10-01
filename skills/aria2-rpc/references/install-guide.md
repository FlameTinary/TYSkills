# AList 安装指南

## 系统要求

- Windows / macOS / Linux（AList 官方提供三平台预编译包）
- 可访问 GitHub（用于下载 AList 发布包）

## 一键安装

```bash
bash scripts/install-alist.sh
```

## 手动安装步骤

### 1. 下载

按平台选一个（`install-alist.sh` 会自动判断）：

```bash
# macOS Apple Silicon
curl -L -o alist.tar.gz https://github.com/AlistGo/alist/releases/latest/download/alist-darwin-arm64.tar.gz
# macOS Intel
curl -L -o alist.tar.gz https://github.com/AlistGo/alist/releases/latest/download/alist-darwin-amd64.tar.gz
# Linux x86_64 / ARM64
curl -L -o alist.tar.gz https://github.com/AlistGo/alist/releases/latest/download/alist-linux-amd64.tar.gz
curl -L -o alist.tar.gz https://github.com/AlistGo/alist/releases/latest/download/alist-linux-arm64.tar.gz
# Windows x86_64（解压得到 alist.exe）
curl -L -o alist.zip https://github.com/AlistGo/alist/releases/latest/download/alist-windows-amd64.zip
```

### 2. 安装

```bash
tar -xzf alist.tar.gz
mkdir -p ~/.local/bin
mv alist ~/.local/bin/alist
chmod +x ~/.local/bin/alist
```

### 3. 初始化并生成密码

```bash
mkdir -p ~/.alist
cd ~/.alist
~/.local/bin/alist admin random --data ~/.alist
```

输出示例：
```
username: admin
password: XXXXXXXX
```

密码也会保存在 `~/.alist/admin_password.txt`。

### 4. 启动

```bash
cd ~/.alist
nohup alist server --data ~/.alist > alist.log 2>&1 &
```

### 5. 配置 PATH

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## 目录结构

```
~/.local/bin/alist          # 可执行文件
~/.alist/
├── data/
│   ├── config.json         # 配置文件
│   └── data.db             # SQLite 数据库
├── start-alist.sh          # 启动脚本
├── stop-alist.sh           # 停止脚本
├── admin_password.txt      # 管理员密码记录
└── alist.log               # 运行日志
```

## 验证安装

```bash
# 检查版本
alist version

# 检查服务
curl -s -o /dev/null -w "%{http_code}" http://localhost:5244
# 应返回 200
```
