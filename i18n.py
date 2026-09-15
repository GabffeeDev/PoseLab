"""Internacionalizacion (i18n): textos por idioma.
Los 4 idiomas base (es, en, pt, ru) estan embebidos. En el runtime dir se
genera languages.json (si no existe) que la comunidad puede editar para
corregir textos o anadir idiomas nuevos. El archivo hace merge sobre los
built-in: claves con prioridad, idiomas nuevos se suman, faltantes -> es.
"""
import json
import logging
import os
from typing import Dict, List, Optional

LOG = logging.getLogger("poselab.i18n")

IDIOMA_DEFECTO = "es"

TEXTOS_BUILTIN: Dict[str, Dict[str, str]] = {
    "es": {
        "_nombre": "Español",
        "bienvenida_titulo": "Select your language",
        "seccion_fuente": "Fuente",
        "seccion_personaje": "Personaje",
        "seccion_componentes": "Componentes",
        "seccion_escena": "Escena",
        "seccion_exportar": "Exportar",
        "selector_brazo_izq": "Brazo izq",
        "selector_brazo_der": "Brazo der",
        "selector_cara": "Cara",
        "selector_compuesto": "Compuesto",
        "selector_offset": "Offset cara:",
        "btn_reset": "Reset pose",
        "btn_atajos": "Atajos",
        "atajos_titulo": "Atajos de teclado",
        "atajo_recargar": "Recargar interfaz",
        "atajo_copiar_show": "Copiar show",
        "atajo_zoom": "Acercar / alejar",
        "atajo_pan": "Desplazar imagen (con zoom)",
        "atajos_cerrar": "Cerrar",
        "selector_fondo": "Fondo:",
        "selector_transform": "Transform:",
        "selector_zoom": "Zoom:",
        "btn_importar": "Importar",
        "btn_fuente": "Fuente",
        "btn_copiar_show": "Copiar show",
        "btn_copiar_def": "Copiar definición",
        "tooltip_copiar_show": "Copiar",
        "tooltip_copiar_def": "Copiar",
        "btn_incluir_def": "Incluir definición image",
        "btn_cargar_rpy": "Cargar definitions.rpy",
        "btn_buscar_update": "Buscar actualizaciones",
        "no_hay_actualizaciones": "Ya tienes la última versión.",
        "update_pendiente": "Actualización descargada. Se aplicará al cerrar la aplicación.",
        "error_update": "No se pudo comprobar actualizaciones. Revisa tu conexión.",
        "lbl_nombre": "Nombre:",
        "lbl_codigo": "Código:",
        "lbl_definicion": "Definición:",
        "estado_definido": "[OK] definido en el .rpy cargado",
        "estado_no_definido": "[!] no existe como image en el .rpy cargado",
        "doki_vacio": "-",
        "titulo_dialog_importar": "Seleccionar carpeta con PNGs del personaje",
        "titulo_dialog_fuente": "Seleccionar carpeta de sprites (images)",
        "titulo_dialog_rpy": "Seleccionar definitions.rpy",
        "tipo_rpy": "Ren'Py files",
        "tipo_todos": "Todos los archivos",
        "error": "Error",
        "error_sin_pngs": "La carpeta no contiene PNGs.",
        "error_nombre_invalido": "Nombre de carpeta no válido.",
        "error_leer_rpy": "No se pudo leer el archivo:\n{detalle}",
        "error_carpeta_sprites": "No se encontró la carpeta de sprites:\n{ruta}",
        "info_importado": "{n} PNGs copiados a:\n{ruta}",
        "reload_recargando": "Recargando interfaz...",
        "import_nuevos": "Nuevos assets detectados, importando...",
        "import_eliminado": "El asset se ha eliminado",
        "faltan_deps": "Falta una dependencia necesaria:\n{detalle}\n\nEjecuta: pip install -r requirements.txt",
        "config_corrupta": "El archivo de configuración no se pudo leer y será ignorado.\n{ruta}\n\nRevisa poselab.log para más detalle.",  # noqa: E501
    },
    "en": {
        "_nombre": "English",
        "bienvenida_titulo": "Select your language",
        "seccion_fuente": "Source",
        "seccion_personaje": "Character",
        "seccion_componentes": "Components",
        "seccion_escena": "Scene",
        "seccion_exportar": "Export",
        "selector_brazo_izq": "Left arm",
        "selector_brazo_der": "Right arm",
        "selector_cara": "Face",
        "selector_compuesto": "Composite",
        "selector_offset": "Face offset:",
        "btn_reset": "Reset pose",
        "btn_atajos": "Shortcuts",
        "atajos_titulo": "Keyboard shortcuts",
        "atajo_recargar": "Reload interface",
        "atajo_copiar_show": "Copy show",
        "atajo_zoom": "Zoom in / out",
        "atajo_pan": "Pan image (with zoom)",
        "atajos_cerrar": "Close",
        "selector_fondo": "Background:",
        "selector_transform": "Transform:",
        "selector_zoom": "Zoom:",
        "btn_importar": "Import",
        "btn_fuente": "Source",
        "btn_copiar_show": "Copy show",
        "btn_copiar_def": "Copy definition",
        "tooltip_copiar_show": "Copy",
        "tooltip_copiar_def": "Copy",
        "btn_incluir_def": "Include image definition",
        "btn_cargar_rpy": "Load definitions.rpy",
        "btn_buscar_update": "Check for updates",
        "no_hay_actualizaciones": "You already have the latest version.",
        "update_pendiente": "Update downloaded. It will be applied when you close the app.",
        "error_update": "Could not check for updates. Check your connection.",
        "lbl_nombre": "Name:",
        "lbl_codigo": "Code:",
        "lbl_definicion": "Definition:",
        "estado_definido": "[OK] defined in the loaded .rpy",
        "estado_no_definido": "[!] does not exist as image in the loaded .rpy",
        "doki_vacio": "-",
        "titulo_dialog_importar": "Select folder with character PNGs",
        "titulo_dialog_fuente": "Select sprites folder (images)",
        "titulo_dialog_rpy": "Select definitions.rpy",
        "tipo_rpy": "Ren'Py files",
        "tipo_todos": "All files",
        "error": "Error",
        "error_sin_pngs": "The folder does not contain PNGs.",
        "error_nombre_invalido": "Invalid folder name.",
        "error_leer_rpy": "Could not read the file:\n{detalle}",
        "error_carpeta_sprites": "Sprites folder not found:\n{ruta}",
        "info_importado": "{n} PNGs copied to:\n{ruta}",
        "reload_recargando": "Reloading interface...",
        "import_nuevos": "New assets detected, importing...",
        "import_eliminado": "The asset has been removed",
        "faltan_deps": "A required dependency is missing:\n{detalle}\n\nRun: pip install -r requirements.txt",
        "config_corrupta": "The configuration file could not be read and will be ignored.\n{ruta}\n\nCheck poselab.log for details.",  # noqa: E501
    },
    "pt": {
        "_nombre": "Português",
        "bienvenida_titulo": "Select your language",
        "seccion_fuente": "Fonte",
        "seccion_personaje": "Personagem",
        "seccion_componentes": "Componentes",
        "seccion_escena": "Cena",
        "seccion_exportar": "Exportar",
        "selector_brazo_izq": "Braço esq",
        "selector_brazo_der": "Braço dir",
        "selector_cara": "Rosto",
        "selector_compuesto": "Composto",
        "selector_offset": "Offset do rosto:",
        "btn_reset": "Redefinir pose",
        "btn_atajos": "Atalhos",
        "atajos_titulo": "Atalhos de teclado",
        "atajo_recargar": "Recarregar interface",
        "atajo_copiar_show": "Copiar show",
        "atajo_zoom": "Ampliar / reduzir",
        "atajo_pan": "Mover imagem (com zoom)",
        "atajos_cerrar": "Fechar",
        "selector_fondo": "Fundo:",
        "selector_transform": "Transform:",
        "selector_zoom": "Zoom:",
        "btn_importar": "Importar",
        "btn_fuente": "Fonte",
        "btn_copiar_show": "Copiar show",
        "btn_copiar_def": "Copiar definição",
        "tooltip_copiar_show": "Copiar",
        "tooltip_copiar_def": "Copiar",
        "btn_incluir_def": "Incluir definição image",
        "btn_cargar_rpy": "Carregar definitions.rpy",
        "btn_buscar_update": "Verificar atualizações",
        "no_hay_actualizaciones": "Você já tem a versão mais recente.",
        "update_pendiente": "Atualização baixada. Será aplicada ao fechar o aplicativo.",
        "error_update": "Não foi possível verificar atualizações. Verifique sua conexão.",
        "lbl_nombre": "Nome:",
        "lbl_codigo": "Código:",
        "lbl_definicion": "Definição:",
        "estado_definido": "[OK] definido no .rpy carregado",
        "estado_no_definido": "[!] não existe como image no .rpy carregado",
        "doki_vacio": "-",
        "titulo_dialog_importar": "Selecionar pasta com PNGs do personagem",
        "titulo_dialog_fuente": "Selecionar pasta de sprites (images)",
        "titulo_dialog_rpy": "Selecionar definitions.rpy",
        "tipo_rpy": "Arquivos Ren'Py",
        "tipo_todos": "Todos os arquivos",
        "error": "Erro",
        "error_sin_pngs": "A pasta não contém PNGs.",
        "error_nombre_invalido": "Nome de pasta inválido.",
        "error_leer_rpy": "Não foi possível ler o arquivo:\n{detalle}",
        "error_carpeta_sprites": "Pasta de sprites não encontrada:\n{ruta}",
        "info_importado": "{n} PNGs copiados para:\n{ruta}",
        "reload_recargando": "Recarregando interface...",
        "import_nuevos": "Novos assets detectados, importando...",
        "import_eliminado": "O asset foi removido",
        "faltan_deps": "Falta uma dependência necessária:\n{detalle}\n\nExecute: pip install -r requirements.txt",
        "config_corrupta": "O arquivo de configuração não pôde ser lido e será ignorado.\n{ruta}\n\nVerifique poselab.log para detalhes.",  # noqa: E501
    },
    "ru": {
        "_nombre": "Русский",
        "bienvenida_titulo": "Select your language",
        "seccion_fuente": "Источник",
        "seccion_personaje": "Персонаж",
        "seccion_componentes": "Компоненты",
        "seccion_escena": "Сцена",
        "seccion_exportar": "Экспорт",
        "selector_brazo_izq": "Левая рука",
        "selector_brazo_der": "Правая рука",
        "selector_cara": "Лицо",
        "selector_compuesto": "Композит",
        "selector_offset": "Смещение лица:",
        "btn_reset": "Сброс позы",
        "btn_atajos": "Горячие клавиши",
        "atajos_titulo": "Горячие клавиши",
        "atajo_recargar": "Перезагрузить интерфейс",
        "atajo_copiar_show": "Копировать show",
        "atajo_zoom": "Приблизить / отдалить",
        "atajo_pan": "Сдвиг изображения (с зумом)",
        "atajos_cerrar": "Закрыть",
        "selector_fondo": "Фон:",
        "selector_transform": "Transform:",
        "selector_zoom": "Zoom:",
        "btn_importar": "Импорт",
        "btn_fuente": "Источник",
        "btn_copiar_show": "Копировать show",
        "btn_copiar_def": "Копировать определение",
        "tooltip_copiar_show": "Копировать",
        "tooltip_copiar_def": "Копировать",
        "btn_incluir_def": "Включить определение image",
        "btn_cargar_rpy": "Загрузить definitions.rpy",
        "btn_buscar_update": "Проверить обновления",
        "no_hay_actualizaciones": "У вас уже последняя версия.",
        "update_pendiente": "Обновление загружено. Оно применится при закрытии приложения.",
        "error_update": "Не удалось проверить обновления. Проверьте соединение.",
        "lbl_nombre": "Имя:",
        "lbl_codigo": "Код:",
        "lbl_definicion": "Определение:",
        "estado_definido": "[OK] определено в загруженном .rpy",
        "estado_no_definido": "[!] не существует как image в загруженном .rpy",
        "doki_vacio": "-",
        "titulo_dialog_importar": "Выберите папку с PNG персонажа",
        "titulo_dialog_fuente": "Выберите папку спрайтов (images)",
        "titulo_dialog_rpy": "Выберите definitions.rpy",
        "tipo_rpy": "Файлы Ren'Py",
        "tipo_todos": "Все файлы",
        "error": "Ошибка",
        "error_sin_pngs": "В папке нет PNG.",
        "error_nombre_invalido": "Недопустимое имя папки.",
        "error_leer_rpy": "Не удалось прочитать файл:\n{detalle}",
        "error_carpeta_sprites": "Папка спрайтов не найдена:\n{ruta}",
        "info_importado": "{n} PNG скопировано в:\n{ruta}",
        "reload_recargando": "Перезагрузка интерфейса...",
        "import_nuevos": "Обнаружены новые assets, импорт...",
        "import_eliminado": "Asset был удалён",
        "faltan_deps": "Отсутствует необходимая зависимость:\n{detalle}\n\nВыполните: pip install -r requirements.txt",
        "config_corrupta": "Файл конфигурации не удалось прочитать и он будет проигнорирован.\n{ruta}\n\nПодробности в poselab.log.",  # noqa: E501
    },
}

