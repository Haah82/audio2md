@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title GitHub Project Manager

REM ===================================================
REM CẤU HÌNH THÔNG TIN CÁ NHÂN (BẠN SỬA Ở ĐÂY)
REM ===================================================
set "GITHUB_USER=Haah82"
set "DEFAULT_BRANCH=main"

:MENU
cls
echo ===================================================
echo        QUAN LY DU AN GITHUB (PRIVATE REPO)
echo ===================================================
echo  Tai khoan Git: %GITHUB_USER%
echo  Thu muc hien tai: %CD%
echo ---------------------------------------------------
echo  [1] Khoi tao va Push du an moi len GitHub (Lan dau)
echo  [2] Pull code tu GitHub ve (An toan voi Stash)
echo  [3] Push ban cap nhat len GitHub (Update)
echo  [0] Thoat
echo ===================================================
set "choice="
set /p choice="Chon thao tac (0-3): "

if /i "!choice!"=="0" exit
if /i "!choice!"=="1" goto PUSH_NEW
if /i "!choice!"=="2" goto PULL_SAFE
if /i "!choice!"=="3" goto PUSH_UPDATE
goto MENU

REM ===================================================
REM 1. KHỞI TẠO VÀ PUSH DỰ ÁN MỚI
REM ===================================================
:PUSH_NEW
echo.
echo --- 1. KHOI TAO VA PUSH DU AN MOI ---
if exist ".git" (
    echo [!] Thu muc nay da duoc khoi tao Git- .git da ton tai.
    set /p tieptuc="Ban co muon xoa .git cu de lam lai tu dau khong? (Y/N): "
    if /i "!tieptuc!"=="Y" (
        rmdir /S /Q .git
        echo [+] Da xoa .git cu.
    ) else (
        echo [-] Huy thao tac.
        pause
        goto MENU
    )
)

set "REPO_NAME="
set /p REPO_NAME="Nhap ten du an tren GitHub (VD: name-of-project): "
if "!REPO_NAME!"=="" (
    echo [X] Ten du an khong duoc de trong!
    pause
    goto MENU
)

set "REPO_URL=https://github.com/%GITHUB_USER%/!REPO_NAME!.git"
echo [+] Dang thiet lap ket noi toi: !REPO_URL!

git init
git add .
git commit -m "Initial commit"
git branch -M %DEFAULT_BRANCH%
git remote add origin !REPO_URL!
git push -u origin %DEFAULT_BRANCH%

echo.
echo [OK] Da day du an moi len GitHub thanh cong!
pause
goto MENU

REM ===================================================
REM 2. PULL DỰ ÁN AN TOÀN (STASH -> PULL -> STASH POP)
REM ===================================================
:PULL_SAFE
echo.
echo --- 2. PULL CODE AN TOAN TUK GITHUB ---
if not exist ".git" (
    echo [X] Day chua phai la mot Git repository ^(Chua co .git^).
    pause
    goto MENU
)

echo [+] Dang cat tam thay doi hien tai (git stash)...
git stash

echo [+] Dang keo code moi nhat ve (git pull)...
git pull origin %DEFAULT_BRANCH%

echo [+] Dang khoi phuc thay doi cua ban (git stash pop)...
git stash pop

echo.
echo [OK] Da cap nhat code thanh cong! Kiem tra lai xem co conflict khong nhe.
pause
goto MENU

REM ===================================================
REM 3. PUSH CẬP NHẬT (UPDATE)
REM ===================================================
:PUSH_UPDATE
echo.
echo --- 3. PUSH BAN CAP NHAT (UPDATE) ---
if not exist ".git" (
    echo [X] Day chua phai la mot Git repository ^(Chua co .git^).
    pause
    goto MENU
)

git add .
echo [+] Da add toan bo thay doi.

set "COMMIT_MSG="
set /p COMMIT_MSG="Nhap noi dung ghi chu commit (Enter de dung thoi gian hien tai): "

if "!COMMIT_MSG!"=="" (
    set "COMMIT_MSG=Update: %DATE% %TIME%"
)

git commit -m "!COMMIT_MSG!"
git push origin %DEFAULT_BRANCH%

echo.
echo [OK] Da push cap nhat len GitHub thanh cong!
pause
goto MENU