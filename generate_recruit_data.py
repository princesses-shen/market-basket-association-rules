# -*- coding: utf-8 -*-
"""
生成仿真招聘数据
基于真实招聘规律：薪资与经验、学历、城市、岗位类别、公司层级相关
"""
import pandas as pd
import numpy as np
import random
import hashlib
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

# ============ 基础配置 ============

CITIES = [
    # 一线城市
    ("北京", "一线"), ("上海", "一线"), ("深圳", "一线"), ("广州", "一线"),
    # 新一线
    ("杭州", "新一线"), ("成都", "新一线"), ("武汉", "新一线"),
    ("南京", "新一线"), ("苏州", "新一线"), ("西安", "新一线"),
    ("重庆", "新一线"), ("天津", "新一线"), ("长沙", "新一线"),
    ("郑州", "新一线"), ("青岛", "新一线"), ("合肥", "新一线"),
    ("佛山", "新一线"), ("东莞", "新一线"), ("宁波", "新一线"),
    # 二线
    ("济南", "二线"), ("大连", "二线"), ("厦门", "二线"), ("福州", "二线"),
    ("南昌", "二线"), ("南宁", "二线"), ("昆明", "二线"), ("贵阳", "二线"),
    ("兰州", "二线"), ("太原", "二线"), ("石家庄", "二线"), ("沈阳", "二线"),
    ("长春", "二线"), ("哈尔滨", "二线"), ("海口", "二线"), ("三亚", "二线"),
    ("呼和浩特", "二线"), ("银川", "二线"), ("西宁", "二线"),
    ("乌鲁木齐", "二线"),
]

CITY_WEIGHTS = {
    "一线": 1.8,
    "新一线": 2.0,
    "二线": 1.0,
}

CITY_SALARY_FACTOR = {
    "一线": 1.4,
    "新一线": 1.1,
    "二线": 0.85,
}

EDUCATIONS = ["不限", "大专", "本科", "硕士", "博士"]
EDU_WEIGHTS = [0.20, 0.20, 0.20, 0.22, 0.18]
EDU_SALARY_FACTOR = {
    "不限": 0.85,
    "大专": 0.75,
    "本科": 1.0,
    "硕士": 1.3,
    "博士": 1.8,
}

EXPERIENCES = ["应届生", "1-3年", "3-5年", "5-10年", "10年以上", "不限"]
EXP_WEIGHTS = [0.15, 0.20, 0.18, 0.17, 0.15, 0.15]
EXP_SALARY_BASE = {
    "应届生": 6,
    "1-3年": 10,
    "3-5年": 15,
    "5-10年": 22,
    "10年以上": 30,
    "不限": 9,
}

CATEGORIES = [
    ("前端开发", "技术"), ("后端开发", "技术"), ("测试开发", "技术"),
    ("算法工程师", "技术"), ("数据分析", "技术"), ("运维工程师", "技术"),
    ("产品经理", "产品"), ("UI设计", "设计"),
    ("运营", "运营"), ("市场推广", "市场"),
    ("职能管理", "职能"),
]
CATEGORY_WEIGHTS = [0.06, 0.05, 0.01, 0.03, 0.02, 0.02, 0.08, 0.22, 0.18, 0.17, 0.16]
CATEGORY_SALARY_FACTOR = {
    "前端开发": 1.15,
    "后端开发": 1.15,
    "测试开发": 1.10,
    "算法工程师": 1.25,
    "数据分析": 1.05,
    "运维工程师": 1.05,
    "产品经理": 0.95,
    "UI设计": 0.90,
    "运营": 0.82,
    "市场推广": 0.85,
    "职能管理": 0.75,
}

COMPANY_TIERS = ["头部大厂", "大型企业", "中型企业"]
TIER_WEIGHTS = [0.45, 0.10, 0.45]
TIER_SALARY_FACTOR = {
    "头部大厂": 1.25,
    "大型企业": 1.10,
    "中型企业": 0.90,
}

