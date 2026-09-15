# -*- coding: utf-8 -*-
"""
模型层：频繁项集挖掘
====================
- Apriori  : 经典逐层迭代，适合中等规模
- FP-Growth: 基于 FP 树，适合大规模、性能更优
返回的频繁项集包含 support 与项集 frozenset，供 evaluator 生成关联规则。
"""
import pandas as pd
from mlxtend.frequent_patterns import apriori, fpgrowth
from typing import Optional


def find_frequent_itemsets(encoded_df: pd.DataFrame,
                            min_support: float = 0.05,
                            algorithm: str = "apriori",
                            max_len: Optional[int] = None) -> pd.DataFrame:
    """挖掘频繁项集。

    Args:
        encoded_df: 0/1 项集矩阵
        min_support: 最小支持度阈值
        algorithm: "apriori" 或 "fpgrowth"
        max_len: 项集最大长度，None 不限制

    Returns:
        DataFrame: [support, itemsets]，itemsets 为 frozenset
    """
    if algorithm == "apriori":
        freq = apriori(encoded_df, min_support=min_support,
                       use_colnames=True, max_len=max_len)
    elif algorithm == "fpgrowth":
        freq = fpgrowth(encoded_df, min_support=min_support,
                        use_colnames=True, max_len=max_len)
    else:
        raise ValueError(f"未知算法: {algorithm}（可选: apriori / fpgrowth）")
    # 按支持度降序
    freq = freq.sort_values("support", ascending=False).reset_index(drop=True)
    return freq


def filter_by_length(freq_df: pd.DataFrame, min_len: int = 2) -> pd.DataFrame:
    """只保留长度 >= min_len 的项集（单一项集无法生成规则）。"""
    mask = freq_df["itemsets"].apply(lambda s: len(s) >= min_len)
    return freq_df[mask].reset_index(drop=True)
