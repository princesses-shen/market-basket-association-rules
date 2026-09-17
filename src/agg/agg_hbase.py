# -*- coding: utf-8 -*-
"""
聚合层：从 recruit_clean.tsv 生成统计表写入 HBase
==================================================
产出 5 张统计表，供 Spring Boot 大屏接口读取：
  recruit_position     城市 → 岗位数
  recruit_salary       薪资区间 → 岗位数
  recruit_salary_trend 薪资趋势序列（按 low 升序）
  recruit_keyword      技能关键词 → 出现次数
  recruit_tier          公司档次 → 岗位数 + 平均薪资

用法：
  python src/agg/agg_hbase.py                 # 写入 HBase
  python src/agg/agg_hbase.py --local         # 仅输出 CSV 到 data/processed/
"""
import os
import sys
import argparse
from collections import Counter, defaultdict

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_CLEAN = os.path.join(BASE, "data", "clean", "recruit_clean.tsv")
DATA_PROCESSED = os.path.join(BASE, "data", "processed")
os.makedirs(DATA_PROCESSED, exist_ok=True)

HBASE_HOST = os.environ.get("HBASE_HOST", "192.168.92.128")
HBASE_PORT = int(os.environ.get("HBASE_PORT", "9090"))
CF = "info"


def load_clean():
    if not os.path.exists(DATA_CLEAN):
        print(f"[ERROR] {DATA_CLEAN} 不存在，请先运行 make gen-data 或 make merge")
        sys.exit(1)
    df = pd.read_csv(DATA_CLEAN, sep="\t")
    print(f"加载 {len(df)} 条岗位数据")
    return df


def agg_position(df):
    """城市 → 岗位数"""
    counts = df["city"].value_counts()
    return {city: int(c) for city, c in counts.items()}


def agg_salary(df):
    """薪资区间 → 岗位数"""
    bins = [0, 5, 10, 15, 20, 30, 50, 999]
    labels = ["0-5K", "5-10K", "10-15K", "15-20K", "20-30K", "30-50K", "50K+"]
    ranges = pd.cut(df["salary_low"], bins=bins, labels=labels, right=False)
    counts = ranges.value_counts().sort_index()
    return {str(idx): int(c) for idx, c in counts.items()}


def agg_salary_trend(df):
    """薪资趋势：按 salary_low 升序取前 30 条 low/high 序列"""
    sorted_df = df.sort_values("salary_low").head(30)
    return [(int(r["salary_low"]), int(r["salary_high"])) for _, r in sorted_df.iterrows()]


def agg_keyword(df):
    """技能关键词 → 出现次数"""
    counter = Counter()
    for tags in df["tags"].dropna():
        for t in str(tags).split(";"):
            t = t.strip()
            if t:
                counter[t] += 1
    return dict(counter.most_common(100))


def agg_tier(df):
    """公司档次 → 岗位数 + 平均薪资"""
    tier_stats = defaultdict(lambda: {"count": 0, "sal_low_sum": 0, "sal_high_sum": 0})
    for _, r in df.iterrows():
        tier = r.get("company_tier", "中小-初创")
        s = tier_stats[tier]
        s["count"] += 1
        s["sal_low_sum"] += int(r["salary_low"])
        s["sal_high_sum"] += int(r["salary_high"])
    result = {}
    for tier, s in tier_stats.items():
        avg_low = s["sal_low_sum"] / s["count"] if s["count"] else 0
        avg_high = s["sal_high_sum"] / s["count"] if s["count"] else 0
        result[tier] = {
            "count": s["count"],
            "avg_salary": round((avg_low + avg_high) / 2, 1),
        }
    return result


