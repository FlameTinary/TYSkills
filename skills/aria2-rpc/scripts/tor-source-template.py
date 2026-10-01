#!/usr/bin/env python3
"""tor-source-template —— 把「你自己的站点」接成 a2 搜索源的骨架。

a2 只认一条契约：你的脚本把结果以 JSON 打到 stdout，一行一条。填完下面三处即可用：

  ① SEARCH_URL / REQUEST_HEADERS —— 你站点的搜索地址与请求头（UA、Cookie 等）
  ② parse(html_or_json)          —— 把响应变成 rows（字段名见下）
  ③ 在 aria2.conf 里登记：
         tor-source-cmd=python3 <本文件绝对路径>        # 或用 {query}/{page} 占位符：
         tor-source-cmd=python3 <本文件绝对路径> --q {query} --p {page}

指向你自己的脚本时，a2 还会通过环境变量把参数传进来（三者同时可用）：
     A2_QUERY=原始关键词   A2_PAGE=页码(从 1 起)   A2_PAGES=本次总共要几页

每行只需要「标题 + 磁力或 infohash」两样就能被 a2 用起来，其余字段缺失都不致命：
     title       必填   torrent 名称
     magnet      二选一 以 magnet:?xt=urn:btih: 开头的完整磁力
     info_hash   二选一 40 位（或 32 位）hex；a2 会拼成磁力，trackers 可选
     size_bytes  可选   字节数（想给人类可读字符串就用 "size": "3.5 GB"）
     seeders / leechers、category（Movies/TV/…）、url（详情页）、source（源名）均可选
完整字段表与别名：references/tor-source.md

硬性要求（a2 会严格照做，避免「源挂了却显示成没有结果」）：
  * stdout 只打 JSON，不要打日志/进度（日志走 stderr）
  * 失败就非零退出（a2 会把退出码与 stderr 末尾原样报给用户）
  * 别自己长时间阻塞；a2 会对整个命令加超时（默认 60s，A2_TOR_TIMEOUT 可调）
"""
import json, os, re, sys
import urllib.error, urllib.parse, urllib.request

# ① 填这里 -------------------------------------------------------------------
SEARCH_URL = "https://EXAMPLE.invalid/search?q={query}&page={page}"   # {query} 会被 URL 编码后替换
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    # "Cookie": "…",            # 需要登录/通行证时在这里补
}
PAGE_START = 1                  # 站点页码从 1 还是从 0 开始
# ---------------------------------------------------------------------------

QUERY = (os.environ.get("A2_QUERY") or "").strip()
PAGE = max(1, int(os.environ.get("A2_PAGE", "1") or 1))


def fetch(url):
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def parse(body):
    """② 把响应变成 rows。默认实现按「页面里到处是 magnet 链接」这种最简单的情况写。
    换成 JSON API 时，直接 json.loads(body) 后映射字段即可。
    """
    rows, seen = [], set()
    for mag in re.findall(r'magnet:\?xt=urn:btih:[0-9a-zA-Z]+[^"\'<>\\ ]*', body):
        mag = mag.replace("&amp;", "&")
        ih = re.search(r"btih:([0-9a-zA-Z]+)", mag)
        if not ih or ih.group(1) in seen:
            continue
        seen.add(ih.group(1))
        dn = re.search(r"[&?]dn=([^&]+)", mag)
        rows.append({
            "title": urllib.parse.unquote_plus(dn.group(1)) if dn else ih.group(1),
            "magnet": mag,
            "seeders": 0,                     # 拿不到就留 0（a2 的 --min-seeds 才会按需过滤）
            "category": "",                   # 留空 = 让 a2 按标题猜 Movies/TV
            "source": os.path.basename(__file__),
        })
    return rows


def main():
    if "EXAMPLE.invalid" in SEARCH_URL:
        print("tor-source-template: 先把 SEARCH_URL 改成你自己站点的搜索地址"
              "（现在还是占位符），再看 references/tor-source.md。", file=sys.stderr)
        return 2
    url = SEARCH_URL.replace("{query}", urllib.parse.quote_plus(QUERY)) \
                    .replace("{page}", str(PAGE + PAGE_START - 1))
    try:
        body = fetch(url)
    except (urllib.error.URLError, OSError) as exc:
        print("tor-source-template: 取页面失败 %s: %s" % (url, exc), file=sys.stderr)
        return 1                                   # 非零退出：a2 会如实报错，不会当成 0 条
    rows = parse(body)
    print(json.dumps({"rows": rows}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
