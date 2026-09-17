# -*- coding: utf-8 -*-
"""读 MapReduce 输出, 写入 HBase recruit_position 表"""
import os, subprocess, happybase

HADOOP_HOME = os.environ.get("HADOOP_HOME", "/usr/local/hadoop")
OUTPUT_PATH = "/output/city_count/part-r-00000"

# 读 HDFS 结果
result = subprocess.run(
    [HADOOP_HOME + "/bin/hdfs", "dfs", "-cat", OUTPUT_PATH],
    capture_output=True, text=True
)
lines = result.stdout.strip().split("\n")

print(f"MapReduce 结果: {len(lines)} 个城市")

# 写 HBase
conn = happybase.Connection(os.environ.get("HBASE_HOST", "127.0.0.1"),
                            int(os.environ.get("HBASE_PORT", "9090")), timeout=30000)
tables = conn.tables()
if b"recruit_position" not in tables:
    conn.create_table("recruit_position", {"info": dict()})
    print("创建表 recruit_position")

table = conn.table("recruit_position")
batch = table.batch(batch_size=50)
for line in lines:
    parts = line.strip().split("\t")
    if len(parts) == 2:
        city, count = parts[0], parts[1]
        batch.put(city, {b"info:position_count": count.encode("utf-8")})
        print(f"  {city}: {count}")
batch.send()
conn.close()
print("写入 HBase 完成!")
