@echo off
REM ============================================================
REM  Chinese-named launcher (added by origin/main, now a thin wrapper).
REM
REM  Merge decision:
REM    - The origin/main version hard-coded the VM address and the SSH
REM      password in this file, which contradicts the "no credentials in
REM      the repo" rule, so that logic is dropped.
REM    - All real launcher logic lives in start_website.bat next to this
REM      file; it reads VM_HOST / VM_SSH_USER from config\local.env.
REM    - This file stays pure ASCII on purpose: a Chinese .bat would be
REM      corrupted when re-encoded between GBK and UTF-8 (see README 6.8.4).
REM ============================================================

title Recruit Web Launcher (zh)
call "%~dp0start_website.bat"
