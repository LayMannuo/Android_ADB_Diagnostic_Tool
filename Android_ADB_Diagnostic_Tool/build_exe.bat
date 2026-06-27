@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Creating virtual environment...
if not exist .venv (
  py -3.11 -m venv .venv
  if errorlevel 1 py -3 -m venv .venv
)

echo [2/4] Installing dependencies...
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\pip.exe install -r requirements.txt

echo [3/4] Building executable...
call .venv\Scripts\python.exe -m PyInstaller ^
  --noconfirm ^
  --windowed ^
  --onefile ^
  --name Android_ADB_Diagnostic_Tool ^
  --add-data "app\config;app\config" ^
  --add-data "app\assets;app\assets" ^
  --add-data "tools\adb;tools\adb" ^
  --add-data "tools\scrcpy;tools\scrcpy" ^
  --hidden-import apkutils2 ^
  --hidden-import cigam ^
  --hidden-import xmltodict ^
  --hidden-import elftools ^
  --version-file version_info.txt ^
  main.py

echo [4/4] Done.
echo EXE path: %cd%\dist\Android_ADB_Diagnostic_Tool.exe
pause
