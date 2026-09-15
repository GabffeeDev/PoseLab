import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.messagebox as tk_msg
from tkinter import filedialog
from typing import Dict, Set

try:
    import customtkinter as ctk
    from PIL import Image, ImageDraw
except ImportError as e:
    tk_msg.showerror(
        "PoseLab",
        f"Falta una dependencia necesaria:\n{e}\n\n"
        "Ejecuta: pip install -r requirements.txt")
    raise
import deteccion
import i18n
import sprites as sp
import updater
from detector import (
    DOKIS,
    analizar_archivo,
    cuerpos_compuestos,
    es_cuerpo_heuristico,
    pose_para_brazos,
    siguiente_nombre,
)
from sprites import TRANS_NOMBRES, ZOOM_MAX, ZOOM_MIN, ZOOM_PASO

LOG = logging.getLogger("poselab.app")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CONFIG_PATH = os.path.join(deteccion.RUNTIME_DIR, "poselab_config.json")
LANGUAGES_PATH = os.path.join(deteccion.RUNTIME_DIR, "languages.json")


def _escribir_config(cfg: dict) -> None:
    """Escribe la config a disco; si falla, solo se loguea (no crashea)."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        LOG.error("no se pudo guardar la config en %s", CONFIG_PATH, exc_info=True)


def _icono_portapapeles(ancho: int = 28, alto: int = 28):
    """Icono de portapapeles dibujado con PIL (renderea en cualquier plataforma)."""
    img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # clip (rectangulo superior con esquinas redondeadas)
    d.rounded_rectangle([8, 4, 20, 9], radius=2, fill="#dddddd")
    # cuerpo del portapapeles
    d.rounded_rectangle([5, 6, 23, 24], radius=3, fill="#dddddd")
    # lineas de texto
    for y in (11, 15, 19):
        d.line([9, y, 19, y], fill="#333333", width=2)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(ancho, alto))


def _tooltip(widget, texto: str) -> None:
    """Muestra un tooltip simple al pasar el mouse (retardo 500ms)."""
    tl = None
    tras_pausa = None

    def _entrar(_e):
        nonlocal tl, tras_pausa
        _salir()
        tras_pausa = widget.after(500, _mostrar)

    def _mostrar():
        nonlocal tl
        tl = tk.Toplevel(widget)
        tl.wm_overrideredirect(True)
        tl.wm_attributes("-topmost", True)
        lbl = tk.Label(tl, text=texto, bg="#333333", fg="#eeeeee",
                       font=("Segoe UI", 10), padx=6, pady=2)
        lbl.pack()
        x = widget.winfo_rootx() + widget.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        tl.wm_geometry(f"+{x}+{y}")

    def _salir(_e=None):
        nonlocal tl, tras_pausa
        if tras_pausa is not None:
            try:
                widget.after_cancel(tras_pausa)
            except Exception:
                pass
            tras_pausa = None
        if tl is not None:
            try:
                tl.destroy()
            except Exception:
                pass
            tl = None

    widget.bind("<Enter>", _entrar, add="+")
    widget.bind("<Leave>", _salir, add="+")


def _popup_centrado(app, ancho: int = 200, alto: int = 60) -> ctk.CTkToplevel:
    """Crea un CTkToplevel sin bordes, siempre al frente, centrado sobre la app."""
    popup = ctk.CTkToplevel(app)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    x = app.winfo_rootx() + app.winfo_width() // 2 - ancho // 2
    y = app.winfo_rooty() + app.winfo_height() // 2 - alto // 2
    popup.geometry(f"+{x}+{y}")
    return popup


class DetectorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"PoseLab v{updater.__version__}")
        self.minsize(700, 500)
        # maximizar: en Windows hay que aplicarlo despues de que la ventana este mapeada,
        # si no Tk lo ignora. <Map> se dispara cuando la ventana ya se mostro.
        self.bind("<Map>", lambda e: self._maximizar(), add="+")

        i18n.cargar_archivo(LANGUAGES_PATH)
        i18n.generar_plantilla(LANGUAGES_PATH)
        self.usados = set()
        self.defs_cargadas = False
        self.incluir_def = False
        self.cfg = self._leer_config()

        idioma = i18n.leer_idioma_config(CONFIG_PATH)
        if idioma:
            i18n.configurar(idioma)
            self._iniciar_ui()
        else:
            # primera ejecucion: el usuario elige idioma antes de la app
            self._mostrar_bienvenida_idioma()

    def _mostrar_bienvenida_idioma(self):
        """Pantalla previa a la app: elige idioma con botones nativos."""
        ctk.CTkLabel(
            self, text=i18n.TEXTOS_BUILTIN["en"]["bienvenida_titulo"],
            font=ctk.CTkFont(size=26, weight="bold")
        ).pack(pady=(60, 8))
        ctk.CTkLabel(
            self, text="EspaÃ±ol Â· English Â· PortuguÃªs Â· Ð ÑƒÑÑÐºÐ¸Ð¹",
            font=ctk.CTkFont(size=13), text_color="#888"
        ).pack(pady=(0, 30))
        for codigo in i18n.idiomas_disponibles():
            ctk.CTkButton(
                self, text=i18n.nombre_idioma(codigo), width=260, height=44,
                font=ctk.CTkFont(size=16),
                command=lambda c=codigo: self._elegir_idioma(c)).pack(pady=6)

    def _elegir_idioma(self, codigo):
        i18n.configurar(codigo)
        self.cfg["idioma"] = codigo
        _escribir_config(self.cfg)
        # limpiar la pantalla de bienvenida antes de construir la UI
        for w in list(self.winfo_children()):
            w.destroy()
        self._iniciar_ui()

    def _iniciar_ui(self):
        """Construye la interfaz principal; se llama al arrancar con idioma."""
        self._reset_estado()
        self._aplicar_config()

        self._construir_ui()
        self._cargar_fondos()
        self._cargar_doki_inicial()
        # auto-deteccion de importados/: estado inicial + escaneo periodico
        self._importados_conocidos = deteccion.listar_importados()
        escanear_importados(self, popup_nuevos, popup_eliminado)
        self._update_pendiente = updater.cargar_pendiente(
            os.path.join(deteccion.RUNTIME_DIR, "_update", "pendiente.json"))
        top = self.winfo_toplevel()
        top.bind("<F5>", self._recargar, add="+")
        top.bind("<Control-c>", lambda e: self.copiar_show(), add="+")
        top.bind("<Control-MouseWheel>", self._on_ctrl_rueda, add="+")
        self.protocol("WM_DELETE_WINDOW", self._on_cerrar)

    def _reset_estado(self):
        """Reinicia el estado de render/caches; compartido por init y hotreload."""
        self.fuente = deteccion.FUENTE_DEFECTO
        self.preview_photo = None
        self._escena_actual = None
        self._sel_prev = None
        self._dibujar_clave = None
        self._fondo_cache = (None, None)
        self._char_paths = {}
        self._capa_cache = {}
        self._cara_folder = None
        self.cara_offset = [0, 0]
        self._recargando = False
        self._popup_reload = None
        self._popup_atajos = None
        self.definidos = set()
        self.cuerpos_por_doki: Dict[str, Set[str]] = {}
        self.zoom = 1.0
        self._pan = [0, 0]
        self._pan_inicio = None
        self._icono_copiar = _icono_portapapeles()
        self._icono_copiar_def = _icono_portapapeles()

    # ---------- config / persistencia ----------
    def _maximizar(self):
        """Maximiza la ventana en cualquier plataforma. state('zoomed') funciona
        en Windows y Linux; en macOS no existe, se cae al tamano de pantalla."""
        try:
            self.state("zoomed")
        except Exception:
            w = self.winfo_screenwidth()
            h = self.winfo_screenheight()
            self.geometry(f"{w}x{h}+0+0")

    def _leer_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg if isinstance(cfg, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError):
            LOG.warning("config ilegible o corrupta: %s", CONFIG_PATH, exc_info=True)
            tk_msg.showerror(
                "PoseLab",
                i18n.tr("config_corrupta", ruta=CONFIG_PATH))
            return {}

    def _guardar_config(self):
        cfg = {
            "fuente": self.fuente,
            "doki": self.combo_doki.get(),
            "izq": self.combo_izq.get(),
            "der": self.combo_der.get(),
            "cara": self.combo_cara.get(),
            "compuesto": self.combo_compuesto.get(),
            "offset_cara": self.cara_offset,
            "fondo": self.lbl_fondo.cget("text"),
            "transform": self.combo_transform.get(),
            "zoom": self.zoom,
            "incluir_def": self.incluir_def,
            "idioma": i18n.idioma_actual(),
        }
        _escribir_config(cfg)

    def _aplicar_config(self):
        if self.cfg.get("fuente") and os.path.isdir(self.cfg["fuente"]):
            self.fuente = self.cfg["fuente"]
        try:
            z = float(self.cfg.get("zoom", 1.0))
            self.zoom = min(max(z, ZOOM_MIN), ZOOM_MAX)
        except (TypeError, ValueError):
            self.zoom = 1.0
        oc = self.cfg.get("offset_cara")
        if isinstance(oc, list) and len(oc) == 2:
            self.cara_offset = [int(oc[0]), int(oc[1])]
        self.incluir_def = bool(self.cfg.get("incluir_def", False))

    def _on_cerrar(self):
        self._guardar_config()
        if self._update_pendiente and getattr(sys, "frozen", False):
            self._lanzar_updater()
        self.destroy()

    def _mostrar_atajos(self):
        """Muestra un popup con los atajos de teclado disponibles.
        Si ya hay uno abierto, lo lleva al frente en vez de acumular otro."""
        if self._popup_atajos is not None:
            try:
                if self._popup_atajos.winfo_exists():
                    self._popup_atajos.lift()
                    self._popup_atajos.focus_force()
                    return
            except Exception:
                pass
            self._popup_atajos = None
        popup = _popup_centrado(self, ancho=320, alto=220)
        self._popup_atajos = popup
        ctk.CTkLabel(
            popup, text=i18n.tr("atajos_titulo"),
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(padx=24, pady=(16, 6))
        lineas = [
            ("F5", i18n.tr("atajo_recargar")),
            ("Ctrl+C", i18n.tr("atajo_copiar_show")),
            ("Ctrl + rueda", i18n.tr("atajo_zoom")),
            ("Click izq + arrastrar", i18n.tr("atajo_pan")),
        ]
        for tecla, desc in lineas:
            ctk.CTkLabel(
                popup, text=f"{tecla:<18} {desc}",
                font=ctk.CTkFont(size=13), anchor="w", justify="left"
            ).pack(padx=28, pady=1, anchor="w")
        ctk.CTkButton(
            popup, text=i18n.tr("atajos_cerrar"), width=80,
            command=lambda: self._cerrar_atajos()
        ).pack(pady=(12, 12))

    def _cerrar_atajos(self):
        if self._popup_atajos is not None:
            try:
                self._popup_atajos.destroy()
            except Exception:
                pass
            self._popup_atajos = None

    def _recargar(self, _=None):
        """Recarga la interfaz en el lugar (F5): la ventana NO se cierra."""
        if self._recargando or not self.winfo_exists():
            return
        self._recargando = True
        popup = _popup_centrado(self, ancho=220, alto=40)
        ctk.CTkLabel(
            popup, text=i18n.tr("reload_recargando"),
            font=ctk.CTkFont(size=14)
        ).pack(padx=24, pady=20)
        self._popup_reload = popup
        self.after(500, self._reconstruir)

    def _reconstruir(self):
        """Destruye y recrea la UI; la ventana permanece abierta."""
        if not self.winfo_exists():
            return  # la app se cerro durante el popup de recarga
        if self._popup_reload:
            try:
                self._popup_reload.destroy()
            except Exception:
                pass
            self._popup_reload = None
        for w in list(self.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        self._recargando = False
        self._iniciar_ui()

    # ---------- UI ----------
    def _construir_ui(self):
        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(pady=(14, 4), fill="x")
        ctk.CTkLabel(
            cabecera, text="PoseLab",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(side="left", padx=(16, 0))
        ctk.CTkButton(
            cabecera, text=i18n.tr("btn_atajos"), width=70,
            fg_color="#555555", command=self._mostrar_atajos
        ).pack(side="right", padx=(0, 16))

        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=14, pady=(4, 10))
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=0)

        ctrl = ctk.CTkFrame(main, width=240)
        ctrl.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=10, pady=10)

        self._seccion(ctrl, i18n.tr("seccion_fuente"))
        fila = ctk.CTkFrame(ctrl, fg_color="transparent")
        fila.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(fila, text="Sprites:").pack(side="left")
        ctk.CTkButton(fila, text=i18n.tr("btn_importar"), width=66,
                      command=self._importar_sprites).pack(side="right")
        ctk.CTkButton(fila, text=i18n.tr("btn_fuente"), width=66,
                      command=self.cambiar_fuente).pack(side="right", padx=(0, 2))

        self._seccion(ctrl, i18n.tr("seccion_personaje"))
        self.combo_doki = ctk.CTkComboBox(ctrl, values=self._dokis_disponibles(), state="readonly", width=180,
                                          command=self._on_doki)
        self.combo_doki.pack(padx=8, pady=2)

        self._seccion(ctrl, i18n.tr("seccion_componentes"))
        self.combo_izq = self._selector(ctrl, i18n.tr("selector_brazo_izq"))
        self.combo_der = self._selector(ctrl, i18n.tr("selector_brazo_der"))
        self.combo_cara = self._selector(ctrl, i18n.tr("selector_cara"))
        # compuesto: al elegirlo, los brazos/cara vuelven a "ninguno"
        self.combo_compuesto = self._selector(
            ctrl, i18n.tr("selector_compuesto"),
            command=lambda _: self._on_compuesto())
        fila = ctk.CTkFrame(ctrl, fg_color="transparent")
        fila.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(fila, text=i18n.tr("selector_offset"), width=80).pack(side="left")
        for txt, dx, dy in (("<", -4, 0), (">", 4, 0), ("^", 0, -4), ("v", 0, 4)):
            boton = ctk.CTkButton(
                fila, text=txt, width=28,
                command=lambda dx=dx, dy=dy: self._mover_cara(dx, dy))
            boton.pack(side="left", padx=1)
        offset_txt = f"{self.cara_offset[0]},{self.cara_offset[1]}"
        self.lbl_offset = ctk.CTkLabel(
            fila, text=offset_txt, width=40, text_color="#aaa")
        self.lbl_offset.pack(side="left", padx=4)
        ctk.CTkButton(fila, text="0", width=28, command=self._reset_cara).pack(side="left", padx=1)
        ctk.CTkButton(
            ctrl, text=i18n.tr("btn_reset"),
            command=self._reset_pose
        ).pack(padx=8, pady=(2, 4), fill="x")

        self._seccion(ctrl, i18n.tr("seccion_escena"))
        fila = ctk.CTkFrame(ctrl, fg_color="transparent")
        fila.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(fila, text=i18n.tr("selector_fondo")).pack(side="left")
        self.lbl_fondo = ctk.CTkLabel(fila, text="-", width=100, fg_color="#1a1a1a", corner_radius=6)
        self.lbl_fondo.pack(side="left", padx=6)
        ctk.CTkButton(fila, text="<", width=30, command=lambda: self._ciclo_fondo(-1)).pack(side="left")
        ctk.CTkButton(fila, text=">", width=30, command=lambda: self._ciclo_fondo(+1)).pack(side="left", padx=(4, 0))
        self.vals_fondo = []

        fila = ctk.CTkFrame(ctrl, fg_color="transparent")
        fila.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(fila, text=i18n.tr("selector_transform")).pack(side="left")
        self.combo_transform = ctk.CTkComboBox(
            fila, values=TRANS_NOMBRES, state="readonly", width=90,
            command=lambda _: self._actualizar_preview())
        self.combo_transform.set("t42")
        self.combo_transform.pack(side="left", padx=6)

        fila = ctk.CTkFrame(ctrl, fg_color="transparent")
        fila.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(fila, text=i18n.tr("selector_zoom")).pack(side="left")
        self.lbl_zoom = ctk.CTkLabel(fila, text="1.0x", width=42)
        self.lbl_zoom.pack(side="left", padx=4)
        self.slider_zoom = ctk.CTkSlider(
            fila, from_=ZOOM_MIN, to=ZOOM_MAX, number_of_steps=20,
            command=self._set_zoom)
        self.slider_zoom.set(self.zoom)
        self.slider_zoom.pack(side="left", fill="x", expand=True, padx=4)

        self._seccion(ctrl, i18n.tr("seccion_exportar"))
        self.chk_def = ctk.CTkCheckBox(
            ctrl, text=i18n.tr("btn_incluir_def"),
            command=self._on_chk_def)
        self.chk_def.pack(padx=8, pady=2, anchor="w")
        ctk.CTkButton(
            ctrl, text=i18n.tr("btn_cargar_rpy"),
            command=self.cargar_definitions, fg_color="#555555"
        ).pack(padx=8, pady=2, fill="x")
        ctk.CTkButton(
            ctrl, text=i18n.tr("btn_buscar_update"),
            command=lambda: self._buscar_update(manual=True), fg_color="#555555"
        ).pack(padx=8, pady=2, fill="x")
        self.lbl_rpy = ctk.CTkLabel(ctrl, text="", font=("Consolas", 10), text_color="#888")
        self.lbl_rpy.pack(padx=8, pady=2)

        self.lienzo = ctk.CTkCanvas(main, bg="#222222", highlightthickness=0)
        self.lienzo.grid(row=0, column=1, sticky="nsew", padx=10, pady=(10, 6))
        self.lienzo.bind("<Configure>", lambda e: self._dibujar())
        self.lienzo.bind("<ButtonPress-1>", self._pan_iniciar, add="+")
        self.lienzo.bind("<B1-Motion>", self._pan_mover, add="+")
        self.lienzo.bind("<ButtonRelease-1>", self._pan_fin, add="+")

        card = ctk.CTkFrame(main, corner_radius=8, fg_color="#2b2b2b")
        card.grid(row=1, column=1, sticky="ew", padx=10, pady=(0, 10))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card, text=i18n.tr("lbl_nombre"), font=("Consolas", 12), text_color="#aaaaaa"
        ).grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(8, 2))
        self.lbl_nombre = ctk.CTkLabel(
            card, text=i18n.tr("doki_vacio"), text_color="#4da6ff",
            font=("Consolas", 18, "bold"), anchor="w"
        )
        self.lbl_nombre.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(8, 2))

        ctk.CTkLabel(
            card, text=i18n.tr("lbl_codigo"), font=("Consolas", 12), text_color="#aaaaaa"
        ).grid(row=1, column=0, sticky="nw", padx=(10, 6), pady=(2, 8))
        self.txt_codigo = ctk.CTkTextbox(
            card, height=40, font=("Consolas", 12), wrap="word",
            fg_color="#1a1a1a", border_width=0
        )
        self.txt_codigo.grid(row=1, column=1, sticky="ew", padx=(0, 4), pady=(2, 8))
        self.txt_codigo.bind("<Key>", self._bloquear_tecla)
        self.btn_copiar = ctk.CTkButton(
            card, text="", image=self._icono_copiar, width=32,
            fg_color="#555555", command=self.copiar_show
        )
        self.btn_copiar.grid(row=1, column=2, sticky="ne", padx=(0, 10), pady=(2, 8))
        _tooltip(self.btn_copiar, i18n.tr("tooltip_copiar_show"))

        ctk.CTkLabel(
            card, text=i18n.tr("lbl_definicion"), font=("Consolas", 12), text_color="#aaaaaa"
        ).grid(row=2, column=0, sticky="nw", padx=(10, 6), pady=(2, 8))
        self.txt_def = ctk.CTkTextbox(
            card, height=40, font=("Consolas", 12), wrap="word",
            fg_color="#1a1a1a", border_width=0
        )
        self.txt_def.grid(row=2, column=1, sticky="ew", padx=(0, 4), pady=(2, 8))
        self.txt_def.bind("<Key>", self._bloquear_tecla)
        self.btn_copiar_def = ctk.CTkButton(
            card, text="", image=self._icono_copiar_def, width=32,
            fg_color="#555555", command=self.copiar_definicion, state="disabled"
        )
        self.btn_copiar_def.grid(row=2, column=2, sticky="ne", padx=(0, 10), pady=(2, 8))
        _tooltip(self.btn_copiar_def, i18n.tr("tooltip_copiar_def"))

        self.lbl_estado = ctk.CTkLabel(
            card, text="", font=("Consolas", 11), text_color="#888"
        )
        self.lbl_estado.grid(row=3, column=1, sticky="w", padx=(0, 10), pady=(0, 6))
        self.lienzo.bind("<Control-MouseWheel>", self._on_ctrl_rueda, add="+")

    def _seccion(self, parent, titulo):
        ctk.CTkLabel(
            parent, text=titulo, font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#4da6ff"
        ).pack(anchor="w", padx=8, pady=(12, 2))

    def _selector(self, parent, label, command=None):
        fila = ctk.CTkFrame(parent, fg_color="transparent")
        fila.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(fila, text=label + ":", width=80).pack(side="left")
        combo = ctk.CTkComboBox(
            fila, state="readonly", width=110,
            command=command or (lambda _: self._actualizar_preview()))
        combo.pack(side="left", padx=(4, 0))
        return combo

    def _bloquear_tecla(self, e):
        # Control (0x4) permite c/a/x/insert (copiar/pegar); bloquea el resto
        _CTRL = 0x4
        if e.state & _CTRL and e.keysym.lower() in ("c", "a", "x", "insert"):
            return
        return "break"

    # ---------- datos ----------
    def _fuente_es_personaje(self):
        """True si la fuente misma es una carpeta de personaje (tiene PNGs directos)."""
        try:
            return any(f.endswith(".png") for f in os.listdir(self.fuente))
        except OSError:
            return False

    def _dokis_disponibles(self):
        """Personajes: fuente (si es personaje o subcarpetas) + importados/ y ejemplos/ como workspaces secundarios.
        Devuelve lista ordenada y guarda self._char_paths (nombre -> carpeta)."""
        chars = {}
        if self._fuente_es_personaje():
            n = os.path.basename(self.fuente)
            chars[n] = self.fuente
        else:
            for n in deteccion.carpetas_con_pngs(self.fuente):
                chars[n] = os.path.join(self.fuente, n)
        # workspaces secundarios: importados/ y ejemplos/ (mods y ejemplos)
        for ws in (deteccion.IMPORTADOS, os.path.join(deteccion.DATA_DIR, "ejemplos")):
            if os.path.isdir(ws) and os.path.normcase(ws) != os.path.normcase(self.fuente):
                for n in deteccion.carpetas_con_pngs(ws):
                    if n not in chars:  # fuente tiene prioridad
                        chars[n] = os.path.join(ws, n)
        if not chars:
            self._char_paths = {}
            return list(DOKIS)
        lower_carp = {c.lower(): c for c in chars}
        vanilla = [lower_carp[d.lower()] for d in DOKIS if d.lower() in lower_carp]
        customs = sorted(c for c in chars if c.lower() not in {d.lower() for d in DOKIS})
        disponibles = vanilla + customs
        self._char_paths = {n: chars[n] for n in disponibles}
        return disponibles

    def _on_doki(self, _):
        self._cargar_doki()

    @staticmethod
    def _restaurar(combo, valor):
        if valor in combo.cget("values"):
            combo.set(valor)

    def _cargar_doki_inicial(self):
        dokis = self.combo_doki.cget("values")
        doki = self.cfg.get("doki") or (dokis[0] if dokis else DOKIS[0])
        if doki not in dokis:
            doki = dokis[0] if dokis else DOKIS[0]
        self.combo_doki.set(doki)
        self._cargar_doki()
        self._restaurar(self.combo_compuesto, self.cfg.get("compuesto", ""))
        self._restaurar(self.combo_izq, self.cfg.get("izq"))
        self._restaurar(self.combo_der, self.cfg.get("der"))
        self._restaurar(self.combo_cara, self.cfg.get("cara"))
        fondo = self.cfg.get("fondo")
        if fondo in self.vals_fondo:
            self.lbl_fondo.configure(text=fondo)
        self._restaurar(self.combo_transform, self.cfg.get("transform"))
        if self.incluir_def:
            self.chk_def.select()
        self._actualizar_preview()

    def cambiar_fuente(self):
        ruta = filedialog.askdirectory(title=i18n.tr("titulo_dialog_fuente"))
        if ruta:
            self.fuente = ruta
            self._cargar_fondos()
            dokis = self._dokis_disponibles()
            self.combo_doki.configure(values=dokis)
            self.combo_doki.set(dokis[0])
            self._cargar_doki()

    def _importar_sprites(self):
        """Copia una carpeta de PNGs como personaje nuevo en importados/."""
        ruta = filedialog.askdirectory(title=i18n.tr("titulo_dialog_importar"))
        if not ruta:
            return
        pngs = [f for f in os.listdir(ruta) if f.endswith(".png")]
        if not pngs:
            tk_msg.showerror(i18n.tr("error"), i18n.tr("error_sin_pngs"))
            return
        # el nombre pasa tal cual (espacios, mayusculas, acentos), como pide el mod.
        # solo se rechaza si esta vacio o trae separadores de ruta.
        nombre = os.path.basename(os.path.normpath(ruta))
        if not nombre or any(c in nombre for c in '<>:"/\\|?*\0'):
            tk_msg.showerror(i18n.tr("error"), i18n.tr("error_nombre_invalido"))
            return
        destino = os.path.join(deteccion.IMPORTADOS, nombre)
        os.makedirs(destino, exist_ok=True)
        for f in pngs:
            shutil.copy2(os.path.join(ruta, f), os.path.join(destino, f))
        self._cargar_fondos()
        dokis = self._dokis_disponibles()
        self.combo_doki.configure(values=dokis)
        if nombre in dokis:
            self.combo_doki.set(nombre)
        self._cargar_doki()
        tk_msg.showinfo("PoseLab", i18n.tr("info_importado", n=len(pngs), ruta=destino))

    def cargar_definitions(self):
        ruta = filedialog.askopenfilename(
            title=i18n.tr("titulo_dialog_rpy"),
            filetypes=[(i18n.tr("tipo_rpy"), "*.rpy"), (i18n.tr("tipo_todos"), "*.*")]
        )
        if not ruta:
            return
        try:
            contenido = open(ruta, "r", encoding="utf-8-sig").read()
        except UnicodeDecodeError:
            contenido = open(ruta, "r", encoding="latin-1").read()
        except OSError as e:
            tk_msg.showerror(i18n.tr("error"), i18n.tr("error_leer_rpy", detalle=e))
            return
        try:
            datos = analizar_archivo(ruta, contenido)
        except Exception as e:
            tk_msg.showerror(i18n.tr("error"), i18n.tr("error_leer_rpy", detalle=e))
            return
        self.usados |= {(tag, pose + expr) for tag, poses in datos.items() for pose, expr in poses}
        self.definidos = {(tag, pose + expr) for tag, poses in datos.items() for pose, expr in poses}
        self.cuerpos_por_doki = cuerpos_compuestos(contenido, self._char_paths)
        self.defs_cargadas = True
        nombre = os.path.basename(ruta)
        self.lbl_rpy.configure(text=f"cargado: {nombre} ({len(self.usados)})")
        self._actualizar_preview()

    def _cargar_doki(self):
        doki = self.combo_doki.get()
        if not doki:
            return
        carpeta = self._char_paths.get(doki)
        if not carpeta or not os.path.isdir(carpeta):
            tk_msg.showerror(i18n.tr("error"), i18n.tr("error_carpeta_sprites", ruta=carpeta))
            return
        self._capa_cache = {}  # el cache de capas es por personaje
        sprites = sorted(f[:-4] for f in os.listdir(carpeta) if f.endswith(".png"))
        # brazos: <num>[b][l|r] (1l, 2r, 1bl, 3l, 4r, ...); normales (sin b) antes que cruzados
        brazos = [n for n in sprites if re.fullmatch(r"\d+b?[lr]", n)]

        def orden_brazo(n):
            return (int(re.match(r"(\d+)", n).group(1)), 1 if "b" in n else 0)

        izq = sorted((n for n in brazos if n.endswith("l")), key=orden_brazo)
        der = sorted((n for n in brazos if n.endswith("r")), key=orden_brazo)
        simples = sorted(n for n in sprites if n not in brazos and re.fullmatch(r"[a-z]", n))
        # compuestos: solo sprites de cuerpo completo. Con definitions.rpy cargado
        # se usa como fuente de verdad; sin el, heuristica (digito + 960x960 + toca suelo).
        cuerpos = self.cuerpos_por_doki.get(doki.lower())
        if cuerpos:
            compuestos = sorted(c for c in cuerpos if c in sprites)
        else:
            compuestos = sorted(n for n in sprites
                                if n not in brazos
                                and not re.fullmatch(r"[a-z]", n)
                                and es_cuerpo_heuristico(n, os.path.join(carpeta, f"{n}.png")))
        self.combo_izq.configure(values=[""] + izq)
        self.combo_der.configure(values=[""] + der)
        self.combo_cara.configure(values=[""] + simples)
        self.combo_compuesto.configure(values=[""] + compuestos)
        if izq:
            self.combo_izq.set(izq[0])
        if der:
            self.combo_der.set(der[0])
        if simples:
            self.combo_cara.configure(state="readonly", values=[""] + simples)
            self.combo_cara.set(simples[0])
            self._cara_folder = None
        else:
            # el mod no trae caras propias: usar las del vanilla que matchea por nombre
            # (ej. "Sleepy Yuri" -> yuri). El usuario puede ajustar el offset para alinear.
            match = next((d for d in DOKIS if d.lower() in doki.lower()), None)
            vf = os.path.join(deteccion.FUENTE_DEFECTO, match) if match else None
            vf_faces = (sorted(f[:-4] for f in os.listdir(vf)
                               if re.fullmatch(r"[a-z]", f[:-4]))
                        if vf and os.path.isdir(vf) else [])
            if vf_faces:
                self._cara_folder = vf
                self.combo_cara.configure(state="readonly", values=[""] + vf_faces)
                self.combo_cara.set(vf_faces[0])
                # auto-alinear: si el cuerpo del mod no tiene cabeza (bbox empieza
                # abajo), la cara vanilla debe subir para que su parte inferior
                # coincida con donde empieza el cuerpo (la zona vacia de arriba
                # es donde va la cabeza)
                brazo_ref = (izq + der + compuestos)[0] if (izq or der or compuestos) else None
                if brazo_ref and self.cara_offset == [0, 0]:
                    cb = self._bbox(os.path.join(carpeta, f"{brazo_ref}.png"))
                    fb = self._bbox(os.path.join(vf, f"{vf_faces[0]}.png"))
                    if cb and fb and cb[1] > 100:  # cuerpo sin cabeza
                        self.cara_offset = [0, cb[1] - fb[3]]
            else:
                self._cara_folder = None
                self.combo_cara.configure(state="disabled", values=[])
                self.combo_cara.set("")
        self.lbl_offset.configure(text=f"{self.cara_offset[0]},{self.cara_offset[1]}")
        if compuestos:
            self.combo_compuesto.set(compuestos[0])
        self._actualizar_preview()

    def _cargar_fondos(self):
        self._fondo_cache = (None, None)  # reset cache al cambiar de fuente
        carpeta = os.path.join(self.fuente, "bg")
        fondos = sorted(
            f[:-4] for f in os.listdir(carpeta) if f.endswith(".png")
        ) if os.path.isdir(carpeta) else []
        self.vals_fondo = fondos
        preferido = "club" if "club" in fondos else (fondos[0] if fondos else "-")
        self.lbl_fondo.configure(text=preferido)

    def _bbox(self, ruta):
        """Bbox de la imagen en (x0, y0, x1, y1), o None si falla."""
        try:
            with Image.open(ruta) as im:
                return im.convert("RGBA").getbbox()
        except Exception:
            return None

    def _mover_cara(self, dx, dy):
        self.cara_offset[0] += dx
        self.cara_offset[1] += dy
        self.lbl_offset.configure(text=f"{self.cara_offset[0]},{self.cara_offset[1]}")
        self._actualizar_preview()

    def _reset_cara(self):
        self.cara_offset = [0, 0]
        self.lbl_offset.configure(text="0,0")
        self._actualizar_preview()

    def _reset_pose(self):
        """Limpia la pose (componentes + offset de cara). No toca escena."""
        self.cara_offset = [0, 0]
        self._cargar_doki()  # re-puebla brazos/cara por defecto y re-habilita combos

    def _ciclo_fondo(self, delta):
        if not self.vals_fondo:
            return
        actual = self.lbl_fondo.cget("text")
        try:
            i = self.vals_fondo.index(actual)
        except ValueError:
            i = 0
        self.lbl_fondo.configure(text=self.vals_fondo[(i + delta) % len(self.vals_fondo)])
        self._actualizar_preview()

    # ---------- render ----------
    def _capa(self, nombre):
        return sp.path_capa(self._char_paths, self.fuente, self.combo_doki.get(),
                            nombre, getattr(self, "_cara_folder", None))

    def _fondo(self, nombre):
        if self._fondo_cache[0] != nombre:
            ruta = os.path.join(self.fuente, "bg", f"{nombre}.png")
            try:
                img = sp.abrir_imagen(ruta)
            except Exception:
                LOG.warning("fondo no encontrado: %s", ruta, exc_info=True)
                img = None
            self._fondo_cache = (nombre, img)
        return self._fondo_cache[1]

    def _componer_sprite(self):
        compuesto = self.combo_compuesto.get()
        return sp.componer_sprite(
            self._char_paths, self.fuente, self.combo_doki.get(),
            compuesto, self.combo_izq.get(), self.combo_der.get(),
            self.combo_cara.get(), getattr(self, "_cara_folder", None),
            tuple(self.cara_offset), self._capa_cache)

    def _construir_escena(self, sprite):
        return sp.construir_escena(sprite, self.lbl_fondo.cget("text"),
                                   self._fondo, self.combo_transform.get() or "t42")

    def _dibujar(self):
        escena = self._escena_actual
        if escena is None:
            return
        w = self.lienzo.winfo_width() or 640
        h = self.lienzo.winfo_height() or 360
        if w < 50 or h < 50:
            w, h = 640, 360
        self._dibujar_clave, self.preview_photo = sp.dibujar_preview(
            self.lienzo, escena, w, h, self.zoom,
            self._sel_prev, self._dibujar_clave, self.preview_photo,
            tuple(self._pan))

    def _pan_iniciar(self, e):
        """Inicia el arrastre. Solo con zoom aplicado (>1) la imagen puede
        desplazarse; con zoom 1 esta ajustada al canvas y no hay pan."""
        if self.zoom <= 1.0 or self._escena_actual is None:
            return
        self._pan_inicio = (e.x, e.y)

    def _pan_mover(self, e):
        if self._pan_inicio is None:
            return
        dx = e.x - self._pan_inicio[0]
        dy = e.y - self._pan_inicio[1]
        self._pan_inicio = (e.x, e.y)
        # limite: la imagen ampliada nunca sale del todo del canvas
        w = self.lienzo.winfo_width() or 640
        h = self.lienzo.winfo_height() or 360
        escala = min(w / sp.PANTALLA[0], h / sp.PANTALLA[1]) * self.zoom
        limx = max(0, (sp.PANTALLA[0] * escala - w) / 2)
        limy = max(0, (sp.PANTALLA[1] * escala - h) / 2)
        self._pan[0] = min(max(self._pan[0] + dx, -limx), limx)
        self._pan[1] = min(max(self._pan[1] + dy, -limy), limy)
        self._dibujar()

    def _pan_fin(self, _e=None):
        self._pan_inicio = None

    def _on_compuesto(self, _valor=None):
        """El compuesto es una pose completa de una sola capa: al elegirlo se
        vacian y deshabilitan brazos/cara (no se arma nada encima). Al volver
        a 'ninguno', se re-puebla todo via _cargar_doki."""
        if self.combo_compuesto.get():
            for combo in (self.combo_izq, self.combo_der, self.combo_cara):
                combo.set("")
                combo.configure(state="disabled")
        else:
            for combo in (self.combo_izq, self.combo_der, self.combo_cara):
                combo.configure(state="readonly")
            self._cargar_doki()
        self._actualizar_preview()

    def _nombre_pose(self, doki, compuesto):
        """Nombre de la pose generada, o '-' si no hay pose valida."""
        if compuesto:
            return compuesto
        izq, der, cara = self.combo_izq.get(), self.combo_der.get(), self.combo_cara.get()
        # cara debe estar en los valores del combo (evita usar caras stale
        # de un mod anterior que ya no existen en este mod)
        if izq and der and cara and cara in self.combo_cara.cget("values"):
            return siguiente_nombre(doki, pose_para_brazos(izq, der), self.usados, cara)
        return "-"

    def _actualizar_preview(self):
        doki = self.combo_doki.get()
        if not doki:
            self.lbl_nombre.configure(text="-")
            self.txt_codigo.delete("1.0", "end")
            return
        compuesto = self.combo_compuesto.get()
        nombre = self._nombre_pose(doki, compuesto)
        self.lbl_nombre.configure(text=nombre)

        sel = (doki, self.combo_izq.get(), self.combo_der.get(), self.combo_cara.get(),
               compuesto, self.lbl_fondo.cget("text"), self.combo_transform.get(),
               tuple(self.cara_offset))
        if sel != self._sel_prev:
            self._escena_actual = self._construir_escena(self._componer_sprite())
            self._sel_prev = sel
            # el pan se mantiene al cambiar de componente; solo el reset de zoom
            # (a 1.0x) o _reset_pose lo vuelven a centrar
        self._dibujar()

        nombre_trans = self.combo_transform.get() or "t42"
        self.txt_codigo.delete("1.0", "end")
        if nombre != "-":
            self.txt_codigo.insert("end", f"show {doki} {nombre} at {nombre_trans} zorder 2")

        # definicion (opcion A): linea image para pegar en el definitions.rpy
        definicion = self._definicion_actual(doki, nombre, compuesto)
        self.txt_def.delete("1.0", "end")
        if definicion:
            self.txt_def.insert("end", definicion)
        self.btn_copiar_def.configure(
            state="normal" if definicion else "disabled")

        # validacion (opcion C): existe la pose como image en el .rpy cargado?
        if self.defs_cargadas and nombre != "-":
            existe = (sp.tag_rpy(doki), nombre) in self.definidos
            if existe:
                self.lbl_estado.configure(text=i18n.tr("estado_definido"), text_color="#6fce6f")
            else:
                self.lbl_estado.configure(
                    text=i18n.tr("estado_no_definido"),
                    text_color="#e07070")
        else:
            self.lbl_estado.configure(text="")

    def _definicion_actual(self, doki, nombre, compuesto):
        """Linea image actual (None si no hay pose o el checkbox esta apagado)."""
        if not self.incluir_def or nombre == "-":
            return None
        carpeta = os.path.basename(self._char_paths.get(doki, ""))
        cara_ruta = None
        if self._cara_folder and compuesto == "":
            cara_ruta = f"{os.path.basename(self._cara_folder)}/{self.combo_cara.get()}.png"
        return sp.definicion_image(
            sp.tag_rpy(doki), nombre, compuesto,
            self.combo_izq.get(), self.combo_der.get(), self.combo_cara.get(),
            carpeta, cara_ruta)

    def _on_chk_def(self):
        self.incluir_def = bool(self.chk_def.get())
        self._actualizar_preview()

    def copiar_definicion(self):
        definicion = self.txt_def.get("1.0", "end").strip()
        if not definicion:
            return
        self.clipboard_clear()
        self.clipboard_append(definicion)
        self.btn_copiar_def.configure(fg_color="#3a7d3a")

    def _set_zoom(self, valor):
        self.zoom = min(max(float(valor), ZOOM_MIN), ZOOM_MAX)
        self.slider_zoom.set(self.zoom)
        self.lbl_zoom.configure(text=f"{self.zoom:.1f}x")
        # con zoom 1.0 la imagen vuelve a su estado original (recentrar)
        if self.zoom <= 1.0:
            self._pan = [0, 0]
        self._dibujar()

    def _on_ctrl_rueda(self, e):
        delta = e.delta if hasattr(e, "delta") else (e.y_delta or 0)
        self._set_zoom(self.zoom + ZOOM_PASO * (1 if delta > 0 else -1))
        return "break"

    def copiar_show(self):
        codigo = self.txt_codigo.get("1.0", "end").strip()
        if not codigo:
            return
        self.clipboard_clear()
        self.clipboard_append(codigo)
        self.btn_copiar.configure(fg_color="#3a7d3a")

    # ---------- update ----------
    def _url_api_update(self):
        """URL de la API de releases; se puede sobreescribir en config para probar."""
        return self.cfg.get("updater_url") or updater.GITHUB_API_URL

    def _lanzar_updater(self):
        """Lanza PoseLabUpdater al cerrar (solo en build empaquetado)."""
        pendiente = self._update_pendiente or {}
        zip_ruta = pendiente.get("zip")
        if not zip_ruta or not os.path.exists(zip_ruta):
            LOG.warning("update pendiente sin zip: %s", zip_ruta)
            return
        updater_exe = os.path.join(
            deteccion.RUNTIME_DIR, "PoseLabUpdater" + (".exe" if os.name == "nt" else ""))
        if not os.path.exists(updater_exe):
            LOG.warning("no se encontro PoseLabUpdater en %s", updater_exe)
            return
        app_exe = os.path.join(deteccion.RUNTIME_DIR, "PoseLab" + (".exe" if os.name == "nt" else ""))
        try:
            subprocess.Popen([
                updater_exe, "--wait-pid", str(os.getpid()),
                "--zip", zip_ruta, "--target", deteccion.RUNTIME_DIR,
                "--app-path", app_exe,
            ])
        except OSError as e:
            LOG.error("no se pudo lanzar el updater: %s", e)

    def _buscar_update(self, manual=False):
        """Busca una version nueva en un hilo (no bloquea la UI)."""
        if getattr(self, "_update_en_curso", False):
            return
        self._update_en_curso = True
        url_api = self._url_api_update()

        def _trabajo():
            try:
                pendiente = updater.preparar_zip_descargado(
                    url_api,
                    os.path.join(deteccion.RUNTIME_DIR, "_update", "pendiente.json"),
                    os.path.join(deteccion.RUNTIME_DIR, "_update"))
            finally:
                self._update_en_curso = False

            def _fin():
                if not self.winfo_exists():
                    return
                if pendiente:
                    self._update_pendiente = pendiente
                    tk_msg.showinfo(
                        "PoseLab",
                        i18n.tr("update_pendiente", v=pendiente.get("version", "")))
                elif manual:
                    tk_msg.showinfo(
                        "PoseLab", i18n.tr("no_hay_actualizaciones"))
            self.after(0, _fin)

        t = threading.Thread(target=_trabajo, daemon=True)
        t.start()

    # ---------- guardado ----------

# ---------- auto-deteccion de importados/ (escaneo + popups) ----------

def escanear_importados(app, callback_nuevos, callback_eliminados,
                        intervalo_ms: int = 3000) -> None:
    """Programa un escaneo periodico. Llama a callback_nuevos(set) y/o
    callback_eliminados(set) con los cambios detectados. Al relanzarlo
    (p.ej. tras un hotreload) cancela la cadena previa para no duplicar."""
    if getattr(app, "_escanear_id", None):
        try:
            app.after_cancel(app._escanear_id)
        except Exception:
            pass

    def _paso():
        try:
            actuales = deteccion.listar_importados()
            conocidos = app._importados_conocidos
            nuevos = actuales - conocidos
            eliminados = conocidos - actuales
            if nuevos:
                app._importados_conocidos = actuales
                callback_nuevos(nuevos)
            if eliminados:
                app._importados_conocidos = actuales
                callback_eliminados(eliminados)
        except OSError:
            LOG.warning("fallo el escaneo de importados", exc_info=True)
        app._escanear_id = app.after(intervalo_ms, _paso)

    app._escanear_id = app.after(intervalo_ms, _paso)


def popup_nuevos(app, nombres):
    """Muestra popup con barra de carga para nuevos assets detectados."""
    popup = _popup_centrado(app, ancho=328, alto=60)
    ctk.CTkLabel(
        popup, text=i18n.tr("import_nuevos"),
        font=ctk.CTkFont(size=14)
    ).pack(padx=24, pady=(16, 8))
    barra = ctk.CTkProgressBar(popup, width=280, mode="determinate")
    barra.pack(padx=24, pady=(4, 16))
    barra.set(0)

    def paso(i=0.0):
        barra.set(i)
        if i < 1.0:
            popup.after(35, paso, i + 0.05)
        else:
            popup.destroy()
            dokis = app._dokis_disponibles()
            app.combo_doki.configure(values=dokis)
            primero = min(nombres, key=lambda n: dokis.index(n) if n in dokis else 999)
            if primero in dokis:
                app.combo_doki.set(primero)
            app._actualizar_preview()
    paso()


def popup_eliminado(app, nombres):
    """Muestra popup breve cuando se elimina un asset. Si el doki eliminado
    estaba seleccionado, cambia la seleccion al primer doki disponible."""
    popup = _popup_centrado(app, ancho=188, alto=40)
    ctk.CTkLabel(
        popup, text=i18n.tr("import_eliminado"),
        font=ctk.CTkFont(size=14)
    ).pack(padx=24, pady=20)
    if app.combo_doki.get() in nombres:
        dokis = app._dokis_disponibles()
        app.combo_doki.configure(values=dokis)
        if dokis:
            app.combo_doki.set(dokis[0])
    popup.after(1500, popup.destroy)


if __name__ == "__main__":
    deteccion.setup_logging()
    app = DetectorApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app._on_cerrar()
