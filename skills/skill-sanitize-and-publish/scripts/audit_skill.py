#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# audit-skip-file: 本文件是泄漏规则与示例词表的定义处，正则字面量（/tmp、品牌名、个人叙述词、
#                   示例路径）即规则本身，不是泄漏内容。改规则时不要顺手放宽这里的豁免。
"""audit_skill.py —— 技能「脱敏 / 可移植性」审计器（跨平台，仅标准库，Python 3.8+）。

做三件事，任何一件失败都以非零码退出：
  1) 泄漏扫描：本机路径、用户名、主机名、卷标、局域网 IP、代理、密钥、令牌、
     真实邮箱、个人服务名/私有域名、机器状态叙述……按 high/medium/low/info 分级。
  2) 可移植性扫描：只在某一个 OS 上成立的 shell/Python 写法、硬编码 /tmp、fcntl 等。
  3) 格式扫描：SKILL.md 的 frontmatter 是否被五大 agent（Hermes / Claude Code /
     Codex / OpenCode / OpenClaw）接受（名字规则、目录名匹配、description 长度、BOM/CRLF）。

用法：
    python3 audit_skill.py <技能目录> [更多目录...] [选项]

选项：
    --json              输出 JSON
    --fail-level LVL    达到该级别即退出码 1（high|medium|low|info，默认 high）
    --terms FILE        追加「本机专属词表」（一行一词，# 注释）—— 你自己的
                        用户名/主机名/域名/站点名/盘符名，通用规则抓不到的用这个兜底
    --no-host-facts     不把当前机器的用户名/主机名家目录当判据
    --report FILE.md    额外写一份 Markdown 报告
    --max-bytes N       单文件扫描上限（默认 2 MiB）
    -q/--quiet          只打印结论

退出码：0 = 无达级问题；1 = 有；2 = 用法/路径错误。
"""
from __future__ import annotations

import argparse
import getpass
import io
import json
import os
import re
import socket
import sys

IS_WINDOWS = os.name == "nt"
HOME = os.path.expanduser("~")
LEVEL_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3}

# 豁免标记：`audit-skip: 理由`（该行）/ `audit-skip-file: 理由`（整个文件，前 8 行内）。
# 豁免会连同理由一起出现在报告里 —— 这正是「保留并说明」的落地方式，不是静默跳过。
SUPPRESS_LINE_RE = re.compile(r"(?:audit-skip|sanitize-skip|脱敏豁免)\s*[:：]?\s*(.*)$",
                              re.MULTILINE)
SUPPRESS_HEAD_LINES = 8

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache",
             ".pytest_cache", ".idea", ".vscode", "dist", "build", ".tox", ".DS_Store"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
              ".tgz", ".bz2", ".xz", ".7z", ".rar", ".mp4", ".mkv", ".mp3", ".woff",
              ".woff2", ".ttf", ".otf", ".so", ".dylib", ".dll", ".exe", ".pyc",
              ".sqlite", ".db", ".bin", ".class", ".jar", ".zst", ".lz4"}

# ---- 占位符/示例判据：命中即降级为 info，不再算泄漏 -------------------------
PLACEHOLDER_MARKERS = [
    "xxx", "yyy", "zzz", "<your", "<yourname", "<name", "<path", "<token", "<secret",
    "<key", "<user", "<host", "your_", "yourname", "your-name", "yournamehere",
    "__home__", "__label__", "__rpc_secret__", "__secret__", "__user__", "{basedir}",
    "${claude_skill_dir}", "$home", "%userprofile%", "$env:", "${", "{{", "example.com",
    "example.invalid", "example.org", "example.net", "样例", "示例", "占位", "你的",
    "你自己的", "自定义", "替换", "补全", "placeholder", "changeme", "change_me",
    "dummy", "foobar", "hunter2", "redacted", "****", "....", "todo", "todo:",
    "/path/to/", "c:\\path\\to", "d:\\path", "someuser", "john.doe", "jane.doe",
    "username", "/users/me", "/home/me", "/users/<", "/home/<", "/home/user",
    "/users/user", "runner", "developer", "test-user", "local-domain",
]
PLACEHOLDER_VALUE_RE = re.compile(
    r"^(?:[<>\[{$_@#*.\-]+|[*xX]+|X+|\d+|\s*)$"          # 纯符号/纯 X/纯数字
    r"|^(?:true|false|none|null|nil|yes|no|on|off)$"
    r"|^[^\x00-\x7f]+$",                                  # 全非 ASCII（多为中文说明）
    re.IGNORECASE)