# 各分类的岗位标题模板
JOB_TITLES = {
    "前端开发": [
        "高级前端开发工程师", "前端开发工程师", "资深前端架构师",
        "Web前端开发", "React前端工程师", "Vue前端开发",
        "前端技术专家", "H5开发工程师", "小程序开发工程师",
    ],
    "后端开发": [
        "Java后端开发工程师", "Python后端开发", "Go开发工程师",
        "高级后端工程师", "后端架构师", "全栈开发工程师",
        "服务端开发工程师", "后端技术专家", "PHP开发工程师",
    ],
    "测试开发": [
        "测试开发工程师", "高级测试开发", "自动化测试工程师",
        "性能测试专家", "测试架构师", "接口测试工程师",
    ],
    "算法工程师": [
        "算法工程师", "高级算法工程师", "机器学习算法专家",
        "推荐算法工程师", "NLP算法工程师", "计算机视觉算法",
        "深度学习工程师", "算法研究员", "数据挖掘工程师",
    ],
    "数据分析": [
        "数据分析师", "高级数据分析师", "商业分析师",
        "数据产品经理", "BI分析师", "数据运营分析师",
    ],
    "运维工程师": [
        "运维工程师", "高级运维工程师", "DevOps工程师",
        "SRE运维专家", "运维架构师", "云平台运维",
    ],
    "产品经理": [
        "产品经理", "高级产品经理", "产品总监",
        "B端产品经理", "C端产品经理", "产品运营经理",
        "电商产品经理", "增长产品经理", "AI产品经理",
    ],
    "UI设计": [
        "UI设计师", "高级UI设计师", "视觉设计师",
        "交互设计师", "平面设计师", "网页设计师",
        "品牌设计师", "电商设计师", "APP界面设计师",
        "游戏UI设计师", "动效设计师", "插画设计师",
    ],
    "运营": [
        "运营专员", "高级运营经理", "用户运营",
        "内容运营", "社群运营", "活动运营",
        "新媒体运营", "电商运营", "数据运营",
        "运营总监", "产品运营", "渠道运营",
    ],
    "市场推广": [
        "市场推广专员", "市场营销经理", "品牌推广专员",
        "市场策划", "数字营销专员", "SEM优化师",
        "SEO专员", "市场总监", "营销策划经理",
        "海外市场推广", "用户增长专员", "品牌公关",
    ],
    "职能管理": [
        "人力资源专员", "行政专员", "财务会计",
        "HRBP", "招聘专员", "行政主管",
        "财务经理", "人事主管", "法务专员",
        "总经理助理", "项目经理", "质量专员",
    ],
}

# 各分类的标签模板
TAG_TEMPLATES = {
    "前端开发": ["React", "Vue", "TypeScript", "Webpack", "Node.js", "小程序", "H5", "性能优化", "组件库", "微前端"],
    "后端开发": ["Java", "Spring", "MySQL", "Redis", "微服务", "分布式", "高并发", "Kafka", "Go", "Python"],
    "测试开发": ["自动化测试", "性能测试", "接口测试", "Selenium", "Jmeter", "CI/CD", "测试框架", "Appium"],
    "算法工程师": ["机器学习", "深度学习", "Python", "TensorFlow", "PyTorch", "NLP", "CV", "推荐系统", "数据挖掘"],
    "数据分析": ["SQL", "Python", "Excel", "Tableau", "数据可视化", "用户分析", "商业分析", "A/B测试"],
    "运维工程师": ["Linux", "Docker", "Kubernetes", "CI/CD", "监控", "自动化", "云平台", "Ansible"],
    "产品经理": ["需求分析", "产品设计", "用户研究", "数据分析", "项目管理", "原型设计", "B端", "C端", "增长"],
    "UI设计": ["PS", "Sketch", "Figma", "原型设计", "视觉设计", "交互设计", "动效", "品牌设计", "APP设计", "网页设计"],
    "运营": ["用户运营", "内容运营", "活动策划", "社群运营", "数据分析", "新媒体", "增长", "转化", "留存"],
    "市场推广": ["品牌推广", "数字营销", "SEM", "SEO", "内容营销", "活动策划", "用户增长", "市场调研", "公关"],
    "职能管理": ["人力资源", "行政管理", "财务", "招聘", "培训", "绩效考核", "法务", "项目管理", "办公软件"],
}

# 公司名称池（按层级分类）
COMPANIES_TIER1 = [
    "字节跳动", "阿里巴巴", "腾讯", "百度", "美团", "京东",
    "拼多多", "网易", "快手", "小米", "华为", "蚂蚁集团",
    "滴滴出行", "B站", "小红书", "知乎", "携程", "去哪儿",
    "新浪微博", "搜狐", "360", "金山软件", "欢聚集团", "陌陌",
]

