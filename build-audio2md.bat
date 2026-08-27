@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Audio to Markdown Pipeline (Raw ^& Refine)
cd /d "%~dp0"

REM Tao bien chua ky tu pipe de tranh loi syntax cua Batch Script
set "pipe=|"

REM Kiem tra va tao thu muc, file can thiet
set "INPUT_DIR=data\input"
set "LINK_FILE=%INPUT_DIR%\build-audio2md.md"
set "TEMP_LIST=%TEMP%\selected_links_audio2md.txt"

if not exist "%INPUT_DIR%" mkdir "%INPUT_DIR%"
if not exist "%LINK_FILE%" (
    > "%LINK_FILE%" echo !pipe! STT !pipe! Link !pipe! Tên file - tiêu đề !pipe! Thời gian !pipe! Raw !pipe! Refine !pipe!
    >> "%LINK_FILE%" echo !pipe!---!pipe!---!pipe!---!pipe!---!pipe!---!pipe!---!pipe!
)

:MENU
cls
echo ===================================================
echo     HỆ THỐNG AUDIO2MD - TRÍCH XUẤT ^& TINH LUYỆN
echo ===================================================
echo [1] Cai dat he thong (Tao .venv va cai requirements)
echo [2] Convert file Video (mp4, avi, mov, mkv...)
echo [3] Convert file Audio (mp3, wav, m4a, aac...)
echo [4] Convert tu Link (Youtube/Facebook/LinkedIn...)
echo [0] Thoat
echo ===================================================
set "choice="
set /p choice="Chon tac vu (0-4): "

if /i "!choice!"=="0" exit
if /i "!choice!"=="1" goto SETUP
if /i "!choice!"=="2" goto VIDEO_FILES
if /i "!choice!"=="3" goto AUDIO_FILES
if /i "!choice!"=="4" goto MENU_LINK
goto MENU

:SETUP
if not exist ".venv" (
    echo [+] Dang tao moi truong ao .venv...
    python -m venv .venv
)
call .venv\Scripts\activate
echo [+] Dang cai dat thu vien...
pip install -r requirements.txt --upgrade

echo.
echo [+] Tien hanh thiet lap FFmpeg (Tu dong tai va them vao System PATH)...
python src\install_ffmpeg.py

echo.
echo [OK] Da thiet lap xong he thong! Vui long khoi dong lai CMD neu truoc do PATH chua co san.
pause
goto MENU

:VIDEO_FILES
set "FILE_EXT=.mp4 .avi .mov .mkv .wmv .flv"
set "SCRIPT_DESC=Video Files (mp4, avi...)"
goto EXEC_LOCAL

:AUDIO_FILES
set "FILE_EXT=.mp3 .wav .m4a .aac .ogg .flac"
set "SCRIPT_DESC=Audio Files (mp3, wav...)"
goto EXEC_LOCAL

:EXEC_LOCAL
cls
echo ===================================================
echo   DANG CHUAN BI XU LY: %SCRIPT_DESC%
echo ===================================================
call :CHON_FILE "%INPUT_DIR%" "%FILE_EXT%"
if /I "!PICKED_MODE!"=="CANCEL" goto MENU
set "FORCE_OVERWRITE=0"
goto RUN_PYTHON
    
:MENU_LINK
cls
echo ===================================================
echo   CONVERT TU LINK (YOUTUBE, FACEBOOK, LINKEDIN...)
echo ===================================================
set "count=0"
REM Fix loi doc Tokens (Dau "|" dung dau dong nen token 1 la STT, token 2 la Link)
for /F "usebackq skip=2 tokens=1,2,3,4 delims=|" %%A in ("%LINK_FILE%") do (
    set "raw_stt=%%A"
    set "raw_stt=!raw_stt: =!"
    
    if "!raw_stt!" NEQ "STT" if "!raw_stt!" NEQ "---" (
        set "raw_link=%%B"
        set "link[!raw_stt!]=!raw_link: =!"
        
        set /a check_stt=!raw_stt! 2>nul
        if "!check_stt!"=="!raw_stt!" (
            if !raw_stt! GTR !count! set "count=!raw_stt!"
            echo  [!raw_stt!] !pipe!!raw_link!!pipe! %%C !pipe! %%D
        )
    )
)

