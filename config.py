# -*- coding: utf-8 -*-
"""
项目配置：路径、算法参数、数据源开关。
所有可调参数集中在此，便于实验与答辩演示。
"""
import os

# ============ 路径配置 ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_RAW = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
CHART_DIR = os.path.join(OUTPUT_DIR, "charts")
REPORT_DIR = os.path.join(OUTPUT_DIR, "reports")

for _d in (DATA_PROCESSED, CHART_DIR, REPORT_DIR):
    os.makedirs(_d, exist_ok=True)

# ============ 本机私有配置（不入库）============
# 真实的服务器地址与密码放在 config/local.env（已在 .gitignore 中），
# 模板见 config/local.env.example —— 复制成 local.env 后填自己的值即可。
# 优先级：同名环境变量 > config/local.env > 下面的占位默认值。
# 这里用纯标准库解析，不额外引入 PyYAML 之类的依赖。
LOCAL_ENV_FILE = os.path.join(BASE_DIR, "config", "local.env")


def _load_local_env(path=LOCAL_ENV_FILE):
    """把 config/local.env 里的 KEY=VALUE 注入环境变量（已存在的同名变量不覆盖）。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


_load_local_env()

# 占位默认值设计原则：仓库里不出现任何真实内网地址与密码。
# 没配 local.env 时会落到这些值上，表现是"连不上"，而不是把秘密写进代码里。
VM_HOST = os.environ.get("VM_HOST", "127.0.0.1")           # 虚拟机 / 服务器地址
VM_SSH_USER = os.environ.get("VM_SSH_USER", "your-user")   # SSH 用户名
VM_SSH_PASSWORD = os.environ.get("VM_SSH_PASSWORD", "")    # SSH 密码（走密钥登录时留空）
VM_BACKEND_PORT = int(os.environ.get("VM_BACKEND_PORT", "8080"))
VM_PREDICT_PORT = int(os.environ.get("VM_PREDICT_PORT", "8788"))

# ============ 数据源选择 ============
# "basket"  -> 购物篮商品组合
# "skills"  -> 招聘技能组合（贴合已有招聘系统）
DATA_SOURCE = "skills"

BASKET_FILE = os.path.join(DATA_RAW, "market_basket.csv")
SKILLS_FILE = os.path.join(DATA_RAW, "recruit_skills.tsv")

# ============ 算法参数 ============
MIN_SUPPORT = 0.05
METRIC = "lift"
MIN_LIFT = 1.0
MIN_CONFIDENCE = 0.3
MAX_LEN = None
ALGORITHM = "apriori"

# ============ HBase 大数据链路（真实接入）============
# 地址取自 VM_HOST / config/local.env，默认端口为 Thrift 服务端口 9090
# 依赖 happybase（pip install happybase）
HBASE_ENABLED = True
HBASE_HOST = os.environ.get("HBASE_HOST", VM_HOST)
HBASE_PORT = int(os.environ.get("HBASE_PORT", "9090"))
HBASE_TABLE_IN = "recruit_keyword"       # 频次表（关键词→出现次数，仅供词云）
HBASE_TABLE_OUT = "recruit_assoc_rules"  # 规则输出表（强规则写回此处供大屏读取）
HBASE_COL_FAMILY = "info"                # 列族与已有表保持一致

# ============ 可视化 ============
MATPLOT_FONT = "SimHei"
TOP_N_RULES = 15
