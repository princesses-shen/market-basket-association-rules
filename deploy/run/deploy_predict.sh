#!/bin/bash
# 部署 predict 薪资预测服务到 VM
# 用法: bash deploy/run/deploy_predict.sh
# 前提: 先设置 VM_IP / VM_USER 环境变量（或在本机 config/local.env 里配好，
#       然后 source 它：set -a; . config/local.env; set +a），且 SSH 免密已配置
set -e

# 仓库里不留真实地址与用户名，未设置就直接报错退出
VM_IP="${VM_IP:?请先设置 VM_IP，例如: export VM_IP=<你的虚拟机IP>}"
VM_USER="${VM_USER:?请先设置 VM_USER，例如: export VM_USER=<你的用户名>}"
VM_HOME="/home/$VM_USER"
PREDICT_DIR="$VM_HOME/predict"

# 项目根目录(脚本在 deploy/run/ 下, 往上 2 层)
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo ">>> 1. 在 VM 上创建 predict 目录结构"
ssh $VM_USER@$VM_IP "mkdir -p $PREDICT_DIR/artifacts/models $PREDICT_DIR/src/analysis"

echo ">>> 2. 上传 serve_api.py"
scp "$PROJECT_ROOT/src/serving/predict_api/serve_api.py" $VM_USER@$VM_IP:$PREDICT_DIR/

echo ">>> 3. 上传模型文件 salary_predictor.pkl"
scp "$PROJECT_ROOT/artifacts/models/salary_predictor.pkl" $VM_USER@$VM_IP:$PREDICT_DIR/artifacts/models/

echo ">>> 4. 上传 features.py"
scp "$PROJECT_ROOT/src/analysis/features.py" $VM_USER@$VM_IP:$PREDICT_DIR/src/analysis/

echo ">>> 5. 安装 Python 依赖"
ssh $VM_USER@$VM_IP "pip3 install numpy scikit-learn 2>&1 | tail -5"

echo ">>> 6. 验证部署"
ssh $VM_USER@$VM_IP "ls -la $PREDICT_DIR/ $PREDICT_DIR/artifacts/models/ $PREDICT_DIR/src/analysis/"

echo ">>> predict 服务部署完成！"
echo "    启动: ssh $VM_USER@$VM_IP 'cd $PREDICT_DIR && nohup python3 serve_api.py 8788 > predict.log 2>&1 &'"
echo "    验证: curl http://$VM_IP:8788/api/overview"
