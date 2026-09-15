# 招聘信息统计分析系统 Makefile
# 用法: make <target>

PY ?= python

.PHONY: test crawl merge model gen-data serve backup clean

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

# 种子数据 (教学兜底, 不与真实采集混淆)
gen-data:
	$(PY) src/ingest/generate.py

# 生成 1200 条岗位 + 测试用户, 直接灌入 HBase (需要 config/local.env 里的 HBASE_HOST)
hbase-data:
	$(PY) scripts/gen_data.py

# 提示虚拟机统一入口（地址读 config/local.env，该文件不入库；注意去掉 CRLF 的 \r）
serve:
	@IP=$$(sed -n 's/^VM_HOST=//p' config/local.env 2>/dev/null | head -1 | tr -d '\r'); \
	IP=$${IP:-127.0.0.1}; \
	echo ">>> 访问入口: http://$$IP:8080"
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
