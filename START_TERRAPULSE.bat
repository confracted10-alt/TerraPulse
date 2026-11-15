@echo off
setlocal
cd /d "%~dp0"
title TerraPulse
echo ==========================================
echo             TERRAPULSE
echo ==========================================
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3.12 --version >nul 2>nul
  if %errorlevel%==0 (
    set "PY=py -3.12"
  ) else (
    set "PY=py -3"
  )
) else (
  set "PY=python"
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating a private Python environment...
  %PY% -m venv .venv
  if errorlevel 1 goto python_error
)
echo Installing or checking TerraPulse packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto install_error
echo.
echo Starting TerraPulse at http://localhost:8501
echo Keep this window open while using the website.
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto run_error
goto end
:python_error
echo.
echo Python could not be found. Install Python 3.12 from python.org, then run this file again.
pause
goto end
:install_error
echo.
echo Package installation failed. Check your internet connection and Python version.
pause
goto end
:run_error
echo.
echo TerraPulse stopped with an error. Read the message above.
pause
:end
endlocal
