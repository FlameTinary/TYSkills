"""a2-search（skill 层搜索）测试：HTML 抽磁力、cmd 源、过滤、去重、全网发现

跑：python3 -m unittest discover -s tests -v
全部离线：HTML 站点用 file:// 夹具，cmd 源用 scripts/search-source-demo.py。
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEARCH = os.path.join(ROOT, "scripts", "a2-search")
DEMO = os.path.join(ROOT, "scripts", "search-source-demo.py")

IH_MOVIE = "1111111111111111111111111111111111111111"
IH_TV = "2222222222222222222222222222222222222222"
IH_EP = "3333333333333333333333333333333333333333"
IH_DUP = IH_MOVIE
IH_OTHER = "4444444444444444444444444444444444444444"

PAGE = """<html><body><table>
<tr><td><a href="magnet:?xt=urn:btih:%s&dn=Dune.Part.Two.2024.2160p.WEB-DL">Dune Part Two 2024 2160p WEB-DL</a></td>
    <td>18.4 GB</td><td>SE 231</td></tr>
<tr><td><a href="/detail/2"><img src="m.png"></a><a href="magnet:?xt=urn:btih:%s">The Bear S03 COMPLETE 1080p</a></td>
    <td>12 GB</td><td>SE 45</td></tr>
<tr><td><a href="magnet:?xt=urn:btih:%s">Some Show S03E05 1080p</a></td><td>1.2 GB</td></tr>
<tr><td><a href="magnet:?xt=urn:btih:%s">Ubuntu 24.04 ISO</a></td><td>5.9 GB</td></tr>
<tr><td><a href="magnet:?xt=urn:btih:%s">dup of the movie</a></td><td>18.4 GB</td></tr>
</table></body></html>
""" % (IH_MOVIE, IH_TV, IH_EP, IH_OTHER, IH_DUP)


def load_script(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="a2search-")
        self.page = os.path.join(self.tmp, "page.html")
        with open(self.page, "w") as fh:
            fh.write(PAGE)
        self.conf = os.path.join(self.tmp, "search-sites.conf")
        os.environ["A2_SITES_CONF"] = self.conf
        os.environ.pop("A2_SEARCH_PROXY", None)
        self.mod = load_script("a2search_under_test", SEARCH)

    def tearDown(self):
        os.environ.pop("A2_SITES_CONF", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_conf(self, *lines):
        with open(self.conf, "w") as fh:
            fh.write("\n".join(lines) + "\n")

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = self.mod.main(["a2-search"] + list(args))
        return rc, out.getvalue(), err.getvalue()

    def json_rows(self, *args):
        rc, out, _err = self.run_cli(*(list(args) + ["--json"]))
        self.assertEqual(rc, 0)
        return json.loads(out[out.index("["):])

    # ---- 配置 ----
    def test_first_run_creates_template(self):
        self.assertFalse(os.path.exists(self.conf))
        rc, _out, err = self.run_cli("sites")
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(self.conf))
        self.assertIn("已生成站点配置", err)
        with open(self.conf) as fh:
            body = fh.read()
        self.assertIn("websearch=", body)
        self.assertIn("site=", body)       # 注释里的示例
        live = [l for l in body.splitlines() if l.startswith("site=")]
        self.assertEqual(live, [], "不该内置任何可用的资源站（站点全部由使用者配置）")

    def test_no_sites_errors(self):
        self.write_conf("# 空配置")
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("电影")
        self.assertIn("还没有配置站点", str(ctx.exception))

    def test_sites_listing(self):
        self.write_conf("site=夹具|file://%s" % self.page, "websearch=https://example.org/?q={query}")
        rc, out, _ = self.run_cli("sites")
        self.assertEqual(rc, 0)
        self.assertIn("夹具", out)
        self.assertIn("HTML", out)

    # ---- HTML 解析 + 过滤 ----
    def test_html_parse_and_default_filter(self):
        self.write_conf("site=夹具|file://%s" % self.page)
        rows = self.json_rows("什么都行")
        titles = [r["title"] for r in rows]
        self.assertEqual(len(rows), 2, "默认过滤只留电影 + 整季剧集：%s" % titles)
        self.assertIn("Dune Part Two 2024 2160p WEB-DL", titles)
        self.assertIn("The Bear S03 COMPLETE 1080p", titles)
        dune = [r for r in rows if "Dune" in r["title"]][0]
        self.assertEqual(dune["size"], "18.4 GB")
        self.assertEqual(dune["seeds"], 231)
        self.assertEqual(dune["cat"], "Movies")
        self.assertEqual(dune["ih"], IH_MOVIE)
        self.assertTrue(dune["magnet"].startswith("magnet:?xt=urn:btih:"))
        bear = [r for r in rows if "Bear" in r["title"]][0]
        self.assertEqual(bear["size"], "12 GB", "体积不能用上一行的")
        self.assertEqual(bear["seeds"], 45)

    def test_all_keeps_episodes_and_other(self):
        self.write_conf("site=夹具|file://%s" % self.page)
        rows = self.json_rows("什么都行", "--all")
        self.assertEqual(len(rows), 4, "5 条磁力里有 1 条重复")
        ihs = [r["ih"] for r in rows]
        self.assertEqual(len(ihs), len(set(ihs)), "按 infohash 去重")
        self.assertIn(IH_EP, ihs)
        self.assertIn(IH_OTHER, ihs)

    def test_res_and_prefer(self):
        self.write_conf("site=夹具|file://%s" % self.page)
        rows = self.json_rows("x", "--res", "2160p", "--all")
        self.assertEqual([r["ih"] for r in rows], [IH_MOVIE])
        rows = self.json_rows("x", "--all", "--prefer", "bear")
        self.assertEqual(rows[0]["ih"], IH_TV, "--prefer 命中标题的排最前")

    def test_min_seeds_skips_unknown(self):
        self.write_conf("site=夹具|file://%s" % self.page)
        rows = self.json_rows("x", "--all", "--min-seeds", "100")
        ihs = [r["ih"] for r in rows]
        self.assertNotIn(IH_TV, ihs, "做种 45 < 100，要被滤掉")
        self.assertIn(IH_MOVIE, ihs)
        self.assertIn(IH_EP, ihs, "seeds 未知的行不参与阈值过滤")
        self.assertIn(IH_OTHER, ihs)

    def test_table_output(self):
        self.write_conf("site=夹具|file://%s" % self.page)
        rc, out, _ = self.run_cli("x")
        self.assertEqual(rc, 0)
        self.assertIn("Dune Part Two", out)
        self.assertIn("a2 add --dir", out, "要告诉人下一步怎么下")

    def test_site_filter(self):
        self.write_conf("site=夹具|file://%s" % self.page, "site=另一个|file:///nonexistent.html")
        rows = self.json_rows("x", "--site", "夹具")
        self.assertTrue(rows)
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("x", "--site", "不存在的站")
        self.assertIn("没有叫", str(ctx.exception))

    # ---- cmd 源 ----
    def test_cmd_source(self):
        self.write_conf("site=本地演示|cmd:python3 %s" % DEMO)
        rows = self.json_rows("示例")
        self.assertTrue(rows)
        self.assertTrue(all(r["magnet"].startswith("magnet:?xt=urn:btih:") for r in rows))
        self.assertTrue(any(r["cat"] == "TV" for r in rows))

    def test_cmd_source_failure_is_reported(self):
        self.write_conf("site=坏源|cmd:false")
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("x")
        self.assertIn("搜索源失败", str(ctx.exception))

    def test_cmd_source_bad_json_is_reported(self):
        self.write_conf("site=坏源|cmd:echo not-json")
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("x")
        self.assertIn("不是 JSON", str(ctx.exception))

    # ---- 全网发现 ----
    def test_discover_extracts_links(self):
        page = os.path.join(self.tmp, "results.html")
        with open(page, "w") as fh:
            fh.write('<html><body>'
                     '<a href="https://example.org/a">Example A — 资源索引</a>'
                     '<a href="//www.bing.com/l?uddg=https%3A%2F%2Fexample.net%2Fb">Example B</a>'
                     '<a href="javascript:void(0)">点击</a>'
                     '</body></html>')
        self.write_conf("websearch=file://%s" % page)
        rows = self.json_rows("--discover", "关键词")
        urls = [r["url"] for r in rows]
        self.assertIn("https://example.org/a", urls)
        self.assertIn("https://example.net/b", urls, "搜索页的 uddg= 跳转链接要解出来")
        self.assertFalse(any(u.startswith("javascript") for u in urls))

    def test_discover_without_websearch(self):
        self.write_conf("site=夹具|file://%s" % self.page)
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("--discover", "x")
        self.assertIn("websearch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
