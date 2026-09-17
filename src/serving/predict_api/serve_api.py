# -*- coding: utf-8 -*-
"""
薪资预测服务 (端口 8788)
GET /api/predict?city=&edu=&exp=&tags=&tier=
GET /api/meta
GET /api/overview
"""
import os, sys, pickle, json, numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODEL_PATH = os.path.join(BASE, "artifacts", "models", "salary_predictor.pkl")
sys.path.insert(0, os.path.join(BASE, "src", "analysis"))
from features import featurize, CITIES, EDU_MAP, EXP_MAP, TIER_MAP, FEATURE_DIM

print("loading model...")
with open(MODEL_PATH, "rb") as f:
    MODEL = pickle.load(f)
ns = MODEL["n_samples"]
fd = MODEL["feature_dim"]
print(f"model loaded: {ns} samples, {fd} dims")


def predict(city, edu, exp, tags, tier):
    x = np.array([featurize(city, edu, exp, tags, tier)], dtype=np.float32)
    models = MODEL["models"]
    q10 = float(models["q0.1"].predict(x)[0])
    q50 = float(models["q0.5"].predict(x)[0])
    q90 = float(models["q0.9"].predict(x)[0])
    high = float(models["high"].predict(x)[0])
    return {
        "city": city, "edu": edu, "exp": exp, "tags": tags, "tier": tier,
        "salary_low_pessimistic": round(max(0, q10), 1),
        "salary_low_median": round(max(0, q50), 1),
        "salary_low_optimistic": round(max(0, q90), 1),
        "salary_high": round(max(0, high), 1),
        "salary_range": str(round(max(0, q50))) + "-" + str(round(max(0, high))) + "K",
        "confidence": "mid" if abs(q90-q10) < 15 else "low"
    }


class PredictHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if parsed.path == "/api/predict":
            city = qs.get("city", ["北京"])[0]
            edu = qs.get("edu", ["本科"])[0]
            exp = qs.get("exp", ["3-5年"])[0]
            tags = qs.get("tags", ["Java"])[0]
            tier = qs.get("tier", ["中大型企业"])[0]
            try:
                result = predict(city, edu, exp, tags, tier)
                self._send_json({"code": 0, "data": result})
            except Exception as e:
                self._send_json({"code": 1, "msg": str(e)}, 500)
        elif parsed.path == "/api/meta":
            self._send_json({"code": 0, "data": {"cities": CITIES, "edu": list(EDU_MAP.keys()), "exp": list(EXP_MAP.keys()), "tier": list(TIER_MAP.keys()), "feature_dim": FEATURE_DIM}})
        elif parsed.path == "/api/overview":
            self._send_json({"code": 0, "data": {"n_samples": MODEL["n_samples"], "feature_dim": MODEL["feature_dim"], "y_low_mean": MODEL["y_low_mean"], "y_high_mean": MODEL["y_high_mean"], "model_type": "XGBoost quantile"}})
        else:
            self._send_json({"code": 404, "msg": "not found"}, 404)

    def log_message(self, fmt, *args):
        print("[" + self.address_string() + "] " + (fmt % args))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8788
    server = HTTPServer(("0.0.0.0", port), PredictHandler)
    print("predict service on http://0.0.0.0:" + str(port))
    server.serve_forever()
