@echo off
REM Build PoseLab como .exe onedir + PoseLabUpdater (Windows)
REM Requisitos: python -m pip install -r requirements.txt pyinstaller
REM Salida:
REM   dist\PoseLab\         -> carpeta portable con PoseLab.exe + PoseLabUpdater.exe
REM   dist\PoseLab-windows.zip + .sha256   -> artefacto para GitHub Releases

if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install -r requirements.txt pyinstaller

REM 1) app principal (onedir, windowed)
pyinstaller --noconfirm --onedir --windowed --name PoseLab ^
    --add-data "images.rpa;images.rpa" ^
    --add-data "ejemplos;ejemplos" ^
    --hidden-import customtkinter ^
    app.py

REM 2) updater externo (onedir, console). Runtime en updater_lib\ para
REM    no colisionar con el _internal del principal.
pyinstaller --noconfirm --onedir --console --name PoseLabUpdater ^
    --contents-directory updater_lib ^
    updater_cli.py

REM 3) fusionar el updater dentro de dist\PoseLab\
copy /y dist\PoseLabUpdater\PoseLabUpdater.exe dist\PoseLab\ >nul
if exist dist\PoseLab\updater_lib rmdir /s /q dist\PoseLab\updater_lib
xcopy /e /y /q dist\PoseLabUpdater\updater_lib dist\PoseLab\updater_lib >nul
rmdir /s /q dist\PoseLabUpdater

REM 4) zip de distribucion (solo programa, sin datos de usuario)
if exist dist\PoseLab-windows.zip del dist\PoseLab-windows.zip
powershell -NoProfile -Command "Compress-Archive -Path 'dist\PoseLab\*' -DestinationPath 'dist\PoseLab-windows.zip' -Force"
certutil -hashfile dist\PoseLab-windows.zip SHA256 | findstr /v "hash" | findstr /v "^$" > dist\PoseLab-windows.zip.sha256
type dist\PoseLab-windows.zip.sha256 > nul

echo.
echo Build completado. Carpeta portable: dist\PoseLab\
echo Artefacto: dist\PoseLab-windows.zip (+ .sha256)
pause