COMPANIES_TIER2 = [
    "滴滴科技", "贝壳找房", "好未来", "新东方", "作业帮", "猿辅导",
    "平安科技", "招商银行", "建设银行", "工商银行", "中国银行",
    "中国平安", "中国人寿", "太平洋保险", "国泰君安", "华泰证券",
    "中信证券", "广发证券", "海通证券", "招商证券",
]

COMPANIES_TIER3 = [
    "明源云科技", "有赞科技", "微盟集团", "声网Agora", "涂鸦智能",
    "青云科技", "优刻得", "金山办公", "用友网络", "金蝶国际",
    "石基信息", "广联达", "同花顺", "东方财富", "恒生电子",
    "科大讯飞", "商汤科技", "旷视科技", "依图科技", "云从科技",
    "影石科技", "绿盟科技", "奇安信", "深信服", "启明星辰",
    "天融信", "卫士通", "美亚柏科", "任子行", "蓝盾股份",
    "超图软件", "数字政通", "易华录", "银江技术", "赛为智能",
    "华宇软件", "久其软件", "远光软件", "恒华科技", "佳都科技",
]

COMPANIES_BY_TIER = {
    "头部大厂": COMPANIES_TIER1,
    "大型企业": COMPANIES_TIER2,
    "中型企业": COMPANIES_TIER3,
}


def weighted_choice(options, weights):
    return random.choices(options, weights=weights, k=1)[0]


def generate_salary(category, exp, edu, city_tier, company_tier):
    """基于多因素生成薪资范围"""
    base = EXP_SALARY_BASE[exp]
    factor = (
        CATEGORY_SALARY_FACTOR[category]
        * EDU_SALARY_FACTOR[edu]
        * CITY_SALARY_FACTOR[city_tier]
        * TIER_SALARY_FACTOR[company_tier]
    )
    mid = base * factor
    # 添加随机波动 ±15%
    mid *= random.uniform(0.85, 1.15)
    mid = max(3, mid)
    # 生成薪资范围，跨度约为中位的 30%
    span = mid * 0.3
    low = max(2, int(round(mid - span / 2)))
    high = max(low + 1, int(round(mid + span / 2)))
    # 对齐到整数K
    return low, high


def generate_job_id(idx, prefix="job"):
    return f"{prefix}_{idx:05d}"


def generate_tags(category, count=3):
    tags = random.sample(TAG_TEMPLATES[category], min(count, len(TAG_TEMPLATES[category])))
    return ";".join(tags)


def generate_desc(title, company, category, city, edu, exp, salary_low, salary_high):
    """生成真实感的职位描述"""
    templates = [
        f"""【岗位名称】{title}
【工作地点】{city}
【学历要求】{edu}
【经验要求】{exp}

岗位职责：
1. 负责{company}相关{category}业务的开发与维护；
2. 参与产品需求分析与技术方案设计，保证系统的高可用性和高性能；
3. 与产品、设计、测试团队紧密协作，按时交付高质量产品；
4. 持续优化技术架构，提升团队研发效率。

任职要求：
1. {edu}及以上学历，{exp}相关工作经验；
2. 熟悉{category}领域常用技术栈和开发工具；
3. 良好的沟通能力和团队合作精神，有较强的学习能力；
4. 有大型互联网公司或相关项目经验者优先。""",
        f"""【岗位名称】{title}
【工作地点】{city}
【薪资范围】{salary_low}-{salary_high}K
【学历要求】{edu}

职位描述：
我们正在寻找一位优秀的{title}加入{company}团队。你将参与核心业务的{category}工作，与行业顶尖人才共同打造优质产品。

岗位职责：
• 负责核心业务模块的{category}设计与实现
• 推动技术方案落地，保障产品质量和用户体验
• 参与技术评审，提出改进建议
• 指导初级工程师，分享技术经验

任职资格：
• {edu}及以上学历，{exp}工作经验
• 扎实的{category}基础知识
• 良好的问题分析和解决能力
• 具备良好的沟通协作能力和团队精神""",
        f"""职位：{title}
公司：{company}
地点：{city}
薪资：{salary_low}-{salary_high}K · 14薪

我们是谁：
{company}是行业领先的科技公司，致力于用技术创造价值。我们拥有充满活力的团队和开放的文化，欢迎优秀的你加入！

你将做什么：
1. 负责{category}方向的核心业务开发
2. 参与产品从0到1的建设过程
3. 优化现有系统的性能和稳定性
4. 跟踪行业技术趋势，引入新技术

我们希望你：
• {edu}以上学历，{exp}相关经验
• 对{category}有浓厚兴趣和深入理解
• 有强烈的责任心和自驱力
• 具备良好的抗压能力和应变能力

我们提供：
• 有竞争力的薪资和股权激励
• 完善的培训体系和晋升通道
• 五险一金、补充医疗、带薪年假
• 免费三餐、下午茶、健身房""",
    ]
    return random.choice(templates)


