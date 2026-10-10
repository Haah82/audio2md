@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title Save MP4 / MP3
cd /d "%~dp0"

REM Python dung chung C:\Addins\.venv; chua co thi lui ve python he thong.
set "PY=C:\Addins\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" src\save_media_gui.py
set "RESULT=%errorlevel%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%
