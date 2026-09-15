# PoseLab

Herramienta gráfica para armar poses y expresiones de las dokis (Sayori,
Natsuki, Yuri, Monika) y personajes custom de mods DDLC, con preview de
escena real (1280x720, fondo + transform) y generación de `show`s Ren'Py.
Incluye auto-actualización vía GitHub Releases (Windows, macOS, Linux).

## Requisitos

- Python 3.13 (Tkinter incluido).
- Dependencias: `customtkinter` y `pillow`.

Instalación:

    pip install -r requirements.txt

## Ejecución

    python app.py

Atajos: `F5` recarga la interfaz; `Ctrl+C` copia el show; `Ctrl+S` guarda en
armadas.rpy; `Ctrl+rueda` cambia el zoom.

## Idiomas

Al primer arranque aparece un menú para elegir el idioma (Español, English,
Português, Русский). La elección se guarda en `poselab_config.json` y no se
vuelve a preguntar. Para cambiarlo, borra el campo `"idioma"` de esa config.

Los textos viven en `languages.json`, que se genera junto al ejecutable en la
primera ejecución. La comunidad puede editarlo para corregir textos o añadir
idiomas nuevos: cada idioma es un bloque `"codigo": { "_nombre": "...", ... }`.
Los textos que falten en un idioma añadido se muestran en español.

## Cómo funciona

Compone hasta 3 capas (brazo izquierdo, brazo derecho y cara, o un sprite
compuesto) sobre el escenario y genera el `show`:

    show sayori 1a at t42 zorder 2

- **Fuente de sprites**: por defecto `images.rpa/images`. Cualquier subcarpeta
  con PNGs es un personaje seleccionable. "Cambiar fuente" apunta a otra
  carpeta (p. ej. la del mod).
- **Importar personaje**: "Importar" copia una carpeta de PNGs a `importados/`
  como personaje nuevo. Las carpetas nuevas en `importados/` se detectan
  automáticamente (escaneo cada 3 s) con un popup.
- **Fondo** (`bg/*.png`, por defecto `club`): solo para el preview; no afecta
  al `show` generado.
- **Transform**: `t41`-`t44`, `t31`-`t33`, `t21`-`t22`, `t11`.
- **Nombre generado**: la pose se deduce de los brazos (1l+1r→1, 1l+2r→2,
  2l+1r→3, 2l+2r→4) y la expresión es la primera letra libre (`a`, `b`, ...).
- **Cargar .rpy**: "Cargar .rpy" lee un `definitions.rpy` del mod para (a) no
  repetir nombres ya definidos y (b) marcar en rojo/verde si la pose propuesta
  existe como `image` en ese archivo.
- **Definición image**: activando "Incluir definición image" se muestra la
  línea `image <tag> <pose> = ...` lista para pegar en el `definitions.rpy`
  del mod (necesaria si el mod aún no define tu pose custom).
- **Offset de cara**: para mods sin caras propias se prestan las caras vanilla.
  Los botones ◀ ▶ ▲ ▼ (paso ±4) ajustan la alineación y ↺ la resetea. El offset
  inicial se auto-calcula si el cuerpo del mod no incluye cabeza.
- **Agregar a armadas.rpy**: guarda el `show` generado (append) para copiarlo
  después a tu mod.

## Archivos que se escriben

Se guardan junto al proyecto/ejecutable:

- `poselab_config.json` — estado de la interfaz al cerrar.
- `importados/` — personajes importados por el usuario.
- `armadas.rpy` — shows guardados.
- `poselab.log` — registro de eventos (config corrupta, capas faltantes, etc.).

## Tests

    python -m pytest

Cubren el parser (`detector`), la composición Pillow (`sprites`), un smoke
de arranque de la interfaz, la i18n y el auto-update. Lint con `ruff`.

## Auto-actualización

Al arrancar y con el botón "Buscar actualizaciones" (sección Exportar), la
app consulta la última release de GitHub, descarga el zip de su plataforma y
verifica su SHA-256. Al cerrar, `PoseLabUpdater` reemplaza el ejecutable y
`_internal/` conservando los datos de usuario (config, `importados/`,
`armadas.rpy`, `languages.json`, `poselab.log`).

Para publicar una versión:

1. Publica la release en GitHub con los assets `PoseLab-windows.zip`,
   `PoseLab-macos.zip`, `PoseLab-linux.zip` y sus `.sha256`.
2. Configura `GITHUB_API_URL` en `updater.py` (o el campo `updater_url` en
   `poselab_config.json`).
3. La versión se toma del `tag_name` de la release (semver, p. ej. `v1.1.0`).

## Empaquetado (.exe / .app)

- **Windows**: `build.bat` → genera `dist/PoseLab/` (onedir) con `PoseLab.exe`,
  `PoseLabUpdater.exe` y los sprites vanilla; y `dist/PoseLab-windows.zip` +
  `.sha256` listos para subir a GitHub Releases.
- **Linux**: `bash build.sh` → genera `dist/PoseLab/` con el binario `PoseLab`
  y `dist/PoseLab-linux.zip` + `.sha256`.
- **macOS**: `bash build.sh` → genera `dist/PoseLab.app` y
  `dist/PoseLab-macos.zip` + `.sha256`. El ejecutable vive dentro del bundle
  (`Contents/MacOS`), por lo que los archivos escribibles (config,
  `importados/`, `armadas.rpy`, `poselab.log`) se crean junto a `PoseLab.app`
  (en `dist/`), no dentro del bundle.

Requisitos del build en todas las plataformas:
`python3 -m pip install -r requirements.txt pyinstaller`.
