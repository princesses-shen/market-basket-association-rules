#!/bin/bash
# 修复简历上传: 重建 + 重启 Spring Boot
set -e
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH

cd "$HOME/day08"

# 确保上传目录存在
mkdir -p uploads
chmod 777 uploads

echo ">>> 杀旧进程"
pkill -f demo-0.0.1-SNAPSHOT.jar 2>/dev/null || true
sleep 2

echo ">>> Maven 打包"
mvn clean package -DskipTests -q 2>&1 | tail -8

echo ">>> 启动 Spring Boot"
nohup java -jar target/demo-0.0.1-SNAPSHOT.jar > app.log 2>&1 < /dev/null &
echo "等 25 秒启动..."
sleep 25

echo ">>> 健康检查"
curl -s http://localhost:8080/api/hello
echo
echo ">>> DONE"
