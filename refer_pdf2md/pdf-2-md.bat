@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Chuyen tai lieu sang Obsidian Markdown

set "ROOT=%~dp0"
set "INPUT=%ROOT%data\input"
set "VENVPY=%ROOT%.venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if not exist "%INPUT%" mkdir "%INPUT%"

set "PY=python"
if exist "%VENVPY%" set "PY=%VENVPY%"

:MENU
cls
echo ============================================================
echo      PDF2MD  -  CHUYEN TAI LIEU SANG OBSIDIAN MARKDOWN
echo ============================================================
echo.
echo   [1]   Cai dat / kiem tra moi truong
echo.
echo   [2]   XU LY TAI LIEU
echo         2.1  Sua file .md dang bi loi  (chi va phan thieu,
echo              KHONG chay lai va KHONG ghi de file hien co)
echo         2.2  Kiem tra file .md thieu trang nao  (mien phi)
echo         2.3  Uoc tinh token truoc khi chay      (mien phi)
echo         2.4  Mo giao dien xu ly (Tkinter)
echo         2.5  Chuan hoa ten file trong data\input (chay TRUOC khi convert)
echo.
echo   [3]   API va CHI PHI
echo         3.1  Xem tinh trang be API key (Free/Paid, token da dung)
echo         3.2  Go trang thai nghi cua cac key (sang ngay moi)
echo.
echo   [4]   Dong bo GitHub (Git Sync)
echo.
echo   [0]   Thoat
echo.
echo ============================================================
set "SEL="
set /p SEL="Chon (go ca so phu, vd 2.1): "
if not defined SEL goto MENU
set "SEL=!SEL: =!"

if "!SEL!"=="0"   exit /b 0
if "!SEL!"=="1"   goto SETUP
if "!SEL!"=="2"   goto MENU2
if "!SEL!"=="2.1" goto VA_LOI
if "!SEL!"=="2.2" goto KIEM_TRA
if "!SEL!"=="2.3" goto UOC_CHI_PHI
if "!SEL!"=="2.4" goto GUI
if "!SEL!"=="2.5" goto DOI_TEN
if "!SEL!"=="3"   goto MENU3
if "!SEL!"=="3.1" goto KEYPOOL
if "!SEL!"=="3.2" goto GO_NGHI
if "!SEL!"=="4"   goto GITSYNC
echo.
echo [X] Lua chon khong hop le: !SEL!
echo.
pause
goto MENU

:MENU2
cls
echo ============================================================
echo                  [2] XU LY TAI LIEU
echo ============================================================
echo.
echo   2.1  Sua file .md dang bi loi
echo        Do xem file da xuat con thieu trang nao roi CHI chay lai
echo        dung nhung trang do va chen vao dung cho. File hien co
echo        khong bi ghi de - ban goc luu thanh .md.bak
echo.
echo   2.2  Kiem tra file .md thieu trang nao
echo        Chi bao cao, khong goi API, khong sua gi. Mien phi.
echo.
echo   2.3  Uoc tinh token truoc khi chay
echo        Xem mot bo ho so ton bao nhieu token truoc khi bam chay.
echo.
echo   2.4  Mo giao dien xu ly (Tkinter)
echo        Chuyen doi tai lieu MOI trong data\input.
echo.
echo   2.5  Chuan hoa ten file trong data\input
echo        Bo dau, ve chu thuong, dung gach noi. Chay TRUOC khi convert
echo        vi ten file co dau tieng Viet lam HONG buoc upload len Gemini.
echo        File .md va thu muc anh da xuat duoc doi ten theo.
echo.
echo   [0]  Quay lai
echo.
echo ============================================================
set "SEL2="
set /p SEL2="Chon (1-5): "
set "SEL2=!SEL2: =!"
if "!SEL2!"=="0" goto MENU
if "!SEL2!"=="1" goto VA_LOI
if "!SEL2!"=="2" goto KIEM_TRA
if "!SEL2!"=="3" goto UOC_CHI_PHI
if "!SEL2!"=="4" goto GUI
if "!SEL2!"=="5" goto DOI_TEN
goto MENU2

:MENU3
cls
echo ============================================================
echo                  [3] API VA CHI PHI
echo ============================================================
echo.
echo   3.1  Xem tinh trang be API key
echo   3.2  Go trang thai nghi cua cac key
echo.
echo   [0]  Quay lai
echo.
set "SEL3="
set /p SEL3="Chon (1-2): "
set "SEL3=!SEL3: =!"
if "!SEL3!"=="0" goto MENU
if "!SEL3!"=="1" goto KEYPOOL
if "!SEL3!"=="2" goto GO_NGHI
goto MENU3

:SETUP
cls
echo ============================================================
echo            [1] CAI DAT / KIEM TRA MOI TRUONG
echo ============================================================
echo.
if not exist ".venv" (
    echo Dang tao moi truong ao .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [X] Khong tao duoc .venv. Kiem tra Python tren may.
        pause
        goto MENU
    )
    set "PY=%VENVPY%"
)
"%VENVPY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [X] Cai requirements that bai.
) else (
    "%VENVPY%" -c "import tkinter; print('[OK] Tkinter san sang')"
    echo.
    echo Kiem tra be API key:
    "%VENVPY%" -u src\gemini_pool.py
)
echo.
pause
goto MENU

