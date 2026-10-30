"""a2-dest（skill 层落点配置）测试

跑：python3 -m unittest discover -s tests -v
覆盖验收点：
  - 首次运行按当前 OS 生成默认下载目录并持久化
  - 修改默认目录后持久化，后续读取沿用新值
  - media-root 未设置时等于 download-dir
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
DEST = os.path.join(ROOT, "scripts", "a2-dest")


def load_script(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class DestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="a2dest-")
        self.conf = os.path.join(self.tmp, "dest.conf")
        os.environ["A2_DEST_CONF"] = self.conf
        self.mod = load_script("a2dest_under_test", DEST)

    def tearDown(self):
        os.environ.pop("A2_DEST_CONF", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = self.mod.main(["a2-dest"] + list(args))
        return rc, out.getvalue().strip(), err.getvalue().strip()

    def test_first_run_creates_os_default(self):
        self.assertFalse(os.path.exists(self.conf))
        rc, out, err = self.run_cli()
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(self.conf), "首次运行应落盘配置")
        self.assertTrue(out.endswith("Downloads"), "默认值应是当前 OS 的下载目录：%r" % out)
        self.assertEqual(out, self.mod.default_download_dir())
        with open(self.conf) as fh:
            self.assertIn("download-dir=%s" % out, fh.read())

    def test_set_persists_and_is_used(self):
        target = os.path.join(self.tmp, "dl")
        rc, out, _ = self.run_cli("set", target)
        self.assertEqual(rc, 0)
        self.assertEqual(out, os.path.abspath(target))
        self.assertTrue(os.path.isdir(target), "set 应该把目录建出来")
        # 新进程/新模块实例读到的必须是改过的值（持久化）
        self.mod = load_script("a2dest_again", DEST)
        rc, out, _ = self.run_cli()
        self.assertEqual(rc, 0)
        self.assertEqual(out, os.path.abspath(target))

    def test_media_root_defaults_to_download_dir(self):
        rc, out, _ = self.run_cli()
        rc, media, _ = self.run_cli("media")
        self.assertEqual(media, out)

    def test_media_root_can_be_set(self):
        media = os.path.join(self.tmp, "media")
        rc, out, _ = self.run_cli("media", "set", media)
        self.assertEqual(rc, 0)
        self.assertEqual(out, os.path.abspath(media))
        rc, out, _ = self.run_cli("media")
        self.assertEqual(out, os.path.abspath(media))

    def test_json(self):
        rc, out, _ = self.run_cli("--json")
        self.assertEqual(rc, 0)
        self.assertIn('"download-dir"', out)
        self.assertIn('"media-root"', out)
        self.assertIn(self.conf, out)

    def test_unknown_arg(self):
        rc, _out, err = self.run_cli("bogus")
        self.assertEqual(rc, 2)
        self.assertIn("a2-dest", err)


if __name__ == "__main__":
    unittest.main()