if !count! EQU 0 echo  (Danh sach link hien dang trong)
echo ---------------------------------------------------
echo  Go so de chon (VD: 1 hoac 1,3,5 hoac 2-4)
echo  [A] Convert toan bo danh sach tren
echo  [O] Nhap link moi (Tu dong luu vao danh sach)
echo  [0] Quay lai Menu chinh
echo ===================================================
set "lchoice="
set /p lchoice="Lua chon cua ban: "

if "!lchoice!"=="" goto MENU_LINK
if /i "!lchoice!"=="0" goto MENU
if /i "!lchoice!"=="A" goto PROCESS_ALL_LINKS
if /i "!lchoice!"=="O" goto ADD_NEW_LINK

set "lchoice=!lchoice: =!"
set "lchoice=!lchoice:;=,!"
set "lchoice=!lchoice:,= !"

if "!lchoice!"=="" goto MENU_LINK

> "%TEMP_LIST%" echo.
set "has_link=0"
for /l %%i in (1,1,!count!) do set "CF_SEL[%%i]="

for %%N in (!lchoice!) do call :CF_MARK "%%N"

for /l %%i in (1,1,!count!) do (
    if defined CF_SEL[%%i] (
        >> "%TEMP_LIST%" echo !link[%%i]!
        set "has_link=1"
    )
)
if "!has_link!"=="0" (
    echo [X] Lua chon khong hop le hoac khong co link.
    pause
    goto MENU_LINK
)
set "FORCE_OVERWRITE=0"
goto RUN_PYTHON

:ADD_NEW_LINK
echo.
set "newlink="
set /p newlink="Paste link moi vao day: "
if "!newlink!"=="" goto MENU_LINK

set "link_exists=0"
for /L %%i in (1,1,!count!) do (
    if /i "!link[%%i]!"=="!newlink!" (
        set "link_exists=1"
    )
)

set "FORCE_OVERWRITE=0"
if "!link_exists!"=="1" (
    echo.
    echo [!] Link da ton tai trong danh sach.
    set /p ow="Co muon ghi de file md cu khong (Y/N)? "
    if /i "!ow!"=="Y" (
        set "FORCE_OVERWRITE=1"
        > "%TEMP_LIST%" echo !newlink!
        goto RUN_PYTHON
    ) else (
        echo [-] Da huy.
        pause
        goto MENU_LINK
    )
)

set /a next_idx=count+1
set "datetime="
for /f "delims=" %%a in ('powershell -Command "Get-Date -Format 'dd/MM/yy HH:mm:ss'"') do set "datetime=%%a"

set "TMP_MD=%TEMP%\temp_build_audio2md.md"
> "!TMP_MD!" echo !pipe! STT !pipe! Link !pipe! Tên file - tiêu đề !pipe! Thời gian !pipe! Raw !pipe! Refine !pipe!
>> "!TMP_MD!" echo !pipe!---!pipe!---!pipe!---!pipe!---!pipe!---!pipe!---!pipe!
>> "!TMP_MD!" echo !pipe! !next_idx! !pipe! !newlink! !pipe! (Chua co tieu de) !pipe! !datetime! !pipe!  !pipe!  !pipe!

for /F "usebackq skip=2 delims=" %%L in ("%LINK_FILE%") do (
    >> "!TMP_MD!" echo %%L
)

move /y "!TMP_MD!" "%LINK_FILE%" >nul

> "%TEMP_LIST%" echo !newlink!
echo [+] Da luu link vao danh sach vi tri so !next_idx! (Moi nhat).
goto RUN_PYTHON

