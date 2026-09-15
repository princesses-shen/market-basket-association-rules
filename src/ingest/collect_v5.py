# -*- coding: utf-8 -*-
"""
51job 真实数据采集 (Playwright)
拉满到风控边界, 增量归档可续采
产出: data/raw/51job/YYYYMMDD_HHMMSS.jsonl
"""
import os, sys, json, time, asyncio
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RAW_DIR = os.path.join(BASE, "data", "raw", "51job")

CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安", "长沙"]
KEYWORDS = ["Java", "Python", "前端", "测试", "运维", "数据分析", "算法", "产品经理", "UI设计", "安全"]

async def crawl_51job(keyword, city, max_pages=5):
    """
    用 Playwright 采集 51job 招聘数据
    返回 list of dict: {city, job_id, title, company, salary_low, salary_high, edu, exp, tags, company_tier}
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[ERROR] 需要安装: pip install playwright && playwright install chromium")
        return []

    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for page_num in range(1, max_pages + 1):
            url = f"https://we.51job.com/pc/search?keyword={keyword}&jobArea={city}&curr={page_num}"
            try:
                await page.goto(url, timeout=15000)
                await page.wait_for_selector(".joblist-box", timeout=5000)
            except Exception as e:
                print(f"  [WARN] {keyword}/{city} 第{page_num}页: {e}")
                break

            items = await page.query_selector_all(".joblist-box .j_joblist")
            for item in items:
                try:
                    title_el = await item.query_selector(".jname")
                    company_el = await item.query_selector(".cname")
                    salary_el = await item.query_selector(".sal")
                    info_el = await item.query_selector(".d_at2 .info span")

                    title = await title_el.inner_text() if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    salary_text = await salary_el.inner_text() if salary_el else "0-0"

                    # 解析薪资 "10-20K/月" -> low=10, high=20
                    import re
                    sal_match = re.match(r"(\d+)\-(\d+)", salary_text)
                    sal_low = int(sal_match.group(1)) if sal_match else 0
                    sal_high = int(sal_match.group(2)) if sal_match else 0

                    results.append({
                        "city": city,
                        "job_id": f"job_{len(results):05d}",
                        "title": title,
                        "company": company,
                        "salary_low": sal_low,
                        "salary_high": sal_high,
                        "edu": "",
                        "exp": "",
                        "tags": keyword,
                        "company_tier": ""
                    })
                except Exception:
                    continue

            time.sleep(1)  # 风控间隔

        await browser.close()
    return results


async def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(RAW_DIR, f"{timestamp}.jsonl")

    all_results = []
    for kw in KEYWORDS[:3]:  # 先采前3个关键词 (演示)
        for city in CITIES[:5]:  # 前5个城市
            print(f"采集: {kw} @ {city}")
            jobs = await crawl_51job(kw, city, max_pages=3)
            all_results.extend(jobs)
            print(f"  采集到 {len(jobs)} 条")

    with open(output_file, "w", encoding="utf-8") as f:
        for job in all_results:
            f.write(json.dumps(job, ensure_ascii=False) + "\n")

    print(f"\n采集完成! {len(all_results)} 条 -> {output_file}")
    print("下一步: python src/ingest/merge_clean.py 合并清洗")


if __name__ == "__main__":
    asyncio.run(main())
