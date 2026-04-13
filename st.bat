@echo off
REM GoTube Windows Startup Script

setlocal enabledelayedexpansion

REM Get script directory
set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

set "VENV_DIR=%PROJECT_DIR%\venv"
set "PIDFILE=%PROJECT_DIR%\.server.pid"

:usage
echo.
echo GoTube Windows Startup Script
echo ==============================
echo.
echo Usage:
echo   %~nx0          Start dev server (hot-reload)
echo   %~nx0 stop     Stop server
echo   %~nx0 restart  Restart server
echo   %~nx0 status   Check server status
echo.

REM Check parameter
if "%~1"=="stop" goto stop
if "%~1"=="restart" goto restart
if "%~1"=="status" goto status
if "%~1"=="" goto start
echo Unknown parameter: %~1
goto usage

:start
echo Starting GoTube dev server...

REM Check virtual environment
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found: %VENV_DIR%
    echo Please run: python -m venv venv
    echo Then run: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Get port
for /f "tokens=2 delims==" %%a in ('findstr "GOTUBE_PORT" "%PROJECT_DIR%\.env"') do set "PORT=%%a"

REM Check port usage
netstat -ano | findstr ":%PORT% " >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARN] Port %PORT% is already in use
    echo Trying to clean up...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% "') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

REM Clean up残留 PID file
if exist "%PIDFILE%" del /q "%PIDFILE%"

REM Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

REM Change to project directory
cd /d "%PROJECT_DIR%"

echo.
echo Starting uvicorn...
echo Port: %PORT%
echo URL: http://localhost:%PORT%
echo API Docs: http://localhost:%PORT%/docs
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start uvicorn (foreground, show logs)
echo.
echo ========================================
echo   GoTube Server Started
echo   URL: http://localhost:%PORT%
echo   Press Ctrl+C to stop
echo ========================================
echo.

uvicorn server.main:app --host 0.0.0.0 --port %PORT% --reload --log-level info

goto end

:stop
echo Stopping server...

REM Clean up all processes on port
for /f "tokens=2 delims==" %%a in ('findstr "GOTUBE_PORT" "%PROJECT_DIR%\.env"') do set "PORT=%%a"

netstat -ano | findstr ":%PORT% " >nul 2>&1
if %errorlevel% equ 0 (
    echo Found processes on port %PORT%, cleaning up...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% "') do (
        taskkill /F /PID %%a >nul 2>&1
        echo Terminated PID %%a
    )
    echo Server stopped
) else (
    echo Server is not running
)

REM Clean up PID file
if exist "%PIDFILE%" del /q "%PIDFILE%"
goto end

:restart
echo Restarting server...
call "%~dp0%~nx0" stop
timeout /t 2 /nobreak >nul
call "%~dp0%~nx0" start
goto end

:status
REM Check server status
for /f "tokens=2 delims==" %%a in ('findstr "GOTUBE_PORT" "%PROJECT_DIR%\.env"') do set "PORT=%%a"

netstat -ano | findstr ":%PORT% " >nul 2>&1
if %errorlevel% equ 0 (
    echo Server is running
    echo URL: http://localhost:%PORT%
    echo API Docs: http://localhost:%PORT%/docs
) else (
    echo Server is not running
)
goto end

:end
echo.
endlocal
