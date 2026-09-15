# -*- coding: utf-8 -*-
"""合并归档 JSONL -> data/clean/recruit_clean.tsv (10列 v1.1.0)"""
import os, sys, json, glob

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE, "data", "raw", "51job")
CLEAN_FILE = os.path.join(BASE, "data", "clean", "recruit_clean.tsv")

sys.path.insert(0, os.path.join(BASE, "src", "ingest"))
from company_tier import infer_tier

def merge():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "*.jsonl")))
    if not files:
        print("[ERROR] 没有找到采集数据, 请先运行 collect_v5.py")
        return

    print(f"合并 {len(files)} 个归档文件")
    all_jobs = []
    seen_ids = set()
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                job = json.loads(line.strip())
                if job["job_id"] not in seen_ids:
                    seen_ids.add(job["job_id"])
                    all_jobs.append(job)

    print(f"去重后 {len(all_jobs)} 条岗位")

    os.makedirs(os.path.dirname(CLEAN_FILE), exist_ok=True)
    with open(CLEAN_FILE, "w", encoding="utf-8") as f:
        # 表头
        f.write("city\tjob_id\ttitle\tcompany\tsalary_low\tsalary_high\tedu\texp\ttags\tcompany_tier\n")
        for job in all_jobs:
            tier = job.get("company_tier") or infer_tier(job.get("company", ""))
            f.write("\t".join([
                job["city"], job["job_id"], job["title"], job["company"],
                str(job["salary_low"]), str(job["salary_high"]),
                job.get("edu", "不限"), job.get("exp", "不限"),
                job.get("tags", ""), tier
            ]) + "\n")

    print(f"清洗完成 -> {CLEAN_FILE}")
    print(f"运行契约校验: python tests/test_schema.py")

if __name__ == "__main__":
    merge()
