"""a2-verify（skill 层资源校验）测试：种子解析 + 校验结论（RPC 全假）

跑：python3 -m unittest discover -s tests -v
"""
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFY = os.path.join(ROOT, "scripts", "a2-verify")

TORRENT = b"d8:announce3:url4:infod4:name4:test6:lengthi100eee"


def load_script(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class FakeA2:
    """够用的假 RPC：记录调用，按脚本返回既定状态。"""

    def __init__(self, status="complete", error_code="0"):
        self.calls = []
        self.status = status
        self.error_code = error_code

    def rpc(self, method, params=None):
        self.calls.append((method, params))
        if method == "aria2.addUri":
            return "gid1234"
        if method == "aria2.tellStatus":
            return {"status": self.status, "errorCode": self.error_code, "errorMessage": ""}
        return "OK"


class TorrentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script("a2verify_under_test", VERIFY)

    def test_infohash_of_info_slice(self):
        start = TORRENT.index(b"4:info") + 6
        info = TORRENT[start:-1]
        self.assertEqual(self.mod.infohash_of(TORRENT), hashlib.sha1(info).hexdigest())
        self.assertEqual(self.mod.infohash_of(b"not a torrent"), "")

    def test_magnet_of_torrent(self):
        mag = self.mod.magnet_of_torrent(TORRENT)
        self.assertTrue(mag.startswith("magnet:?xt=urn:btih:"))
        self.assertIn("&dn=test", mag)

    def test_as_magnet(self):
        self.assertEqual(self.mod.as_magnet("magnet:?xt=urn:btih:" + "a" * 40),
                         "magnet:?xt=urn:btih:" + "a" * 40)
        tmp = tempfile.mkdtemp()
        try:
            p = os.path.join(tmp, "x.torrent")
            with open(p, "wb") as fh:
                fh.write(TORRENT)
            self.assertTrue(self.mod.as_magnet(p).startswith("magnet:"))
            with self.assertRaises(SystemExit):
                self.mod.as_magnet(os.path.join(tmp, "missing.torrent"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="a2verify-")
        os.environ["A2_VERIFY_DIR"] = self.tmp
        self.mod = load_script("a2verify_verify", VERIFY)
        self.mod.VERIFY_DIR = self.tmp
        self.ih = hashlib.sha1(TORRENT[TORRENT.index(b"4:info") + 6:-1]).hexdigest()
        self.magnet = "magnet:?xt=urn:btih:%s&dn=test" % self.ih

    def tearDown(self):
        os.environ.pop("A2_VERIFY_DIR", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def install_fake(self, fake):
        self.mod.load_a2 = lambda: fake

    def test_ok_when_metadata_lands(self):
        fake = FakeA2(status="complete")
        self.install_fake(fake)
        with open(os.path.join(self.tmp, self.ih + ".torrent"), "wb") as fh:
            fh.write(TORRENT)
        res = self.mod.verify(self.magnet, timeout=1)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["name"], "test")
        self.assertEqual(res["bytes"], 100)
        self.assertEqual(res["files"], 1)
        self.assertEqual(os.listdir(self.tmp), [], "校验产物要清掉")
        methods = [c[0] for c in fake.calls]
        self.assertIn("aria2.addUri", methods)
        self.assertIn("aria2.removeDownloadResult", methods)

    def test_fail_when_no_metadata(self):
        fake = FakeA2(status="error", error_code="1")
        self.install_fake(fake)
        res = self.mod.verify(self.magnet, timeout=1)
        self.assertFalse(res["ok"])
        self.assertIn("errorCode=1", res["error"])

    def test_json_cli_exit_codes(self):
        fake = FakeA2(status="error", error_code="1")
        self.install_fake(fake)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.mod.main(["a2-verify", self.magnet, "--json", "--timeout", "1"])
        self.assertEqual(rc, 1)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["ih"], self.ih)

    def test_plain_magnet_without_infohash_errors(self):
        self.install_fake(FakeA2())
        res = self.mod.verify("magnet:?xt=urn:btih:ABCDEFG", timeout=1)
        self.assertFalse(res["ok"])
        self.assertIn("infohash", res["error"])


if __name__ == "__main__":
    unittest.main()
