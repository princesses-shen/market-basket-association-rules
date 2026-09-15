# -*- coding: utf-8 -*-
"""
特征工程单一来源 (训练与预测服务共用)
特征: 城市 / 学历 / 经验年限 / 技术栈数量 / 公司档次 -> 数值向量
"""
import numpy as np

# 枚举有序映射
EDU_MAP = {"不限": 0, "大专": 1, "本科": 2, "硕士": 3, "博士": 4}
EXP_MAP = {"不限": 0, "应届": 0, "1年": 1, "1-3年": 2, "3-5年": 3, "5-10年": 4, "10年以上": 5}
TIER_MAP = {"中小-初创": 0, "成长型企业": 1, "中大型企业": 2, "头部大厂": 3}

# 城市列表(与训练数据一致, one-hot)
CITIES = ["北京","上海","广州","深圳","杭州","成都","南京","武汉","西安","长沙","苏州","重庆","天津","青岛","厦门"]


def extract_years(exp_str):
    """从经验字符串提取数值年限"""
    if not exp_str or exp_str == "不限" or exp_str == "应届":
        return 0.0
    # "1年" -> 1, "1-3年" -> 2(取中值), "3-5年" -> 4, "5-10年" -> 7.5, "10年以上" -> 10
    if "10年以上" in exp_str:
        return 10.0
    if "-" in exp_str:
        parts = exp_str.replace("年", "").split("-")
        try:
            return (float(parts[0]) + float(parts[1])) / 2
        except:
            return 0.0
    for ch in exp_str:
        if ch.isdigit():
            return float(ch)
    return 0.0


def count_tags(tags_str):
    """技能标签数量"""
    if not tags_str:
        return 0
    return len([t for t in tags_str.split(";") if t.strip()])


def featurize(city, edu, exp, tags, company_tier):
    """
    特征工程: 输入原始字段 -> 数值特征向量 (长度 20)
    特征: 15 城市 one-hot + 学历(1) + 年限(1) + 技术栈数(1) + 公司档次(1) + 交互项(1)
    """
    # 城市 one-hot
    city_vec = [1.0 if c == city else 0.0 for c in CITIES]
    # 学历有序
    edu_val = float(EDU_MAP.get(edu, 0))
    # 年限数值
    years = extract_years(exp)
    # 技术栈数
    n_tags = float(count_tags(tags))
    # 公司档次
    tier_val = float(TIER_MAP.get(company_tier, 0))
    # 交互: 学历*年限
    interaction = edu_val * years

    return city_vec + [edu_val, years, n_tags, tier_val, interaction]


def featurize_batch(rows):
    """批量特征化: rows = [(city,edu,exp,tags,tier), ...] -> np.array (n, 20)"""
    X = np.array([featurize(*r) for r in rows], dtype=np.float32)
    return X


FEATURE_NAMES = CITIES + ["edu", "years", "n_tags", "tier", "edu_x_years"]
FEATURE_DIM = len(FEATURE_NAMES)  # 20

if __name__ == "__main__":
    # 自测
    v = featurize("北京", "本科", "3-5年", "Java;Spring;MySQL", "头部大厂")
    print(f"特征维度: {len(v)}")
    print(f"前5维: {v[:5]}")
    print(f"后5维: {v[-5:]}")
