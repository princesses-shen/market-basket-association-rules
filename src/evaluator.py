# -*- coding: utf-8 -*-
"""
评估层：关联规则生成与筛选
==========================
从频繁项集生成关联规则，并按 support / confidence / lift 筛选强规则。
核心指标：
- support(支持度)     : 规则出现的概率 P(A∪B)
- confidence(置信度)  : A 出现时 B 也出现的概率 P(B|A)
- lift(提升度)        : P(B|A)/P(B)；>1 正相关，=1 独立，<1 负相关
"""
import pandas as pd
from mlxtend.frequent_patterns import association_rules


def generate_rules(freq_df: pd.DataFrame,
                   metric: str = "lift",
                   min_threshold: float = 1.0) -> pd.DataFrame:
    """从频繁项集生成关联规则。

    Args:
        freq_df: find_frequent_itemsets 的输出
        metric: 筛选指标 (support/confidence/lift/leverage/conviction)
        min_threshold: 该指标的最小阈值

    Returns:
        rules DataFrame，含 antecedents/consequents/support/confidence/lift 等
    """
    if freq_df.empty or (freq_df["itemsets"].apply(len) < 2).all():
        return pd.DataFrame()
    rules = association_rules(freq_df, metric=metric, min_threshold=min_threshold)
    return rules


def filter_strong_rules(rules: pd.DataFrame,
                        min_confidence: float = 0.3,
                        min_lift: float = 1.0) -> pd.DataFrame:
    """筛选强规则：置信度与提升度同时达标。"""
    if rules.empty:
        return rules
    strong = rules[(rules["confidence"] >= min_confidence) &
                  (rules["lift"] >= min_lift)].copy()
    return strong.sort_values(["lift", "confidence"],
                              ascending=False).reset_index(drop=True)


def format_rules(rules: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """把 frozenset 转成可读字符串，便于展示与写回 HBase。"""
    if rules.empty:
        return rules
    out = rules.copy()
    out["antecedents"] = out["antecedents"].apply(lambda s: ",".join(sorted(s)))
    out["consequents"] = out["consequents"].apply(lambda s: ",".join(sorted(s)))
    cols = ["antecedents", "consequents", "support",
            "confidence", "lift", "leverage", "conviction"]
    cols = [c for c in cols if c in out.columns]
    return out[cols].head(top_n)


def summarize_rules(rules: pd.DataFrame) -> str:
    """规则集统计摘要，用于答辩亮点陈述。"""
    if rules.empty:
        return "未挖掘到满足阈值的关联规则，请降低 min_support / min_lift 后重试。"
    n = len(rules)
    avg_conf = rules["confidence"].mean()
    avg_lift = rules["lift"].mean()
    top = rules.iloc[0]
    a = ",".join(sorted(top["antecedents"])) if not isinstance(top["antecedents"], str) else top["antecedents"]
    c = ",".join(sorted(top["consequents"])) if not isinstance(top["consequents"], str) else top["consequents"]
    return (
        f"强规则总数: {n}\n"
        f"平均置信度: {avg_conf:.4f}\n"
        f"平均提升度: {avg_lift:.4f}\n"
        f"最强规则: [{a}] => [{c}]  "
        f"support={top['support']:.3f} confidence={top['confidence']:.3f} lift={top['lift']:.3f}"
    )