:VA_LOI
cls
echo ============================================================
echo        [2.1] SUA FILE .MD DANG BI LOI (VA PHAN THIEU)
echo ============================================================
echo.
echo Cach lam: doi chieu tung trang PDF goc voi file .md da xuat,
echo tim ra nhung trang bi mat, CHI chay lai dung nhung trang do
echo roi chen vao dung vi tri. Phan da tot giu nguyen, khong ton
echo them token. Ban goc duoc luu thanh .md.bak truoc khi ghi.
echo.
echo Buoc 1 kiem tra mien phi, sau do moi hoi y kien ban roi va.
echo.
pause
cls
"!PY!" -u src\patch_missing_pages.py --chon
echo.
pause
goto MENU

:KIEM_TRA
cls
echo ============================================================
echo      [2.2] KIEM TRA FILE .MD THIEU TRANG NAO (MIEN PHI)
echo ============================================================
echo.
echo Chi bao cao, khong goi API, khong sua file.
echo.
"!PY!" -u src\patch_missing_pages.py --chon --dry-run
echo.
pause
goto MENU

:UOC_CHI_PHI
cls
echo ============================================================
echo       [2.3] UOC TINH TOKEN TRUOC KHI CHAY (MIEN PHI)
echo ============================================================
echo.
echo De trong roi Enter de quet toan bo data\input,
echo hoac keo tha mot file PDF hoac mot thu muc vao day.
echo.
set "TARGET="
set /p TARGET="Duong dan: "
set TARGET=!TARGET:"=!
echo.
if "!TARGET!"=="" (
    "!PY!" -u src\uoc_chi_phi.py
) else (
    "!PY!" -u src\uoc_chi_phi.py "!TARGET!"
)
echo.
pause
goto MENU

:GUI
if not exist "%VENVPY%" (
    echo [X] Chua co .venv. Chay muc [1] Cai dat truoc.
    pause
    goto MENU
)
if not exist "src\gui_app.py" (
    echo [X] Khong tim thay src\gui_app.py
    pause
    goto MENU
)
"%VENVPY%" src\gui_app.py
goto MENU

:KEYPOOL
cls
echo ============================================================
echo           [3.1] TINH TRANG BE API KEY GEMINI
echo ============================================================
echo.
"!PY!" -u src\gemini_pool.py
echo.
echo Ghi chu: chi bien co chu FREE moi duoc coi la Free Tier.
echo Tai lieu mat (ho so thau, hop dong) nen dat
echo GEMINI_KHONG_DUNG_FREE=1 trong .env de ep di key tra phi,
echo vi noi dung gui qua Free Tier co the duoc Google dung de
echo cai thien san pham va co nguoi that xem xet.
echo.
pause
goto MENU

:GO_NGHI
cls
echo ============================================================
echo         [3.2] GO TRANG THAI NGHI CUA CAC API KEY
echo ============================================================
echo.
echo Dung khi da sang ngay moi (han muc Free Tier da reset) ma he
echo thong van con ghi nho la key dang bi 429.
echo.
"!PY!" -u src\gemini_pool.py --go-nghi
echo.
pause
goto MENU

:DOI_TEN
cls
echo ============================================================
echo    [2.5] CHUAN HOA TEN FILE TRONG data\input
echo ============================================================
echo.
echo Ten file co dau tieng Viet lam HONG buoc upload len Gemini
echo (SDK ma hoa ten file bang ASCII), nen phai chuan hoa TRUOC
echo khi convert. File .md va thu muc anh da xuat se duoc doi ten
echo theo de khong dut cap PDF - Markdown.
echo.
echo De trong roi Enter de xu ly ca data\input,
echo hoac keo tha mot thu muc con vao day.
echo.
set "TARGET="
set /p TARGET="Duong dan: "
set TARGET=!TARGET:"=!
echo.
echo --- BUOC 1: XEM TRUOC (khong doi gi) ---
echo.
if "!TARGET!"=="" (
    "!PY!" -u src\doi_ten_input.py --de-quy
) else (
    "!PY!" -u src\doi_ten_input.py "!TARGET!" --de-quy
)
echo.
choice /c YN /n /m "Doi ten that theo danh sach tren? (Y/N): "
if errorlevel 2 goto MENU
echo.
if "!TARGET!"=="" (
    "!PY!" -u src\doi_ten_input.py --de-quy --that
) else (
    "!PY!" -u src\doi_ten_input.py "!TARGET!" --de-quy --that
)
echo.
pause
goto MENU

:GITSYNC
cls
echo ============================================================
echo              [4] DONG BO GITHUB (GIT SYNC)
echo ============================================================
if not exist "src\git_sync.py" (
    echo [X] Khong tim thay src\git_sync.py
    pause
    goto MENU
)
echo.
set "SYNC_MSG="
set /p SYNC_MSG="Noi dung commit (Enter de dung ngay gio hien tai): "
echo.
if "!SYNC_MSG!"=="" (
    "!PY!" src\git_sync.py sync
) else (
    "!PY!" src\git_sync.py sync -m "!SYNC_MSG!"
)
echo.
pause
goto MENU