def generate_publish_time(days_back=60):
    """生成发布时间（近60天内）"""
    now = datetime.now()
    delta_days = random.randint(0, days_back)
    delta_hours = random.randint(9, 20)  # 工作时间发布
    pub_time = now - timedelta(days=delta_days, hours=delta_hours)
    return pub_time.strftime("%Y-%m-%d %H:%M")


def generate_batch(num_records, start_idx=5001):
    """批量生成招聘数据"""
    records = []

    # 预计算城市权重
    city_options = [c[0] for c in CITIES]
    city_tier_map = {c[0]: c[1] for c in CITIES}
    city_weights = []
    for c in CITIES:
        city_weights.append(CITY_WEIGHTS[c[1]])
    # 归一化
    total_w = sum(city_weights)
    city_weights = [w / total_w for w in city_weights]

    cat_names = [c[0] for c in CATEGORIES]

    for i in range(num_records):
        idx = start_idx + i

        # 随机选择各项属性
        category = weighted_choice(cat_names, CATEGORY_WEIGHTS)
        city = weighted_choice(city_options, city_weights)
        city_tier = city_tier_map[city]
        edu = weighted_choice(EDUCATIONS, EDU_WEIGHTS)
        exp = weighted_choice(EXPERIENCES, EXP_WEIGHTS)
        company_tier = weighted_choice(COMPANY_TIERS, TIER_WEIGHTS)

        # 生成薪资
        salary_low, salary_high = generate_salary(category, exp, edu, city_tier, company_tier)

        # 选择公司
        company = random.choice(COMPANIES_BY_TIER[company_tier])

        # 选择职位标题
        title = random.choice(JOB_TITLES[category])

        # 生成标签
        tags = generate_tags(category, random.randint(2, 5))

        # 生成描述
        desc = generate_desc(title, company, category, city, edu, exp, salary_low, salary_high)

        # 生成发布时间
        publish_time = generate_publish_time()

        records.append({
            "job_id": generate_job_id(idx),
            "title": title,
            "company": company,
            "city": city,
            "salary_low": salary_low,
            "salary_high": salary_high,
            "edu": edu,
            "exp": exp,
            "tags": tags,
            "category": category,
            "company_tier": company_tier,
            "desc": desc,
            "publish_time": publish_time,
        })

    return pd.DataFrame(records)


if __name__ == "__main__":
    print("正在加载现有数据...")
    existing_df = pd.read_csv(r"D:\桌面\recruit-github\data\clean\recruit_clean.tsv", sep="\t")
    print(f"现有数据: {len(existing_df)} 条")

    print("正在生成 5000 条仿真数据...")
    new_df = generate_batch(5000, start_idx=len(existing_df) + 1)
    print(f"生成数据: {len(new_df)} 条")

    # 合并
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    print(f"合并后总量: {len(combined_df)} 条")

    # 保存
    output_path = r"D:\桌面\recruit-github\data\clean\recruit_clean.tsv"
    combined_df.to_csv(output_path, sep="\t", index=False, encoding="utf-8")
    print(f"已保存到: {output_path}")

    # 数据概览
    print("\n=== 数据概览 ===")
    print(f"总记录数: {len(combined_df)}")
    print(f"城市数量: {combined_df['city'].nunique()}")
    print(f"公司数量: {combined_df['company'].nunique()}")
    print(f"岗位类别: {combined_df['category'].nunique()}")
    print()
    print("薪资分布:")
    combined_df["salary_mid"] = (combined_df["salary_low"] + combined_df["salary_high"]) / 2
    bins = [0, 5, 10, 15, 20, 30, 50, 100]
    labels = ["0-5K", "5-10K", "10-15K", "15-20K", "20-30K", "30-50K", "50K+"]
    print(pd.cut(combined_df["salary_mid"], bins=bins, labels=labels).value_counts().sort_index())
    print()
    print("类别分布:")
    print(combined_df["category"].value_counts())
