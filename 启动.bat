@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python bootstrap.py
) else (
  py -3 bootstrap.py
)
if errorlevel 1 pause
