# -*- coding: utf-8 -*-
"""
天池真实岗位数据 → 项目 recruit_clean.tsv 格式转换
数据源：https://tianchi.aliyun.com/dataset/221302
"""
import csv
import os
import sys

SRC_DIR = r"D:\Downloads\岗位数据\岗位数据"
BASE_DIR = r"D:\桌面\09-购物篮技能组合分析-关联规则"
OUTPUT = os.path.join(BASE_DIR, "data", "clean", "recruit_clean.tsv")

COMPANIES_BIGTECH = {
    "腾讯", "阿里巴巴", "字节跳动", "百度", "华为", "美团", "京东", "网易",
    "小米", "拼多多", "快手", "滴滴", "哔哩哔哩", "携程", "蚂蚁集团",
    "新浪", "搜狐", "360", "新浪微博", "联想", "大疆",
}

def guess_tier(company, company_type, company_size):
    if company in COMPANIES_BIGTECH:
        return "头部大厂"
    size = str(company_size)
    if "10000" in size or "5000" in size:
        return "大型企业"
    if "1000" in size or "500" in size:
        return "中型企业"
    if "上市" in str(company_type) or "股份" in str(company_type):
        return "中型企业"
    if "外资" in str(company_type) or "外商" in str(company_type) or "合资" in str(company_type):
        return "外企"
    if "国企" in str(company_type) or "国有" in str(company_type):
        return "国企"
    if "创业" in str(company_type) or "天使" in str(company_type):
        return "创业公司"
    return "中型企业"

def normalize_category(cat):
    mapping = {
        "技术": "后端开发",
        "产品": "产品经理",
        "运营": "运营",
        "市场": "市场推广",
        "设计": "UI设计",
        "职能": "职能管理",
    }
    return mapping.get(cat, "后端开发")

def refine_category(title, skills, base_cat):
    """根据标题和技能细化岗位类别"""
    title = str(title)
    skills_lower = str(skills).lower()
    # 技术类细分
    if "前端" in title or "vue" in skills_lower or "react" in skills_lower or "css" in skills_lower:
        return "前端开发"
    if "android" in title.lower() or "ios" in title.lower() or "移动" in title:
        return "移动开发"
    if "算法" in title or "机器学习" in title or "深度学习" in title or "AI" in title:
        return "算法工程师"
    if "数据" in title and ("分析" in title or "挖掘" in title):
        return "数据分析"
    if "测试" in title or "qa" in title.lower():
        return "测试开发"
    if "运维" in title or "devops" in title.lower() or "sre" in title.lower():
        return "运维工程师"
    # 产品类
    if "产品" in title or "pm" in title.lower():
        return "产品经理"
    # 设计类细分
    if "ui" in title.lower() or "交互" in title or "视觉" in title:
        return "UI设计"
    if "设计" in title:
        return "UI设计"
    # 市场类
    if "市场" in title or "营销" in title or "品牌" in title or "推广" in title:
        return "市场推广"
    # 职能类
    if "人事" in title or "hr" in title.lower() or "行政" in title or "财务" in title or "法务" in title:
        return "职能管理"
    # 运营类
    if "运营" in title or "内容" in title or "用户" in title or "新媒体" in title:
        return "运营"
    # 技术类默认 → 根据技能进一步判断
    if base_cat == "技术":
        if "python" in skills_lower or "java" in skills_lower or "go" in skills_lower or "c++" in skills_lower:
            return "后端开发"
        if "sql" in skills_lower or "spark" in skills_lower or "hadoop" in skills_lower:
            return "数据分析"
        return "后端开发"
    return normalize_category(base_cat)

def normalize_skills(skills_str):
    if not skills_str:
        return ""
    tags = [s.strip() for s in str(skills_str).split(",") if s.strip()]
    return ";".join(tags[:8])

def main():
    src = os.path.join(SRC_DIR, "jobs.csv")
    if not os.path.exists(src):
        print(f"错误：找不到 {src}")
        sys.exit(1)

    jobs = []
    with open(src, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            company = row.get("company_name", "").strip()
            company_type = row.get("company_type", "").strip()
            company_size = row.get("company_size", "").strip()
            title = row.get("job_title", "").strip()
            skills = row.get("skills", "").strip()
            base_cat = row.get("job_category", "技术").strip()

            job = {
                "job_id": row.get("job_id", ""),
                "title": title,
                "company": company,
                "city": row.get("city", "").strip(),
                "salary_low": int(float(row.get("salary_min", "0") or "0") / 1000),
                "salary_high": int(float(row.get("salary_max", "0") or "0") / 1000),
                "edu": row.get("education", "不限").strip(),
                "exp": row.get("experience", "不限").strip(),
                "tags": normalize_skills(skills),
                "category": refine_category(title, skills, base_cat),
                "company_tier": guess_tier(company, company_type, company_size),
                "desc": (row.get("job_description", "") + "\n\n任职要求：\n" + row.get("requirements", "")).strip(),
                "publish_time": row.get("publish_date", "").strip(),
            }
            jobs.append(job)

    # 保存为 TSV
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    fieldnames = ["job_id", "title", "company", "city", "salary_low", "salary_high",
                  "edu", "exp", "tags", "category", "company_tier", "desc", "publish_time"]

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(jobs)

    # 统计
    cities = {}
    cats = {}
    salaries = []
    companies = set()
    for j in jobs:
        cities[j["city"]] = cities.get(j["city"], 0) + 1
        cats[j["category"]] = cats.get(j["category"], 0) + 1
        salaries.append(j["salary_low"])
        companies.add(j["company"])

    print(f"天池真实数据导入完成！")
    print(f"总岗位数: {len(jobs)}")
    print(f"公司数: {len(companies)}")
    print(f"城市数: {len(cities)}")
    print(f"岗位类别: {len(cats)}")
    print(f"平均最低薪资: {sum(salaries)/len(salaries):.1f}K")
    print(f"最高薪资: {max(salaries)}K")
    print(f"最低薪资: {min(salaries)}K")
    print(f"\n城市分布:")
    for c, n in sorted(cities.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n} 条")
    print(f"\n类别分布:")
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n} 条")
    print(f"\n数据已保存: {OUTPUT}")

if __name__ == "__main__":
    main()
