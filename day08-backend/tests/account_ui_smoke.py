"""Browser smoke test against explicitly mocked APIs; backend behavior is tested by Maven.
Run: python day08-backend/tests/account_ui_smoke.py (requires Python Playwright + Chromium).
"""
import functools
import http.server
import json
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'target' / 'account-ui'
OUTPUT.mkdir(parents=True, exist_ok=True)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0),
        functools.partial(QuietHandler, directory=str(ROOT / 'src/main/resources/static')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    requests, errors = [], []
    state = {'blocked': True, 'expired': False, 'mail_down': False}

    def route_api(route):
        request = route.request
        path = urlparse(request.url).path
        data = request.post_data_json if 'application/json' in request.headers.get('content-type', '') else {}
        requests.append((path, data, request.headers))
        status = 200
        reply = []
        if path.endswith('/login'):
            role = path.split('/')[2]
            if data['password'] == 'wrong':
                status, reply = 401, {'code': 401, 'msg': '账号或密码错误，还可尝试 4 次'}
            else:
                reply = {'code': 0, 'role': role, 'username': data['username'], 'token': 'fixture-' + role, 'company_name': '演示企业'}
        elif path.endswith('/register'):
            reply = {'code': 0, 'msg': '注册成功，请登录'}
        elif path == '/api/admin/accounts':
            if state['expired']:
                status, reply = 401, {'code': 401, 'msg': '账号已封禁，请联系管理员解封'}
            else:
                query = parse_qs(urlparse(request.url).query)
                items = [{'accountType': 'user', 'username': 'alice', 'email': 'alice@example.com',
                          'failedAttempts': 5 if state['blocked'] else 0, 'blocked': state['blocked'],
                          'blockedAt': '1800000000000' if state['blocked'] else ''}]
                if query.get('keyword', [''])[0] not in ('', 'ali', 'alice') or query.get('accountType') == ['company']:
                    items = []
                reply = {'code': 0, 'items': items, 'total': len(items), 'page': 1, 'size': 20}
        elif path.endswith('/unlock'):
            state['blocked'] = False
            reply = {'code': 0, 'msg': '已解封，请重新登录'}
        elif path.endswith('/code'):
            if state['mail_down']:
                status, reply = 503, {'code': 503, 'msg': '邮件服务未配置，请联系管理员'}
            else:
                reply = {'code': 0, 'msg': '若账号与注册邮箱匹配，验证码将发送至该邮箱，请查收'}
        elif path.endswith('/email-login/confirm'):
            reply = {'code': 0, 'role': data['accountType'], 'username': data['username'], 'token': 'fixture-' + data['accountType'], 'company_name': '演示企业'}
        elif path.endswith('/password-reset/confirm'):
            reply = {'code': 0, 'blocked': data['accountType'] == 'company', 'msg':
                '密码已重置，账号仍处于封禁状态，请联系管理员解封' if data['accountType'] == 'company' else '密码已重置，请重新登录'}
        elif path == '/api/resume/get':
            reply = {'name': '演示用户', 'skills': 'Java', 'city': '北京'}
        route.fulfill(status=status, content_type='application/json', body=json.dumps(reply, ensure_ascii=False))

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 960}, accept_downloads=True)
            context.route('**/api/**', route_api)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('dialog', lambda dialog: dialog.accept())
            page.goto(base + '/login.html')
            page.locator('#userUsername').fill('alice')
            page.locator('#userPassword').fill('wrong')
            page.locator('#userPanel .login-btn').click()
            expect(page.locator('#loginMessage')).to_contain_text('还可尝试 4 次')
            assert page.url.endswith('/login.html')
            for role, prefix, username in [('user', 'user', 'alice'), ('company', 'comp', 'acme'), ('admin', 'admin', 'lihuanshen123')]:
                page.goto(base + '/login.html?type=' + role)
                expect(page.locator('#' + role + 'Panel')).to_be_visible()
                page.locator('#' + prefix + 'Username').fill(username)
                page.locator('#' + prefix + 'Password').fill('123456')
                if role == 'admin': page.screenshot(path=str(OUTPUT / 'login.png'), full_page=True)
                page.locator('#' + prefix + 'Password').press('Enter')
                page.wait_for_url('**/' + role + '/index.html')
                assert page.evaluate("localStorage.getItem('recruit_role')") == role
                assert page.evaluate("localStorage.getItem('recruit_token')") == 'fixture-' + role
            expect(page.locator('#accounts')).to_contain_text('alice')
            expect(page.locator('#accounts')).to_contain_text('已封禁')
            page.screenshot(path=str(OUTPUT / 'admin.png'), full_page=True)
            page.locator('#keyword').fill('nobody'); page.locator('#search').click()
            expect(page.locator('#message')).to_have_text('没有符合条件的账号')
            page.locator('#keyword').fill('ali'); page.locator('#search').click()
            expect(page.locator('#accounts')).to_contain_text('alice')
            page.locator('#accounts button').click()
            expect(page.locator('#message')).to_have_text('已解封，请重新登录')
            expect(page.locator('#accounts')).to_contain_text('正常')
            assert any(path.endswith('/unlock') and headers.get('authorization') == 'Bearer fixture-admin' for path, _, headers in requests)
            state['expired'] = True; page.locator('#search').click()
            page.wait_for_url('**/login.html')
            expect(page.locator('#loginMessage')).to_contain_text('账号已封禁')
            assert page.evaluate("localStorage.getItem('recruit_token')") is None
            # The fetch rejects after redirect intentionally; handle only that expected error.
            errors[:] = [error for error in errors if '账号已封禁' not in error]
            for role, prefix in [('user', 'user'), ('company', 'comp')]:
                page.goto(base + '/register.html?type=' + role)
                page.locator('#' + prefix + 'Username').fill('new-' + role)
                page.locator('#' + prefix + 'Password').fill('123456')
                page.locator('#' + prefix + 'Email').fill('new@example.com')
                if role == 'company': page.locator('#companyName').fill('演示企业')
                state['mail_down'] = True; page.locator('#' + prefix + 'SendCode').click()
                expect(page.locator('#registerMessage')).to_contain_text('邮件服务未配置')
                expect(page.locator('#' + prefix + 'SendCode')).to_be_enabled()
                state['mail_down'] = False; page.locator('#' + prefix + 'SendCode').click()
                expect(page.locator('#' + prefix + 'SendCode')).to_be_disabled()
                expect(page.locator('#' + prefix + 'SendCode')).to_contain_text('秒后重发')
                page.locator('#' + prefix + 'Code').fill('654321')
                page.locator('#' + prefix + 'Email').fill('changed@example.com')
                expect(page.locator('#' + prefix + 'Code')).to_have_value('')
                page.locator('#' + prefix + 'Email').fill('new@example.com')
                expect(page.locator('#' + prefix + 'SendCode')).to_be_disabled()
                page.locator('#' + prefix + 'Code').fill('654321')
                page.screenshot(path=str(OUTPUT / ('register-' + role + '.png')), full_page=True)
                page.locator('#' + role + 'Panel .login-btn').click(); page.wait_for_url('**/login.html?type=' + role)
                assert any(path == '/api/' + role + '/register' and body['email'] == 'new@example.com' and body['code'] == '654321' for path, body, _ in requests)
            for role, prefix in [('user', 'user'), ('company', 'comp')]:
                page.goto(base + '/login.html?type=' + role)
                page.locator('#' + prefix + 'EmailMode').click()
                expect(page.locator('#' + prefix + 'Password')).to_be_hidden()
                page.locator('#' + prefix + 'Username').fill('alice' if role == 'user' else 'acme')
                page.locator('#' + prefix + 'Email').fill('demo@example.com')
                state['mail_down'] = True; page.locator('#' + prefix + 'SendCode').click()
                expect(page.locator('#loginMessage')).to_contain_text('邮件服务未配置')
                state['mail_down'] = False; page.locator('#' + prefix + 'SendCode').click()
                expect(page.locator('#' + prefix + 'SendCode')).to_contain_text('秒后重发')
                page.locator('#' + prefix + 'Code').fill('654321')
                page.screenshot(path=str(OUTPUT / ('email-login-' + role + '.png')), full_page=True)
                page.locator('#' + prefix + 'Code').press('Enter')
                page.wait_for_url('**/' + role + '/index.html')
                assert page.evaluate("localStorage.getItem('recruit_role')") == role
            auth_requests = [(path, body, headers) for path, body, headers in requests if path.startswith('/api/auth/')]
            assert all('authorization' not in headers for _, _, headers in auth_requests)
            for role in ('user', 'company'):
                page.goto(base + '/forgot-password.html?type=' + role)
                expect(page.locator('#accountType')).to_have_value(role)
                page.locator('#username').fill('alice' if role == 'user' else 'acme')
                page.locator('#email').fill('demo@example.com')
                state['mail_down'] = True; page.locator('#sendCode').click()
                expect(page.locator('#message')).to_have_text('邮件服务未配置，请联系管理员')
                expect(page.locator('#sendCode')).to_be_enabled()
                state['mail_down'] = False; page.locator('#sendCode').click()
                expect(page.locator('#sendCode')).to_be_disabled()
                expect(page.locator('#message')).to_contain_text('若账号与注册邮箱匹配')
                page.locator('#code').fill('654321'); page.locator('#password').fill('new-password')
                page.locator('#confirmation').fill('different'); page.locator('#resetSubmit').click()
                expect(page.locator('#message')).to_have_text('两次输入的密码不一致')
                page.locator('#confirmation').fill('new-password')
                if role == 'user': page.screenshot(path=str(OUTPUT / 'reset.png'), full_page=True)
                page.locator('#resetSubmit').click(); expect(page.locator('#resetForm')).to_be_hidden()
                expect(page.locator('#message')).to_contain_text('密码已重置')
                if role == 'company': expect(page.locator('#message')).to_contain_text('仍处于封禁状态')
            # Multipart callers get a token without a manually added JSON content type.
            page.evaluate("localStorage.setItem('recruit_token','fixture-user')")
            page.evaluate("async () => { const form = new FormData(); form.append('file', new Blob(['demo']), 'resume.txt'); await fetch('/api/upload', {method:'POST', body:form}); }")
            uploads = [headers for path, _, headers in requests if path == '/api/upload']
            assert uploads[-1]['authorization'] == 'Bearer fixture-user'
            assert uploads[-1]['content-type'].startswith('multipart/form-data; boundary=')
            assert not errors, errors
            browser.close()
        print('PASS: three-role login, registration email, admin filter/unlock, expiry, both reset flows, SMTP errors, multipart auth.')
        print('Browser screenshots: ' + str(OUTPUT))
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