SAFE_HOSTS = {
    "example.com", "example.invalid", "example.org", "example.net", "localhost",
    "127.0.0.1", "::1", "0.0.0.0", "github.com", "raw.githubusercontent.com",
    "api.github.com", "objects.githubusercontent.com", "codeload.github.com",
    "aria2.github.io", "alist.nn.ci", "www.aliyundrive.com", "aliyundrive.com",
    "zstd.net", "python.org", "nodejs.org", "docs.python.org", "www.apple.com",
    "apple.com", "openai.com", "developers.openai.com", "platform.openai.com",
    "anthropic.com", "code.claude.com", "docs.claude.com", "opencode.ai",
    "docs.openclaw.ai", "openclaw.ai", "agentskills.io", "openagentskills.dev",
    "clawhub.com", "git-scm.com", "gnu.org", "debian.org", "ubuntu.com",
    "archlinux.org", "fedoraproject.org", "brew.sh", "npmjs.com", "pypi.org",
    "tracker.openbittorrent.com", "open.demonii.com", "explodie.org",
    "tracker.opentrackr.com", "tracker.dler.com", "www.gnu.org", "learn.chatgpt.com",
    "chatgpt.com", "claude.com", "x.com",
}
SAFE_HOST_SUFFIX = (".invalid", ".test", ".example", ".local", ".localdomain")
SAFE_HOST_PREFIX = ("tracker.", "tracker-", "tr.", "bt.", "announce.", "www.tracker.")

