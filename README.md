# 项目九 · 购物篮/技能组合分析（关联规则）

## 项目简介

基于 Apriori 和 FP-Growth 算法的购物篮/技能组合关联规则挖掘系统，包含 Spring Boot 后端、ECharts 可视化大屏、HBase 大数据存储，以及完整的招聘网站前端。

## 技术栈

| 组件 | 技术 |
|------|------|
| 关联规则算法 | Apriori, FP-Growth (Python) |
| Web 后端 | Flask (Python) |
| 大数据存储 | Hadoop + HBase |
| 前端可视化 | ECharts, HTML/CSS/JS |
| 薪资预测 | XGBoost 分位数回归 |

## 功能模块

### 数据分析
- Apriori/FP-Growth 频繁项集挖掘
- 关联规则筛选（support/confidence/lift）
- 技能组合关联分析
- 6 张可视化图表

### 招聘网站
- 岗位搜索（城市/薪资/关键词/类别筛选）
- 岗位详情页
- 简历投递（支持 Word/PDF 上传）
- 企业端简历管理
- 求职咨询论坛
- 数据可视化大屏
- 薪资预测（XGBoost）

### 管理功能
- 用户端 / 企业端 / 管理员端三角色登录系统
- 忘记密码功能
- 职位收藏与浏览历史
- 投递流程跟踪
- 招聘信息爬虫（BOSS直聘/拉勾网反爬框架）

## 数据来源

天池岗位数据集（5000条真实招聘数据）
- 来源：https://tianchi.aliyun.com/dataset/221302
- 协议：GPL 2.0

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 生成数据
python scripts/gen_realistic_data.py

# 运行关联规则分析
python main.py

# 启动网站
python serve_website.py
# 访问 http://localhost:8080/
```

## 项目结构

```
├── main.py                 # 主程序入口
├── config.py               # 配置文件
├── serve_website.py        # 招聘网站服务
├── src/
│   ├── analysis/           # 关联规则分析模块
│   ├── ingest/             # 数据采集与爬虫
│   ├── serving/            # 预测服务
│   ├── compute/            # MapReduce 计算
│   └── agg/               # HBase 聚合
├── config/                 # 部署配置
├── data/                   # 数据目录
├── deploy/                 # 部署脚本
├── scripts/                # 工具脚本
├── tests/                  # 测试
├── Makefile                # 构建工具
└── artifacts/              # 模型与产出
```

## 测试账号

| 角色 | 账号 | 密码 |
|------|------|------|
| 管理员 | admin | 123456 |
| 用户 | xiaoliyu | 123456 |
| 企业 | zhangsan | 123456 |

## 部署

### 本地运行
```bash
python main.py
python serve_website.py
```

### 虚拟机部署
```bash
# 配置 Hadoop + HBase
# 设置环境变量 HBASE_ENABLED=true
# 运行部署脚本
python scripts/deploy.py
```
