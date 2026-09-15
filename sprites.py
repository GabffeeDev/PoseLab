"""Composicion y render de sprites y escenas.
Contiene la logica pura de armado de la imagen (sin widgets Tk).
"""
import os
import re
from typing import Callable, Optional, Tuple

from PIL import Image, ImageTk

PANTALLA: Tuple[int, int] = (1280, 720)
ZOOM: float = 0.80
Y_ANCLA: float = 1.03
ZOOM_MIN: float = 1.0
ZOOM_MAX: float = 3.0
ZOOM_PASO: float = 0.2

TRANSFORMS: list[tuple[str, int]] = [
    ("t41", 200), ("t42", 493), ("t43", 786), ("t44", 1080),
    ("t31", 240), ("t32", 640), ("t33", 1040),
    ("t21", 400), ("t22", 880), ("t11", 640),
]
TRANS_NOMBRES: list[str] = [t for t, _ in TRANSFORMS]
TRANS_DICT: dict[str, int] = dict(TRANSFORMS)


def abrir_imagen(ruta: str) -> Image.Image:
    """Abre una imagen y la convierte a RGBA."""
    with Image.open(ruta) as im:
        return im.convert("RGBA")


def path_capa(char_paths: dict, fuente: str, doki: str, nombre: str,
              cara_folder: Optional[str]) -> str:
    """Devuelve la ruta del PNG a componer para `nombre` (brazo, cara, compuesto).
    Las caras a-z se buscan primero en cara_folder (carpeta de caras prestadas)."""
    if re.fullmatch(r"[a-z]", nombre) and cara_folder:
        return os.path.join(cara_folder, f"{nombre}.png")
    carpeta = char_paths.get(doki, fuente)
    return os.path.join(carpeta, f"{nombre}.png")


def componer_sprite(char_paths: dict, fuente: str, doki_actual: str,
                    compuesto: str, izq: str, der: str, cara: str,
                    cara_folder: Optional[str], cara_offset: Tuple[int, int],
                    capa_cache: Optional[dict] = None) -> Image.Image:
    """Compone las partes del sprite en una imagen 960x960 RGBA.
    Si cara_offset no es (0,0) y la parte es una cara prestada, aplica el offset.
    Con compuesto, este va como capa base y los brazos/cara encima.
    capa_cache (dict ruta->Image) evita releer los PNGs del disco en cada preview."""
    partes = ([compuesto] if compuesto else []) + [izq, der, cara]
    imagen = Image.new("RGBA", (960, 960), (0, 0, 0, 0))
    for parte in partes:
        if not parte:
            continue
        ruta = path_capa(char_paths, fuente, doki_actual, parte, cara_folder)
        if capa_cache is not None and ruta in capa_cache:
            capa = capa_cache[ruta]
        else:
            try:
                capa = abrir_imagen(ruta)
            except Exception:
                continue
            if capa_cache is not None:
                capa_cache[ruta] = capa
        if capa.size != (960, 960):
            capa = capa.resize((960, 960), Image.LANCZOS)
        # cara prestada: aplicar offset para alinear con la cabeza del mod
        if (re.fullmatch(r"[a-z]", parte) and cara_folder
                and cara_offset != (0, 0)):
            ox, oy = cara_offset
            base = Image.new("RGBA", (960, 960), (0, 0, 0, 0))
            base.paste(capa, (ox, oy))
            capa = base
        imagen = Image.alpha_composite(imagen, capa)
    return imagen


def construir_escena(sprite: Image.Image, fondo_nombre: Optional[str],
                     cargar_fondo: Callable, transform: str) -> Image.Image:
    """Compone el sprite sobre el fondo y lo posiciona segun el transform."""
    escena = Image.new("RGBA", PANTALLA, (0, 0, 0, 0))
    if fondo_nombre and fondo_nombre != "-":
        img = cargar_fondo(fondo_nombre)
        if img:
            if img.size != PANTALLA:
                img = img.resize(PANTALLA, Image.LANCZOS)
            escena = Image.alpha_composite(escena, img)
    ancho = alto = int(960 * ZOOM)
    sprite = sprite.resize((ancho, alto), Image.LANCZOS)
    xcenter = TRANS_DICT.get(transform, 493)
    x = int(xcenter - ancho / 2)
    y = int(720 * Y_ANCLA - alto)
    escena.alpha_composite(sprite, (x, y))
    return escena


def dibujar_preview(canvas, escena: Optional[Image.Image], ancho: int,
                    alto: int, zoom: float, sel_prev, cache_clave,
                    cache_photo, offset: Tuple[int, int] = (0, 0)):
    """Redibuja el preview en el canvas con desplazamiento `offset` (pan).
    Retorna (cache_clave, cache_photo). La clave de cache NO incluye el
    offset: si la imagen no cambio (misma escena/escala), solo se mueve el
    item del canvas (pan fluido sin re-renderizar)."""
    escala = min(ancho / PANTALLA[0], alto / PANTALLA[1]) * zoom
    img_clave = (sel_prev, round(escala, 4))
    x = ancho // 2 + offset[0]
    y = alto // 2 + offset[1]
    if cache_clave == img_clave and cache_photo is not None:
        # la imagen ya esta en el canvas: moverla sin redibujar
        for item in canvas.find_withtag("preview"):
            canvas.coords(item, x, y)
        return cache_clave, cache_photo
    if escena is None:
        return None, None
    red = escena.resize(
        (max(1, int(PANTALLA[0] * escala)), max(1, int(PANTALLA[1] * escala))),
        Image.LANCZOS
    )
    foto = ImageTk.PhotoImage(red)
    canvas.delete("all")
    canvas.create_image(x, y, image=foto, tags="preview")
    return img_clave, foto


def tag_rpy(nombre: str) -> str:
    """Tag de Ren'Py: sin espacios (un tag de image no admite espacios)."""
    return nombre.replace(" ", "")


def definicion_image(tag: str, nombre_pose: str, compuesto: str, izq: str,
                     der: str, cara: str, carpeta: str,
                     cara_ruta: Optional[str] = None) -> Optional[str]:
    """Genera la linea `image <tag> <pose> = ...` del definitions.rpy del mod.
    Devuelve None si no hay pose valida. `carpeta` es el nombre real de la
    carpeta del personaje (con espacios, va en las rutas de archivo); `tag` es
    el nombre sin espacios (va en el tag). Si la cara es prestada (mod sin
    caras propias), pasar cara_ruta con la ruta del vanilla (ej. 'yuri/a.png').
    El offset manual de cara no es representable en im.Composite."""
    if compuesto:
        if not (izq or der or cara):
            return f'image {tag} {nombre_pose} = "{carpeta}/{nombre_pose}.png"'
        capas = [f'(0, 0), "{carpeta}/{compuesto}.png"']
        for parte in (izq, der):
            if parte:
                capas.append(f'(0, 0), "{carpeta}/{parte}.png"')
        if cara:
            ruta_cara = cara_ruta or f"{carpeta}/{cara}.png"
            capas.append(f'(0, 0), "{ruta_cara}"')
        return f"image {tag} {nombre_pose} = im.Composite((960, 960), {', '.join(capas)})"
    if not (izq and der and cara):
        return None
    if not cara_ruta:
        cara_ruta = f"{carpeta}/{cara}.png"
    capas = (
        f"(0, 0), \"{carpeta}/{izq}.png\", "
        f"(0, 0), \"{carpeta}/{der}.png\", "
        f"(0, 0), \"{cara_ruta}\""
    )
    return f"image {tag} {nombre_pose} = im.Composite((960, 960), {capas})"