# ---- 通用规则表 --------------------------------------------------------------
# level / category / id / regex / hint；match: "line"(整行判占位符) | "value"(取组 1)
RULES = [
    # ---------- 凭据类（一律 high） ----------
    ("high", "secret", "private-key-block",
     r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----",
     "私钥内容，绝不能进公开仓库。", "line", None),
    ("high", "secret", "cloud-provider-key",
     r"\b(?:AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{35}|ya29\.[0-9A-Za-z_\-]{20,}|"
     r"ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|"
     r"github_pat_[A-Za-z0-9_]{22,}|glpat-[A-Za-z0-9_\-]{20,}|xox[abpro]-[A-Za-z0-9\-]{10,}|"
     r"sk-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_\-]{20,}|npm_[A-Za-z0-9]{36}|"
     r"dckr_pat_[A-Za-z0-9_\-]{20,}|(?:r|s)k_live_[A-Za-z0-9]{20,})\b",
     "真实 API key / token。删除，改用环境变量或用户配置文件。", "line", None),
    ("high", "secret", "jwt",
     r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",
     "JWT（常是登录态凭据）。删除。", "line", None),
    ("high", "secret", "credential-in-url",
     r"\b[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s/@:]+:[^\s/@]+@[^\s/]+",
     "URL 里内嵌用户名密码。改为从配置/环境变量读取。", "line", None),
    ("high", "secret", "secret-assignment",
     r"""(?i)\b(password|passwd|pwd|passphrase|secret|rpc[_-]?secret|token|api[_-]?key|
         access[_-]?key|client[_-]?secret|auth[_-]?token|access[_-]?token|
         refresh[_-]?token|bearer|session[_-]?id|cookie|private[_-]?key|
         admin[_-]?password)\b\s*[:=]\s*["']?([^\s"',;#)\]}>]+)""".replace("\n", "").replace(" ", ""),
     "给敏感字段赋了字面值。改成占位符 + 从配置文件/环境变量读。", "value", "_secret_value_ok"),
    ("high", "secret", "authorization-header-value",
     r"(?i)\bAuthorization\b\s*:\s*(?!\*|xxx|<|\$\{|%|<token|bearer\s*<|Bearer\s*\$\{)[^\s\"']{8,}",
     "Authorization 头带真实值。改成 `Bearer $TOKEN` 之类。", "line", None),
    ("high", "secret", "env-file-literal",
     r"(?m)^\s*[A-Z][A-Z0-9_]{2,}\s*=\s*(?![\s\"']*(?:$|<|\$\{|%|\*|xxx))[^\s\"']{12,}$",
     "疑似 .env 里的真实值。公开仓库只放 *.env.example。", "line", None),

    # ---------- 本机身份类 ----------
    ("high", "identity", "unix-home-path",
     r"(?<![\w.])/(?:Users|home)/(?!<|\{|xxx|yyy|user\b|users\b|username|your|me\b|you\b|"
     r"example|runner|app|node|root\b|test)[A-Za-z0-9._\-]{2,}",
     "别人机器上不存在的家目录路径。改成 `~` / `$HOME` / os.path.expanduser。", "line", None),
    ("high", "identity", "windows-user-path",
     r"(?i)\b[A-Z]:\\Users\\(?!<|\{|xxx|user\b|username|your|example|public|default)[A-Za-z0-9._\-]{2,}",
     "Windows 用户目录路径。改成 `%USERPROFILE%` / Path.home()。", "line", None),
    ("high", "identity", "external-volume",
     r"(?<![\w.])/Volumes/(?!<|\{|xxx|yyy)[A-Za-z0-9._\- ]{2,}",
     "外接盘/网络盘的真实卷标（只有你这台机器有）。改成占位符或配置项。", "line", None),
    ("high", "identity", "lan-ip",
     r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b",
     "局域网地址 = 你的网络拓扑。删掉或改成 <host> 占位符。", "line", None),
    ("high", "identity", "email-address",
     r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
     "真实邮箱（提交者身份）。必要时改成 <owner@example.com>。", "value", "email-ok"),
    ("high", "identity", "machine-hostname",
     r"",  # 运行时用本机主机名填充
     "本机主机名出现在技能里。", "value", None),
    ("high", "identity", "machine-username",
     r"",  # 运行时用本机用户名填充
     "本机用户名出现在技能里。", "value", None),

    # ---------- 私有设施/站点类 ----------
    ("medium", "private-infra", "personal-service-label",
     r"(?i)\b(?:com|io|org|net|dev|app)\.[a-z0-9][a-z0-9\-]{1,30}\.[a-z0-9\-]{2,30}\b",
     "个人反向域名服务名（如 com.<你>.<服务>）。改成 com.example.<服务>。", "value",
     "_service_label_ok"),
    ("medium", "private-infra", "proxy-endpoint",
     r"(?i)(?:proxy|socks|clash|v2ray|xray|ss-local|surge|mihomo|代理)"
     r"[^\n]{0,40}?(?:https?|socks5h?|socks4)://(?:127\.0\.0\.1|localhost|0\.0\.0\.0):\d+"
     r"|(?:https?|socks5h?|socks4)://(?:127\.0\.0\.1|localhost):\d+[^\n]{0,20}(?:proxy|代理|clash|mihomo)",
     "本机代理端口/代理地址写死。改成可选配置项，默认直连。", "line", None),
    ("info", "private-infra", "localhost-service-url",
     r"(?i)\bhttps?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0):\d+",
     "本机服务地址：确认端口是软件的默认值，而不是你机器上改过的。", "line", None),
    ("medium", "private-infra", "proxy-env",
     r"(?i)\b(?:h|all|https?|no|ftp)?_?proxy\s*[:=]\s*[^\s\"']+",
     "代理/环境变量写死。改成配置项并默认关闭。", "line", None),
    ("info", "private-infra", "nonstandard-port-hint",
     r"(?i)\b(?:端口|port)\D{0,8}(\d{4,5})\b",
     "写死的端口号：确认是软件默认端口，还是你机器上改过的。", "value", "_port_ok"),
    ("medium", "private-infra", "hardcoded-nas-or-device",
     r"(?i)\b(?:synology|群晖|qnap|威联通|truenas|fnos|飞牛|openwrt|群辉|华硕|asuswrt|"
     r"unraid|omv|openmediavault|极空间|zspace)\b",
     "具体设备/系统品牌：确认是否为个人环境描述。", "line", None),
    ("medium", "private-infra", "personal-narrative",
     r"(?:我的机器|我这台|本机实测|我司|我们公司|本人|笔者的机器|我的盘|我的服务器)",
     "个人环境叙述。改成中性表述或示例值。", "line", None),

    # ---------- 通用路径（多为示例，需人工确认） ----------
    ("medium", "path", "absolute-unix-path",
     r"(?<![\w.${}~])/(?:mnt|data|srv|opt|run|storage|pool|export|backup|vol|volume)"
     r"/[A-Za-z0-9._\-]{2,}",
     "绝对路径：确认是通用示例还是你机器上的真实挂载点。", "line", "_path_ok"),
    ("low", "path", "absolute-etc-or-var",
     r"(?<![\w.])/(?:etc|var|usr/local)/[A-Za-z0-9._\-/]{2,}",
     "系统路径：多为合法默认值（如 /etc/hosts），确认无本机特有内容。", "line", None),
    ("info", "path", "drive-letter-path",
     r"(?i)\b[A-Z]:\\[^\s\"'`)|,;]{2,}",
     "Windows 盘符路径：确认是示例。", "line", None),
    ("info", "path", "unknown-domain-url",
     r"https?://([A-Za-z0-9.\-]+)",
     "非白名单域名：确认不是你的私有站点/内网服务。", "value", "_domain_ok"),

    # ---------- 可移植性 ----------
    ("medium", "portability", "posix-only-api",
     r"(?m)^\s*(?:import|from)\s+(fcntl|pty|termios|pwd|grp|crypt|resource)\b|"
     r"\b(?:os\.fork|os\.killpg|os\.setsid|os\.getuid|signal\.SIGKILL)\b",
     "POSIX 专有 API：Windows 上直接崩。改用 psutil/subprocess/条件分支。", "line", None),
    ("medium", "portability", "hardcoded-tmp",
     r"(?<![\w/])(?:/tmp|/var/tmp|C:\\\\Windows\\\\Temp)(?![\w])",
     "硬编码临时目录：改用 tempfile.gettempdir() / $TMPDIR。", "line", None),
    ("medium", "portability", "bsd-sed-inplace",
     r"\bsed\s+-i\s+(?!''|\"\"|\.\w+)[^\s]",
     "`sed -i` 在 macOS(BSD) 上必须带备份后缀：`sed -i ''`；GNU 则不接受空后缀。", "line", None),
    ("medium", "portability", "gnu-only-flag",
     r"\b(?:grep\s+-P|sed\s+-r\b|sort\s+-V|xargs\s+-r\b|readlink\s+-f|realpath\s|"
     r"date\s+-d\b|stat\s+-c\b|stat\s+-f\b|cp\s+--parents|mktemp\s+-p\b)",
     "GNU/BSD 单边选项：换 Python 实现或在文中按平台给出两种写法。", "line", None),
    ("low", "portability", "os-specific-opener",
     r"(?<![\w.\-])(?:osascript|launchctl|pmset|defaults\s+write|systemctl|schtasks|"
     r"winreg|xdg-open|start\s+[\"']http)(?![\w.\-])",
     "平台专有命令：若技能声称跨平台，需按平台分支或明确标注。", "line", None),
    ("low", "portability", "bare-python-cmd",
     r"(?<![\w.\-/])python\s+-[cm]\b|(?<![\w.\-/])pip\s+install|(?<![\w.\-/])py\s+-3\b",
     "`python`/`pip` 在部分系统不存在（只有 python3/py -3）。统一用 python3 或探测。", "line", None),
    ("low", "portability", "hardcoded-shebang",
     r"^#!\s*/(?:usr/)?bin/(?:env\s+)?(?:bash|python3?|sh|zsh)\b",
     "`#!/usr/bin/env bash` 比绝对路径可移植。", "line", None),
    ("info", "portability", "package-manager-line",
     r"\b(?:brew|apt-get|apt|dnf|yum|pacman|winget|scoop|choco)\s+(?:install|add)\b",
     "包管理器命令：确认三平台都给了对应写法。", "line", None),
]

