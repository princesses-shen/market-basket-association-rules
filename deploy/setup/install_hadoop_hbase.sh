#!/bin/bash
# 部署脚本: 在虚拟机上安装 Hadoop + HBase
# 前提: Ubuntu 22.04+, Java 11
set -e

echo ">>> 1. 检查 Java"
java -version || (echo "请先安装 JDK 11" && exit 1)

echo ">>> 2. 下载 Hadoop 2.10.2"
cd /tmp
wget -q https://archive.apache.org/dist/hadoop/common/hadoop-2.10.2/hadoop-2.10.2.tar.gz
tar xzf hadoop-2.10.2.tar.gz -C /usr/local/
ln -sf /usr/local/hadoop-2.10.2 /usr/local/hadoop

echo ">>> 3. 下载 HBase 2.5.9"
wget -q https://archive.apache.org/dist/hbase/2.5.9/hbase-2.5.9-bin.tar.gz
tar xzf hbase-2.5.9-bin.tar.gz -C /usr/local/
ln -sf /usr/local/hbase-2.5.9 /usr/local/hbase

echo ">>> 4. 配置环境变量"
echo 'export HADOOP_HOME=/usr/local/hadoop' >> ~/.bashrc
echo 'export HBASE_HOME=/usr/local/hbase' >> ~/.bashrc
echo 'export PATH=$PATH:$HADOOP_HOME/bin:$HBASE_HOME/bin' >> ~/.bashrc
source ~/.bashrc

echo ">>> 5. 启动 HDFS + YARN + HBase"
$HADOOP_HOME/sbin/start-dfs.sh
$HADOOP_HOME/sbin/start-yarn.sh
$HBASE_HOME/bin/start-hbase.sh
$HBASE_HOME/bin/hbase-daemon.sh start thrift

echo ">>> Done! 验证: jps"
jps
