#!/bin/bash
# 安装/重置 VM 开机自启 cron
# 只保留一条: @reboot 调用统一自启脚本
# $HOME 在这里就展开成绝对路径写入 crontab，不依赖 cron 运行时的环境变量
echo "@reboot $HOME/vm_autostart.sh >> $HOME/autostart.log 2>&1" | crontab -
echo "=== crontab installed ==="
crontab -l
