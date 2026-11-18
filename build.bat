@echo off
setlocal
cd /d "%~dp0"
rem Нужны: Python 3.12 (только на машине сборки!) и Inno Setup 6 (https://jrsoftware.org/isdl.php)
if not exist .venv ( py -3.12 -m venv .venv || exit /b 1 )
call .venv\Scripts\activate
python -m pip install -U pip || exit /b 1
pip install -r requirements.txt pyinstaller || exit /b 1
pyinstaller --noconfirm --clean isle.spec || exit /b 1
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% ( echo Inno Setup 6 не найден & exit /b 1 )
for /f %%v in ('python -c "from app.version import __version__ as v; print(v)"') do set VER=%%v
%ISCC% /DAppVersion=%VER% installer\isle.iss || exit /b 1
echo.
echo Готово: dist\Isle-Setup-%VER%.exe
