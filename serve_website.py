# -*- coding: utf-8 -*-
"""
本地招聘网站完整服务
====================
无需 HBase / Spring Boot / Maven，一键启动完整招聘网站。

功能：
  - 静态页面：首页 / 搜索 / 详情 / 登录 / 注册 / 数据大屏
  - 岗位接口：搜索 / 详情 / 推荐 / 城市列表
  - 用户接口：注册 / 登录 / 个人资料（内存存储）
  - 统计接口：城市分布 / 薪资分布 / 薪资趋势 / 关键词词云
  - 关联规则接口：频繁项集 / 强规则
  - 薪资预测代理：转发到 8788 预测服务

用法：python serve_website.py [port]
"""
import os
import sys
import ast
import json
import hashlib
import http.server
import socketserver
import urllib.request
from urllib.parse import urlparse, parse_qs, unquote
from datetime import datetime, timedelta
import random

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "serving"))
from forum_data import (get_article_list, get_article_detail,
                         get_comments, add_comment, like_article,
                         create_post, update_post, delete_post,
                         get_user_posts, pin_post,
                         add_notification, get_notifications,
                         get_unread_count, mark_notifications_read,
                         FORUM_CATEGORIES)

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE, "day08-backend", "src", "main", "resources", "static")
ECHARTS_DIR = os.path.join(BASE, "outputs", "charts", "js")
DATA_CLEAN = os.path.join(BASE, "data", "clean", "recruit_clean.tsv")
DATA_PROCESSED = os.path.join(BASE, "data", "processed")

PREDICT_PORT = 8788

# ============ 数据加载 ============

def parse_frozenset(s):
    s = str(s).strip()
    if s.startswith("frozenset("):
        s = s[len("frozenset("):-1]
    try:
        items = ast.literal_eval(s)
        return ",".join(sorted(items))
    except Exception:
        return s.strip("{}'\" ")


def load_jobs():
    """加载岗位数据，转为字典列表"""
    df = pd.read_csv(DATA_CLEAN, sep="\t")
    jobs = []
    for i, r in df.iterrows():
        # 使用 TSV 中的真实职位描述，如果有
        desc = str(r.get("desc", "")) if "desc" in df.columns else ""
        if not desc or desc == "nan":
            desc = (f"【岗位名称】{r['title']}\n"
                    f"【工作地点】{r['city']}\n"
                    f"【学历要求】{r['edu']}\n"
                    f"【经验要求】{r['exp']}\n\n"
                    f"岗位职责：\n1. 负责{r['company']}相关产品的技术架构和开发；\n"
                    f"2. 参与系统设计，保证系统的高可用性和高性能；\n"
                    f"3. 与团队协作，按时交付高质量代码。\n\n"
                    f"任职要求：\n1. {r['edu']}及以上学历，{r['exp']}相关工作经验；\n"
                    f"2. 熟悉常用的开发框架和工具；\n3. 良好的沟通能力和团队合作精神；\n"
                    f"4. 有大型互联网公司经验者优先。")
        # 使用 TSV 中的类别，如果有
        cat = str(r.get("category", "")) if "category" in df.columns else ""
        if not cat or cat == "nan":
            title = str(r["title"])
            if "前端" in title: cat = "前端开发"
            elif "后端" in title or "Java" in title or "Python" in title or "Go" in title or "全栈" in title: cat = "后端开发"
            elif "Android" in title or "iOS" in title or "移动" in title: cat = "移动开发"
            elif "测试" in title: cat = "测试"
            elif "运维" in title or "DevOps" in title: cat = "运维"
            elif "数据" in title or "分析" in title: cat = "数据"
            elif "算法" in title or "机器学习" in title: cat = "算法"
            elif "产品" in title: cat = "产品"
            elif "UI" in title or "设计" in title: cat = "设计"
            elif "安全" in title: cat = "安全"
            else: cat = "后端开发"
        # 使用 TSV 中的发布时间，如果有
        pub_time = str(r.get("publish_time", "")) if "publish_time" in df.columns else ""
        if not pub_time or pub_time == "nan":
            pub_time = (datetime.now() - timedelta(days=random.randint(0, 29),
                                                    hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M")
        # 使用 TSV 中的 job_id，如果为空则生成
        job_id = str(r.get("job_id", "")) if "job_id" in df.columns else ""
        if not job_id or job_id == "nan":
            job_id = f"job_{i:05d}"
        jobs.append({
            "rowKey": job_id,
            "title": r["title"],
            "company": r["company"],
            "city": r["city"],
            "salary_low": str(r["salary_low"]),
            "salary_high": str(r["salary_high"]),
            "edu": r["edu"],
            "exp": r["exp"],
            "tags": r["tags"],
            "category": cat,
            "company_tier": r["company_tier"],
            "desc": desc,
            "publish_time": pub_time,
        })
    return jobs


def load_frequent():
    path = os.path.join(DATA_PROCESSED, "frequent_itemsets.csv")
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path)
    df = df[df["itemsets"].apply(lambda x: "," in str(x))].head(20)
    return [{"items": parse_frozenset(r["itemsets"]),
             "support": round(float(r["support"]), 4)}
            for _, r in df.iterrows()]


def load_strong_rules():
    path = os.path.join(DATA_PROCESSED, "association_rules.csv")
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path)
    results = []
    for _, r in df.iterrows():
        a = parse_frozenset(r["antecedents"])
        c = parse_frozenset(r["consequents"])
        results.append({
            "antecedents": a,
            "consequents": c,
            "rule": "{" + a + "} => {" + c + "}",
            "support": round(float(r["support"]), 4),
            "confidence": round(float(r["confidence"]), 4),
            "lift": round(float(r["lift"]), 4),
        })
    return results


