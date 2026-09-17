@echo off
chcp 936 >nul
title 智聘招聘网站启动器
echo ============================================
echo   智聘 - 招聘分析平台 启动器
echo ============================================
echo.

echo [1/3] 检查虚拟机是否在线...
ping -n 1 -w 2000 192.168.92.128 >nul 2>&1
if errorlevel 1 (
    echo [错误] 虚拟机 192.168.92.128 无法连接!
    echo 请先启动 VMware 虚拟机, 再运行此脚本.
    pause
    exit /b 1
)
echo 虚拟机在线.

echo.
echo [2/3] 检查 Spring Boot 是否在运行...
powershell -Command "try { Invoke-WebRequest -Uri 'http://192.168.92.128:8080/api/hello' -TimeoutSec 3 -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [提示] Spring Boot 未启动, 正在远程启动...
    ssh -o ConnectTimeout=5 xiaoliyu@192.168.92.128 "cd /home/xiaoliyu/day08; export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64; export PATH=$JAVA_HOME/bin:$PATH; nohup java -jar target/demo-0.0.1-SNAPSHOT.jar > app.log 2>&1 < /dev/null &" 2>nul
    if errorlevel 1 (
        echo.
        echo [说明] SSH 自动启动失败
        echo 请手动在虚拟机终端执行:
        echo   cd /home/xiaoliyu/day08
        echo   nohup java -jar target/demo-0.0.1-SNAPSHOT.jar ^> app.log 2^>^&1 ^&
        pause
        exit /b 1
    )
    echo 等待 25 秒 Spring Boot 启动...
    timeout /t 25 /nobreak >nul
) else (
    echo Spring Boot 已在运行.
)

echo.
echo [3/3] 打开浏览器...
start "" "http://192.168.92.128:8080/"
echo.
echo ============================================
echo   网站已在浏览器打开!
echo   地址: http://192.168.92.128:8080/
echo   测试账号: admin / 123456
echo ============================================
timeout /t 3 >nul
