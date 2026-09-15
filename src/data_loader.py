# -*- coding: utf-8 -*-
"""
数据加载层
=========
支持两种数据源：
1. 购物篮（market basket）：CSV，每行一个订单，items 用分隔符拼接
2. 招聘技能（recruit skills）：TSV，每行一个岗位，skills 用分隔符拼接
   可直接替换为真实 recruit_clean.tsv（取第 8 列关键词）
"""
import pandas as pd
from typing import List, Tuple
from collections import Counter


def load_basket(path: str, sep: str = ";") -> Tuple[List[List[str]], pd.DataFrame]:
    """加载购物篮数据。

    Args:
        path: CSV 文件路径，需含 order_id, items 两列
        sep: 商品分隔符

    Returns:
        transactions: 每个订单的商品列表 [[商品1, 商品2], ...]
        df: 原始 DataFrame
    """
    df = pd.read_csv(path)
    if "items" not in df.columns:
        raise ValueError(f"CSV 缺少 items 列，当前列: {list(df.columns)}")
    transactions = [
        [g.strip() for g in str(items).split(sep) if g.strip()]
        for items in df["items"]
    ]
    transactions = [t for t in transactions if t]  # 丢弃空行
    return transactions, df


def load_skills(path: str, sep: str = ";",
                skill_col="skills") -> Tuple[List[List[str]], pd.DataFrame]:
    """加载招聘技能数据。

    Args:
        path: TSV 文件路径
        sep: 技能分隔符
        skill_col: 技能列名或列索引（兼容 recruit_clean.tsv 第 8 列）

    Returns:
        transactions: 每个岗位的技能列表
        df: 原始 DataFrame
    """
    df = pd.read_csv(path, sep="\t")
    # 支持「列名」或「列索引」
    if isinstance(skill_col, int) or (isinstance(skill_col, str) and skill_col.isdigit()):
        col = df.columns[int(skill_col)]
    else:
        col = skill_col
    if col not in df.columns:
        raise ValueError(f"找不到技能列 {col}，当前列: {list(df.columns)}")
    transactions = [
        [s.strip() for s in str(skills).split(sep) if s.strip()]
        for skills in df[col]
    ]
    transactions = [t for t in transactions if t]
    return transactions, df


def load_transactions(source: str, basket_path: str = None,
                      skills_path: str = None, **kwargs) -> Tuple[List[List[str]], pd.DataFrame]:
    """统一加载入口，按 source 分流。"""
    if source == "basket":
        return load_basket(basket_path, **kwargs)
    elif source == "skills":
        return load_skills(skills_path, **kwargs)
    else:
        raise ValueError(f"未知数据源: {source}（可选: basket / skills）")


def summarize(transactions: List[List[str]]) -> str:
    """输出数据集统计摘要，用于答辩说明。"""
    n = len(transactions)
    all_items = [item for t in transactions for item in t]
    n_items = len(all_items)
    unique = len(set(all_items))
    avg_len = n_items / n if n else 0
    top5 = Counter(all_items).most_common(5)
    top5_str = "，".join(f"{k}({v}次)" for k, v in top5)
    return (
        f"篮子/岗位总数: {n}\n"
        f"出现过的不同项: {unique}\n"
        f"平均每篮项数: {avg_len:.2f}\n"
        f"出现最多的 5 项: {top5_str}"
    )
