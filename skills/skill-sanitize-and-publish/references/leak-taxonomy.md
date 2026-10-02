# 泄漏分类库（脱敏操作手册）

<!-- audit-skip-file: 本文档是反面示例库：表中列出的 URL 内嵌凭据、私钥头、代理端口等字面量是
     教学用的「错误写法」，不是本机的真实值。新增示例时仍应使用虚构值（example.com / abcd1234）。-->

每条给出：长什么样 → 为什么算泄漏 → 怎么改。括号里是审计器的规则名（`scripts/audit_skill.py --json` 里的 `rule`）。

处置四档：**删除**（内容本身不该存在）、**参数化**（改成配置项）、**占位**（改成通用示例）、
**保留并说明**（公共知识，但要在文档里讲清是默认值）。

---

## 1. 秘密（一律删除 + 轮换）

| 形态 | 例子 | 改法 |
|---|---|---|
| API key / token 字面值 | `ghp_…`、`sk-…`、`AKIA…`、`xoxb-…`、`AIza…`、`npm_…`（`cloud-provider-key`） | 删除；改读环境变量或配置文件；**去源头吊销/轮换** |
| 赋值给敏感字段 | `rpc-secret=abc123`、`password: hunter2`、`api_key = "…"`（`secret-assignment`） | 值留空 + 注释指向配置文件；安装脚本随机生成 |
| 请求头带凭据 | `-H "Authorization: Bearer eyJ…"`（`authorization-header-value`、`jwt`） | 改 `Bearer $TOKEN`，token 从配置读 |
| URL 内嵌凭据 | `https://user:pass@host/…`（`credential-in-url`） | 删掉内嵌部分，凭据单独配置 |
| 私钥文件内容 | `-----BEGIN OPENSSH PRIVATE KEY-----`（`private-key-block`） | 删除；重签密钥对 |
| .env 真实值 | `ALIST_TOKEN=xxxxxxxxxxxx`（`env-file-literal`） | 只提交 `*.env.example`，真实文件进 `.gitignore` |
| 云盘/第三方 refresh_token | `setup-aliyun.sh "<refresh_token>"` 里带真值（`secret-assignment`） | 参数留占位 `<refresh_token>`，实值走配置文件或交互输入 |

> 判据不是「值看起来随机」，而是**它能不能在你机器之外换到权限或身份**。

## 2. 身份（改成通用写法）

| 形态 | 例子 | 改法 |
|---|---|---|
| 家目录路径 | `/Users/<你>/…`、`/home/<你>/…`（`unix-home-path`） | `~` / `$HOME` / `os.path.expanduser("~")` / `Path.home()` |
| Windows 用户目录 | `C:\Users\<你>\…`（`windows-user-path`） | `%USERPROFILE%` / `Path.home()` |
| 外接盘卷标 | `/Volumes/<你的盘>/media`、`/mnt/<你的盘>/`（`external-volume`） | 配置项 `MAIN_DIR`；文档里写 `<你的盘>` 或 `D:\media` 这类示例 |
| 用户名 / 主机名 | 出现 `shawn`、`mac-mini` 之类（`machine-username`、`machine-hostname`、`local-term`） | 删；需要标识就用 `$USER`、`socket.gethostname()` |
| 真实邮箱 | 提交者邮箱、`user@私域.com`（`email-address`） | `<owner@example.com>`；git 作者换成 GitHub noreply 邮箱 |
| 局域网地址 | `192.168.x.x`、`10.x.x.x`、`172.16-31.x.x`（`lan-ip`） | 删；写 `<host>` / `<nas-ip>` |

## 3. 私有设施（参数化或占位）

| 形态 | 例子 | 改法 |
|---|---|---|
| 个人反向域名服务名 | `com.<你>.aria2`、`io.<你>.app`（`personal-service-label`） | `com.example.<服务>`；真实服务名走配置 |
| 本机代理 | `http://127.0.0.1:7897`、`export ALL_PROXY=…`（`proxy-endpoint`、`proxy-env`） | 配置项 `PROXY`，默认直连；文档说明「需要时再填」 |
| 私有站点/索引站 | 自建站、内网站、个人博客、私有 tracker（`unknown-domain-url` + 词表） | 删除站点名；需保留则做成「源命令」配置，由用户自己填 |
| 具体设备/品牌 | `群晖`、`TrueNAS`、`极空间`、`Unraid`（`hardcoded-nas-or-device`） | 改成「网络盘/外接盘」中性表述 |
| 个人叙述 | 「我这台机器实测」「我的盘写满了」（`personal-narrative`） | 改中性：「在 HFS+ 外接盘上实测」 |

## 4. 通用但被写死（保留，但要确认）

这类**通常不是泄漏**，删掉反而降低可操作性。确认是软件默认值/公知事实即可保留：

- 端口：`5244`（AList）、`6800`（aria2 RPC）、`6881`（BT）、`8080`（`localhost-service-url`、`nonstandard-port-hint`）
- 公知上游：`github.com/…`、`alist.nn.ci`、`aria2.github.io/manual`（`unknown-domain-url` 的白名单）
- 标准路径：`/opt/homebrew`、`/usr/local/bin`、`/etc/hosts`、`/mnt/usb`（`absolute-unix-path` 的安全前缀）
- 公开 tracker announce 列表、示例磁力、示例域名 `example.com` / `example.invalid`
- 包管理器命令：`brew install` / `apt install` / `winget install`（`package-manager-line`，info 级）

**唯一要求**：文档里说清「这是默认值，改过请改配置」——不要让读者以为必须照抄。

## 5. 可移植性缺陷（不是泄漏，但属于「别人用不了」）

见 `references/cross-platform.md`。审计器会标 `posix-only-api`、`hardcoded-tmp`、`bsd-sed-inplace`、
`gnu-only-flag`、`os-specific-opener`、`bare-python-cmd`、`hardcoded-shebang`。

真实例子：`import fcntl` 在模块顶层 → Windows 原生 Python 直接 `ImportError`，钩子永远跑不起来。
改法：`try: import fcntl / except ImportError: import msvcrt`，锁语义分别实现
（`flock(LOCK_EX|LOCK_NB)` vs `msvcrt.locking(LK_NBLCK)`），两者都没有时退化为不加锁 + 超时。

## 6. 仓库与元数据层面的泄漏（文件之外）

| 面 | 内容 | 处置 |
|---|---|---|
| git 提交者 | `user.name` / `user.email` 真实姓名+邮箱 | 按用户意愿换 noreply 邮箱；已推送的历史改写要单独确认 |
| git 历史 | 旧提交里的密钥、被删除文件的内容 | 秘密必须轮换；历史清洗用 `git filter-repo`（需用户明确同意） |
| `.git/logs` | reflog 里的作者信息与时间 | 随历史处理，不必单独处理 |
| assets/screenshots | 截图里的浏览器书签栏、桌面文件名、登录态 | 打码或重拍 |
| README/日志样本 | 贴的终端输出里含家目录、主机名提示符 | 用中性提示符重贴（`$`、`PS>`） |
| launchd/systemd 文件 | 服务名、`WorkingDirectory` 指向个人目录 | 模板化（`__HOME__` / `__LABEL__`），由安装脚本渲染 |

## 处置记录格式

每条处置都要能追溯（模板见 `references/report-template.md`）：

```
规则 / 位置 / 原文片段 / 类别 / 处置(删除|参数化|占位|保留) / 理由 / 落地位置
```

「保留」也必须写理由（为什么它不构成泄漏），否则审计等于没跑。
