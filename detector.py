"""Parser del definitions.rpy vanilla de DDLC Mod Template."""
import os
import re
import string
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

# Solo estas dokis serán consideradas (para prioridad en la UI, no excluyente)
DOKIS: Tuple[str, ...] = ("sayori", "natsuki", "yuri", "monika")

# Coincide con: image <doki> <code> = im.Composite(...) para CUALQUIER personaje
PATRON = re.compile(
    r'^\s*image\s+(\w+)\s+(\w+)\s*=\s*im\.Composite\((.*)\)',
    re.IGNORECASE
)

# (tag, pose, expresion)
Definicion = Tuple[str, str, str]


def extraer_definiciones(texto: str) -> List[Definicion]:
    resultados: List[Definicion] = []
    for linea in texto.splitlines():
        # Filtro rápido: si no empieza con "image" lo ignoramos
        if not linea.lstrip().startswith("image"):
            continue
        m = PATRON.match(linea)
        if not m:
            continue
        tag = m.group(1).lower()
        code = m.group(2)
        args = m.group(3)
        strings = re.findall(r'"([^"]+)"', args)
        if not strings:
            continue
        # Solo poses/expresiones reales: el código empieza con dígito.
        # Filtra especiales (mouth, scream, oneeye, eyes, stab_6, ...).
        if not code[0].isdigit():
            continue
        pose = code[0]
        resto = code[1:]
        if resto and resto[0].isalpha():
            expresion = resto
        else:
            ultima = strings[-1]
            expresion = ultima.split('/')[-1].split('.')[0]
        resultados.append((tag, pose, expresion))
    return resultados


def analizar_archivo(ruta: str, contenido: Optional[str] = None) -> Dict[str, Set[Tuple[str, str]]]:
    """Lee `ruta` (o usa `contenido` si se pasa) y extrae definiciones de poses."""
    if contenido is None:
        try:
            with open(ruta, 'r', encoding='utf-8-sig') as f:
                contenido = f.read()
        except UnicodeDecodeError:
            with open(ruta, 'r', encoding='latin-1') as f:
                contenido = f.read()
    definiciones = extraer_definiciones(contenido)
    datos: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
    for tag, pose, expr in definiciones:
        datos[tag].add((pose, expr))
    return datos


def es_cuerpo_heuristico(nombre: str, ruta: str) -> bool:
    r"""True si `nombre` es un sprite de cuerpo completo usable como compuesto.

    Heuristica sin definitions.rpy: empieza con digito, no es un brazo
    (\d+b?[lr]), mide 960x960 y su bbox toca el suelo (y1 ~= 960). Asi se
    excluyen caras (a-z), cabezas (1t/2t*), ojos (blackeyes), efectos
    (glitch*, scream, ghost*, vomit) y sprites pequenos (noface*, ...).
    """
    if not re.fullmatch(r"\d+\w*", nombre) or re.fullmatch(r"\d+b?[lr]", nombre):
        return False
    if not os.path.isfile(ruta):
        return False
    try:
        from PIL import Image
        with Image.open(ruta) as im:
            if im.size != (960, 960):
                return False
            bbox = im.convert("RGBA").getbbox()
            return bool(bbox) and bbox[3] >= 955
    except Exception:
        return False


# capas de un im.Composite que no son brazo (\d+b?[lr]) ni cara simple ([a-z])
# ni cabeza numerada (\d+t[a-z]*). Las demas son candidatas a cuerpo completo.
_PATRON_NO_CUERPO = re.compile(r"(\d+b?[lr]|[a-z]|\d+t[a-z]*)")


def cuerpos_compuestos(texto: str, char_paths: Dict[str, str]) -> Dict[str, Set[str]]:
    """Mapa {doki: sprites de cuerpo completo} a partir de las definiciones del
    definitions.rpy. Para cada `image <doki> <codigo numerico> = im.Composite(...)`:
      - una sola capa -> esa capa es cuerpo (regla del Mod Template: pose 5);
      - varias capas   -> solo las que tocan el suelo (y1 ~= 960), lo que excluye
        caras/cabezas (a, a2, 2t) y los cuerpos de efectos no declarados.
    """
    cuerpos: Dict[str, Set[str]] = defaultdict(set)
    for linea in texto.splitlines():
        if not linea.lstrip().startswith("image"):
            continue
        m = PATRON.match(linea)
        if not m or not m.group(2)[0].isdigit():
            continue
        tag = m.group(1).lower()
        capas = re.findall(r'"([^"]+\.png)"', m.group(3))
        if not capas:
            continue
        if len(capas) == 1:
            cuerpos[tag].add(capas[0].split("/")[-1][:-4])
            continue
        carpeta = char_paths.get(tag)
        for capa in capas:
            nombre = capa.split("/")[-1][:-4]
            if _PATRON_NO_CUERPO.fullmatch(nombre):
                continue
            ruta = os.path.join(carpeta, nombre + ".png") if carpeta else None
            if ruta and es_cuerpo_heuristico(nombre, ruta):
                cuerpos[tag].add(nombre)
    return {k: set(v) for k, v in cuerpos.items()}


# Regla derivada de las definiciones reales: combinacion de brazos -> pose
POZAS: Dict[Tuple[str, str], str] = {
    ("1l", "1r"): "1", ("1l", "2r"): "2", ("2l", "1r"): "3", ("2l", "2r"): "4",
}


def pose_para_brazos(izq: str, der: str) -> str:
    return POZAS.get((izq, der), "5")


def siguiente_nombre(doki: str, pose: str, usados: Set[Tuple[str, str]],
                     cara: str = "") -> str:
    # si se da una cara simple (a-z) y no esta usada, esa es la primera opcion
    if cara and re.fullmatch(r"[a-z]", cara) and (doki, f"{pose}{cara}") not in usados:
        return f"{pose}{cara}"
    for c in string.ascii_lowercase:
        nombre = f"{pose}{c}"
        if (doki, nombre) not in usados:
            return nombre
    i = 1
    while (doki, f"{pose}_{i}") in usados:
        i += 1
    return f"{pose}_{i}"
