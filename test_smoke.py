"""Smoke test: construye la UI headless y verifica que no crashea.
No automatiza el event loop de Tk (frágil en CI); solo arranca, actualiza
y destruye. Crea los datos en un directorio temporal."""
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as a
import deteccion


@pytest.fixture
def runtime(tmp_path):
    """Apunta deteccion/app a DATA y RUNTIME temporales con sprites minimos."""
    data = tmp_path / "data"
    runtime = tmp_path / "runtime"
    sayori = data / "images.rpa" / "images" / "sayori"
    yuri = data / "images.rpa" / "images" / "yuri"
    bg = data / "images.rpa" / "images" / "bg"
    for p in (sayori, yuri, bg):
        p.mkdir(parents=True)
    for n in ("1l.png", "1r.png", "a.png"):
        Image.new("RGBA", (960, 960), (255, 0, 0, 255)).save(sayori / n)
    Image.new("RGBA", (960, 960), (0, 255, 0, 255)).save(yuri / "a.png")
    Image.new("RGBA", (1280, 720), (50, 50, 50, 255)).save(bg / "club.png")

    deteccion.DATA_DIR = str(data)
    deteccion.RUNTIME_DIR = str(runtime)
    deteccion.FUENTE_DEFECTO = str(sayori.parent)
    deteccion.IMPORTADOS = str(runtime / "importados")
    deteccion.LOG_PATH = str(runtime / "poselab.log")
    a.CONFIG_PATH = str(runtime / "poselab_config.json")
    a.LANGUAGES_PATH = str(runtime / "languages.json")
    deteccion.setup_logging()
    return runtime


def test_smoke_ui(runtime):
    app = a.DetectorApp()
    app.update_idletasks()
    app.update()
    # primera ejecucion: sin config -> bienvenida de idioma
    assert not hasattr(app, "combo_doki")
    app._elegir_idioma("es")
    app.update_idletasks()
    app.update()
    assert "sayori" in app.combo_doki.cget("values")
    app._on_cerrar()
    assert os.path.exists(a.CONFIG_PATH)
    # segunda ejecucion: idioma guardado -> salta la bienvenida
    app2 = a.DetectorApp()
    app2.update_idletasks()
    app2.update()
    assert hasattr(app2, "combo_doki")
    app2._on_cerrar()
