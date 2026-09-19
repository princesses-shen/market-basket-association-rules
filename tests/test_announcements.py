import http.server
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from src.serving.announcements import AnnouncementStore, AnnouncementError


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "announcements.json"
        self.store = AnnouncementStore(self.path, now=lambda: 1800000000000)

    def test_lifecycle_reload_and_private_author(self):
        self.assertEqual(0, self.store.list()["total"])
        item = self.store.create({"title": " 通知 ", "body": " 第一行\n第二行 ", "publishedAt": "1"}, "admin-name")
        self.assertEqual("通知", item["title"])
        self.assertEqual("管理员", item["author"])
        self.assertEqual("admin-name", json.loads(self.path.read_text(encoding="utf-8"))[0]["author"])
        restarted = AnnouncementStore(self.path, now=lambda: 1800000001000)
        self.assertEqual(item, restarted.detail(item["id"]))
        updated = restarted.update(item["id"], {"title": "更新", "body": "<script>alert(1)</script>"})
        self.assertEqual(item["publishedAt"], updated["publishedAt"])
        self.assertNotEqual(item["updatedAt"], updated["updatedAt"])
        self.assertNotIn("body", restarted.list()["items"][0])
        restarted.delete(item["id"])
        with self.assertRaises(AnnouncementError) as error:
            self.store.detail(item["id"])
        self.assertEqual(404, error.exception.status)

    def test_stable_pagination_and_edit_order(self):
        items = [self.store.create({"title": str(i), "body": "正文"}, "admin") for i in range(12)]
        ids = sorted((item["id"] for item in items), reverse=True)
        self.assertEqual(ids[:3], [item["id"] for item in self.store.list(size="3")["items"]])
        self.store.now = lambda: 1800000001000
        self.store.update(ids[-1], {"title": "更新", "body": "正文"})
        self.assertEqual(ids[10:], [item["id"] for item in self.store.list(page="2")["items"]])
        self.assertEqual([], self.store.list(page="2147483647", size="50")["items"])

    def test_validation_and_unicode_boundaries(self):
        for body in ({}, [], None, {"title": 1, "body": "x"}, {"title": " \n\u00a0", "body": "x"},
                     {"title": "x" * 101, "body": "x"}, {"title": "x", "body": "x" * 10001}):
            with self.subTest(body=str(body)[:30]), self.assertRaises(AnnouncementError) as error:
                self.store.create(body, "admin")
            self.assertEqual(400, error.exception.status)
        item = self.store.create({"title": "\u00a0" + "😀" * 100 + "\u0085", "body": "x" * 10000}, "admin")
        self.assertEqual("😀" * 100, item["title"])
        for value in ("", "0", "-1", "2147483648", "1.2", "abc"):
            with self.assertRaises(AnnouncementError):
                self.store.list(page=value)

    def test_corrupt_storage_never_overwritten(self):
        for contents in ("broken", "{}", '[{"id":"bad"}]'):
            self.path.write_text(contents, encoding="utf-8")
            with self.assertRaises(AnnouncementError) as error:
                self.store.create({"title": "公告", "body": "正文"}, "admin")
            self.assertEqual(503, error.exception.status)
            self.assertEqual(contents, self.path.read_text(encoding="utf-8"))

    def test_write_failure_preserves_file_for_all_mutations(self):
        item = self.store.create({"title": "原公告", "body": "正文"}, "admin")
        before = self.path.read_bytes()
        with patch("src.serving.announcements.os.replace", side_effect=OSError("read only")):
            for action in (lambda: self.store.create({"title": "新公告", "body": "正文"}, "admin"),
                           lambda: self.store.update(item["id"], {"title": "修改", "body": "正文"}),
                           lambda: self.store.delete(item["id"])):
                with self.assertRaises(AnnouncementError) as error:
                    action()
                self.assertEqual(503, error.exception.status)
                self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([], list(self.path.parent.glob("*.tmp")))


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import serve_website
        cls.site = serve_website
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), serve_website.WebsiteHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "announcements.json"
        self.storage = AnnouncementStore(self.path)
        patched = patch.object(self.site, "ANNOUNCEMENTS", self.storage)
        patched.start(); self.addCleanup(patched.stop)

    def request(self, path, body=None, token=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            response = urlopen(Request(self.base + path, data=data, headers=headers), timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_http_permissions_and_lifecycle(self):
        body = {"title": "公告", "body": "正文", "role": "admin"}
        admin = self.site.gen_token("admin")
        code, result = self.request("/api/admin/announcements", body, admin)
        self.assertEqual(200, code); identifier = result["item"]["id"]
        for user in (None, "xiaoliyu", "zhangsan"):
            token = self.site.gen_token(user) if user else None
            self.assertEqual(200, self.request("/api/announcements", token=token)[0])
            self.assertEqual(200, self.request("/api/announcements/" + identifier, token=token)[0])
            for path in ("/api/admin/announcements", f"/api/admin/announcements/{identifier}/update", f"/api/admin/announcements/{identifier}/delete"):
                self.assertEqual(403 if user else 401, self.request(path, body, token)[0])
        self.assertEqual(401, self.request("/api/admin/announcements", body, "forged")[0])
        self.assertEqual(200, self.request(f"/api/admin/announcements/{identifier}/update", {"title": "更新", "body": "新正文"}, admin)[0])
        self.assertEqual("更新", self.request("/api/announcements/" + identifier)[1]["item"]["title"])
        self.assertEqual(200, self.request(f"/api/admin/announcements/{identifier}/delete", {}, admin)[0])
        self.assertEqual(404, self.request("/api/announcements/" + identifier)[0])

    def test_http_validation_and_storage_errors(self):
        token = self.site.gen_token("admin")
        for raw in (b"{broken", b"[]", b"null", b"{}"):
            self.assertEqual(400, self.request("/api/admin/announcements", token=token, raw=raw)[0])
        for query in ("page=", "page=0", "page=bad", "size=", "size=51", "size=-1"):
            self.assertEqual(400, self.request("/api/announcements?" + query)[0])
        self.path.write_text("broken", encoding="utf-8")
        self.assertEqual(503, self.request("/api/announcements")[0])
        self.assertEqual(503, self.request("/api/admin/announcements", {"title": "公告", "body": "正文"}, token)[0])


if __name__ == "__main__":
    unittest.main()