RULE_TITLES = {}
for _lvl, _cat, _rid, _rx, _hint, _mode, _ok in RULES:
    RULE_TITLES[_rid] = _hint


EXEMPTIONS = []


def _clean_reason(raw):
    r = (raw or "").strip()
    r = re.sub(r"^-?file\s*[:：]?\s*", "", r)          # 去掉标记名残留
    for cut in ("-->", " | "):                            # 截断注释/表格残余
        if cut in r:
            r = r.split(cut)[0].strip()
    return r or "(未写理由)"


def _is_placeholder(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in PLACEHOLDER_MARKERS)


def _value_is_placeholder(value: str) -> bool:
    v = value.strip().strip("\"'`")
    if not v:
        return True
    if PLACEHOLDER_VALUE_RE.match(v):
        return True
    return _is_placeholder(v)


def _service_label_ok(value: str) -> bool:
    parts = value.lower().split(".")
    if len(parts) != 3:
        return True
    return parts[1] in {"example", "company", "yourcompany", "your", "mydomain", "domain",
                        "mycompany", "corp", "internal", "local", "test", "acme", "foo", "bar"}


def _domain_ok(value: str) -> bool:
    host = value.lower().strip("./")
    if host in SAFE_HOSTS:
        return True
    if host.endswith(SAFE_HOST_SUFFIX) or host.startswith(SAFE_HOST_PREFIX):
        return True
    base = ".".join(host.split(".")[-2:])
    return base in SAFE_HOSTS


def _email_ok(value: str) -> bool:
    dom = value.split("@")[-1].lower()
    return dom in SAFE_HOSTS or dom.endswith(SAFE_HOST_SUFFIX) or _is_placeholder(value)


