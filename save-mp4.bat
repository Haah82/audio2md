@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Save MP4 - YouTube Facebook Instagram
cd /d "%~dp0"

set "PYTHON=.venv\Scripts\python.exe"
set "TEMP_LIST=%TEMP%\audio2md-save-mp4-links.txt"
set "DEFAULT_DIR=%~dp0data\mp4"

if not exist "%PYTHON%" (
    echo [X] Chua tim thay .venv. Hay chay audio2md.bat va chon Menu [1] truoc.
    pause
    exit /b 1
)

:INPUT_LINKS
cls
echo ===================================================
echo   SAVE MP4 TRUC TIEP - YouTube / Facebook / Instagram
echo ===================================================
echo Dan mot hoac nhieu link, cach nhau bang dau phay , hoac cham phay ;
echo Link kenh/playlist YouTube se mo menu chon video nhu Menu 4 ^> O.
echo Khong goi Gemini, khong tao Raw/Refine, khong sua build-audio2md.md.
echo.
set "RAW_LINKS="
set /p "RAW_LINKS=Links (Enter de huy): "
if not defined RAW_LINKS exit /b 0

"%PYTHON%" src\chon_video_kenh.py "!RAW_LINKS!" "%TEMP_LIST%"
if errorlevel 1 (
    echo.
    echo [X] Khong tao duoc danh sach link.
    pause
    goto INPUT_LINKS
)

:CHOOSE_FOLDER
echo.
echo Luu chung cho toan bo danh sach:
echo [1] Mac dinh: %DEFAULT_DIR%
echo [2] Chon thu muc khac...
set "FOLDER_CHOICE="
set /p "FOLDER_CHOICE=Lua chon (mac dinh 1): "
if not defined FOLDER_CHOICE set "FOLDER_CHOICE=1"
if "!FOLDER_CHOICE!"=="1" set "TARGET_DIR=%DEFAULT_DIR%"
if "!FOLDER_CHOICE!"=="2" (
    for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; $dialog=New-Object System.Windows.Forms.FolderBrowserDialog; $dialog.Description='Chon thu muc luu MP4'; if($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$dialog.SelectedPath}"`) do set "TARGET_DIR=%%D"
    if not defined TARGET_DIR (
        echo [-] Khong chon thu muc, quay lai lua chon.
        goto CHOOSE_FOLDER
    )
)
if not defined TARGET_DIR (
    echo [X] Lua chon khong hop le.
    goto CHOOSE_FOLDER
)

:CHOOSE_QUALITY
echo.
echo Chat luong MP4 toi da:
echo [1] 1080p - mac dinh
echo [2] 720p
set "QUALITY_CHOICE="
set /p "QUALITY_CHOICE=Lua chon (mac dinh 1): "
if not defined QUALITY_CHOICE set "QUALITY_CHOICE=1"
if "!QUALITY_CHOICE!"=="1" set "MAX_HEIGHT=1080"
if "!QUALITY_CHOICE!"=="2" set "MAX_HEIGHT=720"
if not defined MAX_HEIGHT (
    echo [X] Lua chon khong hop le.
    goto CHOOSE_QUALITY
)

:CHOOSE_NAMES
echo.
echo Cach dat ten file:
echo [1] Ten mac dinh theo tieu de video
echo [2] Nhap ten rieng cho tung file .mp4
set "NAME_CHOICE="
set /p "NAME_CHOICE=Lua chon (mac dinh 1): "
if not defined NAME_CHOICE set "NAME_CHOICE=1"
set "NAME_ARG="
if "!NAME_CHOICE!"=="1" goto START_SAVE
if "!NAME_CHOICE!"=="2" (
    set "NAME_ARG=--custom-names"
    goto START_SAVE
)
echo [X] Lua chon khong hop le.
goto CHOOSE_NAMES

:START_SAVE
echo.
echo ===================================================
echo Dang luu MP4 vao: !TARGET_DIR!
echo Chat luong toi da: !MAX_HEIGHT!p
echo ===================================================
"%PYTHON%" src\save_mp4.py "%TEMP_LIST%" "!TARGET_DIR!" "!MAX_HEIGHT!" !NAME_ARG!
set "RESULT=!errorlevel!"
echo.
if "!RESULT!"=="0" (
    echo [OK] Da luu xong toan bo danh sach.
) else (
    echo [!] Mot hoac nhieu link khong tai duoc. Xem log ben tren de biet chi tiet.
)
pause
exit /b !RESULT!
