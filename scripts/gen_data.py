# -*- coding: utf-8 -*-
"""
生成 1200 条岗位 + 5 个测试用户，灌入 HBase。
用 happybase 连虚拟机 192.168.92.128:9090。
"""
import os
import happybase
import hashlib
import random
import time
from datetime import datetime, timedelta

HOST = os.environ.get("HBASE_HOST", "192.168.92.128"); PORT = int(os.environ.get("HBASE_PORT", "9090"))

# 数据池
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安", "长沙", "苏州", "重庆",
          "天津", "青岛", "厦门", "宁波", "郑州", "合肥", "福州", "济南", "大连", "沈阳", "长春",
          "哈尔滨", "石家庄", "太原", "南昌", "南宁", "昆明", "贵阳", "兰州", "西宁", "银川",
          "乌鲁木齐", "呼和浩特", "海口", "三亚", "珠海", "东莞", "佛山", "无锡", "常州", "南通",
          "徐州", "温州", "绍兴", "嘉兴", "泉州", "烟台", "潍坊", "洛阳"]
TITLES = ["Java开发工程师", "Python开发工程师", "前端开发工程师", "后端开发工程师", "全栈工程师",
          "数据分析师", "算法工程师", "测试工程师", "运维工程师", "DevOps工程师",
          "产品经理", "UI设计师", "项目经理", "大数据工程师", "机器学习工程师",
          "Go开发工程师", "Android开发", "iOS开发", "数据库工程师", "安全工程师"]
COMPANIES = ["字节跳动", "腾讯", "阿里巴巴", "百度", "美团", "京东", "网易", "小米", "华为",
             "拼多多", "快手", "滴滴", "携程", "哔哩哔哩", "蚂蚁集团", "菜鸟网络",
             "大疆创新", "商汤科技", "旷视科技", "地平线", "蔚来汽车", "理想汽车",
             "小红书", "知乎", "链家", "贝壳找房", "同程旅行", "58同城", "新浪微博", "搜狐"]
EDUS = ["不限", "大专", "本科", "本科", "本科", "硕士"]  # 本科多一些
EXPS = ["应届", "1年", "1-3年", "1-3年", "3-5年", "3-5年", "5-10年", "不限"]
CATEGORIES = ["后端开发", "前端开发", "移动开发", "测试", "运维", "数据", "算法", "产品", "设计", "安全"]
TAGS_POOL = ["Java", "Python", "Go", "React", "Vue", "Spring", "MySQL", "Redis", "Docker",
             "Kubernetes", "Linux", "Hadoop", "Spark", "Flink", "Kafka", "ElasticSearch",
             "TensorFlow", "PyTorch", "微服务", "分布式", "高并发", "机器学习", "深度学习"]
SALARY_RANGES = [(5, 10), (8, 15), (10, 20), (15, 25), (15, 30), (20, 35), (25, 40), (30, 50), (35, 60)]


def gen_desc(title, company, city, edu, exp):
    """生成岗位描述"""
    return (f"【岗位名称】{title}\n"
            f"【工作地点】{city}\n"
            f"【学历要求】{edu}\n"
            f"【经验要求】{exp}\n\n"
            f"岗位职责：\n1. 负责{company}相关产品的技术架构和开发；\n"
            f"2. 参与系统设计，保证系统的高可用性和高性能；\n"
            f"3. 与团队协作，按时交付高质量代码。\n\n"
            f"任职要求：\n1. {edu}及以上学历，{exp}相关工作经验；\n"
            f"2. 熟悉常用的开发框架和工具；\n3. 良好的沟通能力和团队合作精神；\n"
            f"4. 有大型互联网公司经验者优先。")