CODE_VALUE_RE = re.compile(r"[()\[\]{}<>$%`\\;,]|\.get\b|\.format\b|^\s*$")


def _looks_like_secret(value: str) -> bool:
    """值本身像不像「真凭据」。不像就放过，避免把代码/占位符当泄漏。"""
    v = value.strip().strip("\"'`")
    if len(v) < 8 or len(v) > 512:
        return False
    if CODE_VALUE_RE.search(v):            # 函数调用、格式化串、shell 替换、结构体……
        return False
    if _value_is_placeholder(v):
        return False
    if not re.match(r"^[A-Za-z0-9+/=_\-.~!@#:]{8,}$", v):
        return False
    if re.match(r"^[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+$", v):   # args.secret / self.token
        return False
    kinds = sum(bool(re.search(p, v)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]"))
    return kinds >= 2 or len(v) >= 20


def _secret_value_ok(value: str) -> bool:
    """返回 True = 跳过（不报）。只有「像真凭据」才报。"""
    return not _looks_like_secret(value)


SAFE_PATH_PREFIXES = ("/opt/homebrew", "/opt/local", "/usr/local", "/mnt/usb", "/mnt/data",
                      "/mnt/media", "/media/usb", "/srv/app", "/srv/data", "/data/app",
                      "/var/lib", "/var/log", "/usr/share", "/mnt/xxx", "/mnt/your")

COMMON_PORTS = {"80", "443", "1080", "3000", "3128", "5000", "5244", "5432", "6379", "6800",
                "6881", "7000", "7474", "8000", "8080", "8081", "8086", "8088", "8443", "8888",
                "9000", "9090", "9200", "11434", "27017", "51413", "62078", "20171", "7890",
                "7891", "7897", "10809", "8889", "19090", "3306", "1521", "5672", "2375"}


def _path_ok(value: str) -> bool:
    return value.lower().startswith(SAFE_PATH_PREFIXES)


def _port_ok(value: str) -> bool:
    return value.strip() in COMMON_PORTS


VALUE_FILTERS = {
    "_path_ok": _path_ok,
    "_port_ok": _port_ok,
    "_service_label_ok": _service_label_ok,
    "_domain_ok": _domain_ok,
    "email-ok": _email_ok,
    "_secret_value_ok": _secret_value_ok,
}


class Finding(object):
    __slots__ = ("level", "category", "rule", "file", "line", "text", "hint")

    def __init__(self, level, category, rule, file, line, text, hint):
        self.level, self.category, self.rule = level, category, rule
        self.file, self.line, self.text, self.hint = file, line, text, hint

    def as_dict(self):
        return {"level": self.level, "category": self.category, "rule": self.rule,
                "file": self.file, "line": self.line, "text": self.text, "hint": self.hint}

    def render(self, root):
        rel = os.path.relpath(self.file, root) if self.file.startswith(root) else self.file
        return "[%s] %s:%d  %s\n        %s\n        → %s" % (
            self.level.upper(), rel, self.line, self.rule, self.text.strip()[:160], self.hint)


def iter_files(root, max_bytes, extra_skip):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and d not in extra_skip)
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            if os.path.islink(p) and not os.path.exists(p):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext in BINARY_EXT:
                continue
            try:
                if os.path.getsize(p) > max_bytes:
                    continue
            except OSError:
                continue
            yield p


def read_text(path):
    try:
        with io.open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return raw.decode(enc), raw
        except UnicodeDecodeError:
            continue
    return None


def load_terms(paths):
    terms = []
    for p in paths:
        if not p or not os.path.exists(p):
            continue
        txt, _ = read_text(p) or ("", None)
        for line in txt.splitlines():
            t = line.strip()
            if t and not t.startswith("#"):
                terms.append(t)
    return terms


def build_rules(host_facts):
    rules = []
    for lvl, cat, rid, rx, hint, mode, ok in RULES:
        if rid == "machine-hostname":
            if not host_facts.get("hostname"):
                continue
            rx = r"\b%s\b" % re.escape(host_facts["hostname"])
        elif rid == "machine-username":
            if not host_facts.get("username"):
                continue
            rx = r"(?<![\w.\-/])%s(?![\w.\-/])" % re.escape(host_facts["username"])
        if not rx:
            continue
        flags = 0
        if "(?i)" in rx:
            flags |= re.IGNORECASE
            rx = rx.replace("(?i)", "")
        if "(?m)" in rx:
            flags |= re.MULTILINE
            rx = rx.replace("(?m)", "")
        try:
            pat = re.compile(rx, flags)
        except re.error as exc:
            sys.stderr.write("bad rule %s: %s\n" % (rid, exc))
            continue
        rules.append({"level": lvl, "category": cat, "id": rid, "pat": pat,
                      "hint": hint, "mode": mode, "ok": VALUE_FILTERS.get(ok) if ok else None})
    return rules


