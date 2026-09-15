"""Tests de i18n: paridad de claves, interpolacion, merge y fallback."""
import json

import i18n

CLAVES = set(i18n.TEXTOS_BUILTIN["es"].keys())


def test_paridad_claves_entre_idiomas():
    for codigo, tabla in i18n.TEXTOS_BUILTIN.items():
        faltan = CLAVES - set(tabla.keys())
        assert not faltan, f"idioma {codigo} le faltan claves: {faltan}"
        # sin claves extra
        extras = set(tabla.keys()) - CLAVES
        assert not extras, f"idioma {codigo} tiene claves extras: {extras}"


def test_todos_tienen_nombre():
    for codigo, tabla in i18n.TEXTOS_BUILTIN.items():
        assert tabla.get("_nombre"), f"idioma {codigo} sin _nombre"


def test_tr_interpola():
    i18n.cargar_archivo("/no/existe.json")
    i18n.configurar("es")
    s = i18n.tr("info_importado", n=5, ruta="/tmp/x")
    assert "5" in s and "/tmp/x" in s


def test_tr_fallback_a_es():
    i18n.cargar_archivo("/no/existe.json")
    i18n.configurar("xx")  # idioma inexistente -> es
    assert i18n.tr("seccion_fuente") == "Fuente"


def test_merge_con_archivo(tmp_path):
    # idioma nuevo + claves con prioridad sobre built-in
    extra = {"fr": {"_nombre": "Français", "seccion_fuente": "Source"}}
    ruta = tmp_path / "languages.json"
    ruta.write_text(json.dumps(extra), encoding="utf-8")
    i18n.cargar_archivo(str(ruta))
    assert "fr" in i18n.idiomas_disponibles()
    assert i18n.nombre_idioma("fr") == "Français"
    i18n.configurar("fr")
    assert i18n.tr("seccion_fuente") == "Source"
    # clave no definida en fr -> fallback a es
    assert i18n.tr("seccion_personaje") == "Personaje"
    # sobreescribir una clave built-in
    extra2 = {"es": {"seccion_fuente": "Origem"}}
    ruta.write_text(json.dumps(extra2), encoding="utf-8")
    i18n.cargar_archivo(str(ruta))
    i18n.configurar("es")
    assert i18n.tr("seccion_fuente") == "Origem"


def test_generar_plantilla(tmp_path):
    ruta = tmp_path / "languages.json"
    i18n.generar_plantilla(str(ruta))
    assert ruta.exists()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert "es" in datos and "en" in datos and "pt" in datos and "ru" in datos


def test_leer_idioma_config(tmp_path):
    ruta = tmp_path / "cfg.json"
    ruta.write_text(json.dumps({"idioma": "pt"}), encoding="utf-8")
    assert i18n.leer_idioma_config(str(ruta)) == "pt"
    ruta.write_text("{corrupto", encoding="utf-8")
    assert i18n.leer_idioma_config(str(ruta)) is None
    assert i18n.leer_idioma_config(str(tmp_path / "no.json")) is None
