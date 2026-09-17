#!/bin/bash
# VM 开机自启: Hadoop -> HBase -> Thrift -> Spring Boot -> predict
# 顺序很关键: HBase 依赖 HDFS, Thrift 依赖 HBase, Spring Boot 依赖 HBase+Thrift, predict 独立
# 日志统一写 ~/autostart.log；目录一律用 $HOME，换用户名不用改脚本
LOG="$HOME/autostart.log"
echo "=== $(date) autostart begin ===" >> $LOG

source ~/.bashrc 2>/dev/null

# 1. Hadoop (HDFS + YARN)
echo ">>> start hadoop" >> $LOG
$HADOOP_HOME/sbin/start-dfs.sh >> $LOG 2>&1
$HADOOP_HOME/sbin/start-yarn.sh >> $LOG 2>&1
sleep 8

# 2. HBase + Thrift
echo ">>> start hbase" >> $LOG
$HBASE_HOME/bin/start-hbase.sh >> $LOG 2>&1
sleep 5
$HBASE_HOME/bin/hbase-daemon.sh start thrift >> $LOG 2>&1
sleep 3

# 3. Spring Boot
echo ">>> start spring boot" >> $LOG
cd "$HOME/day08"
source "$HOME/day08/deploy/run/account_env.sh" || exit 1
nohup java -jar target/demo-0.0.1-SNAPSHOT.jar > app.log 2>&1 < /dev/null &
echo $! > "$HOME/day08/app.pid"

# 4. predict 服务 (cron 已有独立 @reboot, 这里兜底, pkill 避免重复)
pkill -f serve_api 2>/dev/null
sleep 1
cd "$HOME/predict"
nohup python3 serve_api.py 8788 >> predict.log 2>&1 < /dev/null &

echo "=== $(date) autostart done ===" >> $LOG
