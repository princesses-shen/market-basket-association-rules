#!/bin/bash
# 启动 Spring Boot 后端
# 关键: export HADOOP_CLASSPATH=$(hbase classpath) 解决 ZK 版本冲突
set -e
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_CLASSPATH=$(/usr/local/hbase/bin/hbase classpath)
export PATH=$JAVA_HOME/bin:$PATH

cd /home/xiaoliyu/day08
pkill -f demo-0.0.1-SNAPSHOT.jar 2>/dev/null || true
sleep 2

echo ">>> 启动 Spring Boot..."
nohup java -jar target/demo-0.0.1-SNAPSHOT.jar > app.log 2>&1 &
echo $! > app.pid
sleep 10

echo ">>> 检查启动"
if curl -s http://localhost:8080/api/hello | grep -q "已启动"; then
    echo "Spring Boot 启动成功!"
else
    echo "启动失败, 查看日志: tail -20 app.log"
    tail -20 app.log
fi