_idioma_actual = IDIOMA_DEFECTO
_textos_activos: Dict[str, Dict[str, str]] = {
    codigo: dict(tabla) for codigo, tabla in TEXTOS_BUILTIN.items()
}


def configurar(codigo: str) -> None:
    """Activa un idioma (built-in o anadido via archivo). Fallback a es."""
    global _idioma_actual
    codigo = codigo or IDIOMA_DEFECTO
    _idioma_actual = codigo if codigo in _textos_activos else IDIOMA_DEFECTO


def tr(clave: str, **kwargs) -> str:
    """Texto de la clave en el idioma activo, con fallback a es."""
    tabla = _textos_activos.get(_idioma_actual, {})
    texto = tabla.get(clave) or TEXTOS_BUILTIN.get(IDIOMA_DEFECTO, {}).get(clave, clave)
    if kwargs:
        texto = texto.format(**kwargs)
    return texto


def idioma_actual() -> str:
    return _idioma_actual


def idiomas_disponibles() -> List[str]:
    """Codigos de idioma disponibles (built-in + los del archivo)."""
    return sorted(_textos_activos.keys())


def nombre_idioma(codigo: str) -> str:
    """Nombre nativo del idioma (para los botones del menu)."""
    tabla = _textos_activos.get(codigo)
    if tabla:
        return tabla.get("_nombre", codigo)
    return codigo