def write_local(position, salary, trend, keyword, tier):
    """本地模式：写 CSV 到 data/processed/"""
    pd.DataFrame(list(position.items()), columns=["city", "count"]).to_csv(
        os.path.join(DATA_PROCESSED, "agg_position.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(list(salary.items()), columns=["range", "count"]).to_csv(
        os.path.join(DATA_PROCESSED, "agg_salary.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(trend, columns=["low", "high"]).to_csv(
        os.path.join(DATA_PROCESSED, "agg_salary_trend.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(list(keyword.items()), columns=["keyword", "count"]).to_csv(
        os.path.join(DATA_PROCESSED, "agg_keyword.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([
        {"tier": t, "count": v["count"], "avg_salary": v["avg_salary"]}
        for t, v in tier.items()
    ]).to_csv(
        os.path.join(DATA_PROCESSED, "agg_tier.csv"), index=False, encoding="utf-8-sig")
    print(f"[本地] 5 个统计 CSV 已写入 {DATA_PROCESSED}")


def write_hbase(position, salary, trend, keyword, tier):
    """写入 HBase 5 张统计表"""
    try:
        import happybase
    except ImportError:
        print("[ERROR] happybase 未安装，请 pip install happybase 或使用 --local 模式")
        return

    print(f"连接 HBase {HBASE_HOST}:{HBASE_PORT} ...")
    conn = happybase.Connection(HBASE_HOST, HBASE_PORT, timeout=30000)
    existing = [t.decode() if isinstance(t, bytes) else t for t in conn.tables()]

    def ensure_table(name):
        if name in existing:
            conn.disable_table(name)
            conn.delete_table(name)
        conn.create_table(name, {CF: dict()})
        print(f"  [建表] {name}")
        return conn.table(name)

    # 1. recruit_position
    print("写入 recruit_position ...")
    t = ensure_table("recruit_position")
    with t.batch() as b:
        for city, count in position.items():
            b.put(city, {f"{CF}:position_count": str(count)})

    # 2. recruit_salary
    print("写入 recruit_salary ...")
    t = ensure_table("recruit_salary")
    with t.batch() as b:
        for rng, count in salary.items():
            b.put(rng, {f"{CF}:count": str(count)})

    # 3. recruit_salary_trend
    print("写入 recruit_salary_trend ...")
    t = ensure_table("recruit_salary_trend")
    with t.batch() as b:
        for i, (low, high) in enumerate(trend):
            b.put(f"row_{i:04d}", {f"{CF}:low": str(low), f"{CF}:high": str(high)})

    # 4. recruit_keyword
    print("写入 recruit_keyword ...")
    t = ensure_table("recruit_keyword")
    with t.batch() as b:
        for kw, count in keyword.items():
            b.put(kw, {f"{CF}:count": str(count)})

    # 5. recruit_tier
    print("写入 recruit_tier ...")
    t = ensure_table("recruit_tier")
    with t.batch() as b:
        for tier_name, stats in tier.items():
            b.put(tier_name, {
                f"{CF}:count": str(stats["count"]),
                f"{CF}:avg_salary": str(stats["avg_salary"]),
            })

    conn.close()
    print("[HBase] 5 张统计表写入完成！")


def main():
    parser = argparse.ArgumentParser(description="聚合统计表到 HBase 或本地 CSV")
    parser.add_argument("--local", action="store_true", help="仅输出 CSV，不连 HBase")
    args = parser.parse_args()

    df = load_clean()

    position = agg_position(df)
    salary = agg_salary(df)
    trend = agg_salary_trend(df)
    keyword = agg_keyword(df)
    tier = agg_tier(df)

    print(f"\n聚合结果：")
    print(f"  城市: {len(position)} 个")
    print(f"  薪资区间: {len(salary)} 档")
    print(f"  趋势序列: {len(trend)} 条")
    print(f"  关键词: {len(keyword)} 个")
    print(f"  公司档次: {len(tier)} 档")

    if args.local:
        write_local(position, salary, trend, keyword, tier)
    else:
        write_hbase(position, salary, trend, keyword, tier)


if __name__ == "__main__":
    main()
