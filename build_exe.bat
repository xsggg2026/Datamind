@echo off
rem Build DataMind single-file exe with PyInstaller.
pyinstaller --noconfirm --onefile --name "DataMind" ^
  --collect-submodules numpy ^
  --collect-submodules pandas ^
  --collect-submodules openpyxl ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  web_portal.py
echo.
echo Output: dist\DataMind.exe
