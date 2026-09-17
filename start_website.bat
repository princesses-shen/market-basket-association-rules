@echo off
REM ============================================================
REM  Recruit Web Launcher
REM  Usage: double-click this file.
REM  Job:   make sure all 5 services on the Ubuntu VM are up,
REM         then open the recruit web in the browser.
REM  VM address is read from config\local.env (not tracked by git).
REM  Every run writes a log next to this file: start_website.log
REM ============================================================

title Recruit Web Launcher

REM ---- Private config: config\local.env (git-ignored; template: local.env.example) ----
set "VM_IP="
set "VM_USER="
if exist "%~dp0config\local.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0config\local.env") do (
        if /i "%%a"=="VM_HOST" set "VM_IP=%%b"
        if /i "%%a"=="VM_SSH_USER" set "VM_USER=%%b"
    )
)
if not defined VM_IP (
    echo   [ERROR] VM_HOST not found in config\local.env
    echo           Copy config\local.env.example to config\local.env and fill in your VM address first.
    echo.
    pause
    exit /b 1
)
if not defined VM_USER set "VM_USER=your-user"

set "BACKEND_PORT=8080"
set "PREDICT_PORT=8788"
set "LOG=%~dp0start_website.log"
set "SSH_OPTS=-o ConnectTimeout=6 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

echo. > "%LOG%"
call :log "=== Recruit Web Launcher %DATE% %TIME% ==="

echo ============================================
echo   Recruit Web Launcher
echo   VM    : %VM_IP%
echo   Log   : %LOG%
echo ============================================
echo.

REM ---------------- [1/6] VM reachable ----------------
echo [1/6] Checking VM reachability ...
call :log "[1/6] ping %VM_IP%"
ping -n 2 -w 800 %VM_IP% >nul 2>&1
if errorlevel 1 (
    echo   [WARN] No ICMP reply from %VM_IP%.
    echo          Not fatal - checking TCP/HTTP services directly below.
    echo          If everything below still fails, start VMware and the VM first.
    call :log "[1/6] WARN no ICMP reply"
) else (
    echo   VM replies to ping.
    call :log "[1/6] ping OK"
)

REM ---------------- [2/6] big data layer ----------------
echo.
echo [2/6] Checking big data layer (Hadoop / HBase / Thrift) ...
python "%~dp0scripts\deploy_local_vm.py" start >> "%LOG%" 2>&1
if errorlevel 1 (
    echo   [WARN] Could not start services. Check that VMware is running and review start_website.log.
    call :log "[2/6] deploy_local_vm.py start FAILED"
) else (
    echo   Big data layer OK.
    call :log "[2/6] OK"
)

REM ---------------- [3/6] Spring Boot ----------------
echo.
echo [3/6] Checking Spring Boot (%BACKEND_PORT%) ...
powershell -NoProfile -Command "try{Invoke-WebRequest -Uri 'http://%VM_IP%:%BACKEND_PORT%/api/hello' -TimeoutSec 4 -UseBasicParsing|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    echo   Not running. Starting it over SSH ...
    call :log "[3/6] not running, starting jar"
    ssh %SSH_OPTS% %VM_USER%@%VM_IP% "cd $HOME/day08 && export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 && export PATH=$JAVA_HOME/bin:$PATH && nohup java -jar target/demo-0.0.1-SNAPSHOT.jar > app.log 2>&1 < /dev/null &" >nul 2>&1
    echo   Waiting 25s for Spring Boot ...
    timeout /t 25 /nobreak >nul
) else (
    echo   Spring Boot running.
    call :log "[3/6] OK"
)

REM ---------------- [4/6] predict service ----------------
echo.
echo [4/6] Checking predict service (%PREDICT_PORT%) ...
powershell -NoProfile -Command "try{Invoke-WebRequest -Uri 'http://%VM_IP%:%PREDICT_PORT%/api/overview' -TimeoutSec 4 -UseBasicParsing|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    echo   Not running. Starting it over SSH ...
    call :log "[4/6] not running, starting serve_api.py"
    ssh %SSH_OPTS% %VM_USER%@%VM_IP% "cd $HOME/predict && nohup .venv/bin/python serve_api.py %PREDICT_PORT% > predict.log 2>&1 < /dev/null &" >nul 2>&1
    echo   Waiting 8s for predict service ...
    timeout /t 8 /nobreak >nul
) else (
    echo   Predict service running.
    call :log "[4/6] OK"
)

REM ---------------- [5/6] final verify ----------------
echo.
echo [5/6] Final verify (backend /api/hello) ...
set "READY="
powershell -NoProfile -Command "try{Invoke-WebRequest -Uri 'http://%VM_IP%:%BACKEND_PORT%/api/hello' -TimeoutSec 6 -UseBasicParsing|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 set "READY=1"
if defined READY (
    echo   Backend ready.
    call :log "[5/6] backend ready"
) else (
    echo   [WARN] Backend not answering yet. Waiting 15s more ...
    call :log "[5/6] WARN not ready"
    timeout /t 15 /nobreak >nul
)

REM ---------------- [6/6] open browser ----------------
echo.
echo [6/6] Opening browser ...
start "" "http://%VM_IP%:%BACKEND_PORT%/"
call :log "[6/6] opened http://%VM_IP%:%BACKEND_PORT%/"

echo.
echo ============================================
echo   Done. Website: http://%VM_IP%:%BACKEND_PORT%/
echo   Dashboard   : http://%VM_IP%:%BACKEND_PORT%/dashboard.html
echo   User account: admin / 123456
echo   Company     : demo_co / 123456
echo   Full log    : %LOG%
echo ============================================
echo.
timeout /t 8
exit /b 0

:log
>>"%LOG%" echo %~1
exit /b 0
