# -*- coding: utf-8 -*-
"""
本地大屏服务：从 CSV 生成 JSON API + HTTP 静态服务
===============================================
无需 HBase / Spring Boot / Maven，直接在本地 8080 端口提供：
  - 静态文件服务（outputs/charts/ 下的 HTML/CSS/JS/PNG）
  - /api/rules/frequent  频繁项集
  - /api/rules/strong    强规则
  - /api/stats/keyword   关键词频次
  - /api/predict         薪资预测（代理到 8788）
  - /api/overview        模型概览（代理到 8788）

用法：python serve_local.py [port]
"""
import os
import sys
import ast
import json
import http.server
import socketserver
import urllib.request
from urllib.parse import urlparse, parse_qs

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(BASE, "outputs", "charts")
DATA_PROCESSED = os.path.join(BASE, "data", "processed")

PREDICT_PORT = 8788


def parse_frozenset(s):
    """把 frozenset({'a','b'}) 字符串解析为逗号分隔的字符串 'a,b'"""
    s = str(s).strip()
    if s.startswith("frozenset("):
        s = s[len("frozenset("):-1]
    try:
        items = ast.literal_eval(s)
        return ",".join(sorted(items))
    except Exception:
        return s.strip("{}'\" ")


def load_frequent():
    """加载频繁项集，返回 [{items: "java,spring", support: 0.4}, ...]"""
    path = os.path.join(DATA_PROCESSED, "frequent_itemsets.csv")
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path)
    df = df[df["itemsets"].apply(lambda x: "," in str(x))].head(20)
    return [{"items": parse_frozenset(r["itemsets"]),
             "support": round(float(r["support"]), 4)}
            for _, r in df.iterrows()]


def load_strong_rules():
    """加载强规则，返回 [{antecedents, consequents, support, confidence, lift}, ...]"""
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
    """加载关键词频次，返回 {keyword: count}"""
    path = os.path.join(DATA_PROCESSED, "item_frequency.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    return {str(r["item"]): int(r["count"]) for _, r in df.head(50).iterrows()}


FREQUENT_DATA = load_frequent()
RULES_DATA = load_strong_rules()
KEYWORD_DATA = load_keywords()


class LocalHandler(http.server.SimpleHTTPRequestHandler):
    """静态文件 + JSON API"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=CHART_DIR, **kwargs)

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _proxy_predict(self, path):
        """代理到 8788 预测服务"""
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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/rules/frequent":
            self._send_json(FREQUENT_DATA)
        elif path == "/api/rules/strong":
            self._send_json(RULES_DATA)
        elif path == "/api/stats/keyword":
            self._send_json(KEYWORD_DATA)
        elif path == "/api/predict":
            self._proxy_predict(path + "?" + parsed.query)
        elif path == "/api/overview":
            self._proxy_predict(path)
        elif path == "/api/hello":
            self._send_json({"status": "ok", "msg": "本地大屏服务已启动"})
        elif path == "/" or path == "":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def log_message(self, fmt, *args):
        msg = fmt % args
        if "api/" in msg or "404" in msg:
            print(f"  [{self.address_string()}] {msg}")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    print("=" * 50)
    print("  本地大屏服务")
    print("=" * 50)
    print(f"  频繁项集: {len(FREQUENT_DATA)} 条")
    print(f"  强规则:   {len(RULES_DATA)} 条")
    print(f"  关键词:   {len(KEYWORD_DATA)} 个")
    print(f"  端口:     {port}")
    print(f"  预测服务: http://localhost:{PREDICT_PORT}")
    print()
    print(f"  大屏地址: http://localhost:{port}/")
    print(f"  预测测试: http://localhost:{port}/api/predict?city=北京&edu=本科&exp=3-5年&tags=Java&tier=头部大厂")
    print("=" * 50)

    with socketserver.TCPServer(("0.0.0.0", port), LocalHandler) as httpd:
        print(f"\n  服务已启动，按 Ctrl+C 停止...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  服务已停止。")


if __name__ == "__main__":
    main()
