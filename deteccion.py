"""Rutas e infraestructura del runtime: carpetas de datos, config y log.
Sin UI (Tk/customtkinter): el escaneo con popups vive en app.py.
"""
import logging
import os
import sys
from typing import List, Set

LOG = logging.getLogger("poselab.deteccion")


def _data_dir() -> str:
    """Carpeta con datos de solo lectura (sprites vanilla empaquetados).
    En dev es la carpeta del script; bajo PyInstaller onedir es _internal."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _runtime_dir() -> str:
    """Carpeta escribible: config, importados/ y el log.
    En dev es la carpeta del script; bajo el .exe es la carpeta del ejecutable
    (no _MEIPASS, que es temporal). En macOS el ejecutable vive dentro del
    bundle .app/Contents/MacOS: escribir ahi rompe la firma, asi que los
    archivos runtime van junto al .app (dist/)."""
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(sys.executable))))
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DATA_DIR: str = _data_dir()
RUNTIME_DIR: str = _runtime_dir()
FUENTE_DEFECTO: str = os.path.join(DATA_DIR, "images.rpa", "images")
IMPORTADOS: str = os.path.join(RUNTIME_DIR, "importados")
LOG_PATH: str = os.path.join(RUNTIME_DIR, "poselab.log")


def setup_logging():
    """Configura logging a poselab.log junto al ejecutable. Si la carpeta
    runtime no es escribible, cae a salida estandar para no crashear."""
    try:
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        logging.basicConfig(
            filename=LOG_PATH, level=logging.INFO, encoding="utf-8",
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    except OSError:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("poselab").info(
        "PoseLab iniciado (data=%s, runtime=%s)", DATA_DIR, RUNTIME_DIR)


def listar_importados() -> Set[str]:
    """Devuelve el set de carpetas de personajes actualmente en importados/."""
    if not os.path.isdir(IMPORTADOS):
        return set()
    return {n for n in os.listdir(IMPORTADOS)
            if os.path.isdir(os.path.join(IMPORTADOS, n))}


def carpetas_con_pngs(ws: str) -> List[str]:
    """Subcarpetas de `ws` que contienen al menos un .png (excepto bg)."""
    if not os.path.isdir(ws):
        return []
    try:
        return [n for n in os.listdir(ws)
                if n != "bg" and os.path.isdir(os.path.join(ws, n))
                and any(f.endswith(".png") for f in os.listdir(os.path.join(ws, n)))]
    except OSError:
        LOG.warning("no se pudo listar %s", ws, exc_info=True)
        return []
