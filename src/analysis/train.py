# -*- coding: utf-8 -*-
"""
XGBoost 薪资预测器训练
目标: 给定城市/学历/经验/技术栈/公司档次 -> 预测薪资下限和区间(分位数回归)
产出: artifacts/models/salary_predictor.pkl
"""
import os, sys, pickle, numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "src", "analysis"))
sys.path.insert(0, os.path.join(BASE, "src"))

from features import featurize_batch, CITIES, FEATURE_DIM
import happybase

# === 1. 从 HBase 读数据 ===
def load_from_hbase():
    host = os.environ.get("HBASE_HOST", "192.168.92.128")
    port = int(os.environ.get("HBASE_PORT", "9090"))
    conn = happybase.Connection(host, port, timeout=30000)
    table = conn.table("recruit_job")
    rows = list(table.scan())
    conn.close()
    data = []
    for rk, d in rows:
        city = d.get(b"info:city", b"").decode("utf-8")
        edu = d.get(b"info:edu", b"").decode("utf-8")
        exp = d.get(b"info:exp", b"").decode("utf-8")
        tags = d.get(b"info:tags", b"").decode("utf-8")
        tier = d.get(b"info:company_tier", "中小-初创".encode("utf-8")).decode("utf-8")
        sal_low = int(d.get(b"info:salary_low", b"0").decode("utf-8") or "0")
        sal_high = int(d.get(b"info:salary_high", b"0").decode("utf-8") or "0")
        data.append((city, edu, exp, tags, tier, sal_low, sal_high))
    return data

# === 2. 训练 XGBoost 分位数预测器 ===
def train():
    print(">>> 1. 从 HBase 加载数据")
    data = load_from_hbase()
    print(f"    {len(data)} 条岗位数据")

    features_list = [(d[0], d[1], d[2], d[3], d[4]) for d in data]
    X = featurize_batch(features_list)
    y_low = np.array([d[5] for d in data], dtype=np.float32)
    y_high = np.array([d[6] for d in data], dtype=np.float32)
    print(f"    特征矩阵: {X.shape}, 目标: y_low均值={y_low.mean():.1f}K, y_high均值={y_high.mean():.1f}K")

    print(">>> 2. 训练 XGBoost 分位数回归")
    import xgboost as xgb

    # 分位数: 0.1(保守) / 0.5(中位) / 0.9(乐观)
    quantiles = [0.1, 0.5, 0.9]
    models = {}
    for q in quantiles:
        print(f"    训练 q={q} ...")
        reg = xgb.XGBRegressor(
            objective="reg:quantileerror",
            quantile_alpha=q,
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )
        reg.fit(X, y_low, eval_set=[(X, y_low)], verbose=False)
        train_score = reg.score(X, y_low)
        print(f"      q={q} R2={train_score:.3f}")
        models[f"q{q}"] = reg

    # 也训练一个上限预测器
    print("    训练上限预测器 (q=0.5) ...")
    reg_high = xgb.XGBRegressor(
        objective="reg:squarederror",
        n_estimators=200, max_depth=6, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, random_state=42
    )
    reg_high.fit(X, y_high, eval_set=[(X, y_high)], verbose=False)
    print(f"      上限 R2={reg_high.score(X, y_high):.3f}")
    models["high"] = reg_high

    # === 3. 保存模型 ===
    model_path = os.path.join(BASE, "artifacts", "models", "salary_predictor.pkl")
    bundle = {
        "models": models,
        "feature_dim": FEATURE_DIM,
        "cities": CITIES,
        "n_samples": len(data),
        "y_low_mean": float(y_low.mean()),
        "y_high_mean": float(y_high.mean())
    }
    with open(model_path, "wb") as f:
        pickle.dump(bundle, f)
    print(f">>> 3. 模型已保存: {model_path}")
    print(f"    大小: {os.path.getsize(model_path)//1024} KB")
    print(f"    样本数: {len(data)}, 特征维度: {FEATURE_DIM}")
    print(f"    薪资下限均值: {y_low.mean():.1f}K, 上限均值: {y_high.mean():.1f}K")
    return model_path

if __name__ == "__main__":
    train()
