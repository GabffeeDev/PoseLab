#!/usr/bin/env bash
# Build PoseLab onedir + PoseLabUpdater (macOS/Linux)
# Requisitos: python3 -m pip install -r requirements.txt pyinstaller
# Salida:
#   macOS  -> dist/PoseLab.app (bundle; el updater va junto a el en dist/)
#   Linux  -> dist/PoseLab/PoseLab (carpeta portable)
#   dist/PoseLab-<plataforma>.zip + .sha256 -> artefacto para GitHub Releases

set -e

python3 -m pip install -r requirements.txt pyinstaller

SEP=":"

pyinstaller --noconfirm --onedir --windowed --name PoseLab \
    --add-data "images.rpa${SEP}images.rpa" \
    --add-data "ejemplos${SEP}ejemplos" \
    --hidden-import customtkinter \
    app.py

pyinstaller --noconfirm --onedir --console --name PoseLabUpdater \
    --contents-directory updater_lib \
    updater_cli.py

# fusionar el updater dentro de dist/PoseLab/ (Linux)
cp dist/PoseLabUpdater/PoseLabUpdater dist/PoseLab/
rm -rf dist/PoseLab/updater_lib
cp -r dist/PoseLabUpdater/updater_lib dist/PoseLab/updater_lib
rm -rf dist/PoseLabUpdater

# macOS: el bundle es PoseLab.app; el updater y el zip van junto a el
if [[ -d dist/PoseLab.app ]]; then
    cp dist/PoseLab/PoseLabUpdater dist/
    cp -r dist/PoseLab/updater_lib dist/updater_lib
    # zip de distribucion desde el contenido del bundle (exe + _internal)
    (cd dist/PoseLab.app/Contents && zip -r ../../PoseLab-macos.zip MacOS _internal)
    # conservar el updater junto al .app para el runtime dir
    rm -rf dist/PoseLab
else
    (cd dist && zip -r PoseLab-linux.zip PoseLab)
fi

sha256sum dist/PoseLab-*.zip > dist/PoseLab-*.zip.sha256 || true

echo "Build completado en dist/"