def scan_file(path, rules, root, max_hits_per_rule=200):
    got = read_text(path)
    if got is None:
        return []
    text, raw = got
    out = []
    if b"\r\n" in raw and os.path.basename(path) == "SKILL.md":
        out.append(Finding("medium", "format", "crlf-line-endings", path, 1,
                           "SKILL.md 含 CRLF 行尾（Windows 编辑器保存过）",
                           "统一为 LF：git config core.autocrlf input / .gitattributes eol=lf。"))
    if raw.startswith(b"\xef\xbb\xbf"):
        out.append(Finding("high", "format", "bom-prefix", path, 1, "文件带 UTF-8 BOM",
                           "BOM 会让 frontmatter 的 `---` 不在字节 0：去掉 BOM。"))
    lines = text.splitlines()
    for i0, l0 in enumerate(lines[:SUPPRESS_HEAD_LINES], 1):
        m0 = SUPPRESS_LINE_RE.search(l0)
        if m0 and "audit-skip-file" in l0:
            EXEMPTIONS.append({"file": path, "line": 0, "rule": "file",
                               "reason": _clean_reason(m0.group(1))})
            return out
    exempt_lines = set()
    for i, line in enumerate(lines, 1):
        m = SUPPRESS_LINE_RE.search(line)
        if m:
            exempt_lines.add(i)
            EXEMPTIONS.append({"file": path, "line": i, "rule": "line",
                               "reason": _clean_reason(m.group(1))})
    for rule in rules:
        hits = 0
        for i, line in enumerate(lines, 1):
            if i in exempt_lines:
                continue
            m = rule["pat"].search(line)
            if not m:
                continue
            snippet = m.group(0)
            if rule["mode"] == "value":
                val = m.group(m.lastindex) if m.lastindex else m.group(0)
                if rule["ok"] and rule["ok"](val):
                    continue
                snippet = val
            else:
                # 整行判占位符：行内出现 xxx / <your / example.com / 你的 … 就放过
                if _is_placeholder(line) and m.group(0).lower() not in ("authorization",):
                    continue
                if rule["ok"] and rule["ok"](m.group(0)):
                    continue
            # 行内联注释说明「本机」「示例」时降一级，但保留可见性
            hits += 1
            if hits > max_hits_per_rule:
                break
            lvl = rule["level"]
            if rule["id"] == "posix-only-api" and ("msvcrt" in text or "ImportError" in text):
                lvl = "info"      # 文件里有 Windows 兜底分支，不算可移植性缺陷
            out.append(Finding(lvl, rule["category"], rule["id"], path, i,
                               snippet, rule["hint"]))
    return out


