"""a2 CLI 行为测试（unittest，无第三方依赖；不需要真实的 aria2 守护进程）

跑：python3 -m unittest discover -s tests -v
覆盖验收点：
  - a2 add --help 里没有 -m/-t/-P/-flat/-d
  - a2 add 不传 --dir 时报错，传了就只下到该目录（不改名/不移动）
  - -p / -o 仍然生效
  - 分类/暂存/入库相关代码（route/sweep/MEDIA_ROOT…）已不存在
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A2 = os.path.join(ROOT, "scripts", "a2")
MAGNET = "magnet:?xt=urn:btih:" + "a" * 40
REMOVED = ("-m", "--movie", "-t", "--tv", "-P", "--private", "-flat", "--flat", "-d")


def load_script(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class AddTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="a2test-")
        os.environ["A2_CONF"] = os.path.join(cls.tmp, "aria2.conf")
        os.environ["A2_RC"] = os.path.join(cls.tmp, "a2.conf")
        cls.mod = load_script("a2_under_test", A2)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.calls = []
        self.added = []

        def fake_rpc(method, params=None):
            self.calls.append((method, params))
            self.added.append(method)
            return "gid0001"

        self.mod.rpc = fake_rpc
        self.dest = tempfile.mkdtemp(prefix="a2dest-")

    def tearDown(self):
        shutil.rmtree(self.dest, ignore_errors=True)

    # ---- 帮助文本 ----
    def test_add_help_has_no_removed_flags(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.mod.cmd_add(["--help"])
        help_text = buf.getvalue()
        self.assertIn("--dir", help_text)
        for flag in REMOVED:
            self.assertNotIn(flag + " ", help_text)
            self.assertNotIn(flag + "\n", help_text)
            self.assertNotIn("%s " % flag, help_text)
        for word in ("暂存", "入库"):
            self.assertNotIn(word, help_text)

    # ---- 必须显式 --dir ----
    def test_missing_dir_errors_out(self):
        with self.assertRaises(SystemExit) as ctx, contextlib.redirect_stderr(io.StringIO()):
            self.mod.cmd_add([MAGNET])
        self.assertIn("--dir", str(ctx.exception))
        self.assertEqual(self.calls, [], "不该在缺目录时打出任何 RPC")

    def test_dir_only_used(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.cmd_add(["--dir", self.dest, MAGNET])
        self.assertEqual(len(self.calls), 1)
        method, params = self.calls[0]
        self.assertEqual(method, "aria2.addUri")
        self.assertEqual(params[0], [MAGNET])
        self.assertEqual(params[1]["dir"], os.path.abspath(self.dest))
        self.assertEqual(os.listdir(self.dest), [], "add 不该在目标目录里放别的文件（不改名/不搬动）")

    def test_pause_and_out(self):
        url = "https://example.invalid/x.mkv"
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.cmd_add(["--dir", self.dest, "-p", "-o", "renamed.mkv", url])
        opts = self.calls[0][1][1]
        self.assertEqual(opts["pause"], "true")
        self.assertEqual(opts["out"], "renamed.mkv")
        self.assertEqual(opts["dir"], os.path.abspath(self.dest))

    def test_removed_flags_rejected(self):
        for flag in REMOVED:
            with self.subTest(flag=flag):
                self.calls.clear()
                with self.assertRaises(SystemExit) as ctx, contextlib.redirect_stderr(io.StringIO()):
                    self.mod.cmd_add([flag, self.dest, MAGNET])
                self.assertIn("已移除", str(ctx.exception))
                self.assertEqual(self.calls, [])

    def test_torrent_file(self):
        tor = os.path.join(self.dest, "x.torrent")
        with open(tor, "wb") as fh:
            fh.write(b"d4:name4:teste")
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.cmd_add(["--dir", self.dest, tor])
        method, params = self.calls[0]
        self.assertEqual(method, "aria2.addTorrent")
        self.assertEqual(params[2]["dir"], os.path.abspath(self.dest))

    def test_urls_txt(self):
        lst = os.path.join(self.dest, "urls.txt")
        with open(lst, "w") as fh:
            fh.write("https://example.invalid/a.zip\n# 注释\nhttps://example.invalid/b.zip\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.cmd_add(["--dir", self.dest, lst])
        self.assertEqual([c[0] for c in self.calls], ["aria2.addUri", "aria2.addUri"])
        for _method, params in self.calls:
            self.assertEqual(params[1]["dir"], os.path.abspath(self.dest))

    def test_unknown_flag_rejected(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.mod.cmd_add(["--nope", self.dest, MAGNET])

    # ---- 落点决策代码已移除 ----
    def test_no_classification_machinery_left(self):
        for name in ("route", "target_name", "sweep", "done_entries", "media_guard", "find_ffprobe"):
            self.assertFalse(hasattr(self.mod, name), "%s 应该已经删除" % name)
        for name in ("MEDIA_ROOT", "STAGING", "MOVIE_DIR", "TV_DIR", "PRIVATE_DIR"):
            self.assertFalse(hasattr(self.mod, name), "%s 应该已经删除" % name)


class HelpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="a2test-help-")
        os.environ["A2_CONF"] = os.path.join(cls.tmp, "aria2.conf")
        os.environ["A2_RC"] = os.path.join(cls.tmp, "a2.conf")
        cls.mod = load_script("a2_under_test_help", A2)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_top_level_help(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.mod.main(["a2", "--help"])
        text = buf.getvalue()
        self.assertIn("a2 add --dir DIR", text)
        self.assertIn("a2 grab", text)
        self.assertNotIn("sweep", text)
        for flag in REMOVED:
            self.assertNotIn("%s " % flag, text)
            self.assertNotIn("|%s|" % flag, text)


if __name__ == "__main__":
    unittest.main()
