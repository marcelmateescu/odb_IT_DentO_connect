@echo off
:: ========================================================================================
:: 🦷 ODONTO.BOT PMS SYNC CONNECTOR INSTALLER FOR WINDOWS 🦷
:: ========================================================================================
:: Designed & Owned by: S.C. INFORMATICA ECOLOGICA TRANSILVANIA 2004 SRL
:: VAT ID: RO17075938 | Contact: iet2k4@gmail.com
:: ========================================================================================

echo ========================================================================================
echo 🦷 ODONTO.BOT CONNECTOR WINDOWS DEPLOYMENT & DAEMON SETUP 🦷
echo ========================================================================================

:: --- Step 1: Verify Windows Python & Pip environment ---
echo.
echo [Phase 1/4] Verifying Python 3 Environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not added to your system PATH.
    echo 👉 Please download and install Python 3.x from: https://www.python.org/downloads/
    echo 💡 Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
echo    » Python verified.

:: --- Step 2: Install Python Libraries ---
echo.
echo [Phase 2/4] Setting up Python dependencies...
python -m pip install requests --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo ❌ Failed to install requests package. Retrying with --user bypass...
    python -m pip install requests --user --quiet --disable-pip-version-check
)
if %errorlevel% eq 0 (
    echo    » Python 'requests' package installed successfully.
) else (
    echo ⚠️ Warning: Failed to install 'requests' package automatically. Please run: pip install requests
)

:: --- Step 3: Run Verification Local Extraction ---
echo.
echo [Phase 3/4] Executing test extractor & database check...
if exist "%~dp0extractor.py" (
    python "%~dp0extractor.py"
    if %errorlevel% eq 0 (
        echo    » Verification extractor successfully executed!
    ) else (
        echo ⚠️ SQLite extraction/decryption verify completed with warning.
        echo    On Windows, if you need to re-compile the C-based de-obfuscation tool,
        echo    please use WSL (Windows Subsystem for Linux) or MSYS2/MinGW toolchains.
    )
) else (
    echo ⚠️ Warning: extractor.py not found in root directory.
)

:: --- Step 4: Register Windows Task Scheduler Daemon ---
echo.
echo [Phase 4/4] Registering Windows Task Scheduler for hourly synchronization...

:: Remove existing task if it exists
schtasks /delete /tn "OdontoBotSync" /f >nul 2>&1

:: Create the task (runs the sync client in background hourly)
schtasks /create /tn "OdontoBotSync" /tr "python \"%~dp0odontobot_sync_all.py\"" /sc hourly /mo 1 /f
if %errorlevel% eq 0 (
    echo.
    echo 🎉 SUCCESS! Hourly background sync registered in Windows Task Scheduler.
    echo    You can inspect, test, or manage this task in the Windows Task Scheduler UI.
) else (
    echo ❌ Failed to register Task Scheduler daemon automatically.
    echo    👉 Try running this cmd script as Administrator to permit task creation.
)

echo ========================================================================================
echo 🎉 WINDOWS DEPLOYMENT STEPS COMPLETED!
echo ========================================================================================
pause
