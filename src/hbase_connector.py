# -*- coding: utf-8 -*-
"""
HBase 大数据链路（真实接入）
================================
功能：
1. 从 recruit_keyword 频次表读取 Top 关键词，用于大屏词云展示（非事务源）
2. 把挖掘出的强规则写回新表 recruit_assoc_rules，供前端 ECharts 大屏 fetch 接口展示

真实环境：一台装好 HBase 2.5.9 的虚拟机，Thrift 服务端口默认 9090；
          地址与端口在 config/local.env 里配置（模板见 config/local.env.example）。
依赖 happybase。
未连接时自动降级为本地 CSV，不影响主流程。

注：recruit_keyword 表是「关键词→出现次数」的频次表，不是事务表，
   无法直接做关联规则挖掘。事务数据走本地 recruit_skills.tsv（贴合文档第五节）。
   规则结果写回 HBase recruit_assoc_rules 表，供 Spring Boot 接口读取。
"""
import pandas as pd
from typing import List, Optional, Dict

from config import (HBASE_ENABLED, HBASE_HOST, HBASE_PORT,
                    HBASE_TABLE_IN, HBASE_TABLE_OUT, HBASE_COL_FAMILY)


def _get_connection():
    """惰性连接 happybase，失败返回 None。"""
    if not HBASE_ENABLED:
        return None
    try:
        import happybase
        conn = happybase.Connection(HBASE_HOST, HBASE_PORT)
        return conn
    except Exception as e:
        print(f"[HBase] 连接失败，降级为本地模式: {e}")
        return None


def load_from_hbase() -> Optional[List[List[str]]]:
    """recruit_keyword 是频次表不是事务表，无法用于关联规则挖掘。
    返回 None 让主流程走本地 recruit_skills.tsv 事务数据。"""
    return None


def load_keyword_freq_from_hbase(top_n: int = 20) -> Optional[Dict[str, int]]:
    """从 recruit_keyword 频次表读 Top N 关键词，供大屏词云 panel 使用。
    返回 {关键词: 次数} 字典；连接失败返回 None。"""
    conn = _get_connection()
    if conn is None:
        return None
    try:
        table = conn.table(HBASE_TABLE_IN)
        col = (HBASE_COL_FAMILY + ":count").encode()
        result = {}
        for key, data in table.scan():
            v = data.get(col)
            if v:
                try:
                    result[key.decode()] = int(v.decode())
                except ValueError:
                    continue
        conn.close()
        # 按次数降序取 Top N
        sorted_items = sorted(result.items(), key=lambda x: x[1], reverse=True)[:top_n]
        print(f"[HBase] 从 {HBASE_TABLE_IN} 读 {len(result)} 个关键词，取 Top {top_n}")
        return dict(sorted_items)
    except Exception as e:
        print(f"[HBase] 读取频次失败: {e}")
        try: conn.close()
        except: pass
        return None


def write_rules_to_hbase(rules: pd.DataFrame) -> bool:
    """把强规则写回 HBase 新表 recruit_assoc_rules，供前端展示。
    列族用 info（与 recruit_keyword 等已有表保持一致），便于 Spring Boot 统一 scan。"""
    conn = _get_connection()
    if conn is None:
        return False
    try:
        tables = [t.decode() if isinstance(t, bytes) else t for t in conn.tables()]
        if HBASE_TABLE_OUT not in tables:
            # 创建新表，列族 info
            conn.create_table(HBASE_TABLE_OUT, {"info": dict()})
            print(f"[HBase] 新建表 {HBASE_TABLE_OUT}（列族 info）")
        table = conn.table(HBASE_TABLE_OUT)
        cf = "info"
        # 先清空旧数据
        for key, _ in table.scan():
            table.delete(key)
        with table.batch() as b:
            for i, (_, r) in enumerate(rules.iterrows()):
                a = ",".join(sorted(r["antecedents"])) if not isinstance(r["antecedents"], str) else r["antecedents"]
                c = ",".join(sorted(r["consequents"])) if not isinstance(r["consequents"], str) else r["consequents"]
                row_key = f"rule_{i:04d}"
                b.put(row_key, {
                    f"{cf}:antecedents": a,
                    f"{cf}:consequents": c,
                    f"{cf}:support": str(round(float(r["support"]), 4)),
                    f"{cf}:confidence": str(round(float(r["confidence"]), 4)),
                    f"{cf}:lift": str(round(float(r["lift"]), 4)),
                })
        conn.close()
        print(f"[HBase] 写入 {len(rules)} 条规则到 {HBASE_TABLE_OUT}")
        return True
    except Exception as e:
        print(f"[HBase] 写入失败: {e}")
        try: conn.close()
        except: pass
        return False
