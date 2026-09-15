# -*- coding: utf-8 -*-
"""
项目九 · 购物篮 / 技能组合分析（关联规则）
=========================================
建模路线：
  ① 数据加载 -> ② 事务编码(TransactionEncoder) -> ③ Apriori/FP-Growth 找频繁项集
  ④ association_rules 生成规则 -> ⑤ lift/confidence 筛选强规则
  ⑥ 可视化 + 写回 HBase（地址见 config/local.env，没配则跳过、降级为本地 CSV）

运行：
    python main.py
默认数据源见 config.DATA_SOURCE（skills / basket），可改 config 切换。
"""
import os
import pandas as pd

import config
from src.data_loader import load_transactions, summarize
from src.preprocessor import encode_transactions, item_frequency
from src.model import find_frequent_itemsets, filter_by_length
from src.evaluator import generate_rules, filter_strong_rules, format_rules, summarize_rules
from src.visualizer import (plot_top_itemsets, plot_rules_scatter,
                            plot_rules_bar, plot_cooccurrence_heatmap,
                            export_day08_dashboard,
                            export_echarts_network, export_echarts_heatmap)
from src.hbase_connector import load_from_hbase, load_keyword_freq_from_hbase, write_rules_to_hbase


def main():
    print("=" * 60)
    print("项目九 · 购物篮 / 技能组合分析（关联规则）")
    print("=" * 60)

    # -------- ① 数据加载 --------
    print("\n[1/6] 数据加载")
    transactions = load_from_hbase() if config.HBASE_ENABLED else None
    if transactions is None:
        source = config.DATA_SOURCE
        transactions, raw_df = load_transactions(
            source,
            basket_path=config.BASKET_FILE,
            skills_path=config.SKILLS_FILE,
        )
        print(f"数据源: {source}（本地 recruit_skills.tsv 事务数据）")
    else:
        print(f"数据源: HBase（{config.HBASE_TABLE_IN}）")
    print(summarize(transactions))

    # -------- ② 事务编码 --------
    print("\n[2/6] 事务编码（TransactionEncoder -> 0/1 矩阵）")
    encoded_df = encode_transactions(transactions)
    print(f"矩阵形状: {encoded_df.shape}（篮子数 x 项数）")
    item_freq = item_frequency(encoded_df)
    item_freq.to_csv(os.path.join(config.DATA_PROCESSED, "item_frequency.csv"),
                     index=False, encoding="utf-8-sig")
    print("高频 Top5:")
    print(item_freq.head().to_string(index=False))

    # -------- ③ 频繁项集挖掘 --------
    print(f"\n[3/6] 频繁项集挖掘（{config.ALGORITHM}, min_support={config.MIN_SUPPORT}）")
    freq_df = find_frequent_itemsets(
        encoded_df,
        min_support=config.MIN_SUPPORT,
        algorithm=config.ALGORITHM,
        max_len=config.MAX_LEN,
    )
    freq_df_multi = filter_by_length(freq_df, min_len=2)
    print(f"频繁项集总数: {len(freq_df)}，其中长度>=2: {len(freq_df_multi)}")
    freq_df.to_csv(os.path.join(config.DATA_PROCESSED, "frequent_itemsets.csv"),
                   index=False, encoding="utf-8-sig")
    print("Top 频繁项集:")
    print(freq_df.head(10).to_string(index=False))

    # -------- ④ 关联规则生成 --------
    print(f"\n[4/6] 关联规则生成（metric={config.METRIC}, min_threshold={config.MIN_LIFT}）")
    rules = generate_rules(freq_df, metric=config.METRIC,
                           min_threshold=config.MIN_LIFT)
    if rules.empty:
        print("未生成任何规则，请降低 min_support 或 min_lift。")
        return
    print(f"规则总数: {len(rules)}")

    # -------- ⑤ 强规则筛选 --------
    print(f"\n[5/6] 强规则筛选（min_confidence={config.MIN_CONFIDENCE}, min_lift={config.MIN_LIFT}）")
    strong_rules = filter_strong_rules(rules,
                                      min_confidence=config.MIN_CONFIDENCE,
                                      min_lift=config.MIN_LIFT)
    print(summarize_rules(strong_rules))
    strong_rules.to_csv(
        os.path.join(config.DATA_PROCESSED, "association_rules.csv"),
        index=False, encoding="utf-8-sig")

    readable = format_rules(strong_rules, top_n=config.TOP_N_RULES)
    readable.to_csv(
        os.path.join(config.REPORT_DIR, "strong_rules_readable.csv"),
        index=False, encoding="utf-8-sig")
    print(f"\nTop {config.TOP_N_RULES} 强规则:")
    print(readable.to_string(index=False))

    # -------- ⑥ 可视化 + HBase 写回 --------
    print("\n[6/6] 可视化与结果落地")
    # matplotlib 静态图（答辩截图/备份）
    p1 = plot_top_itemsets(freq_df_multi)
    p2 = plot_rules_scatter(strong_rules)
    p3 = plot_rules_bar(strong_rules)
    p4 = plot_cooccurrence_heatmap(encoded_df)
    # ECharts day8 风格大屏（4-panel + 本地 echarts 库）
    p5 = export_day08_dashboard()
    # 备用独立图（旧版，保留）
    p6 = export_echarts_network(strong_rules)
    p7 = export_echarts_heatmap(strong_rules)
    for p in (p1, p2, p3, p4, p5, p6, p7):
        print(f"  生成: {p}")

    # 真实写回 HBase（recruit_assoc_rules 表）
    if config.HBASE_ENABLED:
        write_rules_to_hbase(strong_rules)
        # 顺便验证一下能读回来
        from src.hbase_connector import load_keyword_freq_from_hbase
        kw_freq = load_keyword_freq_from_hbase(top_n=5)
        if kw_freq:
            print(f"[HBase] 关键词频次 Top5: {kw_freq}")

    print("\n" + "=" * 60)
    print("全部完成！")
    print(f"  频繁项集: {os.path.join(config.DATA_PROCESSED, 'frequent_itemsets.csv')}")
    print(f"  关联规则: {os.path.join(config.DATA_PROCESSED, 'association_rules.csv')}")
    print(f"  可读规则: {os.path.join(config.REPORT_DIR, 'strong_rules_readable.csv')}")
    print(f"  图表目录: {config.CHART_DIR}")
    print(f"  day8 大屏: {os.path.join(config.CHART_DIR, 'index.html')}")
    print(f"  部署到虚拟机 Spring Boot static 后访问 http://{config.VM_HOST}:{config.VM_BACKEND_PORT}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
