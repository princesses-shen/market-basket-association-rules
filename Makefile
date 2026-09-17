# 招聘信息统计分析系统 Makefile
# 用法: make <target>

PY ?= python

.PHONY: test crawl merge model agg gen-data serve backup clean

# 数据契约校验 (10列 v1.1.0, 要求 PASS)
test:
	$(PY) tests/test_schema.py

# 51job 真实数据采集 (拉满到风控边界, 增量归档可续采)
crawl:
	$(PY) src/ingest/collect_v5.py

# 合并归档 -> data/clean/recruit_clean.tsv
merge:
	$(PY) src/ingest/merge_clean.py

# 训练 XGBoost 薪资预测模型
model:
	$(PY) src/analysis/train.py

# 聚合生成 HBase 统计表 (recruit_position/salary/keyword/tier)
agg:
	$(PY) src/agg/agg_hbase.py

# 种子数据 (教学兜底, 不与真实采集混淆)
gen-data:
	$(PY) src/ingest/generate.py

# 提示虚拟机统一入口
serve:
	@echo ">>> 访问入口: http://192.168.92.128:8080"
	@echo ">>> 测试账号: admin / 123456"

# 全量备份
backup:
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	backup_dir=_backup/$$timestamp; \
	mkdir -p $$backup_dir; \
	cp -r src config schemas data tests tools $$backup_dir/; \
	echo "备份完成: $$backup_dir"

# 清理
clean:
	rm -rf __pycache__ .pytest_cache
	find . -name "*.pyc" -delete
