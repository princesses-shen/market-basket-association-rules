#!/bin/bash
# 启动 Python 预测服务 (8788)
set -e
cd "$HOME/predict"
pkill -f serve_api 2>/dev/null || true
sleep 2

echo ">>> 启动预测服务..."
nohup python3 serve_api.py 8788 > predict.log 2>&1 &
echo $! > predict.pid
sleep 5

echo ">>> 检查启动"
if curl -s http://localhost:8788/api/overview | grep -q "code"; then
    echo "预测服务启动成功!"
else
    echo "启动失败, 查看日志: cat predict.log"
    cat predict.log
fi
