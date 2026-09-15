"""Tests del auto-update: semver, seleccion de asset, descarga y pendiente."""
import json
import os
import threading
import zipfile
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest

import updater


@pytest.fixture
def release_data(tmp_path):
    """Release de GitHub de ejemplo con los 3 assets."""
    return {
        "tag_name": "v2.0.0",
        "assets": [
            {"browser_download_url": "https://x/PoseLab-windows.zip"},
            {"browser_download_url": "https://x/PoseLab-macos.zip"},
            {"browser_download_url": "https://x/PoseLab-linux.zip"},
        ],
    }


def test_parse_semver():
    assert updater.parse_semver("v1.2.3") == (1, 2, 3)
    assert updater.parse_semver("1.2.3") == (1, 2, 3)
    assert updater.parse_semver("1.2.3-beta") == (1, 2, 3)
    with pytest.raises(ValueError):
        updater.parse_semver("abc")


def test_es_nueva():
    assert not updater.es_nueva("1.0.0", "1.0.0")
    assert updater.es_nueva("1.0.0", "1.0.1")
    assert not updater.es_nueva("1.0.1", "1.0.0")
    assert updater.es_nueva("1.0.0", "2.0.0")
    # version actual invalida -> se trata como 0.0.0
    assert updater.es_nueva("invalida", "1.0.0")


def test_elegir_asset_windows(release_data, monkeypatch):
    monkeypatch.setattr(updater.sys, "platform", "win32")
    assert updater.elegir_asset(release_data["assets"]) == "https://x/PoseLab-windows.zip"


def test_elegir_asset_linux(release_data, monkeypatch):
    monkeypatch.setattr(updater.sys, "platform", "linux")
    assert updater.elegir_asset(release_data["assets"]) == "https://x/PoseLab-linux.zip"


def test_elegir_asset_sin_match(release_data):
    release_data["assets"] = [{"browser_download_url": "https://x/otro.zip"}]
    assert updater.elegir_asset(release_data["assets"]) is None


def test_sha256_archivo(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hola")
    assert updater.sha256_archivo(str(f)) == updater.sha256_archivo(str(f))


def _servidor_http(tmp_path):
    """Levanta un HTTP server local sirviendo tmp_path. Devuelve (puerto, stop)."""
    os.chdir(tmp_path)
    handler = SimpleHTTPRequestHandler

    class _Quiet(handler):
        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), _Quiet)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def test_descargar_y_verificar(tmp_path):
    # zip falso con un archivo dentro
    zip_path = tmp_path / "PoseLab-windows.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("_internal/README.txt", "ok")
    # archivo .sha256 junto al zip
    (tmp_path / "PoseLab-windows.zip.sha256").write_text(
        updater.sha256_archivo(str(zip_path)) + "  PoseLab-windows.zip",
        encoding="utf-8")

    server = _servidor_http(tmp_path)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        destino = tmp_path / "descarga" / "PoseLab-windows.zip"
        ok = updater.descargar(f"{base}/PoseLab-windows.zip", str(destino))
        assert ok and destino.exists()
        sha = updater.leer_sha256(f"{base}/PoseLab-windows.zip.sha256")
        assert sha and updater.verificar_sha256(str(destino), sha)
        # checksum incorrecto -> falla
        assert not updater.verificar_sha256(str(destino), "0" * 64)
    finally:
        server.shutdown()


def test_preparar_zip_descargado(tmp_path):
    """Flujo completo contra el servidor local: release + descarga + pendiente."""
    zip_path = tmp_path / "PoseLab-windows.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("_internal/README.txt", "ok")
    (tmp_path / "PoseLab-windows.zip.sha256").write_text(
        updater.sha256_archivo(str(zip_path)) + "  PoseLab-windows.zip",
        encoding="utf-8")

    # simulamos la API con un JSON servido localmente
    api_json = tmp_path / "latest.json"
    api_json.write_text(json.dumps({
        "tag_name": "v9.9.9",
        "assets": [{"browser_download_url": "http://127.0.0.1:1/PoseLab-windows.zip"}],
    }), encoding="utf-8")

    server = _servidor_http(tmp_path)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        # sobrescribir el json con la URL correcta del server
        api_json.write_text(json.dumps({
            "tag_name": "v9.9.9",
            "assets": [{"browser_download_url": f"{base}/PoseLab-windows.zip"}],
        }), encoding="utf-8")
        pend = updater.preparar_zip_descargado(
            f"{base}/latest.json",
            str(tmp_path / "pendiente.json"),
            str(tmp_path / "update"))
        assert pend and pend["version"] == "v9.9.9"
        assert os.path.exists(pend["zip"])
        assert os.path.exists(tmp_path / "pendiente.json")
        assert os.path.exists(tmp_path / "update")
    finally:
        server.shutdown()


def test_preparar_zip_version_igual(tmp_path):
    # la version remota es la misma que la actual -> no hay pendiente
    server = _servidor_http(tmp_path)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        import json as j
        api = tmp_path / "latest.json"
        api.write_text(j.dumps({"tag_name": updater.__version__,
                                "assets": []}), encoding="utf-8")
        pend = updater.preparar_zip_descargado(
            f"{base}/latest.json", str(tmp_path / "pend.json"), str(tmp_path / "up"))
        assert pend is None
    finally:
        server.shutdown()


def test_cargar_guardar_pendiente(tmp_path):
    ruta = tmp_path / "pendiente.json"
    updater.guardar_pendiente(str(ruta), {"version": "v1.0.0", "zip": "/tmp/a.zip"})
    datos = updater.cargar_pendiente(str(ruta))
    assert datos["version"] == "v1.0.0"
    assert updater.cargar_pendiente(str(tmp_path / "no.json")) is None
