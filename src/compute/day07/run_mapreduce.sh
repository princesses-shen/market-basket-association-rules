#!/bin/bash
# MapReduce day07: 聚合城市岗位数
# 用法: bash run_mapreduce.sh
# 前提: HDFS + YARN 已启动, recruit_clean.tsv 已上传到 HDFS

set -e

HADOOP_HOME=${HADOOP_HOME:-/usr/local/hadoop}
INPUT_PATH="/data/recruit/recruit_clean.tsv"
OUTPUT_PATH="/output/city_count"

echo ">>> 1. 编译 MapReduce"
mkdir -p /tmp/mr_classes
javac -classpath $(${HADOOP_HOME}/bin/hadoop classpath) -d /tmp/mr_classes \
  src/compute/day07/java/com/example/mr/CityCountMapper.java \
  src/compute/day07/java/com/example/mr/CityCountReducer.java \
  src/compute/day07/java/com/example/mr/CityCountDriver.java

echo ">>> 2. 打包 jar"
jar cf /tmp/citycount.jar -C /tmp/mr_classes .

echo ">>> 3. 上传数据到 HDFS (如果还没有)"
${HADOOP_HOME}/bin/hdfs dfs -mkdir -p /data/recruit
${HADOOP_HOME}/bin/hdfs dfs -put -f data/clean/recruit_clean.tsv /data/recruit/ 2>/dev/null || true

echo ">>> 4. 删除旧输出"
${HADOOP_HOME}/bin/hdfs dfs -rm -r -f $OUTPUT_PATH 2>/dev/null || true

echo ">>> 5. 运行 MapReduce job"
${HADOOP_HOME}/bin/hadoop jar /tmp/citycount.jar com.example.mr.CityCountDriver $INPUT_PATH $OUTPUT_PATH

echo ">>> 6. 查看结果"
${HADOOP_HOME}/bin/hdfs dfs -cat $OUTPUT_PATH/part-r-00000

echo ">>> 7. 写入 HBase (recruit_position 表)"
python3 src/compute/day07/write_hbase.py

echo ">>> Done!"
