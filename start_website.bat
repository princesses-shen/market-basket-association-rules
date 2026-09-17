@echo off
title Recruit Web Launcher
echo ============================================
echo   Recruit Web Launcher
echo ============================================
echo.

echo [1/3] Checking VM...
ping -n 1 -w 2000 192.168.92.128 >nul 2>&1
if errorlevel 1 (
    echo [ERROR] VM 192.168.92.128 unreachable!
    echo Please start VMware first, then run this.
    pause
    exit /b 1
)
echo VM online.

echo.
echo [2/3] Checking Spring Boot...
powershell -Command "try { Invoke-WebRequest -Uri 'http://192.168.92.128:8080/api/hello' -TimeoutSec 3 -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo Spring Boot not running, starting remotely...
    ssh -o ConnectTimeout=5 xiaoliyu@192.168.92.128 "cd /home/xiaoliyu/day08; export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64; export PATH=$JAVA_HOME/bin:$PATH; nohup java -jar target/demo-0.0.1-SNAPSHOT.jar > app.log 2>&1 < /dev/null &" 2>nul
    if errorlevel 1 (
        echo SSH auto-start failed.
        echo Please start manually in VM terminal:
        echo   cd /home/xiaoliyu/day08
        echo   nohup java -jar target/demo-0.0.1-SNAPSHOT.jar ^> app.log 2^>^&1 ^&
        pause
        exit /b 1
    )
    echo Waiting 25s for Spring Boot...
    timeout /t 25 /nobreak >nul
) else (
    echo Spring Boot running.
)

echo.
echo [3/3] Opening browser...
start "" "http://192.168.92.128:8080/"
echo.
echo ============================================
echo   Website opened in browser!
echo   URL: http://192.168.92.128:8080/
echo   Test account: admin / 123456
echo ============================================
timeout /t 3 >nul
