#!/usr/bin/env python3
"""
Aria2 JSON-RPC 客户端工具
用于通过 RPC 接口控制 aria2c 下载引擎
"""
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any

CONF = os.path.expanduser(os.environ.get("A2_CONF", "~/.aria2/aria2.conf"))


def _conf_get(key: str, default: str = "") -> str:
    """从 aria2.conf 读一个选项（端口/密钥一般不用手写，直接从配置里取）。"""
    try:
        with open(CONF) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return default


class Aria2Client:
    def __init__(self, host: str = "127.0.0.1", port: Optional[int] = None, secret: Optional[str] = None):
        # 不传就跟随 ~/.aria2/aria2.conf（端口默认 6800、密钥默认空）
        if port is None:
            port = int(_conf_get("rpc-listen-port", "6800"))
        if secret is None:
            secret = os.environ.get("A2_SECRET") or _conf_get("rpc-secret", "")
        self.url = f"http://{host}:{port}/jsonrpc"
        self.secret = secret
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _call(self, method: str, params: Optional[List] = None) -> Dict[str, Any]:
        """调用 aria2 RPC 方法"""
        if params is None:
            params = []
        if self.secret:
            params = [f"token:{self.secret}"] + params

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if "error" in result:
                    raise Exception(f"RPC 错误: {result['error']}")
                return result.get("result", {})
        except urllib.error.HTTPError as e:
            # aria2 用 HTTP 400 + JSON 体表达 RPC 错误（比如 "GID#… cannot be unpaused now"）。
            # 不单独处理的话只会看到没有信息量的 "HTTP Error 400: Bad Request"。
            msg = None
            try:
                detail = json.loads(e.read().decode("utf-8")).get("error", {})
                msg = detail.get("message") if isinstance(detail, dict) else detail
            except Exception:
                msg = None
            raise Exception(f"RPC 错误: {msg or 'HTTP %s %s' % (e.code, e.reason)}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"无法连接 aria2 RPC ({self.url}): {e}")

    # ========== 任务管理 ==========

    def add_uri(self, uris: List[str], options: Optional[Dict] = None) -> str:
        """添加下载任务，返回 GID"""
        params = [uris]
        if options:
            params.append(options)
        return self._call("aria2.addUri", params)

    def add_torrent(self, torrent_base64: str, uris: Optional[List[str]] = None, options: Optional[Dict] = None) -> str:
        """添加种子文件任务（传入base64编码的种子内容）"""
        params = [torrent_base64]
        if uris:
            params.append(uris)
        if options:
            params.append(options)
        return self._call("aria2.addTorrent", params)

    def tell_status(self, gid: str, keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """查询单个任务状态"""
        params = [gid]
        if keys:
            params.append(keys)
        return self._call("aria2.tellStatus", params)

    def tell_active(self, keys: Optional[List[str]] = None) -> List[Dict]:
        """获取活动中的下载任务"""
        params = []
        if keys:
            params.append(keys)
        return self._call("aria2.tellActive", params)

    def tell_waiting(self, offset: int = 0, num: int = 100, keys: Optional[List[str]] = None) -> List[Dict]:
        """获取等待中的任务"""
        params = [offset, num]
        if keys:
            params.append(keys)
        return self._call("aria2.tellWaiting", params)

    def tell_stopped(self, offset: int = 0, num: int = 100, keys: Optional[List[str]] = None) -> List[Dict]:
        """已停止/已完成的任务"""
        params = [offset, num]
        if keys:
            params.append(keys)
        return self._call("aria2.tellStopped", params)

    def pause(self, gid: str) -> str:
        """暂停任务"""
        return self._call("aria2.pause", [gid])

    def unpause(self, gid: str) -> str:
        """继续任务"""
        return self._call("aria2.unpause", [gid])

    def remove(self, gid: str) -> str:
        """移除任务（保留已下载文件）"""
        return self._call("aria2.remove", [gid])

    def remove_download_result(self, gid: str) -> str:
        """从已完成列表中删除记录"""
        return self._call("aria2.removeDownloadResult", [gid])

    # ========== 全局状态 ==========

    def get_global_stat(self) -> Dict[str, Any]:
        """获取全局下载统计"""
        return self._call("aria2.getGlobalStat")

    def tell_version(self) -> Dict[str, Any]:
        """获取 aria2 版本"""
        return self._call("aria2.getVersion")

    # ========== BT 相关 ==========

    def get_servers(self, gid: str) -> Dict[str, Any]:
        """获取任务的服务器信息"""
        return self._call("aria2.getServers", [gid])

    def add_magnet(self, magnet_uri: str, options: Optional[Dict] = None) -> str:
        """添加磁力链接任务"""
        return self.add_uri([magnet_uri], options)


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} MB"
    else:
        return f"{size_bytes / (1024*1024*1024):.2f} GB"


def format_speed(speed_bytes: int) -> str:
    """格式化下载速度"""
    return f"{format_size(speed_bytes)}/s"


def print_task_summary(tasks: List[Dict]):
    """打印任务列表摘要"""
    if not tasks:
        print("  (无任务)")
        return
    for t in tasks:
        gid = t.get("gid", "?")
        status = t.get("status", "?")
        total = int(t.get("totalLength", 0))
        completed = int(t.get("completedLength", 0))
        speed = int(t.get("downloadSpeed", 0))
        name = t.get("files", [{}])[0].get("path", "").split("/")[-1] or "(获取元信息中...)"

        progress = f"{(completed/total*100):.1f}%" if total > 0 else "0%"
        print(f"  [{status:8s}] {progress:>7s}  {format_speed(speed):>12s}  {name[:50]}")
        print(f"             GID: {gid}")


def main():
    """命令行入口"""
    import argparse
    parser = argparse.ArgumentParser(description="Aria2 RPC 客户端")
    parser.add_argument("--host", default="127.0.0.1", help="RPC 主机")
    parser.add_argument("--port", type=int, default=None, help="RPC 端口（默认读 ~/.aria2/aria2.conf）")
    parser.add_argument("--secret", default=None, help="RPC 密钥（默认读 ~/.aria2/aria2.conf 的 rpc-secret）")

    sub = parser.add_subparsers(dest="command", help="子命令")

    # 添加任务
    p_add = sub.add_parser("add", help="添加下载任务")
    p_add.add_argument("uri", help="下载链接 (HTTP/FTP/磁力)")
    p_add.add_argument("--dir", help="下载目录")

    # 状态查询
    sub.add_parser("status", help="查看所有任务状态")
    p_gid = sub.add_parser("info", help="查看单个任务详情")
    p_gid.add_argument("gid", help="任务 GID")

    # 控制操作
    p_pause = sub.add_parser("pause", help="暂停任务")
    p_pause.add_argument("gid", help="任务 GID")
    p_resume = sub.add_parser("resume", help="继续任务")
    p_resume.add_argument("gid", help="任务 GID")
    p_rm = sub.add_parser("remove", help="移除任务")
    p_rm.add_argument("gid", help="任务 GID")

    # 全局统计
    sub.add_parser("stats", help="全局统计")
    sub.add_parser("version", help="查看 aria2 版本")

    args = parser.parse_args()
    client = Aria2Client(host=args.host, port=args.port, secret=args.secret)

    try:
        if args.command == "add":
            opts = {}
            if args.dir:
                opts["dir"] = args.dir
            gid = client.add_uri([args.uri], opts if opts else None)
            print(f"✅ 任务已添加，GID: {gid}")

        elif args.command == "status":
            print("📥 活动任务:")
            active = client.tell_active()
            print_task_summary(active)

            print("\n⏳ 等待任务:")
            waiting = client.tell_waiting(0, 20)
            print_task_summary(waiting)

            print("\n✅ 已完成/停止:")
            stopped = client.tell_stopped(0, 10)
            print_task_summary(stopped)

        elif args.command == "info":
            t = client.tell_status(args.gid)
            print(json.dumps(t, indent=2, ensure_ascii=False))

        elif args.command == "pause":
            client.pause(args.gid)
            print(f"⏸️  任务 {args.gid} 已暂停")

        elif args.command == "resume":
            client.unpause(args.gid)
            print(f"▶️  任务 {args.gid} 已继续")

        elif args.command == "remove":
            client.remove(args.gid)
            print(f"🗑️  任务 {args.gid} 已移除")

        elif args.command == "stats":
            s = client.get_global_stat()
            print(f"活动任务: {s.get('numActive', 0)}")
            print(f"等待任务: {s.get('numWaiting', 0)}")
            print(f"已停止: {s.get('numStopped', 0)}")
            print(f"总下载速度: {format_speed(int(s.get('downloadSpeed', 0)))}")
            print(f"总上传速度: {format_speed(int(s.get('uploadSpeed', 0)))}")

        elif args.command == "version":
            v = client.tell_version()
            print(f"aria2 版本: {v.get('version', '?')}")
            print(f"功能特性: {', '.join(v.get('enabledFeatures', []))}")

        else:
            parser.print_help()

    except (ConnectionError, Exception) as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
