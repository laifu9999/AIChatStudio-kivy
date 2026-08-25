@echo off
chcp 65001 >nul 2>&1
set PYTHONUTF8=1
set "PY="
cd /d %~dp0

REM ---------- 1. 选定 Python（强制系统 3.10，避开 WorkBuddy 受管 Python 的 pip 拦截 / 3.13 缺 kivy wheel）----------
if exist "C:\Users\uuuu\AppData\Local\Programs\Python\Python310\python.exe" (
    set "PY=C:\Users\uuuu\AppData\Local\Programs\Python\Python310\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) else (
    where py >nul 2>&1 && set "PY=py -3.10"
)
if not defined PY (
    where python >nul 2>&1 && (
        for /f "delims=" %%p in ('where python') do (
            echo %%p | find /i "WindowsApps" >nul || set "PY=%%p"
        )
    )
)
if not defined PY (
    echo [错误] 未找到 Python 3.10。请安装 Python 3.10 并勾选 "Add Python to PATH"。
    pause
    exit /b 1
)

echo 使用 Python: %PY%
%PY% --version

REM ---------- 2. 已装 Kivy 则直接启动；否则建 venv 安装 ----------
%PY% -c "import kivy" >nul 2>&1
if %errorlevel%==0 (
    echo 检测到 Kivy 已安装，启动应用...
    %PY% main.py
    if errorlevel 1 (
        echo.
        echo [应用异常退出，返回码 %ERRORLEVEL%] 上方应有报错信息。
        pause
    )
    exit /b 0
)

IF NOT EXIST venv (
    echo [1/3] 创建虚拟环境...
    %PY% -m venv venv
    if errorlevel 1 (
        echo [失败] 创建虚拟环境出错。
        pause
        exit /b 1
    )
    call venv\Scripts\activate.bat
    echo [2/3] 升级 pip 并安装依赖（首次约 1~3 分钟，请稍候）...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [失败] 依赖安装出错，请查看 run.log 或重试。
        pause
        exit /b 1
    )
) ELSE (
    call venv\Scripts\activate.bat
)

echo [3/3] 启动应用...
python main.py
if errorlevel 1 (
    echo.
    echo [应用异常退出，返回码 %ERRORLEVEL%]
    pause
)
