# -*- coding: utf-8 -*-
"""
特征工程：事务编码
==================
用 mlxtend 的 TransactionEncoder 把「每行一个组合列表」
转成「0/1 项集矩阵」（每列一个项，每行一个篮子）。
这是 Apriori / FP-Growth 的标准输入格式。

示例:
    输入: [["java","spring"], ["java","kafka"]]
    输出:
           java  kafka  spring
        0     1      0      1
        1     1      1      0
"""
import pandas as pd
from mlxtend.preprocessing import TransactionEncoder
from typing import List


def encode_transactions(transactions: List[List[str]]) -> pd.DataFrame:
    """将事务列表编码为 0/1 矩阵。"""
    te = TransactionEncoder()
    te_array = te.fit(transactions).transform(transactions)
    df = pd.DataFrame(te_array, columns=te.columns_)
    return df


def item_frequency(encoded_df: pd.DataFrame) -> pd.DataFrame:
    """统计每个项的支持频次与支持度，辅助调参。"""
    freq = encoded_df.sum().sort_values(ascending=False)
    support = freq / len(encoded_df)
    return pd.DataFrame({
        "item": freq.index,
        "count": freq.values,
        "support": support.values,
    }).reset_index(drop=True)
