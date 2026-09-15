"""Tests de la logica pura de composicion (sin widgets Tk)."""
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sprites import (
    PANTALLA,
    abrir_imagen,
    componer_sprite,
    construir_escena,
    definicion_image,
    path_capa,
)


@pytest.fixture
def tmp_sprites(tmp_path):
    """Crea un personaje vanilla con brazos y cara, y un mod sin caras."""
    vanilla = tmp_path / "sayori"
    vanilla.mkdir()
    for n in ("1l.png", "1r.png", "a.png"):
        Image.new("RGBA", (960, 960), (255, 0, 0, 255)).save(vanilla / n)
    # un compuesto (cuerpo sin cara) para probar composicion multicapa
    Image.new("RGBA", (960, 960), (0, 0, 255, 255)).save(vanilla / "5.png")
    mod = tmp_path / "ModX"
    mod.mkdir()
    for n in ("1l.png", "1r.png"):
        Image.new("RGBA", (960, 960), (0, 0, 255, 255)).save(mod / n)
    return tmp_path


def test_componer_sprite_brazos_cara(tmp_sprites):
    sp = componer_sprite(
        {"sayori": str(tmp_sprites / "sayori")}, str(tmp_sprites),
        "sayori", "", "1l", "1r", "a", None, (0, 0))
    assert sp.size == (960, 960)
    # la cara roja se ve (opaco)
    assert sp.getbbox() is not None


def test_componer_sprite_offset(tmp_sprites):
    # mod sin caras propias: la cara prestada se desplaza con el offset
    char_paths = {
        "sayori": str(tmp_sprites / "sayori"),
        "ModX": str(tmp_sprites / "ModX"),
    }
    sp0 = componer_sprite(char_paths, str(tmp_sprites), "ModX", "",
                          "1l", "1r", "a", str(tmp_sprites / "sayori"), (0, 0))
    sp1 = componer_sprite(char_paths, str(tmp_sprites), "ModX", "",
                          "1l", "1r", "a", str(tmp_sprites / "sayori"), (-20, -10))
    dif = sum(1 for y in range(0, 960, 4) for x in range(0, 960, 4)
              if sp0.getpixel((x, y)) != sp1.getpixel((x, y)))
    assert dif > 0, "el offset de cara debe desplazar la composicion"


def test_componer_sprite_capa_faltante(tmp_sprites):
    # un brazo que no existe se ignora sin crashear
    sp = componer_sprite(
        {"sayori": str(tmp_sprites / "sayori")}, str(tmp_sprites),
        "sayori", "", "1l", "zzz", "a", None, (0, 0))
    assert sp.size == (960, 960)


def test_componer_sprite_compuesto_solo(tmp_sprites):
    # compuesto sin partes -> solo esa capa (el compuesto, azul)
    sp = componer_sprite(
        {"sayori": str(tmp_sprites / "sayori")}, str(tmp_sprites),
        "sayori", "5", "", "", "", None, (0, 0))
    assert sp.size == (960, 960)
    assert sp.getpixel((100, 100))[3] > 0, "debe verse el compuesto"


def test_componer_sprite_compuesto_con_cara(tmp_sprites):
    # compuesto como base + cara encima -> la cara roja se ve sobre el azul
    char = str(tmp_sprites / "sayori")
    sp_base = componer_sprite({"sayori": char}, str(tmp_sprites),
                              "sayori", "5", "", "", "", None, (0, 0))
    sp_comp = componer_sprite({"sayori": char}, str(tmp_sprites),
                              "sayori", "5", "", "", "a", None, (0, 0))
    dif = sum(1 for y in range(0, 960, 4) for x in range(0, 960, 4)
              if sp_base.getpixel((x, y)) != sp_comp.getpixel((x, y)))
    assert dif > 0, "la cara debe componerse encima del compuesto"


def test_componer_sprite_compuesto_izq_der_cara(tmp_sprites):
    # compuesto + brazo izq + brazo der + cara: todos se apilan sin pisarse
    char = str(tmp_sprites / "sayori")
    sp = componer_sprite({"sayori": char}, str(tmp_sprites),
                         "sayori", "5", "1l", "1r", "a", None, (0, 0))
    assert sp.size == (960, 960)
    # el resultado es opaco en el area del compuesto (sin crashear)
    assert sp.getbbox() is not None


def test_definicion_image_compuesto_con_partes():
    # compuesto + partes extra -> im.Composite real con el compuesto abajo
    assert definicion_image("sayori", "5", "5", "1l", "1r", "a", "sayori") == \
        ('image sayori 5 = im.Composite((960, 960), '
         '(0, 0), "sayori/5.png", (0, 0), "sayori/1l.png", '
         '(0, 0), "sayori/1r.png", (0, 0), "sayori/a.png")')  # noqa: E501


def test_definicion_image_compuesto_con_cara_prestada():
    # cara prestada en un compuesto -> la cara apunta al vanilla
    assert definicion_image("SleepyYuri", "5", "5", "", "", "a",
                            "Sleepy Yuri", "yuri/a.png") == \
        ('image SleepyYuri 5 = im.Composite((960, 960), '
         '(0, 0), "Sleepy Yuri/5.png", (0, 0), "yuri/a.png")')  # noqa: E501


def test_construir_escena(tmp_sprites):
    sprite = abrir_imagen(str(tmp_sprites / "sayori" / "1l.png"))
    escena = construir_escena(sprite, None, lambda n: None, "t42")
    assert escena.size == PANTALLA


def test_path_capa(tmp_sprites):
    vanilla = str(tmp_sprites / "sayori")
    mod = str(tmp_sprites / "ModX")
    # cara prestada -> busca en la carpeta de caras
    p = path_capa({}, str(tmp_sprites), "ModX", "a", vanilla)
    assert os.path.normcase(p).endswith(os.path.normcase("sayori/a.png"))
    # brazo del mod -> carpeta del personaje
    p = path_capa({"ModX": mod}, str(tmp_sprites), "ModX", "1l", None)
    assert os.path.normcase(p).endswith(os.path.normcase("ModX/1l.png"))