:PROCESS_ALL_LINKS
if !count! EQU 0 (
    echo [X] Khong co link nao de xu ly.
    pause
    goto MENU_LINK
)
> "%TEMP_LIST%" echo.
for /L %%i in (1, 1, !count!) do (
     >> "%TEMP_LIST%" echo !link[%%i]!
)
set "FORCE_OVERWRITE=0"
goto RUN_PYTHON

:RUN_PYTHON
echo.
echo ===================================================
echo  ĐANG GỌI PYTHON XỬ LÝ (TRÍCH XUẤT ^& REFINE)...
echo ===================================================
if not exist ".venv" (
    echo [!] Chua co moi truong. Vui long chon Menu [1] truoc de cai dat.
    pause
    goto MENU
)
call .venv\Scripts\activate 2>nul
python src\main_audio2md.py "%TEMP_LIST%"
echo.
echo [OK] DA XU LY XONG TOAN BO!
pause
goto MENU

REM ============================================================
REM  CHON_FILE - chon file trong thu muc (Dung cho Local File)
REM ============================================================
:CHON_FILE
setlocal EnableDelayedExpansion
set "CF_DIR=%~1"
set "CF_EXTS=%~2"
set "CF_N=0"

for %%F in ("%CF_DIR%\*") do call :CF_ADD "%%~fF"

if !CF_N! EQU 0 (
    echo.
    echo   [X] Trong "%CF_DIR%" khong co file nao thuoc loai: %CF_EXTS%
    echo       Chep file dung dinh dang vao thu muc va thu lai.
    echo.
    pause
    goto CF_HUY
)

:CF_MENU
echo.
echo   Thu muc : %CF_DIR%
echo   Loai file: %CF_EXTS%      -  tim thay !CF_N! file
echo  ------------------------------------------------------------
for /l %%i in (1,1,!CF_N!) do echo     [%%i]  !CF_F[%%i]!   -  !CF_S[%%i]! KB
echo  ------------------------------------------------------------
echo   Go so de chon:  1   hoac  1,3,5   hoac  2-4   hoac  1,3-5,8
echo   Go A = toan bo !CF_N! file,  T = chon theo ten,  0 = quay lai
set "CF_IN="
set /p "CF_IN=  Chon file: "
if not defined CF_IN goto CF_MENU
if "!CF_IN!"=="0" goto CF_HUY
if /I "!CF_IN!"=="A" goto CF_ALL
if "!CF_IN!"=="*" goto CF_ALL
if /I "!CF_IN!"=="T" goto CF_BYNAME

set "CF_TOK=!CF_IN: =!"
set "CF_TOK=!CF_TOK:;=,!"
set "CF_TOK=!CF_TOK:,= !"
if not defined CF_TOK goto CF_MENU
for /l %%i in (1,1,!CF_N!) do set "CF_SEL[%%i]="
set "CF_ANY="
for %%N in (!CF_TOK!) do call :CF_MARK "%%N"
if not defined CF_ANY (
    echo   [X] Chua chon duoc file nao hop le. Thu lai.
    goto CF_MENU
)
goto CF_WRITE

:CF_BYNAME
echo.
set "CF_NAMES="
set /p "CF_NAMES=  Nhap ten file, cach nhau bang dau phay, khong can duoi: "
if not defined CF_NAMES goto CF_MENU
for /l %%i in (1,1,!CF_N!) do set "CF_SEL[%%i]="
set "CF_ANY="
for %%A in ("!CF_NAMES:,=" "!") do call :CF_MARK_NAME %%A
if not defined CF_ANY (
    echo   [X] Chua chon duoc file nao hop le. Thu lai.
    goto CF_MENU
)
goto CF_WRITE

:CF_HUY
endlocal & set "PICKED_MODE=CANCEL" & set "PICKED_ALL=0" & exit /b 1