def cargar_archivo(ruta: str) -> None:
    """Merge del archivo languages.json sobre los built-in: claves con
    prioridad, idiomas nuevos se suman, faltantes -> es. Si el archivo no
    existe o es invalido, se usan solo los built-in."""
    global _textos_activos
    _textos_activos = {codigo: dict(tabla) for codigo, tabla in TEXTOS_BUILTIN.items()}
    try:
        with open(ruta, encoding="utf-8") as f:
            extra = json.load(f)
        if not isinstance(extra, dict):
            return
        for codigo, tabla in extra.items():
            if not isinstance(tabla, dict):
                continue
            if codigo not in _textos_activos:
                _textos_activos[codigo] = {}
            for clave, texto in tabla.items():
                _textos_activos[codigo][clave] = str(texto)
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError):
        LOG.warning("languages.json ilegible: %s", ruta, exc_info=True)


def generar_plantilla(ruta: str) -> None:
    """Crea languages.json si no existe, para que la comunidad anada idiomas."""
    try:
        if not os.path.exists(ruta):
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(TEXTOS_BUILTIN, f, ensure_ascii=False, indent=2)
    except OSError:
        LOG.warning("no se pudo crear languages.json en %s", ruta, exc_info=True)


def leer_idioma_config(ruta_config: str) -> Optional[str]:
    """Lee el idioma guardado en poselab_config.json; None si no existe."""
    try:
        with open(ruta_config, encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict):
            return cfg.get("idioma")
    except (OSError, json.JSONDecodeError):
        pass
    return None