def gen_jobs(conn, n=1200):
    """生成 n 条岗位数据写入 recruit_job 表"""
    # 建表
    tables = [t.decode() if isinstance(t, bytes) else t for t in conn.tables()]
    if "recruit_job" in tables:
        conn.disable_table("recruit_job")
        conn.delete_table("recruit_job")
    conn.create_table("recruit_job", {"info": dict()})
    print(f"[建表] recruit_job")

    table = conn.table("recruit_job")
    now = datetime.now()
    with table.batch() as b:
        for i in range(1, n + 1):
            title = random.choice(TITLES)
            city = random.choice(CITIES)
            company = random.choice(COMPANIES)
            edu = random.choice(EDUS)
            exp = random.choice(EXPS)
            sal = random.choice(SALARY_RANGES)
            category = random.choice(CATEGORIES)
            tags = random.sample(TAGS_POOL, random.randint(3, 6))
            # 发布时间：最近 30 天内随机
            pub = (now - timedelta(days=random.randint(0, 29),
                                   hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M")
            row_key = f"job_{i:05d}"
            b.put(row_key, {
                "info:title": title,
                "info:city": city,
                "info:salary_low": str(sal[0]),
                "info:salary_high": str(sal[1]),
                "info:company": company,
                "info:edu": edu,
                "info:exp": exp,
                "info:category": category,
                "info:tags": ";".join(tags),
                "info:desc": gen_desc(title, company, city, edu, exp),
                "info:publish_time": pub,
                "info:owner": "demo_co" if i <= 50 else "",
                "info:status": "active",
            })
    print(f"[灌数据] {n} 条岗位写入 recruit_job")


def gen_users(conn):
    """生成 5 个测试用户写入 recruit_user 表"""
    tables = [t.decode() if isinstance(t, bytes) else t for t in conn.tables()]
    if "recruit_user" in tables:
        conn.disable_table("recruit_user")
        conn.delete_table("recruit_user")
    conn.create_table("recruit_user", {"info": dict()})
    print(f"[建表] recruit_user")

    table = conn.table("recruit_user")
    users = [
        ("admin", "123456", "admin@recruit.com", "13800000001", "admin", "管理员"),
        ("xiaoliyu", "123456", "xiaoliyu@recruit.com", "13800000002", "user", "小李鱼"),
        ("zhangsan", "123456", "zhangsan@recruit.com", "13800000003", "user", "张三"),
        ("lisi", "123456", "lisi@recruit.com", "13800000004", "user", "李四"),
        ("wangwu", "123456", "wangwu@recruit.com", "13800000005", "user", "王五"),
    ]
    with table.batch() as b:
        for username, pwd, email, phone, role, nickname in users:
            pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()
            b.put(username, {
                "info:password": pwd_hash,
                "info:email": email,
                "info:phone": phone,
                "info:role": role,
                "info:nickname": nickname,
                "info:created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
    print(f"[灌数据] {len(users)} 个用户写入 recruit_user")
    print(f"  测试账号: admin/123456, xiaoliyu/123456, zhangsan/123456 ...")


def gen_supporting_tables(conn):
    """创建网站功能需要的辅助表，并写入本地开发用企业账号。"""
    tables = {t.decode() if isinstance(t, bytes) else t for t in conn.tables()}
    required = [
        "recruit_company", "recruit_resume", "recruit_chat_session",
        "recruit_chat_message", "recruit_application", "recruit_talent_pool",
        "recruit_position", "recruit_salary", "recruit_salary_trend",
        "recruit_keyword", "recruit_assoc_rules"
    ]
    for table_name in required:
        if table_name not in tables:
            conn.create_table(table_name, {"info": dict()})
            print(f"[建表] {table_name}")

    company = conn.table("recruit_company")
    company.put("demo_co", {
        "info:password_hash": hashlib.sha256(b"123456").hexdigest(),
        "info:company_name": "智聘科技",
        "info:industry": "互联网",
        "info:city": "北京",
        "info:scale": "150-500人",
        "info:created_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    print("[灌数据] 企业测试账号 demo_co/123456")

    # 城市统计表供数据大屏使用；城市下拉本身会直接从 recruit_job 动态读取。
    position = conn.table("recruit_position")
    job_table = conn.table("recruit_job")
    city_counts = {}
    for _, data in job_table.scan(columns=["info:city"]):
        city = data.get(b"info:city", b"").decode("utf-8")
        if city:
            city_counts[city] = city_counts.get(city, 0) + 1
    with position.batch() as batch:
        for city, count in city_counts.items():
            batch.put(city, {"info:position_count": str(count)})


def main():
    print(f">>> 连接 HBase {HOST}:{PORT} ...")
    conn = happybase.Connection(HOST, PORT)
    print(f"现有表: {[t.decode() if isinstance(t,bytes) else t for t in conn.tables()]}")

    print("\n>>> 生成岗位数据...")
    gen_jobs(conn, 1200)

    print("\n>>> 生成用户数据...")
    gen_users(conn)

    print("\n>>> 创建网站辅助表...")
    gen_supporting_tables(conn)

    # 验证
    print("\n>>> 验证数据...")
    jt = conn.table("recruit_job")
    jcount = sum(1 for _ in jt.scan())
    print(f"recruit_job: {jcount} 行")
    for key, data in jt.scan(limit=2):
        print(f"  {key.decode()}: {data}")

    ut = conn.table("recruit_user")
    ucount = sum(1 for _ in ut.scan())
    print(f"recruit_user: {ucount} 行")

    conn.close()
    print("\n>>> 数据生成完成！")


if __name__ == "__main__":
    main()
