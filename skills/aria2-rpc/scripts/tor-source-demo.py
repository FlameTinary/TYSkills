#!/usr/bin/env python3
"""tor-source-demo —— a2 的「离线自测搜索源」：不联网，用来验证 a2 find / a2 grab 的整条流程。

配置（aria2.conf 里写一行即可）：
    tor-source-cmd=python3 <本文件绝对路径>
之后：
    a2 find 示例                     # 默认过滤（电影留、剧集要整季、单集与噪音剔除）
    a2 find 示例 --all               # 关掉过滤，连非影视分类一起看
    a2 find 示例 --json              # 直接看源输出的规范化结果
    a2 grab 2 --no-verify            # 走入库流程（演示行是假磁力，校验必然失败，--no-verify 才会入库）

数据来源：默认用下面内置的 SAMPLE；也可以用 A2_TOR_DEMO_ROWS 指向自己的 JSON 文件
（数组，或 {"rows":[...]}），文件里同样按契约给字段，见 references/tor-source.md。
分页：按 A2_PAGE 返回第 N 页（每页 A2_TOR_DEMO_PAGE_SIZE 条，默认 20）。
"""
import json, os, sys

PAGE_SIZE = int(os.environ.get("A2_TOR_DEMO_PAGE_SIZE", "20"))
QUERY = (os.environ.get("A2_QUERY") or "").strip()
PAGE = max(1, int(os.environ.get("A2_PAGE", "1") or 1))

# 演示行：故意覆盖各种情况 —— 电影/整季剧集/单集/噪音/非影视，以及
# 只给 info_hash（由 a2 拼磁力）、不给 category（由 a2 按标题猜）、size 用字符串 等写法。
SAMPLE = [
    {"title": "示例电影.Example.Movie.2024.1080p.WEB-DL.x264-GROUP", "category": "Movies",
     "info_hash": "0123456789abcdef0123456789abcdef01234567", "size_bytes": 8_589_934_592,
     "seeders": 42, "leechers": 7, "url": "https://example.invalid/detail/1", "source": "demo"},
    {"title": "示例剧集 Example Show S01 COMPLETE 1080p BluRay", "category": "TV",
     "magnet": "magnet:?xt=urn:btih:fedcba9876543210fedcba9876543210fedcba98&dn=Example+Show+S01",
     "size": "24.6 GB", "seeders": 18, "leechers": 3, "url": "https://example.invalid/detail/2",
     "source": "demo"},
    {"title": "示例剧集 Example Show S01E03 1080p WEB-DL", "category": "TV",
     "magnet": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
     "size_bytes": 2_147_483_648, "seeders": 99, "leechers": 1, "source": "demo"},
    {"title": "示例电影.Example.Movie.2024.3D.HSBS.mkv", "category": "Movies",
     "magnet": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
     "size_bytes": 12_884_901_888, "seeders": 5, "source": "demo"},
    {"title": "示例资料包 example-scan-pack.zip", "category": "Other",
     "magnet": "magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc",
     "size_bytes": 1_073_741_824, "seeders": 3, "source": "demo"},
    # 没有 category：a2 按标题猜（这一条会被猜成 TV 并因「整季」通过过滤）
    {"title": "另一部剧 Another Show S02 2160p Complete",
     "magnet": "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd",
     "size_gb": 51.2, "seeds": 12, "leech": 2, "source": "demo"},
    # 只有 infohash、没有标题中的年份/质量词 → a2 归成 Other（--all 可见）
    {"title": "无磁力链接但有 infohash 的条目", "trackers": ["udp://tracker.example.invalid:1337/announce"],
     "info_hash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "size_bytes": 734_003_200, "seeders": 1},
    # 缺 title：a2 会丢掉这一行（源的坏数据不该中断整次搜索）
    {"category": "Movies", "magnet": "magnet:?xt=urn:btih:ffffffffffffffffffffffffffffffffffffffff"},
]


def load_rows():
    path = (os.environ.get("A2_TOR_DEMO_ROWS") or "").strip()
    if not path:
        return SAMPLE
    path = os.path.expanduser(path)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print("tor-source-demo: 读不了 %s: %s" % (path, exc), file=sys.stderr)
        sys.exit(1)
    if isinstance(data, dict):
        data = data.get("rows") or data.get("results") or []
    if not isinstance(data, list):
        print("tor-source-demo: %s 里应该是 JSON 数组或 {\"rows\":[...]}" % path, file=sys.stderr)
        sys.exit(1)
    return data


def main():
    rows = [r for r in load_rows() if isinstance(r, dict)]
    if QUERY:
        low = QUERY.lower()
        rows = [r for r in rows if low in str(r.get("title") or r.get("name") or "").lower()]
    total = len(rows)
    start = (PAGE - 1) * PAGE_SIZE
    page = rows[start:start + PAGE_SIZE]
    if not page:
        print("tor-source-demo: 第 %d 页没有内容（关键词 %r，共 %d 条）" % (PAGE, QUERY, total),
              file=sys.stderr)
    print(json.dumps({"rows": page, "page": PAGE, "total": total}, ensure_ascii=False))


if __name__ == "__main__":
    main()
