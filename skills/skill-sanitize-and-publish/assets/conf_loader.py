#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""conf_loader.py —— 三平台通用的「私有配置」加载器（仅标准库，Python 3.8+）。

给被脱敏的技能用：把原来写死在代码里的本机值（路径、端口、密钥、站点命令）挪到用户配置文件里。

优先级（高到低）：显式传入 > 环境变量 > 配置文件 > 内置默认。
配置文件：`~/.<app>/<app>.conf`，`KEY=VALUE` 一行一条，`#` 注释，值可用 `${VAR:-默认}` 与 `~`。

用法：
    from conf_loader import Conf
    conf = Conf("my-skill")                       # 读 ~/.my-skill/my-skill.conf
    root = conf.path("MEDIA_ROOT", "~/media")     # 展开 ~ 与 ${VAR:-x}
    port = conf.get_int("PORT", 5244)
    key  = conf.get("API_KEY")                    # 缺失返回 None；报错时不回显值
"""
from __future__ import annotations

import io
import os
import re
import sys

_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def default_conf_path(app):
    """三平台统一的配置位置：家目录下（不用 /etc、不用注册表）。"""
    return os.path.join(os.path.expanduser("~"), "." + app, app + ".conf")


def expand(value, env=None):
    """展开 ${VAR} / ${VAR:-默认} 与开头的 ~。"""
    env = os.environ if env is None else env

    def repl(m):
        name, dflt = m.group(1), m.group(2)
        return env.get(name, dflt if dflt is not None else "")

    out = _VAR_RE.sub(repl, value)
    return os.path.expanduser(out)


def parse(text):
    """解析 KEY=VALUE；忽略空行与 # 注释；值两端引号去掉。"""
    data = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        data[key] = val
    return data


class Conf(object):
    def __init__(self, app, path=None, env_prefix=None, defaults=None):
        self.app = app
        self.path = path or default_conf_path(app)
        self.env_prefix = (env_prefix if env_prefix is not None
                           else app.upper().replace("-", "_").replace(".", "_") + "_")
        self.defaults = dict(defaults or {})
        self._data = None
        self.load_error = None

    # ---- 载入 ----
    def load(self):
        if self._data is not None:
            return self._data
        self._data = {}
        if os.path.exists(self.path):
            try:
                with io.open(self.path, "r", encoding="utf-8") as fh:
                    self._data = parse(fh.read())
            except (OSError, UnicodeDecodeError) as exc:
                # 报错只说文件与原因，不回显任何值
                self.load_error = "%s（%s）" % (self.path, type(exc).__name__)
        return self._data

    # ---- 取值 ----
    def get(self, key, default=None, required=False):
        for candidate in (self.env_prefix + key, self.env_prefix + key.lower(), key):
            if candidate in os.environ:
                return expand(os.environ[candidate])
        data = self.load()
        if key in data:
            return expand(data[key])
        if default is not None:
            return expand(str(default)) if isinstance(default, str) else default
        if required:
            raise SystemExit(self.help_missing(key))
        return None

    def help_missing(self, key):
        return ("缺少配置 %s。\n"
                "  配置文件：%s%s\n"
                "  或环境变量：%s%s\n"
                "  模板：把技能目录里的 assets/%s.conf.template 复制到上面的路径后填写。"
                % (key, self.path,
                   ("（读取失败：%s）" % self.load_error) if self.load_error else "",
                   self.env_prefix, key, self.app))

    def get_int(self, key, default=None):
        raw = self.get(key, None if default is None else str(default))
        if raw is None or raw == "":
            return default
        try:
            return int(str(raw).strip())
        except ValueError:
            raise SystemExit("配置 %s 必须是整数，当前值不是（已隐去）。" % key)

    def get_bool(self, key, default=False):
        raw = self.get(key, None if default is None else ("1" if default else "0"))
        if raw is None:
            return default
        return str(raw).strip().lower() in ("1", "true", "yes", "on", "y")

    def path_value(self, key, default=None, required=True):
        """取一个路径：展开 ~ / 变量；可选校验存在性由调用方决定。"""
        raw = self.get(key, default, required=required)
        if raw is None:
            return None
        return os.path.abspath(expand(str(raw)))

    def set_temp(self, key, value):
        """测试/单次运行覆盖用（不进配置文件）。"""
        os.environ[self.env_prefix + key] = str(value)

    def __repr__(self):
        return "<Conf %s path=%s keys=%d>" % (self.app, self.path, len(self.load()))


if __name__ == "__main__":
    app = sys.argv[1] if len(sys.argv) > 1 else "demo-skill"
    conf = Conf(app)
    print("配置文件：", conf.path, "存在" if os.path.exists(conf.path) else "不存在（用默认值）")
    data = conf.load()
    if conf.load_error:
        print("读取失败：", conf.load_error)
    if not data:
        print("没有可显示的键；复制模板后重试。")
    for k in sorted(data):
        v = conf.get(k) or ""
        sensitive = any(s in k.upper() for s in ("SECRET", "TOKEN", "PASSWORD", "KEY"))
        print("  %-24s = %s" % (k, "<已隐去，长度 %d>" % len(v) if sensitive and v else v))
