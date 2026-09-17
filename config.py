# -*- coding: utf-8 -*-
"""
项目配置：路径、算法参数、数据源开关。
所有可调参数集中在此，便于实验与答辩演示。
"""
import os

# ============ 路径配置 ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_RAW = os.path.join(BASE_DIR, "data", "raw")
DATA_CLEAN = os.path.join(BASE_DIR, "data", "clean")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
CHART_DIR = os.path.join(OUTPUT_DIR, "charts")
REPORT_DIR = os.path.join(OUTPUT_DIR, "reports")

for _d in (DATA_PROCESSED, CHART_DIR, REPORT_DIR):
    os.makedirs(_d, exist_ok=True)

# ============ 数据源选择 ============
# "basket"  -> 购物篮商品组合
# "skills"  -> 招聘技能组合（贴合已有招聘系统）
DATA_SOURCE = "skills"

BASKET_FILE = os.path.join(DATA_RAW, "market_basket.csv")
SKILLS_FILE = os.path.join(DATA_CLEAN, "recruit_clean.tsv")
SKILL_COL = "tags"  # 真实数据中的技能列名

# ============ 算法参数 ============
MIN_SUPPORT = 0.05
METRIC = "lift"
MIN_LIFT = 1.0
MIN_CONFIDENCE = 0.3
MAX_LEN = None
ALGORITHM = "apriori"

# ============ HBase 大数据链路（真实接入）============
# 虚拟机 192.168.92.128，HBase 2.5.9，Thrift 服务端口 9090
# 依赖 happybase（pip install happybase）
HBASE_ENABLED = os.environ.get("HBASE_ENABLED", "false").lower() in ("true", "1", "yes")
HBASE_HOST = os.environ.get("HBASE_HOST", "192.168.92.128")
HBASE_PORT = int(os.environ.get("HBASE_PORT", "9090"))
HBASE_TABLE_IN = "recruit_keyword"       # 频次表（关键词→出现次数，仅供词云）
HBASE_TABLE_OUT = "recruit_assoc_rules"  # 规则输出表（强规则写回此处供大屏读取）
HBASE_COL_FAMILY = "info"                # 列族与已有表保持一致

# ============ 可视化 ============
MATPLOT_FONT = "SimHei"
TOP_N_RULES = 15
