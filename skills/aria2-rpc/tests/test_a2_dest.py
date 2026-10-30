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
import json
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
        # 夹具目录在 /var/folders（家目录之外、系统盘）：默认会被落点策略拒绝，测试里放行
        os.environ["A2_ALLOW_CREATE"] = "1"
        self.mod = load_script("a2dest_under_test", DEST)

    def tearDown(self):
        os.environ.pop("A2_DEST_CONF", None)
        os.environ.pop("A2_ALLOW_CREATE", None)
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

    # ---- check：落点策略（原来压在 a2 里） ----
    def test_check_creates_dir_with_allow_create(self):
        os.environ["A2_ALLOW_CREATE"] = "1"
        try:
            target = os.path.join(self.tmp, "new", "sub")
            rc, out, _ = self.run_cli("check", target)
            self.assertEqual(rc, 0)
            self.assertEqual(out, os.path.abspath(target))
            self.assertTrue(os.path.isdir(target))
        finally:
            os.environ.pop("A2_ALLOW_CREATE", None)

    def test_check_refuses_system_disk_path(self):
        # 不在家目录内、又会被建在系统盘上（外接盘没挂载的样子）——默认拒绝
        os.environ.pop("A2_ALLOW_CREATE", None)
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("check", "/nonexistent-mount-point-xyz/media")
        msg = str(ctx.exception)
        self.assertIn("落点不可用", msg)
        self.assertIn("A2_ALLOW_CREATE", msg)

    def test_check_refuses_when_space_below_threshold(self):
        os.environ["A2_ALLOW_CREATE"] = "1"
        os.environ["A2_MIN_FREE_GB"] = str(10 ** 9)
        try:
            mod = load_script("a2dest_tight", DEST)       # 阈值在 import 时读入
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    mod.main(["a2-dest", "check", self.tmp])
            self.assertIn("剩余空间不足", str(ctx.exception))
        finally:
            os.environ.pop("A2_MIN_FREE_GB", None)
            os.environ.pop("A2_ALLOW_CREATE", None)

    def test_check_json(self):
        os.environ["A2_ALLOW_CREATE"] = "1"
        try:
            rc, out, _ = self.run_cli("check", self.tmp, "--json")
            self.assertEqual(rc, 0)
            payload = json.loads(out)
            self.assertEqual(payload["dir"], os.path.abspath(self.tmp))
            self.assertIn("free_gb", payload)
        finally:
            os.environ.pop("A2_ALLOW_CREATE", None)

    def test_set_uses_check(self):
        os.environ["A2_ALLOW_CREATE"] = "1"
        try:
            target = os.path.join(self.tmp, "dl2")
            rc, out, _ = self.run_cli("set", target)
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isdir(target))
            with open(self.conf) as fh:
                self.assertIn("download-dir=%s" % os.path.abspath(target), fh.read())
        finally:
            os.environ.pop("A2_ALLOW_CREATE", None)

    def test_unknown_arg(self):
        rc, _out, err = self.run_cli("bogus")
        self.assertEqual(rc, 2)
        self.assertIn("a2-dest", err)


if __name__ == "__main__":
    unittest.main()