def check_frontmatter(root):
    """SKILL.md 是否满足五大 agent 的共同要求。"""
    out = []
    skill_md = None
    for cand in ("SKILL.md", "skill.md", "Skill.md"):
        p = os.path.join(root, cand)
        if os.path.exists(p):
            skill_md = p
            break
    if skill_md is None:
        nested = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            if "SKILL.md" in filenames:
                nested.append(dirpath)
        if nested:
            # 集合型仓库（根下若干个技能）：根目录本来就不该有 SKILL.md
            return [Finding("info", "format", "collection-root", root, 0,
                            "根目录是技能集合，发现 %d 个技能" % len(nested),
                            "对集合审计只需逐个子技能满足格式要求；根目录放 README 即可。")]
        return [Finding("high", "format", "missing-skill-md", root, 0, "目录下没有 SKILL.md",
                        "必须存在 SKILL.md（全大写），否则没有 agent 会加载它。")]
    if os.path.basename(skill_md) != "SKILL.md":
        out.append(Finding("high", "format", "skill-md-casing", skill_md, 0,
                           "文件名不是全大写 SKILL.md",
                           "OpenCode 等要求全大写：重命名为 SKILL.md。"))
    got = read_text(skill_md)
    if got is None:
        return out
    text, _ = got
    if not text.startswith("---"):
        out.append(Finding("high", "format", "frontmatter-start", skill_md, 1,
                           "文件不是以 `---` 开头（前面有空行/BOM）",
                           "frontmatter 必须从字节 0 开始。"))
        return out
    m = re.search(r"\n---[ \t]*\n", text[3:])
    if not m:
        out.append(Finding("high", "format", "frontmatter-end", skill_md, 1,
                           "找不到 frontmatter 结束的 `---`", "补上闭合 `---`。"))
        return out
    fm = text[3:m.start() + 3]
    body = text[m.end() + 3:]
    name = re.search(r"(?m)^name\s*:\s*(.+?)\s*$", fm)
    desc = re.search(r"(?m)^description\s*:\s*(.+?)\s*$", fm)
    if not name:
        out.append(Finding("high", "format", "frontmatter-name", skill_md, 1,
                           "frontmatter 缺 `name`", "name 为必需字段。"))
    else:
        val = name.group(1).strip().strip("\"'")
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", val):
            out.append(Finding("high", "format", "name-charset", skill_md, 1, "name=%s" % val,
                               "必须是 ^[a-z0-9]+(-[a-z0-9]+)*$（小写、单连字符、无首尾连字符）。"))
        if len(val) > 64:
            out.append(Finding("high", "format", "name-length", skill_md, 1, "name 超过 64 字符",
                               "OpenCode/AgentSkills 上限 64。"))
        if val != os.path.basename(root.rstrip("/")):
            out.append(Finding("high", "format", "name-dir-mismatch", skill_md, 1,
                               "name=%s ≠ 目录名 %s" % (val, os.path.basename(root.rstrip("/"))),
                               "OpenCode 要求 name 与所在目录名一致。"))
    if not desc:
        out.append(Finding("high", "format", "frontmatter-description", skill_md, 1,
                           "frontmatter 缺 `description`",
                           "description 决定技能何时被加载，必需。"))
    else:
        val = desc.group(1).strip().strip("\"'")
        if len(val) > 1024:
            out.append(Finding("high", "format", "description-length", skill_md, 1,
                               "description %d 字符" % len(val), "上限 1024 字符。"))
        elif len(val) > 60:
            out.append(Finding("info", "format", "description-long", skill_md, 1,
                               "description %d 字符（>60）" % len(val),
                               "Hermes 索引窗口约 57 字符：把触发词放在最前面。"))
    if not body.strip():
        out.append(Finding("high", "format", "empty-body", skill_md, 1, "frontmatter 之后没有正文",
                           "加正文（When to Use / Procedure / Verification…）。"))
    if "{{" in body and "}}" in body and "{" not in body.replace("{{", ""):
        pass
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="技能脱敏/可移植性审计（跨平台）")
    ap.add_argument("paths", nargs="+", help="要审计的技能目录（可多个）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-level", default="high",
                    choices=["info", "low", "medium", "high"])
    ap.add_argument("--terms", action="append", default=[],
                    help="本机专属词表文件（一行一词，# 注释）；可重复")
    ap.add_argument("--no-host-facts", action="store_true")
    ap.add_argument("--report", default=None, help="额外写一份 Markdown 报告")
    ap.add_argument("--max-bytes", type=int, default=2 * 1024 * 1024)
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    home_terms = [os.path.join(HOME, ".config", "skill-sanitize", "local-terms.txt")]
    terms = load_terms(home_terms + list(args.terms))

    host_facts = {}
    if not args.no_host_facts:
        try:
            host_facts["username"] = getpass.getuser()
        except Exception:
            host_facts["username"] = os.environ.get("USER") or os.environ.get("USERNAME") or ""
        try:
            hn = socket.gethostname()
            host_facts["hostname"] = hn.split(".")[0] if hn else ""
        except Exception:
            host_facts["hostname"] = ""
        for key in ("username", "hostname"):
            v = host_facts.get(key) or ""
            if len(v) < 3 or v.lower() in ("root", "user", "admin", "localhost", "build",
                                           "runner", "server", "node", "mac", "pc"):
                host_facts[key] = ""
        if host_facts.get("username"):
            terms.append(host_facts["username"])
        if host_facts.get("hostname"):
            terms.append(host_facts["hostname"])

    rules = build_rules(host_facts)
    term_rules = []
    for t in sorted(set(terms)):
        try:
            pat = re.compile(re.escape(t), re.IGNORECASE)
        except re.error:
            continue
        term_rules.append({"level": "high", "category": "local-term", "id": "local-term:%s" % t,
                           "pat": pat, "hint": "命中了本机专属词表（词表文件或本机用户名/主机名）。",
                           "mode": "line", "ok": None})

    all_findings = []
    roots = []
    for root in args.paths:
        if not os.path.isdir(root):
            sys.stderr.write("不是目录：%s\n" % root)
            return 2
        root = os.path.abspath(root)
        roots.append(root)
        all_findings.extend(check_frontmatter(root))
        for f in iter_files(root, args.max_bytes, set()):
            all_findings.extend(scan_file(f, rules + term_rules, root))

    per_rule_cap = 5
    capped, seen = [], {}
    for f in all_findings:
        key = (f.rule, f.file)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= per_rule_cap:
            capped.append(f)
        elif seen[key] == per_rule_cap + 1:
            capped.append(Finding(f.level, f.category, f.rule, f.file, f.line,
                                  "… 同类命中已折叠",
                                  "同一文件里该规则还有更多命中；见 --json 输出。"))
    all_findings = capped
    all_findings.sort(key=lambda x: (-LEVEL_ORDER[x.level], x.file, x.line))
    counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
    for f in all_findings:
        if "已折叠" not in f.text:
            counts[f.level] += 1

    if args.json:
        print(json.dumps({"roots": roots, "counts": counts,
                          "exemptions": EXEMPTIONS,
                          "findings": [f.as_dict() for f in all_findings]},
                         ensure_ascii=False, indent=2))
    else:
        cur = None
        for f in all_findings:
            if f.level != cur:
                cur = f.level
                if not args.quiet:
                    print("\n===== %s =====" % cur.upper())
            if args.quiet and LEVEL_ORDER[cur] < LEVEL_ORDER[args.fail_level]:
                continue
            print(f.render(roots[0] if len(roots) == 1 else os.path.dirname(f.file)))
        if not all_findings:
            print("干净：未发现任何泄漏/可移植性/格式问题。")
        if EXEMPTIONS and not args.quiet:
            print("\n---- 豁免（audit-skip，理由已记录；仍需人工复核）----")
            for e in EXEMPTIONS[:40]:
                loc = os.path.relpath(e["file"], roots[0]) if e["file"].startswith(roots[0]) else e["file"]
                print("  %s%s  → %s" % (loc, ":%d" % e["line"] if e["line"] else " (整个文件)",
                                        e["reason"]))
            if len(EXEMPTIONS) > 40:
                print("  … 共 %d 处" % len(EXEMPTIONS))
        print("\n---- 汇总 ----")
        for lvl in ("high", "medium", "low", "info"):
            print("  %-7s %d" % (lvl, counts[lvl]))
        print("  豁免：  %d 处（已写理由）" % len(EXEMPTIONS))
        print("  结论：%s（--fail-level=%s）" % (
            "需要处理" if counts[args.fail_level] or any(
                LEVEL_ORDER[k] > LEVEL_ORDER[args.fail_level] for k in counts if counts[k])
            else "通过", args.fail_level))

    if args.report:
        with io.open(args.report, "w", encoding="utf-8") as fh:
            fh.write("# 脱敏审计报告\n\n")
            fh.write("- 审计目录：%s\n" % "、".join(roots))
            fh.write("- 计数：high %d / medium %d / low %d / info %d\n\n" % (
                counts["high"], counts["medium"], counts["low"], counts["info"]))
            fh.write("## 已豁免（audit-skip，理由如下）\n\n")
            if EXEMPTIONS:
                fh.write("| 位置 | 理由 |\n|---|---|\n")
                for e in EXEMPTIONS:
                    fh.write("| %s%s | %s |\n" % (
                        os.path.relpath(e["file"], roots[0]),
                        ":%d" % e["line"] if e["line"] else " (文件级)",
                        e["reason"].replace("|", "\\|")))
            else:
                fh.write("（无）\n")
            fh.write("\n## 命中明细\n\n")
            fh.write("| 级别 | 类别 | 规则 | 位置 | 命中 | 处理建议 |\n|---|---|---|---|---|---|\n")
            for f in all_findings:
                fh.write("| %s | %s | %s | %s:%d | `%s` | %s |\n" % (
                    f.level, f.category, f.rule,
                    os.path.relpath(f.file, roots[0]), f.line,
                    f.text.strip().replace("|", "\\|")[:80], f.hint))
        print("\n报告已写入：%s" % args.report)
        print("注意：报告内嵌命中原文，可能含敏感片段 —— 只留在本地或私有仓库，别提交到公开仓库。")

    worst = max([LEVEL_ORDER[f.level] for f in all_findings] or [0])
    return 1 if worst >= LEVEL_ORDER[args.fail_level] else 0


if __name__ == "__main__":
    sys.exit(main())
