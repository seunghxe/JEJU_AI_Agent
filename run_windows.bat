@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  for %%V in (3.12 3.13 3.11) do (
    py -%%V -c "import sys" >nul 2>&1
    if not errorlevel 1 (
      py -%%V -m venv .venv
      goto run
    )
  )
  echo Install Python 3.12 with the Windows Python launcher, then try again.
  pause
  exit /b 1
)
:run
.venv\Scripts\python.exe -c "import sys;sys.exit(not ((3,11) <= sys.version_info[:2] <= (3,13)))"
if errorlevel 1 (
  echo Use Python 3.11-3.13 in a fresh project folder, not the old Python 3.14 environment.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe server.py
if not errorlevel 1 exit /b 0
:failed
pause
exit /b 1
