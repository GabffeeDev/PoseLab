import os
import re

from PIL import Image

from detector import (
    PATRON,
    cuerpos_compuestos,
    es_cuerpo_heuristico,
    extraer_definiciones,
    pose_para_brazos,
    siguiente_nombre,
)
from sprites import definicion_image, tag_rpy

RUTA_EJEMPLO = os.path.join(os.path.dirname(__file__), "ejemplos", "definitions.rpy")
IMAGES = os.path.join(os.path.dirname(__file__), "images.rpa", "images")

CHAR_PATHS = {n: os.path.join(IMAGES, n) for n in ("sayori", "natsuki", "yuri", "monika")}


def parsear_composite(linea):
    m = PATRON.match(linea)
    if not m:
        return None
    args = m.group(3)
    caps = re.findall(r'\((-?\d+),\s*(-?\d+)\)\s*,\s*"([^"]+)"', args)
    return [(int(x), int(y), ruta) for x, y, ruta in caps]


def test_extraer_definiciones():
    d = extraer_definiciones(open(RUTA_EJEMPLO, encoding="utf-8").read())

    assert {t for t, _, _ in d} <= {"sayori", "natsuki", "yuri", "monika"}
    especiales = [p for _, p, _ in d if not p[0].isdigit()]
    assert not especiales, f"poses especiales no deben filtrarse: {especiales}"
    assert ("sayori", "1", "a") in d
    assert ("sayori", "1", "ba") in d
    assert ("natsuki", "1", "1t") in d
    assert ("natsuki", "1", "2t") in d
    assert ("yuri", "1", "y1") in d
    assert ("yuri", "4", "a2") in d
    assert not any(e == "n_rects_mouth" for _, _, e in d)


def test_parsear_composite():
    linea = ('image sayori 1a = im.Composite((960, 960), '
             '(0, 0), "sayori/1l.png", (0, 0), "sayori/1r.png", '
             '(0, 0), "sayori/a.png")')
    caps = parsear_composite(linea)
    assert caps == [(0, 0, "sayori/1l.png"), (0, 0, "sayori/1r.png"), (0, 0, "sayori/a.png")], caps
    assert parsear_composite("image black = \"#000000\"") is None


def test_pose_para_brazos():
    assert pose_para_brazos("1l", "1r") == "1"
    assert pose_para_brazos("1l", "2r") == "2"
    assert pose_para_brazos("2l", "1r") == "3"
    assert pose_para_brazos("2l", "2r") == "4"
    assert pose_para_brazos("1bl", "2br") == "5"


def test_siguiente_nombre():
    usados = {("sayori", "1a"), ("sayori", "1b"), ("sayori", "2a")}
    assert siguiente_nombre("sayori", "1", usados) == "1c"
    assert siguiente_nombre("sayori", "2", usados) == "2b"
    todas = {("sayori", f"1{c}") for c in "abcdefghijklmnopqrstuvwxyz"}
    assert siguiente_nombre("sayori", "1", todas) == "1_1"


def test_composicion_pillow():
    a = Image.open(os.path.join(IMAGES, "sayori", "1l.png")).convert("RGBA")
    b = Image.open(os.path.join(IMAGES, "sayori", "a.png")).convert("RGBA")
    img = Image.alpha_composite(a, b)
    assert img.size == (960, 960)


def test_escena_t42():
    a = Image.open(os.path.join(IMAGES, "sayori", "1l.png")).convert("RGBA")
    b = Image.open(os.path.join(IMAGES, "sayori", "a.png")).convert("RGBA")
    img = Image.alpha_composite(a, b)
    escena = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    sprite = img.resize((768, 768), Image.LANCZOS)
    x0, y0, x1, y1 = sprite.getbbox()
    escena.alpha_composite(sprite, (109, -26))
    assert escena.size == (1280, 720)
    px_escena = (109 + (x0 + x1) // 2, max(0, -26 + (y0 + y1) // 2))
    px_sprite = ((x0 + x1) // 2, (y0 + y1) // 2)
    assert escena.getpixel(px_escena) == sprite.getpixel(px_sprite)


def test_tag_rpy():
    assert tag_rpy("Sleepy Yuri") == "SleepyYuri"


def test_definicion_image():
    assert definicion_image("yuri", "1a", "", "1l", "1r", "a", "yuri") == \
        'image yuri 1a = im.Composite((960, 960), (0, 0), "yuri/1l.png", (0, 0), "yuri/1r.png", (0, 0), "yuri/a.png")'  # noqa: E501
    assert definicion_image("SleepyYuri", "1a", "", "1l", "1r", "a", "Sleepy Yuri", "yuri/a.png") == \
        'image SleepyYuri 1a = im.Composite((960, 960), (0, 0), "Sleepy Yuri/1l.png", (0, 0), "Sleepy Yuri/1r.png", (0, 0), "yuri/a.png")'  # noqa: E501
    assert definicion_image("sayori", "5", "5", "", "", "", "sayori") == \
        'image sayori 5 = "sayori/5.png"'  # noqa: E501
    assert definicion_image("sayori", "1a", "", "", "", "a", "sayori") is None


def test_es_cuerpo_heuristico():
    """Distinguir cuerpos reales (pose 5) de caras, cabezas y efectos."""
    base = os.path.join(IMAGES, "sayori")
    # cuerpos: 960x960 y tocan el suelo
    assert es_cuerpo_heuristico("3a", os.path.join(base, "3a.png")) is True
    assert es_cuerpo_heuristico("3d", os.path.join(base, "3d.png")) is True
    # cara simple (a-z) -> no
    assert es_cuerpo_heuristico("a", os.path.join(base, "a.png")) is False
    # brazos -> no
    assert es_cuerpo_heuristico("1l", os.path.join(base, "1l.png")) is False
    # sprite de efecto no-960 (894x894) -> no
    assert es_cuerpo_heuristico("glitch1", os.path.join(base, "glitch1.png")) is False
    # archivo inexistente -> no
    assert es_cuerpo_heuristico("9z", os.path.join(base, "9z.png")) is False


def test_cuerpos_compuestos_definitions():
    """Los compuestos derivados del definitions.rpy real solo son cuerpos."""
    texto = open(RUTA_EJEMPLO, encoding="utf-8").read()
    cuerpos = cuerpos_compuestos(texto, CHAR_PATHS)
    # sayori: pose 5 -> 3a-3d (cuerpos de una sola capa)
    assert cuerpos["sayori"] >= {"3a", "3b", "3c", "3d"}
    assert "1l" not in cuerpos["sayori"] and "a" not in cuerpos["sayori"]
    # natsuki: 3/3b de una capa; cara a y cabezas 1t/2t* no
    assert cuerpos["natsuki"] >= {"3", "3b"}
    assert not ({"a", "1t", "2t", "2ta", "blackeyes", "scream", "vomit"}
                & cuerpos["natsuki"])
    # yuri: 3/3b cuerpos; cara a2 y efectos no declarados quedan fuera
    assert cuerpos["yuri"] >= {"3", "3b"}
    assert not ({"a2", "0a", "cuts", "dragon1", "oneeye"} & cuerpos["yuri"])
    # monika: pose 5 -> 3a/3b
    assert cuerpos["monika"] >= {"3a", "3b"}