def load_keywords():
    path = os.path.join(DATA_PROCESSED, "item_frequency.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    return {str(r["item"]): int(r["count"]) for _, r in df.head(50).iterrows()}


JOBS_DATA = load_jobs()
FREQUENT_DATA = load_frequent()
RULES_DATA = load_strong_rules()
KEYWORD_DATA = load_keywords()

# 内存用户表（初始测试账号）
USERS = {
    "admin": {"password": hashlib.sha256("123456".encode()).hexdigest(),
              "email": "admin@recruit.com", "nickname": "管理员", "role": "admin"},
    "xiaoliyu": {"password": hashlib.sha256("123456".encode()).hexdigest(),
                 "email": "xiaoliyu@recruit.com", "nickname": "小李鱼", "role": "user"},
    "zhangsan": {"password": hashlib.sha256("123456".encode()).hexdigest(),
                 "email": "zhangsan@recruit.com", "nickname": "张三公司", "role": "company",
                 "company_name": "张三科技有限公司"},
}

# 简易 token 存储
TOKENS = {}


def gen_token(username):
    token = hashlib.md5(f"{username}{datetime.now().timestamp()}".encode()).hexdigest()
    TOKENS[token] = username
    return token


def verify_token(auth_header):
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    return TOKENS.get(token)


# ============ 业务逻辑 ============

def search_jobs(city="", sal_min=0, sal_max=0, keyword="", category="全部", page=1, size=10):
    filtered = []
    for job in JOBS_DATA:
        if city and city != "全部" and job["city"] != city:
            continue
        if category and category != "全部" and job["category"] != category:
            continue
        if keyword:
            match_text = job["title"] + job["company"] + job["tags"]
            if keyword.lower() not in match_text.lower():
                continue
        try:
            low = int(job["salary_low"])
            high = int(job["salary_high"])
            if sal_min > 0 and high < sal_min:
                continue
            if sal_max > 0 and low > sal_max:
                continue
        except (ValueError, KeyError):
            pass
        filtered.append(job)

    # 按发布时间倒序
    filtered.sort(key=lambda j: j.get("publish_time", ""), reverse=True)

    total = len(filtered)
    total_pages = (total + size - 1) // size
    start = (page - 1) * size
    end = min(start + size, total)
    page_data = filtered[start:end]

    return {"list": page_data, "total": total, "page": page,
            "size": size, "totalPages": total_pages}


def get_job_detail(job_id):
    for job in JOBS_DATA:
        if job["rowKey"] == job_id:
            return job
    return None


def agg_position():
    counts = {}
    for job in JOBS_DATA:
        city = job["city"]
        counts[city] = counts.get(city, 0) + 1
    return {str(k): str(v) for k, v in counts.items()}


def agg_salary():
    bins = [(0, 5, "0-5K"), (5, 10, "5-10K"), (10, 15, "10-15K"),
            (15, 20, "15-20K"), (20, 30, "20-30K"), (30, 50, "30-50K"), (50, 999, "50K+")]
    counts = {b[2]: 0 for b in bins}
    for job in JOBS_DATA:
        try:
            low = int(job["salary_low"])
            for lo, hi, label in bins:
                if lo <= low < hi:
                    counts[label] += 1
                    break
        except (ValueError, KeyError):
            pass
    return {k: str(v) for k, v in counts.items()}


def agg_salary_trend():
    sorted_jobs = sorted(JOBS_DATA, key=lambda j: int(j.get("salary_low", 0)))
    return [str(j["salary_low"]) for j in sorted_jobs[:30]]


# ============ HTTP 服务 ============

class WebsiteHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def translate_path(self, path):
        """支持从两个静态目录服务文件"""
        parsed = urlparse(path)
        path = unquote(parsed.path)

        # echarts 文件从 charts/js 目录提供
        if path.startswith("/js/echarts"):
            fname = os.path.basename(path)
            fpath = os.path.join(ECHARTS_DIR, fname)
            if os.path.exists(fpath):
                return fpath

        # 其他从 static 目录
        return super().translate_path(path)

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}

    def _proxy_predict(self, path):
        url = f"http://localhost:{PREDICT_PORT}{path}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
        except Exception as e:
            self._send_json({"code": 1, "msg": str(e)}, 502)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # === 岗位接口 ===
        if path == "/api/job/search":
            city = qs.get("city", [""])[0]
            keyword = qs.get("keyword", [""])[0]
            category = qs.get("category", ["全部"])[0]
            sal_min = int(qs.get("salaryMin", ["0"])[0] or 0)
            sal_max = int(qs.get("salaryMax", ["0"])[0] or 0)
            page = int(qs.get("page", ["1"])[0] or 1)
            size = int(qs.get("size", ["10"])[0] or 10)
            result = search_jobs(city, sal_min, sal_max, keyword, category, page, size)
            self._send_json(result)
            return

        if path.startswith("/api/job/detail/"):
            job_id = path.split("/")[-1]
            job = get_job_detail(job_id)
            if job:
                self._send_json(job)
            else:
                self._send_json({"error": "岗位不存在"})
            return

        if path == "/api/job/featured":
            result = search_jobs("", 0, 0, "", "全部", 1, 6)
            self._send_json(result["list"])
            return

        if path == "/api/job/cities":
            pos = agg_position()
            cities = sorted(pos.keys())
            self._send_json(cities)
            return

        # === 论坛接口 ===
        if path == "/api/forum/list":
            category = qs.get("category", ["全部"])[0]
            keyword = qs.get("keyword", [""])[0]
            page = int(qs.get("page", ["1"])[0] or 1)
            size = int(qs.get("size", ["10"])[0] or 10)
            result = get_article_list(category, keyword, page, size)
            self._send_json(result)
            return

        if path.startswith("/api/forum/detail/"):
            article_id = path.split("/")[-1]
            article = get_article_detail(article_id)
            if article:
                self._send_json(article)
            else:
                self._send_json({"error": "文章不存在"}, 404)
            return

        if path.startswith("/api/forum/comments/"):
            article_id = path.split("/")[-1]
            comments = get_comments(article_id)
            self._send_json(comments)
            return

        if path.startswith("/api/forum/like/"):
            article_id = path.split("/")[-1]
            ok = like_article(article_id)
            self._send_json({"success": ok})
            return

        if path == "/api/forum/categories":
            self._send_json(FORUM_CATEGORIES)
            return

        # 用户帖子列表
        if path.startswith("/api/forum/my-posts"):
            auth = self.headers.get("Authorization", "")
            username = verify_token(auth)
            if not username:
                self._send_json({"error": "请先登录"})
                return
            posts = get_user_posts(username)
            self._send_json(posts)
            return

        # 未读通知数
        if path.startswith("/api/forum/unread"):
            auth = self.headers.get("Authorization", "")
            username = verify_token(auth)
            if not username:
                self._send_json({"count": 0})
                return
            self._send_json({"count": get_unread_count(username)})
            return

        # 通知列表
        if path.startswith("/api/forum/notifications"):
            auth = self.headers.get("Authorization", "")
            username = verify_token(auth)
            if not username:
                self._send_json([])
                return
            self._send_json(get_notifications(username))
            return

        # === 用户接口 ===
        if path == "/api/user/profile":
            auth = self.headers.get("Authorization", "")
            username = verify_token(auth)
            if not username:
                self._send_json({"error": "未登录"})
                return
            user = USERS.get(username, {})
            profile = {k: v for k, v in user.items() if k != "password"}
            profile["username"] = username
            self._send_json(profile)
            return

        # === 统计接口 ===
        if path == "/api/stats/position":
            self._send_json(agg_position())
            return

        if path == "/api/stats/salary":
            self._send_json(agg_salary())
            return

        if path == "/api/stats/salary/trend":
            self._send_json(agg_salary_trend())
            return

        if path == "/api/stats/keyword":
            self._send_json({k: str(v) for k, v in KEYWORD_DATA.items()})
            return

        # === 关联规则接口 ===
        if path == "/api/rules/frequent":
            self._send_json(FREQUENT_DATA)
            return

        if path == "/api/rules/strong":
            self._send_json(RULES_DATA)
            return

        # === 预测接口（代理）===
        if path == "/api/predict":
            self._proxy_predict(self.path)
            return

        if path == "/api/overview":
            self._proxy_predict("/api/overview")
            return

        # === 健康检查 ===
        if path == "/api/hello":
            self._send_json({"status": "ok", "msg": "招聘分析系统后端已启动（本地模式）"})
            return

        if path == "/api/ping":
            self._send_json({"status": "ok", "time": int(datetime.now().timestamp() * 1000)})
            return

        # === 静态文件 ===
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/user/register":
            username = body.get("username", "").strip()
            password = body.get("password", "")
            email = body.get("email", "")
            if not username or len(username) < 3:
                self._send_json({"success": False, "msg": "用户名至少3个字符"})
                return
            if not password or len(password) < 6:
                self._send_json({"success": False, "msg": "密码至少6位"})
                return
            if username in USERS:
                self._send_json({"success": False, "msg": "用户名已存在"})
                return
            USERS[username] = {
                "password": hashlib.sha256(password.encode()).hexdigest(),
                "email": email, "nickname": username, "role": "user",
            }
            token = gen_token(username)
            self._send_json({"success": True, "token": token,
                             "username": username, "msg": "注册成功"})
            return

        if path in ("/api/user/login", "/api/company/login", "/api/admin/login"):
            username = body.get("username", "").strip()
            password = body.get("password", "")
            user = USERS.get(username)
            if not user:
                self._send_json({"code": 1, "msg": "用户不存在"})
                return
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            if pwd_hash != user["password"]:
                self._send_json({"code": 1, "msg": "密码错误"})
                return
            role = user.get("role", "user")
            expected_role = path.split("/")[2]
            if expected_role == "admin" and role != "admin":
                self._send_json({"code": 1, "msg": "该账号无管理员权限"})
                return
            token = gen_token(username)
            resp = {"code": 0, "token": token,
                    "username": username,
                    "role": role,
                    "nickname": user.get("nickname", username),
                    "msg": "登录成功"}
            if role == "company":
                resp["company_name"] = user.get("company_name", username)
            self._send_json(resp)
            return

        # === 论坛评论 ===
        if path.startswith("/api/forum/comment/"):
            auth = self.headers.get("Authorization", "")
            username = verify_token(auth)
            if not username:
                self._send_json({"success": False, "msg": "请先登录"}, 401)
                return
            article_id = path.split("/")[-1]
            content = body.get("content", "").strip()
            if not content or len(content) < 2:
                self._send_json({"success": False, "msg": "评论内容太短"})
                return
            comment = add_comment(article_id, username, content)
            if comment:
                # 给帖子作者发通知
                article = get_article_detail(article_id)
                if article and article.get("author") != username:
                    add_notification(article["author"], "comment", article_id,
                                     f"{username} 评论了你的文章《{article['title']}》")
                self._send_json({"success": True, "comment": comment, "msg": "评论成功"})
            else:
                self._send_json({"success": False, "msg": "文章不存在"})
            return

        # === 论坛点赞（POST） ===
        if path.startswith("/api/forum/like/"):
            article_id = path.split("/")[-1]
            ok = like_article(article_id)
            if ok:
                article = get_article_detail(article_id)
                if article:
                    auth = self.headers.get("Authorization", "")
                    username = verify_token(auth)
                    if username and article.get("author") != username:
                        add_notification(article["author"], "like", article_id,
                                         f"{username} 点赞了你的文章《{article['title']}》")
            self._send_json({"success": ok})
            return

        # === 用户发帖 ===
        if path == "/api/forum/create":
            auth = self.headers.get("Authorization", "")
            username = verify_token(auth)
            if not username:
                self._send_json({"code": 1, "msg": "请先登录"}, 401)
                return
            title = body.get("title", "").strip()
            content = body.get("content", "").strip()
            category = body.get("category", "求职攻略")
            summary = body.get("summary", "").strip()
            tags = body.get("tags", [])
            if not title or not content:
                self._send_json({"code": 1, "msg": "标题和内容不能为空"})
                return
            post = create_post(username, title, content, category, summary, tags)
            self._send_json({"code": 0, "post": post, "msg": "发帖成功"})
            return

        # === 编辑帖子 ===
        if path.startswith("/api/forum/update/"):
            auth = self.headers.get("Authorization", "")
            username = verify_token(auth)
            if not username:
                self._send_json({"code": 1, "msg": "请先登录"}, 401)
                return
            post_id = path.split("/")[-1]
            post = update_post(post_id, username,
                               title=body.get("title"),
                               content=body.get("content"),
                               category=body.get("category"),
                               summary=body.get("summary"),
                               tags=body.get("tags"))
            if post:
                self._send_json({"code": 0, "post": post, "msg": "修改成功"})
            else:
                self._send_json({"code": 1, "msg": "只能编辑自己的帖子"})
            return

        # === 删除帖子 ===
        if path.startswith("/api/forum/delete/"):
            auth = self.headers.get("Authorization", "")
            username = verify_token(auth)
            if not username:
                self._send_json({"code": 1, "msg": "请先登录"}, 401)
                return
            post_id = path.split("/")[-1]
            user = USERS.get(username, {})
            is_admin = user.get("role") == "admin"
            ok = delete_post(post_id, username, is_admin)
            if ok:
                self._send_json({"code": 0, "msg": "删除成功"})
            else:
                self._send_json({"code": 1, "msg": "只能删除自己的帖子"})
            return

        # === 置顶/取消置顶（管理员） ===
        if path.startswith("/api/forum/pin/"):
            auth = self.headers.get("Authorization", "")
            username = verify_token(auth)
            if not username:
                self._send_json({"code": 1, "msg": "请先登录"}, 401)
                return
            user = USERS.get(username, {})
            if user.get("role") != "admin":
                self._send_json({"code": 1, "msg": "只有管理员可以置顶"})
                return
            post_id = path.split("/")[-1]
            pinned = body.get("pinned", True)
            ok = pin_post(post_id, pinned)
            if ok:
                self._send_json({"code": 0, "msg": "置顶成功" if pinned else "取消置顶"})
            else:
                self._send_json({"code": 1, "msg": "文章不存在"})
            return

        # === 标记通知已读 ===
        if path == "/api/forum/notifications/read":
            auth = self.headers.get("Authorization", "")
            username = verify_token(auth)
            if not username:
                self._send_json({"code": 1, "msg": "请先登录"}, 401)
                return
            mark_notifications_read(username)
            self._send_json({"code": 0, "msg": "已标记为已读"})
            return

        self._send_json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        msg = fmt % args
        if "api/" in msg or "POST" in msg:
            print(f"  [{self.address_string()}] {msg}")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    print("=" * 60)
    print("  招聘分析系统 · 本地完整服务")
    print("=" * 60)
    print(f"  岗位数据: {len(JOBS_DATA)} 条")
    print(f"  频繁项集: {len(FREQUENT_DATA)} 条")
    print(f"  强规则:   {len(RULES_DATA)} 条")
    print(f"  关键词:   {len(KEYWORD_DATA)} 个")
    print(f"  测试账号: admin/123456  xiaoliyu/123456  zhangsan/123456")
    print(f"  预测服务: http://localhost:{PREDICT_PORT}")
    print()
    print(f"  首页:     http://localhost:{port}/")
    print(f"  搜索:     http://localhost:{port}/search.html")
    print(f"  登录:     http://localhost:{port}/login.html")
    print(f"  数据大屏: http://localhost:{port}/dashboard.html")
    print("=" * 60)
    print(f"\n  服务已启动，按 Ctrl+C 停止...")

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), WebsiteHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  服务已停止。")


if __name__ == "__main__":
    main()
