"""Auto-update: consulta GitHub Releases, descarga el zip de la plataforma
y verifica su checksum. Logica pura, sin UI ni procesos externos."""
import hashlib
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

LOG = logging.getLogger("poselab.updater")

__version__ = "1.0.0"

# TODO: poner el repo real aqui antes de publicar.
GITHUB_API_URL = "https://api.github.com/repos/OWNER/REPO/releases/latest"

_NAMES_PLATAFORMA = {
    "win32": "windows",
    "darwin": "macos",
    "linux": "linux",
}


def parse_semver(v: str) -> Tuple[int, int, int]:
    """'v1.2.3' o '1.2.3' -> (1, 2, 3). Pre-releases (1.2.3-beta) se truncan."""
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", (v or "").strip())
    if not m:
        raise ValueError(f"version semver invalida: {v!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def es_nueva(actual: str, remota: str) -> bool:
    """True si remota > actual (semver). Invalida en actual se trata como 0.0.0."""
    try:
        a = parse_semver(actual)
    except ValueError:
        a = (0, 0, 0)
    try:
        r = parse_semver(remota)
    except ValueError:
        return False
    return r > a


def obtener_release(url_api: str, timeout: int = 10) -> Optional[Dict]:
    """GET a la API de GitHub. Devuelve el dict del release o None si falla."""
    try:
        req = urllib.request.Request(url_api, headers={"User-Agent": "PoseLab-updater"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            json.JSONDecodeError) as e:
        LOG.warning("no se pudo obtener el release desde %s: %s", url_api, e)
        return None


def plataforma_actual() -> str:
    """'windows' | 'macos' | 'linux' segun sys.platform."""
    return _NAMES_PLATAFORMA.get(sys.platform, "windows")


def elegir_asset(assets: List[Dict]) -> Optional[str]:
    """URL de descarga del zip para la plataforma actual, o None."""
    prefijo = f"PoseLab-{plataforma_actual()}.zip"
    for a in assets or []:
        url = a.get("browser_download_url", "")
        if isinstance(url, str) and url.endswith(prefijo):
            return url
    return None


def descargar(url: str, destino: str, timeout: int = 30) -> bool:
    """Descarga `url` a `destino` (streaming, sin cargar todo en memoria)."""
    try:
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "PoseLab-updater"})
        with urllib.request.urlopen(req, timeout=timeout) as resp, \
                open(destino, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        LOG.error("fallo la descarga desde %s: %s", url, e)
        try:
            os.remove(destino)
        except OSError:
            pass
        return False


def leer_sha256(url_sha: str, timeout: int = 10) -> Optional[str]:
    """Descarga el .sha256 y devuelve el hash (primer token de la primera linea)."""
    try:
        req = urllib.request.Request(url_sha, headers={"User-Agent": "PoseLab-updater"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            texto = resp.read().decode("utf-8", "replace")
        m = re.search(r"[0-9a-fA-F]{64}", texto)
        return m.group(0).lower() if m else None
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        LOG.warning("no se pudo obtener sha256 desde %s: %s", url_sha, e)
        return None


def sha256_archivo(ruta: str) -> str:
    """SHA-256 de un archivo local (chunked)."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verificar_sha256(ruta_zip: str, hash_esperado: Optional[str]) -> bool:
    """True si el zip coincide con el hash (o si no hay hash esperado)."""
    if not hash_esperado:
        return True
    return sha256_archivo(ruta_zip) == hash_esperado


# ---------- pendiente (persistencia del update que se aplica al cerrar) ----------

def _url_sha(url_zip: str) -> str:
    """URL del .sha256 a partir de la URL del zip (mismo nombre + .sha256)."""
    return url_zip + ".sha256"


def cargar_pendiente(ruta_pendiente: str) -> Optional[Dict]:
    """Lee _update/pendiente.json (si existe). Devuelve dict o None."""
    try:
        with open(ruta_pendiente, encoding="utf-8") as f:
            datos = json.load(f)
        if isinstance(datos, dict):
            return datos
    except (OSError, json.JSONDecodeError):
        pass
    return None


def guardar_pendiente(ruta_pendiente: str, datos: Dict) -> None:
    """Escribe _update/pendiente.json."""
    try:
        os.makedirs(os.path.dirname(ruta_pendiente), exist_ok=True)
        with open(ruta_pendiente, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except OSError:
        LOG.error("no se pudo guardar el pendiente en %s", ruta_pendiente, exc_info=True)


def preparar_zip_descargado(url_api: str, ruta_pendiente: str, destino_dir: str) -> Optional[Dict]:
    """Flujo completo sin UI: obtiene release, elige asset, descarga y verifica.
    Devuelve el dict pendiente {version, zip, sha, url} listo para aplicar, o None.
    Usado por tests y por el flujo manual."""
    release = obtener_release(url_api)
    if not release:
        return None
    version = release.get("tag_name", "")
    if not es_nueva(__version__, version):
        return None
    url_zip = elegir_asset(release.get("assets") or [])
    if not url_zip:
        LOG.warning("no hay asset para la plataforma %s", plataforma_actual())
        return None
    os.makedirs(destino_dir, exist_ok=True)
    nombre_zip = os.path.basename(url_zip)
    ruta_zip = os.path.join(destino_dir, nombre_zip)
    if not descargar(url_zip, ruta_zip):
        return None
    sha = leer_sha256(_url_sha(url_zip))
    if not verificar_sha256(ruta_zip, sha):
        LOG.error("checksum no coincide para %s", ruta_zip)
        try:
            os.remove(ruta_zip)
        except OSError:
            pass
        return None
    datos = {"version": version, "zip": ruta_zip, "sha": sha, "url": url_zip}
    guardar_pendiente(ruta_pendiente, datos)
    return datos
