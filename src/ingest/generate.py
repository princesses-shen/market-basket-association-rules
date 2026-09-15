# -*- coding: utf-8 -*-
"""种子数据生成 (教学兜底, 不与真实采集混淆)"""
import os, sys, random

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "src", "ingest"))
from company_tier import infer_tier

CITIES = ["北京","上海","广州","深圳","杭州","成都","南京","武汉","西安","长沙","苏州","重庆","天津","青岛","厦门"]
TITLES = ["Java开发工程师","前端开发工程师","Python工程师","测试工程师","运维工程师","数据分析师","算法工程师","产品经理","UI设计师","安全工程师","Go开发工程师","C++开发工程师","Android开发","iOS开发","全栈工程师"]
COMPANIES = ["阿里巴巴","腾讯科技","字节跳动","百度","华为","京东","小米","美团","拼多多","网易","快手","哔哩哔哩","蚂蚁集团","微软中国","IBM","某科技有限公司","XX咨询有限公司","创业团队"]
EDUS = ["不限","大专","本科","硕士"]
EXPS = ["应届","1年","1-3年","3-5年","5-10年"]
TAGS_POOL = ["Java","Spring","MySQL","Python","Django","Flask","Vue","React","Angular","Node.js","Go","Docker","Kubernetes","Redis","MongoDB","Hadoop","Spark","Flink","TensorFlow","PyTorch","CI/CD","Git","Linux","Nginx"]
CATEGORIES = ["后端开发","前端开发","测试","运维","数据","算法","产品","设计","安全","移动开发"]

def gen(n=1200):
    rows = []
    for i in range(n):
        city = random.choice(CITIES)
        title = random.choice(TITLES)
        company = random.choice(COMPANIES)
        sal_low = random.randint(5, 30)
        sal_high = sal_low + random.randint(5, 25)
        edu = random.choice(EDUS)
        exp = random.choice(EXPS)
        tags = ";".join(random.sample(TAGS_POOL, random.randint(2, 6)))
        tier = infer_tier(company)
        rows.append({
            "city": city, "job_id": f"job_{i:05d}", "title": title, "company": company,
            "salary_low": sal_low, "salary_high": sal_high, "edu": edu, "exp": exp,
            "tags": tags, "company_tier": tier
        })
    return rows

def write_tsv(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("city\tjob_id\ttitle\tcompany\tsalary_low\tsalary_high\tedu\texp\ttags\tcompany_tier\n")
        for r in rows:
            f.write("\t".join([r["city"],r["job_id"],r["title"],r["company"],
                str(r["salary_low"]),str(r["salary_high"]),r["edu"],r["exp"],r["tags"],r["company_tier"]]) + "\n")

if __name__ == "__main__":
    rows = gen(1200)
    path = os.path.join(BASE, "data", "clean", "recruit_clean.tsv")
    write_tsv(rows, path)
    print(f"生成 {len(rows)} 条种子数据 -> {path}")
