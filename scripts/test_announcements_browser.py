"""Run with: python scripts/test_announcements_browser.py (requires Playwright Chromium)."""
import http.server
import json
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve_website as site
from src.serving.announcements import AnnouncementStore
from playwright.sync_api import sync_playwright, expect


def run():
    screenshots = Path(__file__).resolve().parents[1] / "outputs" / "announcement-qa"
    screenshots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary, patch.object(site, "ANNOUNCEMENTS", AnnouncementStore(Path(temporary) / "announcements.json")):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), site.WebsiteHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(server.server_port)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1050})
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/announcements.html")
                expect(page.locator("#announcement-status")).to_have_text("暂无公告")
                # Authenticate through the actual login endpoint and the site's login-state contract.
                response = context.request.post(base + "/api/admin/login", data={"username": "admin", "password": "123456"})
                login = response.json()
                page.evaluate("result => { localStorage.setItem('recruit_token', result.token); localStorage.setItem('recruit_role', result.role); localStorage.setItem('recruit_username', result.username); }", login)
                page.goto(base + "/admin/announcements.html")
                expect(page.get_by_role("link", name="账号安全管理")).to_be_visible()
                expect(page.get_by_role("link", name="公告管理", exact=True)).to_be_visible()
                expect(page.locator("#announcement-status")).to_have_text("暂无公告")
                title = "服务更新 <img src=x onerror=alert(1)>"
                body = "第一行：服务升级通知\n第二行：<script>window.announcementXss=true</script>"
                page.get_by_label("标题", exact=True).fill(title)
                page.get_by_label("正文", exact=True).fill(body)
                page.get_by_role("button", name="发布公告", exact=True).click()
                expect(page.locator("#announcement-form-status")).to_have_text("公告已发布")
                expect(page.locator("#announcement-list article")).to_have_count(1)
                original = site.ANNOUNCEMENTS.list()["items"][0]
                identifier = original["id"]
                expect(page.locator("#announcement-list img")).to_have_count(0)
                page.get_by_role("button", name="编辑：" + title, exact=True).click()
                expect(page.get_by_label("正文", exact=True)).to_have_value(body)
                page.get_by_label("标题", exact=True).fill("平台服务升级通知")
                page.get_by_role("button", name="保存修改").click()
                expect(page.locator("#announcement-form-status")).to_have_text("修改已保存")
                assert site.ANNOUNCEMENTS.detail(identifier)["publishedAt"] == original["publishedAt"]
                page.screenshot(path=str(screenshots / "admin-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(screenshots / "admin-mobile.png"), full_page=True)
                page.set_viewport_size({"width": 1440, "height": 1050})

                # Saving failure keeps the draft, allows retry, and does not publish anything.
                page.get_by_label("标题", exact=True).fill("保存失败后的草稿")
                page.get_by_label("正文", exact=True).fill("这个输入必须保留")
                page.route("**/api/admin/announcements", lambda route: route.fulfill(status=503, content_type="application/json", body=json.dumps({"code": 503, "msg": "测试存储不可用"})))
                page.get_by_role("button", name="发布公告", exact=True).click()
                expect(page.locator("#announcement-form-status")).to_have_text("测试存储不可用")
                expect(page.get_by_label("正文", exact=True)).to_have_value("这个输入必须保留")
                expect(page.get_by_role("button", name="发布公告", exact=True)).to_be_enabled()
                page.unroute("**/api/admin/announcements")
                assert site.ANNOUNCEMENTS.list()["total"] == 1

                # Visitors see literal content and the complete list on a narrow screen.
                visitor = browser.new_context(viewport={"width": 390, "height": 844})
                public = visitor.new_page()
                public.on("pageerror", lambda error: errors.append(str(error)))
                public.goto(base + "/announcement.html?id=" + identifier)
                expect(public.locator("#announcement-body")).to_have_text(body)
                assert public.evaluate("window.announcementXss") is None
                assert public.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                public.screenshot(path=str(screenshots / "detail-mobile.png"), full_page=True)
                for i in range(11):
                    site.ANNOUNCEMENTS.create({"title": f"网站运行通知 {i + 1}", "body": "服务运行正常。"}, "admin")
                public.goto(base + "/announcements.html")
                expect(public.locator("#announcement-list article")).to_have_count(10)
                public.get_by_role("button", name="下一页").click()
                expect(public.locator("#announcement-list article")).to_have_count(2)
                expect(public.locator("#announcement-page-label")).to_have_text("2 / 2 页 · 共 12 条")
                assert public.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                public.screenshot(path=str(screenshots / "list-mobile.png"), full_page=True)
                # Expired client credentials do not interfere with public announcements.
                public.evaluate("localStorage.setItem('recruit_token', 'expired')")
                public.reload()
                expect(public.locator("#announcement-list article")).to_have_count(10)
                public.evaluate("localStorage.clear()")
                public.goto(base + "/")
                expect(public.locator("#announcement-list article")).to_have_count(3)
                expect(public.locator("#featuredList .job-card").first).to_be_visible()
                public.route("**/api/announcements?*", lambda route: route.fulfill(status=503, content_type="application/json", body='{"code":503,"msg":"公告暂不可用"}'))
                public.reload()
                expect(public.locator("#announcement-status")).to_have_text("公告暂不可用")
                expect(public.locator("#featuredList .job-card").first).to_be_visible()
                public.unroute("**/api/announcements?*")
                public.get_by_role("button", name="重新加载").click()
                expect(public.locator("#announcement-list article")).to_have_count(3)

                # Delete the only item on the last page; pagination must recover to page one.
                site.ANNOUNCEMENTS.delete(site.ANNOUNCEMENTS.list()["items"][0]["id"])
                page.reload()
                expect(page.locator("#announcement-list article")).to_have_count(10)
                page.get_by_role("button", name="下一页").click()
                expect(page.locator("#announcement-list article")).to_have_count(1)
                page.once("dialog", lambda dialog: dialog.dismiss())
                page.get_by_role("button", name="删除：平台服务升级通知").click()
                expect(page.locator("#announcement-list article")).to_have_count(1)
                page.once("dialog", lambda dialog: dialog.accept())
                page.get_by_role("button", name="删除：平台服务升级通知").click()
                expect(page.locator("#announcement-form-status")).to_have_text("公告已删除")
                expect(page.locator("#announcement-page-label")).to_have_text("1 / 1 页 · 共 10 条")
                for item in site.ANNOUNCEMENTS.list()["items"]:
                    site.ANNOUNCEMENTS.delete(item["id"])
                page.reload()
                expect(page.locator("#announcement-status")).to_have_text("暂无公告")
                public.goto(base + "/announcement.html?id=" + identifier)
                expect(public.locator("#announcement-status")).to_have_text("公告不存在或已删除")
                expect(public.get_by_role("link", name="← 返回公告列表")).to_be_visible()
                assert not errors, errors
                visitor.close(); context.close(); browser.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()
    print("PASS: admin CRUD, literal text, guest browsing, pagination, storage failure, homepage retry, mobile layout")


if __name__ == "__main__":
    run()