:CF_ALL
> "%TEMP_LIST%" (
    for /l %%i in (1,1,!CF_N!) do echo %CF_DIR%\!CF_F[%%i]!
)
echo.
echo   [OK] Da chon toan bo !CF_N! file.
endlocal & set "PICKED_MODE=LIST" & set "PICKED_ALL=1" & exit /b 0

:CF_WRITE
set "CF_DEM=0"
> "%TEMP_LIST%" (
    for /l %%i in (1,1,!CF_N!) do if defined CF_SEL[%%i] echo %CF_DIR%\!CF_F[%%i]!
)
for /l %%i in (1,1,!CF_N!) do if defined CF_SEL[%%i] set /a CF_DEM+=1
echo.
echo   [OK] Da chon !CF_DEM! file:
for /l %%i in (1,1,!CF_N!) do if defined CF_SEL[%%i] echo        - !CF_F[%%i]!
endlocal & set "PICKED_MODE=LIST" & set "PICKED_ALL=0" & exit /b 0

:CF_ADD
set "AD_EXT=%~x1"
if "%CF_EXTS%"=="*" goto CF_ADD_OK
if not defined AD_EXT exit /b 0
for %%E in (%CF_EXTS%) do if /I "%AD_EXT%"=="%%E" goto CF_ADD_OK
exit /b 0
:CF_ADD_OK
set /a CF_N+=1
set "CF_F[%CF_N%]=%~nx1"
set "AD_KB=0"
set /a AD_KB=(%~z1+1023)/1024 >nul 2>&1
set "CF_S[%CF_N%]=%AD_KB%"
exit /b 0

:CF_MARK
set "MK=%~1"
if not defined MK exit /b 0
set "MK_R=%MK:-= %"
if "%MK_R%"=="%MK%" (
    call :CF_MARK_ONE "%MK%"
    exit /b 0
)
set "MK_A="
set "MK_B="
for /F "tokens=1,2" %%a in ("%MK_R% #") do (
    set "MK_A=%%a"
    set "MK_B=%%b"
)
if "!MK_B!"=="#" (
    call :CF_MARK_ONE "!MK_A!"
    exit /b 0
)
set "MK_I=0"
set "MK_J=0"
set /a MK_I=MK_A >nul 2>&1
set /a MK_J=MK_B >nul 2>&1
if !MK_I! GTR !MK_J! (
    set /a MK_T=!MK_I!
    set /a MK_I=!MK_J!
    set /a MK_J=!MK_T!
)
if !MK_I! LSS 1 set "MK_I=1"
if !MK_J! GTR !CF_N! set "MK_J=!CF_N!"
if !MK_I! GTR !MK_J! (
    echo   [^!] Bo qua khoang khong hop le: %MK%
    exit /b 0
)
for /l %%i in (!MK_I!,1,!MK_J!) do call :CF_MARK_ONE "%%i"
exit /b 0

:CF_MARK_ONE
set "M1=%~1"
if not defined M1 exit /b 0
set "M1N=0"
set /a M1N=M1 >nul 2>&1
if !M1N! LSS 1 (
    exit /b 0
)
if !M1N! GTR 9999 (
    exit /b 0
)
set "CF_SEL[!M1N!]=1"
set "CF_ANY=1"
exit /b 0

:CF_MARK_NAME
set "NM=%~1"
if not defined NM exit /b 0
set "NM_HIT="
for /l %%i in (1,1,!CF_N!) do call :CF_NAME_CMP %%i "!NM!"
if not defined NM_HIT (
    echo   [^!] Khong thay file ten "%NM%" trong %CF_DIR%.
)
exit /b 0

:CF_NAME_CMP
set "CI=%~1"
call set "CN=%%CF_F[%CI%]%%"
for %%X in ("!CN!") do if /I "%%~nX"=="%~2" (
    set "CF_SEL[%CI%]=1"
    set "CF_ANY=1"
    set "NM_HIT=1"
)
exit /b 0