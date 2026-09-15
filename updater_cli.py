"""Updater externo (compilado con PyInstaller). Reemplaza el binario y _internal
de PoseLab conservando los datos de usuario.

Se ejecuta desde su propia ubicacion (junto a PoseLab.exe), que el zip de
distribucion NO contiene, asi que no colisiona consigo mismo. El zip solo
trae PoseLab.exe + _internal/.

Uso: updater_cli --wait-pid <pid> --zip <zip> --target <dir> --app-path <exe>
"""
import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import time
import zipfile

EXE_EXT = ".exe" if sys.platform == "win32" else ""


def _esperar_proceso(pid: int, timeout: float = 30.0) -> bool:
    """Espera a que el proceso muera. True si murio; False si agoto el timeout."""
    inicio = time.time()
    while time.time() - inicio < timeout:
        if sys.platform == "win32":
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if not handle:
                return True  # el proceso ya no existe
            r = ctypes.windll.kernel32.WaitForSingleObject(handle, 500)
            ctypes.windll.kernel32.CloseHandle(handle)
            if r == 0:  # WAIT_OBJECT_0: termino
                return True
        else:
            try:
                os.kill(pid, 0)
            except OSError:
                return True  # proceso inexistente
            time.sleep(0.3)
    return False


def _relanzar_app(app_path: str) -> None:
    try:
        subprocess.Popen([app_path])
    except OSError as e:
        print(f"no se pudo relanzar la app: {e}", file=sys.stderr)


def _reemplazar(target: str, app_path: str, zip_ruta: str) -> bool:
    """Backup de exe+_internal, extraccion del zip, rollback si falla."""
    nombre_exe = os.path.basename(app_path)
    backup_dir = os.path.join(target, "_backup")
    internal = os.path.join(target, "_internal")

    try:
        os.makedirs(backup_dir, exist_ok=True)
        for origen, nombre in ((app_path, nombre_exe), (internal, "_internal")):
            if os.path.exists(origen):
                destino = os.path.join(backup_dir, nombre)
                if os.path.exists(destino):
                    shutil.rmtree(destino) if os.path.isdir(destino) else os.remove(destino)
                shutil.move(origen, destino)
    except OSError as e:
        print(f"fallo el backup: {e}", file=sys.stderr)
        return False

    try:
        with zipfile.ZipFile(zip_ruta) as z:
            z.extractall(target)
        return True
    except (zipfile.BadZipFile, OSError) as e:
        print(f"fallo la extraccion: {e}", file=sys.stderr)
        for origen, nombre in ((app_path, nombre_exe), (internal, "_internal")):
            destino = os.path.join(backup_dir, nombre)
            if os.path.exists(destino):
                shutil.move(destino, origen)
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--zip", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--app-path", required=True)
    args = parser.parse_args()

    _esperar_proceso(args.wait_pid)
    ok = _reemplazar(args.target, args.app_path, args.zip)
    if ok:
        _relanzar_app(args.app_path)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
