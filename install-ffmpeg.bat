@echo off
title FFmpeg Auto Installer by Gemini
color 0A

:: Kiem tra quyen Administrator (Bat buoc de sua System Variables)
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :menu
) else (
    color 0C
    echo =======================================================
    echo LOI: BAN CHUA CUNG CAP QUYEN QUAN TRI VIEN (ADMINISTRATOR)
    echo =======================================================
    echo Vui long tat cua so nay, click chuot phai vao file .bat
    echo va chon "Run as administrator".
    echo =======================================================
    pause
    exit /b
)

:menu
cls
echo =======================================================
echo          FFMPEG AUTO INSTALLER TREN WINDOWS
echo =======================================================
echo 1. Tu dong tai, cai dat FFmpeg va them vao System Path
echo 2. Thoat
echo =======================================================
set /p choice="Vui long chon (1 hoac 2): "

if "%choice%"=="1" goto :install_ffmpeg
if "%choice%"=="2" exit /b
goto :menu

:install_ffmpeg
cls
echo =======================================================
echo 1/4: DANG TAI XUONG FFMPEG... (Vui long doi it phut)
echo =======================================================
:: Su dung PowerShell de tai file zip ve thu muc TEMP
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile '%TEMP%\ffmpeg.zip'"

echo.
echo =======================================================
echo 2/4: DANG GIAI NEN VA CAI DAT...
echo =======================================================
:: Xoa thu muc cu neu da ton tai truoc do de tranh loi
if exist "C:\ffmpeg" rmdir /s /q "C:\ffmpeg"
if exist "C:\ffmpeg_temp" rmdir /s /q "C:\ffmpeg_temp"

:: Giai nen vao thu muc tam
powershell -Command "Expand-Archive -Path '%TEMP%\ffmpeg.zip' -DestinationPath 'C:\ffmpeg_temp' -Force"

:: Di chuyen thu muc con ra dung vi tri C:\ffmpeg
powershell -Command "Move-Item -Path (Get-ChildItem -Path 'C:\ffmpeg_temp' -Directory).FullName -Destination 'C:\ffmpeg' -Force"

:: Don dep file rac
rmdir /s /q "C:\ffmpeg_temp"
del /q "%TEMP%\ffmpeg.zip"

echo.
echo =======================================================
echo 3/4: DANG THEM VAO SYSTEM VARIABLES PATH...
echo =======================================================
:: Su dung PowerShell de kiem tra va them vao System Path
powershell -Command "$sysPath = [Environment]::GetEnvironmentVariable('Path', 'Machine'); $ffmpegPath = 'C:\ffmpeg\bin'; if ($sysPath -notmatch [regex]::Escape($ffmpegPath)) { $newPath = $sysPath + ';' + $ffmpegPath; [Environment]::SetEnvironmentVariable('Path', $newPath, 'Machine'); Write-Host '-> DA THEM THANH CONG C:\ffmpeg\bin VAO PATH!' -ForegroundColor Green } else { Write-Host '-> FFMPEG DA TON TAI SAN TRONG PATH TREN HE THONG.' -ForegroundColor Yellow }"

echo.
echo =======================================================
echo 4/4: HOAN TAT!
echo =======================================================
echo Thu muc cai dat cua ban tai: C:\ffmpeg
echo De su dung, ban hay MO LAI mot cua so Command Prompt (CMD)
echo hoac PowerShell MOI va go lenh: ffmpeg -version
echo =======================================================
pause
goto :menu