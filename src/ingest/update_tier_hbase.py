# -*- coding: utf-8 -*-
"""给 recruit_job 表的每行加 company_tier 列"""
import os, sys
import happybase

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "src", "ingest"))
sys.path.insert(0, BASE)
import config
from company_tier import infer_tier

conn = happybase.Connection(config.HBASE_HOST, config.HBASE_PORT, timeout=30000)
table = conn.table("recruit_job")
rows = list(table.scan())
print(f"扫描到 {len(rows)} 行")

batch = table.batch(batch_size=100)
updated = 0
for row_key, data in rows:
    company = data.get(b"info:company", b"").decode("utf-8")
    tier = infer_tier(company)
    batch.put(row_key.decode("utf-8"), {b"info:company_tier": tier.encode("utf-8")})
    updated += 1
    if updated % 200 == 0:
        print(f"  已更新 {updated}/{len(rows)}")
batch.send()
conn.close()
print(f"完成! 共更新 {updated} 行 company_tier 列")
