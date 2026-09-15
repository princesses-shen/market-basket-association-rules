# -*- coding: utf-8 -*-
"""
生成 1200 条岗位 + 5 个测试用户，灌入 HBase。
用 happybase 连 config/local.env 里配置的 HBase Thrift 地址。
"""
import happybase
import hashlib
import os
import random
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

HOST = config.HBASE_HOST; PORT = config.HBASE_PORT

# 数据池
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安", "长沙", "苏州", "重庆", "天津", "青岛", "厦门"]
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


def main():
    print(f">>> 连接 HBase {HOST}:{PORT} ...")
    conn = happybase.Connection(HOST, PORT)
    print(f"现有表: {[t.decode() if isinstance(t,bytes) else t for t in conn.tables()]}")

    print("\n>>> 生成岗位数据...")
    gen_jobs(conn, 1200)

    print("\n>>> 生成用户数据...")
    gen_users(conn)

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
