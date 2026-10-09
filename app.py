"""La Verdulería de Margarita - Sistema de gestión para verdulería (POS de escritorio).

Ejecutar:  python app.py   (o doble clic en iniciar.bat)
"""
import os
import socket
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox, simpledialog, ttk

import datos
import iconos
import impresora
import servidor
from balanza import Balanza, probar_protocolos, puertos_disponibles
from formato import cantidad_txt, kg, num, pesos
from PIL import Image, ImageTk

F = "Segoe UI"
MEDIOS = ["Efectivo", "Débito", "Crédito", "Transferencia", "Mercado Pago"]

TEMAS = {
    "claro": dict(fondo="#E8F5E9", superficie="#FFFFFF", texto="#1B5E20", texto_sec="#6B7B6C",
                  cabecera="#1B5E20", cabecera_txt="#FFFFFF", primario="#2E7D32", secundario="#43A047",
                  boton_txt="#FFFFFF", acento="#FDD835", acento_txt="#1B5E20", prod_pesable="#FFF8C4",
                  prod_unidad="#FFFFFF", prod_txt="#1B5E20", visor="#0D3B12", visor_txt="#FDD835",
                  rojo="#C62828", gris="#9E9E9E", bajo_bg="#FFEBEE", bajo_txt="#C62828", positivo="#2E7D32",
                  egreso_txt="#C62828", destacado="#2E7D32"),
    "gris": dict(fondo="#D9DCDF", superficie="#F5F6F7", texto="#263238", texto_sec="#5F6B70",
                 cabecera="#37474F", cabecera_txt="#FFFFFF", primario="#2E7D32", secundario="#546E7A",
                 boton_txt="#FFFFFF", acento="#FDD835", acento_txt="#263238", prod_pesable="#F1EBC8",
                 prod_unidad="#FFFFFF", prod_txt="#263238", visor="#1E272C", visor_txt="#FDD835",
                 rojo="#C62828", gris="#8A949A", bajo_bg="#F8E1E1", bajo_txt="#B71C1C", positivo="#2E7D32",
                 egreso_txt="#C62828", destacado="#2E7D32"),
    "oscuro": dict(fondo="#16191C", superficie="#23272B", texto="#E3EAE4", texto_sec="#8E9A91",
                   cabecera="#0E2512", cabecera_txt="#E3EAE4", primario="#2E7D32", secundario="#2F5D34",
                   boton_txt="#FFFFFF", acento="#FDD835", acento_txt="#14290F", prod_pesable="#36331C",
                   prod_unidad="#2B3034", prod_txt="#FFE97A", visor="#081A0B", visor_txt="#FDD835",
                   rojo="#B3261E", gris="#6C7570", bajo_bg="#3B1F1F", bajo_txt="#FF8A80", positivo="#81C784",
                   egreso_txt="#FF8A80", destacado="#FDD835"),
}
T = dict(TEMAS["claro"])   # tema activo; se reemplaza en App.construir()

ACCIONES = [  # (clave en config, descripción)
    ("agregar", "Agregar producto a la venta"),
    ("cobrar", "Cobrar"),
    ("quitar", "Quitar ítem"),
    ("deseleccionar", "Deseleccionar / limpiar"),
    ("buscar", "Ir al buscador"),
    ("cancelar", "Cancelar venta"),
    ("reimprimir", "Reimprimir último ticket"),
    ("ir_pos", "Ir a la pestaña POS"),
    ("pantalla_completa", "Pantalla completa sí/no"),
]
MOD_ALT = 0x20000 if sys.platform == "win32" else 0x8
TECLAS_MODIFICADORAS = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R",
                        "Caps_Lock", "Num_Lock", "Win_L", "Win_R", "App", "ISO_Level3_Shift"}
TECLAS_EDICION = {"BackSpace", "Delete", "Left", "Right", "Home", "End", "space", "Insert"}
NOMBRES_TECLAS = {"Return": "Enter", "Delete": "Supr", "Escape": "Esc", "Control": "Ctrl", "Prior": "RePág",
                  "Next": "AvPág", "space": "Espacio", "BackSpace": "Retroceso", "Shift": "Mayús"}


# ====================================================================== atajos de teclado
def atajo_desde_evento(e):
    if e.keysym in TECLAS_MODIFICADORAS:
        return None
    mods = []
    if e.state & 0x4:
        mods.append("Control")
    if e.state & MOD_ALT:
        mods.append("Alt")
    if e.state & 0x1 and len(e.keysym) > 1:
        mods.append("Shift")
    return "-".join(mods + [e.keysym])


def secuencia_tk(atajo):
    partes = atajo.split("-")
    return "<" + "-".join(partes[:-1] + ["KeyPress", partes[-1]]) + ">"


def nombre_atajo(atajo):
    if not atajo:
        return "-"
    return "+".join(NOMBRES_TECLAS.get(p, p.upper() if len(p) == 1 else p) for p in atajo.split("-"))


def es_tecla_de_edicion(e):
    """True si la tecla, apretada dentro de un campo de texto, es para escribir (no un atajo)."""
    try:
        clase = e.widget.winfo_class()
    except (AttributeError, tk.TclError):
        return False
    if clase not in ("Entry", "TEntry", "TCombobox", "Text", "Spinbox"):
        return False
    if e.state & (0x4 | MOD_ALT):
        return False
    return len(e.keysym) == 1 or e.keysym in TECLAS_EDICION or (e.keysym.startswith("KP_") and e.keysym != "KP_Enter")


# ====================================================================== imágenes (íconos y logos)
class Imagenes:
    """Carga y achica una sola vez los íconos de img/iconos y los logos de img/."""

    def __init__(self):
        self._cache = {}

    def icono(self, cp, tam=20):
        if not cp:
            return None
        clave = (cp, tam)
        if clave not in self._cache:
            try:
                im = Image.open(iconos.ruta(cp)).convert("RGBA").resize((tam, tam), Image.LANCZOS)
            except OSError:
                return None          # todavía no se descargó: no se guarda, así aparece cuando llegue
            self._cache[clave] = ImageTk.PhotoImage(im)
        return self._cache[clave]

    def ui(self, nombre, tam=20):
        return self.icono(iconos.UI.get(nombre), tam)

    def archivo(self, nombre, alto):
        clave = (nombre, alto)
        if clave not in self._cache:
            try:
                im = Image.open(os.path.join(datos.BASE, "img", nombre)).convert("RGBA")
            except OSError:
                return None
            im = im.resize((max(1, round(im.width * alto / im.height)), alto), Image.LANCZOS)
            self._cache[clave] = ImageTk.PhotoImage(im)
        return self._cache[clave]


IMG = None   # se crea en App (necesita la ventana principal)


# ====================================================================== helpers de UI
def boton(padre, texto, comando, bg=None, fg=None, size=12, icono=None, tam_icono=None, **kw):
    img = IMG.ui(icono, tam_icono or size + 8) if (IMG and icono) else None
    extra = {"image": img, "compound": "left"} if img else {}
    return tk.Button(padre, text=(" " + texto) if img and texto else texto, command=comando, bg=bg or T["primario"],
                     fg=fg or T["boton_txt"], activebackground=T["acento"], activeforeground=T["acento_txt"],
                     font=(F, size, "bold"), relief="flat", cursor="hand2", padx=10, pady=6, bd=0, **extra, **kw)


def etiqueta(padre, texto="", size=11, bold=False, bg=None, fg=None, **kw):
    return tk.Label(padre, text=texto, bg=bg or T["fondo"], fg=fg or T["texto"],
                    font=(F, size, "bold" if bold else "normal"), **kw)


def entrada(padre, var, ancho=20, size=12, **kw):
    return tk.Entry(padre, textvariable=var, width=ancho, font=(F, size), relief="solid", bd=1,
                    bg=T["superficie"], fg=T["texto"], insertbackground=T["texto"],
                    disabledbackground=T["fondo"], disabledforeground=T["texto_sec"], **kw)


def casilla(padre, texto, var, size=11, bold=False):
    return tk.Checkbutton(padre, text=texto, variable=var, bg=T["fondo"], fg=T["texto"], selectcolor=T["superficie"],
                          activebackground=T["fondo"], activeforeground=T["texto"],
                          font=(F, size, "bold" if bold else "normal"))


def marco(padre, **kw):
    return tk.Frame(padre, bg=kw.pop("bg", T["fondo"]), **kw)


def tabla(padre, columnas):
    """columnas: [(id, título, ancho, alineación)]"""
    frame = marco(padre)
    tv = ttk.Treeview(frame, columns=[c[0] for c in columnas], show="headings", selectmode="browse")
    for id_, tit, ancho, anc in columnas:
        tv.heading(id_, text=tit)
        tv.column(id_, width=ancho, anchor=anc)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frame, tv


def pedir_numero(texto, campo, padre):
    try:
        return num(texto)
    except ValueError:
        messagebox.showerror("Dato inválido", f"'{campo}' tiene que ser un número.", parent=padre)
        return None


class Dialogo(tk.Toplevel):
    def __init__(self, padre, titulo, escape_cierra=True):
        super().__init__(padre)
        self.title(titulo)
        self.configure(bg=T["fondo"], padx=20, pady=16)
        self.transient(padre)
        self.resizable(False, False)
        self.resultado = None
        if escape_cierra:
            self.bind("<Escape>", lambda e: self.destroy())

    def mostrar(self):
        self.update_idletasks()
        p = self.master.winfo_toplevel()
        x = p.winfo_rootx() + (p.winfo_width() - self.winfo_width()) // 2
        y = p.winfo_rooty() + (p.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        if p.attributes("-fullscreen"):
            self.attributes("-topmost", True)
        self.grab_set()
        self.wait_window()
        return self.resultado


# ====================================================================== aplicación
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("La Verdulería de Margarita")
        try:
            self.state("zoomed")
        except tk.TclError:
            self.geometry("1280x800")
        self.minsize(1000, 640)
        global IMG
        IMG = Imagenes()
        icono_ventana = IMG.archivo("icono_64.png", 64)
        if icono_ventana:
            self.iconphoto(True, icono_ventana)

        self.cfg = datos.cargar_config()
        self.productos = datos.cargar_productos()
        self._mtime_prod = self._mtime_productos()
        self.balanza = Balanza(self.cfg["balanza"])
        self.balanza.iniciar()
        self._secuencias = []

        self.construir()
        if self.cfg["interfaz"].get("pantalla_completa"):
            self.attributes("-fullscreen", True)
            self._actualizar_boton_pc()
        self.protocol("WM_DELETE_WINDOW", self.salir)
        self._iconos_nuevos = False
        threading.Thread(target=self._bajar_iconos, daemon=True).start()
        self._reloj()

    def _bajar_iconos(self):
        """Si falta algún ícono en img/iconos lo baja del CDN (una vez; después funciona sin internet)."""
        if iconos.descargar_faltantes():
            self._iconos_nuevos = True

    # ---------- construcción / tema
    def construir(self, carrito=None, pestana=0):
        T.clear()
        T.update(TEMAS.get(self.cfg["interfaz"].get("tema"), TEMAS["claro"]))
        for w in self.winfo_children():
            w.destroy()
        self.configure(bg=T["fondo"])
        self._estilos()
        self._encabezado()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        self.pos = TabPOS(self.nb, self)
        self.tab_prod = TabProductos(self.nb, self)
        self.tab_stock = TabStock(self.nb, self)
        self.tab_caja = TabCaja(self.nb, self)
        self.tab_conf = TabConfig(self.nb, self)
        for tab, txt, ico in ((self.pos, "POS", "pos"), (self.tab_prod, "Productos", "productos"),
                              (self.tab_stock, "Stock", "stock"), (self.tab_caja, "Ventas / Caja", "caja"),
                              (self.tab_conf, "Configuración", "config")):
            img = IMG.ui(ico, 22)
            self.nb.add(tab, text=(" " + txt) if img else txt, image=img or "", compound="left")
        self.nb.bind("<<NotebookTabChanged>>", self._cambio_tab)
        if carrito:
            self.pos.carrito = carrito
            self.pos._dibujar_carrito()
        self.nb.select(pestana)
        self.aplicar_atajos()

    def reconstruir(self):
        """Vuelve a armar la pantalla (cambio de tema o de atajos) sin perder la venta en curso."""
        self.construir(carrito=self.pos.carrito, pestana=self.nb.index(self.nb.select()))

    def _estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=T["fondo"], foreground=T["texto"])
        s.configure("TNotebook", background=T["fondo"], borderwidth=0)
        s.configure("TNotebook.Tab", font=(F, 13, "bold"), padding=(22, 8), background=T["secundario"],
                    foreground=T["boton_txt"], borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", T["acento"])], foreground=[("selected", T["acento_txt"])])
        s.configure("Sub.TNotebook", background=T["fondo"], borderwidth=0)
        s.configure("Sub.TNotebook.Tab", font=(F, 11, "bold"), padding=(14, 5), background=T["secundario"],
                    foreground=T["boton_txt"])
        s.map("Sub.TNotebook.Tab", background=[("selected", T["acento"])], foreground=[("selected", T["acento_txt"])])
        s.configure("Treeview", font=(F, 12), rowheight=30, background=T["superficie"],
                    fieldbackground=T["superficie"], foreground=T["texto"], borderwidth=0)
        s.configure("Treeview.Heading", font=(F, 11, "bold"), background=T["primario"], foreground=T["boton_txt"],
                    relief="flat")
        s.map("Treeview.Heading", background=[("active", T["cabecera"])])
        s.map("Treeview", background=[("selected", T["acento"])], foreground=[("selected", T["acento_txt"])])
        s.configure("TCombobox", padding=4, fieldbackground=T["superficie"], background=T["secundario"],
                    foreground=T["texto"], arrowcolor=T["boton_txt"])
        s.map("TCombobox", fieldbackground=[("readonly", T["superficie"])], foreground=[("readonly", T["texto"])],
              selectbackground=[("readonly", T["superficie"])], selectforeground=[("readonly", T["texto"])])
        s.configure("Vertical.TScrollbar", background=T["secundario"], troughcolor=T["fondo"],
                    arrowcolor=T["boton_txt"], bordercolor=T["fondo"])
        s.configure("TLabelframe", background=T["fondo"], bordercolor=T["secundario"])
        s.configure("TLabelframe.Label", background=T["fondo"], foreground=T["texto"], font=(F, 12, "bold"))
        self.option_add("*TCombobox*Listbox.background", T["superficie"])
        self.option_add("*TCombobox*Listbox.foreground", T["texto"])
        self.option_add("*TCombobox*Listbox.selectBackground", T["acento"])
        self.option_add("*TCombobox*Listbox.selectForeground", T["acento_txt"])

    def _encabezado(self):
        h = tk.Frame(self, bg=T["cabecera"])
        h.pack(fill="x")
        logo = IMG.archivo("icono.png", 54)
        if logo:
            tk.Label(h, image=logo, bg=T["cabecera"]).pack(side="left", padx=(16, 0), pady=6)
        neg = self.cfg["negocio"]
        tk.Label(h, text=neg["nombre"], font=(F, 24, "bold"), bg=T["cabecera"], fg=T["acento"]).pack(side="left", padx=(10, 10), pady=8)
        tk.Label(h, text=neg.get("linea1", ""), font=(F, 12), bg=T["cabecera"], fg=T["cabecera_txt"]).pack(side="left", pady=(12, 0))
        self.lbl_reloj = tk.Label(h, font=(F, 14, "bold"), bg=T["cabecera"], fg=T["cabecera_txt"])
        self.lbl_reloj.pack(side="right", padx=(10, 20))
        self.btn_pc = boton(h, "", self.alternar_pantalla_completa, bg=T["cabecera"], fg=T["cabecera_txt"], size=10, icono="pantalla")
        self.btn_pc.pack(side="right", padx=4)
        self.lbl_bal = tk.Label(h, font=(F, 11), bg=T["cabecera"], fg=T["acento"])
        self.lbl_bal.pack(side="right", padx=10)
        self._actualizar_boton_pc()

    def _reloj(self):
        try:
            self.lbl_reloj.config(text=datetime.now().strftime("%d/%m/%Y  %H:%M"))
            b = self.balanza
            if not b.activa:
                self.lbl_bal.config(text="Balanza: desactivada (peso manual)")
            elif b.error:
                self.lbl_bal.config(text=f"Balanza: {b.error[:60]}")
            else:
                self.lbl_bal.config(text=f"Balanza: conectada en {b.cfg['puerto']}")
            # si el panel web cambió productos/precios, los recargamos
            if self._mtime_productos() != self._mtime_prod:
                self.productos_cambiaron()
            if self._iconos_nuevos:
                self._iconos_nuevos = False
                self.reconstruir()
        except tk.TclError:
            pass
        self.after(1000, self._reloj)

    @staticmethod
    def _mtime_productos():
        try:
            return os.path.getmtime(datos.ARCH_PRODUCTOS)
        except OSError:
            return None

    def _cambio_tab(self, _e=None):
        actual = self.nametowidget(self.nb.select())
        if hasattr(actual, "al_mostrar"):
            actual.al_mostrar()

    # ---------- atajos y pantalla completa
    def tecla(self, accion):
        return nombre_atajo(self.cfg["atajos"].get(accion, ""))

    def aplicar_atajos(self):
        for seq in self._secuencias:
            self.unbind(seq)
        self._secuencias = []
        for accion, atajo in self.cfg["atajos"].items():
            if not atajo:
                continue
            seq = secuencia_tk(atajo)
            try:
                self.bind(seq, lambda e, a=accion: self._atajo(a, e))
                self._secuencias.append(seq)
            except tk.TclError:
                pass   # atajo inválido escrito a mano en config.json

    def _atajo(self, accion, e):
        if es_tecla_de_edicion(e):
            return None
        if accion == "pantalla_completa":
            self.alternar_pantalla_completa()
            return "break"
        if accion == "ir_pos":
            self.nb.select(self.pos)
            self.pos.enfocar_buscar()
            return "break"
        if self.nb.select() != str(self.pos):
            return None
        {"agregar": self.pos.agregar, "cobrar": self.pos.cobrar, "quitar": self.pos.quitar,
         "deseleccionar": self.pos.deseleccionar, "buscar": self.pos.enfocar_buscar,
         "cancelar": self.pos.cancelar, "reimprimir": self.pos.reimprimir_ultimo}[accion]()
        return "break"

    def alternar_pantalla_completa(self):
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))
        self._actualizar_boton_pc()

    def _actualizar_boton_pc(self):
        texto = "Salir de pantalla completa" if self.attributes("-fullscreen") else "Pantalla completa"
        self.btn_pc.config(text=f" {texto} [{self.tecla('pantalla_completa')}]")

    # ---------- comunes
    def productos_cambiaron(self):
        self.productos = datos.cargar_productos()
        self._mtime_prod = self._mtime_productos()
        self.pos.refrescar()
        self.tab_prod.refrescar()
        self.tab_stock.refrescar()

    def imprimir_ticket(self, venta, reimpresion=False):
        texto = impresora.armar_ticket(venta, self.cfg, reimpresion)
        try:
            impresora.imprimir(texto, self.cfg["impresora"], self.balanza)
            return True
        except Exception as e:
            messagebox.showerror("Impresora", f"No se pudo imprimir el ticket:\n{e}", parent=self)
            return False

    def salir(self):
        self.balanza.detener()
        self.destroy()


# ====================================================================== POS
class TabPOS(tk.Frame):
    COLUMNAS_GRILLA = 4

    def __init__(self, padre, app):
        super().__init__(padre, bg=T["fondo"])
        self.app = app
        self.carrito = []
        self.sel = None
        self._botones = {}
        self.columnconfigure(0, weight=5)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(0, weight=1)
        tec = app.tecla

        # ---------- izquierda: búsqueda y grilla de productos
        izq = marco(self)
        izq.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        fb = marco(izq)
        fb.pack(fill="x")
        etiqueta(fb, f"Buscar / código [{tec('buscar')}]:", 12, True).pack(side="left")
        self.var_buscar = tk.StringVar()
        self.var_buscar.trace_add("write", lambda *a: self._dibujar_grilla())
        self.ent_buscar = entrada(fb, self.var_buscar, size=16)
        self.ent_buscar.pack(side="left", fill="x", expand=True, padx=8)
        self.ent_buscar.bind("<Return>", self._buscar_enter)
        boton(fb, "Limpiar", lambda: self.var_buscar.set(""), bg=T["secundario"], icono="limpiar").pack(side="left")

        cont = marco(izq)
        cont.pack(fill="both", expand=True, pady=(8, 0))
        self.canvas = tk.Canvas(cont, bg=T["fondo"], highlightthickness=0)
        sb = ttk.Scrollbar(cont, orient="vertical", command=self.canvas.yview)
        self.grilla = marco(self.canvas)
        self.grilla.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.grilla, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._rueda))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # ---------- derecha: visor de balanza, carrito y total
        der = marco(self)
        der.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

        cab = T["cabecera"]
        visor = tk.Frame(der, bg=cab, padx=14, pady=8)
        visor.pack(fill="x")
        fila_prod = tk.Frame(visor, bg=cab)
        fila_prod.pack(fill="x")
        self.lbl_prod = tk.Label(fila_prod, text="Elegí un producto", font=(F, 18, "bold"), bg=cab, fg=T["acento"], anchor="w")
        self.lbl_prod.pack(side="left")
        self.lbl_precio = tk.Label(fila_prod, text="", font=(F, 12), bg=cab, fg=T["cabecera_txt"], anchor="e")
        self.lbl_precio.pack(side="right")
        self.lbl_peso = tk.Label(visor, text="0,000 kg", font=("Consolas", 38, "bold"), bg=T["visor"],
                                 fg=T["visor_txt"], anchor="e", padx=14)
        self.lbl_peso.pack(fill="x", pady=(4, 0))
        self.lbl_estado = tk.Label(visor, text="", font=(F, 10), bg=cab, fg=T["cabecera_txt"], anchor="e")
        self.lbl_estado.pack(fill="x")
        fila = tk.Frame(visor, bg=cab)
        fila.pack(fill="x")
        tk.Label(fila, text="Cantidad / peso manual:", font=(F, 11), bg=cab, fg=T["cabecera_txt"]).pack(side="left")
        self.var_cant = tk.StringVar()
        self.ent_cant = entrada(fila, self.var_cant, ancho=8, size=16, justify="right")
        self.ent_cant.pack(side="left", padx=8)
        boton(fila, f"AGREGAR [{tec('agregar')}]", self.agregar, bg=T["acento"], fg=T["acento_txt"], size=13, icono="agregar").pack(side="right")
        self.lbl_importe = tk.Label(fila, text=pesos(0), font=(F, 22, "bold"), bg=cab, fg=T["cabecera_txt"])
        self.lbl_importe.pack(side="right", padx=10)

        # los de abajo se empaquetan primero para que la lista sea la que se achica en pantallas chicas
        self.lbl_msj = etiqueta(der, "", 12, True)
        self.lbl_msj.pack(side="bottom", fill="x", pady=(4, 0))
        fbtn = marco(der)
        fbtn.pack(side="bottom", fill="x", pady=(6, 0))
        fbtn.columnconfigure((0, 1, 2), weight=1)
        boton(fbtn, f"Quitar ítem [{tec('quitar')}]", self.quitar, bg=T["secundario"], size=11, icono="quitar").grid(row=0, column=0, sticky="ew", padx=(0, 3))
        boton(fbtn, f"Reimprimir último [{tec('reimprimir')}]", self.reimprimir_ultimo, bg=T["secundario"], size=11, icono="reimprimir").grid(row=0, column=1, sticky="ew", padx=3)
        boton(fbtn, f"Cancelar venta [{tec('cancelar')}]", self.cancelar, bg=T["rojo"], size=11, icono="cancelar").grid(row=0, column=2, sticky="ew", padx=(3, 0))
        ft = tk.Frame(der, bg=T["acento"], padx=12, pady=4)
        ft.pack(side="bottom", fill="x")
        tk.Label(ft, text="TOTAL", font=(F, 20, "bold"), bg=T["acento"], fg=T["acento_txt"]).pack(side="left")
        self.lbl_total = tk.Label(ft, text=pesos(0), font=(F, 28, "bold"), bg=T["acento"], fg=T["acento_txt"])
        self.lbl_total.pack(side="left", padx=16)
        boton(ft, f"COBRAR [{tec('cobrar')}]", self.cobrar, bg=cab, fg=T["acento"], size=16, icono="cobrar", tam_icono=30).pack(side="right")

        frame, self.tv = tabla(der, [("prod", "Producto", 200, "w"), ("cant", "Cantidad", 100, "e"),
                                      ("precio", "Precio", 100, "e"), ("imp", "Importe", 110, "e")])
        frame.pack(fill="both", expand=True, pady=6)

        self.refrescar()
        self._tick()

    # ---------- productos
    def al_mostrar(self):
        self.ent_buscar.focus_set()

    def enfocar_buscar(self):
        self.ent_buscar.focus_set()
        self.ent_buscar.select_range(0, "end")

    def refrescar(self):
        if self.sel:
            self.sel = next((p for p in self.app.productos if p["codigo"] == self.sel["codigo"]), None)
        self._dibujar_grilla()

    def _visibles(self):
        q = self.var_buscar.get().strip().lower()
        return [p for p in self.app.productos if p.get("activo", True)
                and (not q or q in p["nombre"].lower() or q == str(p["codigo"]).lower())]

    def _dibujar_grilla(self):
        for w in self.grilla.winfo_children():
            w.destroy()
        self._botones = {}
        n = self.COLUMNAS_GRILLA
        for i in range(n):
            self.grilla.columnconfigure(i, weight=1, uniform="g")
        for i, p in enumerate(sorted(self._visibles(), key=lambda x: x["nombre"].lower())):
            unidad = "/kg" if p["pesable"] else " c/u"
            img = IMG.icono(iconos.de_producto(p), 44)
            b = tk.Button(self.grilla, text=f"{p['nombre']}\n{pesos(p['precio'])}{unidad}",
                          command=lambda p=p: self.seleccionar(p), font=(F, 11, "bold"),
                          relief="flat", bd=0, wraplength=170, cursor="hand2", pady=6,
                          activebackground=T["acento"], activeforeground=T["acento_txt"],
                          **({"image": img, "compound": "top"} if img else {"height": 3}))
            b.grid(row=i // n, column=i % n, sticky="nsew", padx=4, pady=4)
            self._botones[p["codigo"]] = (b, p)
        self._colorear_botones()

    def _colorear_botones(self):
        for cod, (b, p) in self._botones.items():
            if self.sel and cod == self.sel["codigo"]:
                b.config(bg=T["acento"], fg=T["acento_txt"])
            else:
                b.config(bg=T["prod_pesable"] if p["pesable"] else T["prod_unidad"], fg=T["prod_txt"])

    def _rueda(self, e):
        try:
            self.canvas.yview_scroll(int(-e.delta / 120), "units")
        except tk.TclError:
            pass

    def _buscar_enter(self, _e):
        visibles = self._visibles()
        q = self.var_buscar.get().strip().lower()
        exacto = [p for p in visibles if str(p["codigo"]).lower() == q]
        if q and (exacto or len(visibles) == 1):
            self.seleccionar((exacto or visibles)[0])
        elif self.sel:
            self.agregar()
        return "break"

    def seleccionar(self, p):
        self.sel = p
        self.var_cant.set("")
        img = IMG.icono(iconos.de_producto(p), 30)
        self.lbl_prod.config(text=(" " + p["nombre"]) if img else p["nombre"], image=img or "", compound="left")
        unidad = "por kg" if p["pesable"] else "por unidad"
        self.lbl_precio.config(text=f"{pesos(p['precio'])} {unidad}  ·  stock {p.get('stock', 0):g}")
        self._colorear_botones()
        if p["pesable"] and self.app.balanza.activa:
            self.focus_set()          # Enter agrega con el peso de la balanza
        else:
            self.var_cant.set("" if p["pesable"] else "1")
            self.ent_cant.focus_set()
            self.ent_cant.select_range(0, "end")

    def deseleccionar(self):
        self.sel = None
        self.var_cant.set("")
        self.lbl_prod.config(text="Elegí un producto", image="")
        self.lbl_precio.config(text="")
        self._colorear_botones()
        self.ent_buscar.focus_set()

    # ---------- balanza
    def _cantidad(self):
        """Lo escrito a mano tiene prioridad; si no, el peso de la balanza (pesables) o 1 (unidades)."""
        t = self.var_cant.get().strip()
        if t:
            return num(t)
        if self.sel and self.sel["pesable"]:
            return self.app.balanza.peso if self.app.balanza.activa else None
        return 1

    def _tick(self):
        if not self.winfo_exists():
            return          # la pantalla se reconstruyó (cambio de tema)
        b = self.app.balanza
        try:
            c = self._cantidad()
        except ValueError:
            c = None
        if self.sel and not self.sel["pesable"]:
            self.lbl_peso.config(text=f"{c:g} u" if c else "-- u")
            self.lbl_estado.config(text="producto por unidad")
        elif self.var_cant.get().strip():
            self.lbl_peso.config(text=kg(c) if c is not None else "--- kg")
            self.lbl_estado.config(text="peso manual")
        elif b.activa:
            self.lbl_peso.config(text=kg(b.peso) if b.peso is not None else "--- kg")
            if b.peso is None:
                self.lbl_estado.config(text=b.error or "esperando balanza...")
            else:
                self.lbl_estado.config(text="ESTABLE" if b.estable else "pesando...")
        else:
            self.lbl_peso.config(text="0,000 kg")
            self.lbl_estado.config(text="balanza desactivada: escribí el peso a mano")
        imp = round(c * self.sel["precio"], 2) if self.sel and c else 0
        self.lbl_importe.config(text=pesos(imp))
        self.after(200, self._tick)

    # ---------- carrito
    def agregar(self):
        if not self.sel:
            self.lbl_msj.config(text="Primero elegí un producto.", fg=T["rojo"])
            return
        p = self.sel
        try:
            c = self._cantidad()
        except ValueError:
            messagebox.showerror("Cantidad", "La cantidad/peso escrito no es un número.", parent=self)
            return
        if not c or c <= 0:
            msg = "Apoyá el producto en la balanza o escribí el peso." if p["pesable"] else "Cantidad inválida."
            self.lbl_msj.config(text=msg, fg=T["rojo"])
            return
        c = round(c, 3)
        self.carrito.append({"codigo": p["codigo"], "nombre": p["nombre"], "pesable": p["pesable"],
                             "cantidad": c, "precio": p["precio"], "costo": p.get("costo", 0),
                             "importe": round(c * p["precio"], 2)})
        self._dibujar_carrito()
        self.lbl_msj.config(text=f"Agregado: {p['nombre']} {cantidad_txt(self.carrito[-1])}", fg=T["texto"])
        self.var_buscar.set("")
        self.deseleccionar()

    def _total(self):
        return round(sum(i["importe"] for i in self.carrito), 2)

    def _dibujar_carrito(self):
        self.tv.delete(*self.tv.get_children())
        for n, it in enumerate(self.carrito):
            self.tv.insert("", "end", iid=str(n), values=(it["nombre"], cantidad_txt(it), pesos(it["precio"]), pesos(it["importe"])))
        if self.carrito:
            self.tv.see(str(len(self.carrito) - 1))
        self.lbl_total.config(text=pesos(self._total()))

    def quitar(self):
        sel = self.tv.selection()
        if sel:
            del self.carrito[int(sel[0])]
        elif self.carrito:
            self.carrito.pop()
        self._dibujar_carrito()

    def cancelar(self):
        if self.carrito and messagebox.askyesno("Cancelar venta", "¿Vaciar la venta actual?", parent=self):
            self.carrito = []
            self._dibujar_carrito()
            self.lbl_msj.config(text="Venta cancelada.", fg=T["rojo"])
            self.deseleccionar()

    def cobrar(self):
        if not self.carrito:
            self.lbl_msj.config(text="No hay productos en la venta.", fg=T["rojo"])
            return
        total = self._total()
        pago = DialogoCobro(self.app, total).mostrar()
        if not pago:
            return
        imprimir = pago.pop("imprimir")
        venta = {"items": self.carrito, "total": total,
                 "costo_total": round(sum(i["cantidad"] * i["costo"] for i in self.carrito), 2), "pago": pago}
        try:
            venta = datos.registrar_venta(venta)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la venta:\n{e}", parent=self)
            return
        if imprimir:
            self.app.imprimir_ticket(venta)
        self.carrito = []
        self._dibujar_carrito()
        self.app.productos_cambiaron()
        self.app.tab_caja.refrescar()
        vuelto = f"  ·  Vuelto: {pesos(pago['vuelto'])}" if pago.get("paga_con") else ""
        self.lbl_msj.config(text=f"Venta #{venta['numero']} registrada ({pesos(total)}){vuelto}", fg=T["texto"])
        self.deseleccionar()

    def reimprimir_ultimo(self):
        v = datos.ultima_venta()
        if not v:
            self.lbl_msj.config(text="Todavía no hay ventas.", fg=T["rojo"])
            return
        if self.app.imprimir_ticket(v, reimpresion=True):
            self.lbl_msj.config(text=f"Reimpreso ticket #{v['numero']}", fg=T["texto"])


class DialogoCobro(Dialogo):
    def __init__(self, padre, total):
        super().__init__(padre, "Cobrar")
        self.total = total
        etiqueta(self, "Total a cobrar", 14).grid(row=0, column=0, columnspan=2)
        tk.Label(self, text=pesos(total), font=(F, 36, "bold"), bg=T["acento"], fg=T["acento_txt"], padx=20).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.medio = "Efectivo"
        self._btn_medios = {}
        fm = marco(self)
        fm.grid(row=2, column=0, columnspan=2)
        for i, m in enumerate(MEDIOS):
            b = tk.Button(fm, text=m, font=(F, 12, "bold"), relief="flat", bd=0, padx=10, pady=6, cursor="hand2",
                          command=lambda m=m: self._medio(m))
            b.grid(row=0, column=i, padx=2)
            self._btn_medios[m] = b
        etiqueta(self, "Paga con:", 14).grid(row=3, column=0, sticky="e", pady=12)
        self.var_paga = tk.StringVar()
        self.ent_paga = entrada(self, self.var_paga, ancho=10, size=20, justify="right")
        self.ent_paga.grid(row=3, column=1, sticky="w", padx=8)
        self.var_paga.trace_add("write", lambda *a: self._vuelto())
        self.lbl_vuelto = etiqueta(self, "Vuelto: -", 18, True)
        self.lbl_vuelto.grid(row=4, column=0, columnspan=2)
        self.var_imp = tk.BooleanVar(value=True)
        casilla(self, "Imprimir ticket", self.var_imp, 12).grid(row=5, column=0, columnspan=2, pady=8)
        fb = marco(self)
        fb.grid(row=6, column=0, columnspan=2)
        boton(fb, "Confirmar [Enter]", self.confirmar, size=14, icono="ok").pack(side="left", padx=5)
        boton(fb, "Volver [Esc]", self.destroy, bg=T["rojo"], size=14, icono="atras").pack(side="left", padx=5)
        self.bind("<Return>", lambda e: self.confirmar())
        self._medio("Efectivo")

    def _paga(self):
        t = self.var_paga.get().strip()
        return num(t) if t else None

    def _vuelto(self):
        try:
            p = self._paga()
        except ValueError:
            self.lbl_vuelto.config(text="Monto inválido", fg=T["rojo"])
            return
        if p is None:
            self.lbl_vuelto.config(text="Vuelto: -", fg=T["texto"])
        elif p < self.total:
            self.lbl_vuelto.config(text=f"Faltan {pesos(self.total - p)}", fg=T["rojo"])
        else:
            self.lbl_vuelto.config(text=f"Vuelto: {pesos(p - self.total)}", fg=T["texto"])

    def _medio(self, medio):
        self.medio = medio
        for m, b in self._btn_medios.items():
            if m == medio:
                b.config(bg=T["acento"], fg=T["acento_txt"], activebackground=T["acento"])
            else:
                b.config(bg=T["superficie"], fg=T["texto"], activebackground=T["acento"])
        if medio == "Efectivo":
            self.ent_paga.config(state="normal")
            self.ent_paga.focus_set()
        else:
            self.var_paga.set("")
            self.ent_paga.config(state="disabled")
            self.focus_set()

    def confirmar(self):
        paga, vuelto = None, 0
        if self.medio == "Efectivo":
            try:
                paga = self._paga()
            except ValueError:
                messagebox.showerror("Cobrar", "El monto con que paga no es válido.", parent=self)
                return
            if paga is not None:
                if paga + 0.001 < self.total:
                    messagebox.showerror("Cobrar", "El monto no alcanza.", parent=self)
                    return
                vuelto = round(paga - self.total, 2)
        self.resultado = {"medio": self.medio, "paga_con": paga, "vuelto": vuelto, "imprimir": self.var_imp.get()}
        self.destroy()


# ====================================================================== Productos
class TabProductos(tk.Frame):
    def __init__(self, padre, app):
        super().__init__(padre, bg=T["fondo"])
        self.app = app
        self.editando = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        frame, self.tv = tabla(self, [("cod", "Código", 70, "center"), ("nom", "Nombre", 240, "w"),
                                       ("tipo", "Se vende", 90, "center"), ("precio", "Precio", 110, "e"),
                                       ("costo", "Costo", 110, "e"), ("margen", "Margen", 80, "e"),
                                       ("activo", "En POS", 70, "center")])
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.tv.tag_configure("inactivo", foreground=T["gris"])
        self.tv.bind("<<TreeviewSelect>>", self._cargar)

        form = marco(self, padx=10)
        form.grid(row=0, column=1, sticky="n", pady=10)
        etiqueta(form, "Producto", 16, True).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.v = {k: tk.StringVar() for k in ("codigo", "nombre", "precio", "costo", "stock", "stock_min")}
        self.v_pesable = tk.BooleanVar(value=True)
        self.v_activo = tk.BooleanVar(value=True)
        filas = [("codigo", "Código"), ("nombre", "Nombre"), ("precio", "Precio de venta $"),
                 ("costo", "Costo $"), ("stock", "Stock inicial"), ("stock_min", "Stock mínimo")]
        self.ent = {}
        for i, (k, txt) in enumerate(filas, start=1):
            etiqueta(form, txt, 12).grid(row=i, column=0, sticky="e", pady=4)
            self.ent[k] = entrada(form, self.v[k], ancho=24)
            self.ent[k].grid(row=i, column=1, sticky="w", padx=8, pady=4)
        casilla(form, "Pesable (se vende por kg)", self.v_pesable, 12).grid(row=7, column=1, sticky="w")
        casilla(form, "Activo (aparece en el POS)", self.v_activo, 12).grid(row=8, column=1, sticky="w")
        self.lbl_margen = etiqueta(form, "", 12, True)
        self.lbl_margen.grid(row=9, column=1, sticky="w", pady=6)
        self.lbl_nota = etiqueta(form, "", 10, fg=T["texto_sec"])
        self.lbl_nota.grid(row=10, column=0, columnspan=2, sticky="w")
        self.v_icono = tk.StringVar()
        fi = marco(form)
        fi.grid(row=12, column=0, columnspan=2, sticky="w", pady=(4, 0))
        etiqueta(fi, "Ícono:", 12).pack(side="left")
        self.lbl_icono = tk.Label(fi, bg=T["fondo"], fg=T["texto_sec"])
        self.lbl_icono.pack(side="left", padx=8)
        boton(fi, "Elegir ícono", self._elegir_icono, bg=T["secundario"], size=10).pack(side="left")
        boton(fi, "Automático", lambda: self._poner_icono(""), bg=T["secundario"], size=10).pack(side="left", padx=4)
        self.v["nombre"].trace_add("write", lambda *a: self._poner_icono(self.v_icono.get()))
        for k in ("precio", "costo"):
            self.v[k].trace_add("write", lambda *a: self._margen())
        fb = marco(form)
        fb.grid(row=11, column=0, columnspan=2, pady=14)
        boton(fb, "Nuevo", self.nuevo, bg=T["secundario"], icono="nuevo").pack(side="left", padx=4)
        boton(fb, "Guardar", self.guardar, icono="guardar").pack(side="left", padx=4)
        boton(fb, "Eliminar", self.eliminar, bg=T["rojo"], icono="eliminar").pack(side="left", padx=4)
        self.refrescar()
        self.nuevo()

    def refrescar(self):
        self.tv.delete(*self.tv.get_children())
        for p in sorted(self.app.productos, key=lambda x: x["nombre"].lower()):
            margen = f"{(p['precio'] - p['costo']) / p['costo'] * 100:.0f}%" if p.get("costo") else "-"
            self.tv.insert("", "end", iid=p["codigo"], tags=() if p.get("activo", True) else ("inactivo",),
                           values=(p["codigo"], p["nombre"], "kg" if p["pesable"] else "unidad", pesos(p["precio"]),
                                   pesos(p.get("costo", 0)), margen, "Sí" if p.get("activo", True) else "No"))
        if self.editando and self.tv.exists(self.editando):
            self.tv.selection_set(self.editando)

    def _poner_icono(self, cp):
        self.v_icono.set(cp)
        img = IMG.icono(cp or iconos.adivinar(self.v["nombre"].get()), 40)
        self.lbl_icono.config(image=img or "", text="" if img else "(sin ícono)")

    def _elegir_icono(self):
        cp = DialogoIcono(self.app).mostrar()
        if cp is not None:
            self._poner_icono(cp)

    def _margen(self):
        try:
            pr, co = num(self.v["precio"].get()), num(self.v["costo"].get())
            self.lbl_margen.config(text=f"Ganancia: {pesos(pr - co)}  ({(pr - co) / co * 100:.0f}%)" if co else "")
        except ValueError:
            self.lbl_margen.config(text="")

    def nuevo(self):
        self.editando = None
        self.tv.selection_remove(self.tv.selection())
        for k in self.v:
            self.v[k].set("")
        self.v["codigo"].set(datos.siguiente_codigo(self.app.productos))
        self.v["stock"].set("0")
        self.v["stock_min"].set("0")
        self.v_pesable.set(True)
        self.v_activo.set(True)
        self._poner_icono("")
        self.ent["stock"].config(state="normal")
        self.lbl_nota.config(text="")
        self.ent["nombre"].focus_set()

    def _cargar(self, _e=None):
        sel = self.tv.selection()
        if not sel or sel[0] == self.editando:
            return
        p = next((x for x in self.app.productos if x["codigo"] == sel[0]), None)
        if not p:
            return
        self.editando = p["codigo"]
        self.ent["stock"].config(state="normal")
        for k in ("codigo", "nombre"):
            self.v[k].set(p[k])
        for k in ("precio", "costo", "stock", "stock_min"):
            self.v[k].set(f"{p.get(k, 0):g}")
        self.v_pesable.set(p["pesable"])
        self.v_activo.set(p.get("activo", True))
        self._poner_icono(p.get("icono", ""))
        self.ent["stock"].config(state="disabled")
        self.lbl_nota.config(text="El stock se modifica desde la pestaña Stock.")

    def guardar(self):
        valores = {}
        for k, txt in (("precio", "Precio"), ("costo", "Costo"), ("stock", "Stock"), ("stock_min", "Stock mínimo")):
            valores[k] = pedir_numero(self.v[k].get().strip() or "0", txt, self)
            if valores[k] is None:
                return
        prod = dict(valores, codigo=self.v["codigo"].get(), nombre=self.v["nombre"].get(),
                    pesable=self.v_pesable.get(), activo=self.v_activo.get(), icono=self.v_icono.get())
        try:
            guardado = datos.guardar_producto(prod, self.editando)
        except ValueError as e:
            messagebox.showerror("Producto", str(e), parent=self)
            return
        self.editando = guardado["codigo"]
        self.app.productos_cambiaron()
        self.tv.see(self.editando)

    def eliminar(self):
        if not self.editando:
            return
        if not messagebox.askyesno("Eliminar", "¿Eliminar este producto?\n(Las ventas anteriores no se modifican. "
                                   "Si solo querés ocultarlo del POS, destildá 'Activo'.)", parent=self):
            return
        datos.eliminar_producto(self.editando)
        self.editando = None
        self.app.productos_cambiaron()
        self.nuevo()


# ====================================================================== Stock
class TabStock(tk.Frame):
    def __init__(self, padre, app):
        super().__init__(padre, bg=T["fondo"])
        self.app = app
        top = marco(self)
        top.pack(fill="x", padx=10, pady=(10, 0))
        boton(top, "Ingreso de mercadería", self.ingreso, icono="ingreso_merc").pack(side="left")
        boton(top, "Ajuste / merma", self.ajuste, bg=T["secundario"], icono="ajuste").pack(side="left", padx=8)
        self.lbl_valor = etiqueta(top, "", 13, True)
        self.lbl_valor.pack(side="right")
        frame, self.tv = tabla(self, [("cod", "Código", 70, "center"), ("nom", "Producto", 260, "w"),
                                       ("stock", "Stock", 120, "e"), ("min", "Mínimo", 100, "e"),
                                       ("costo", "Costo", 110, "e"), ("valor", "Valorizado", 130, "e"),
                                       ("estado", "Estado", 120, "center")])
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.tv.tag_configure("bajo", foreground=T["bajo_txt"], background=T["bajo_bg"])
        self.tv.bind("<Double-1>", lambda e: self.ingreso())
        self.refrescar()

    def refrescar(self):
        sel = self.tv.selection()
        self.tv.delete(*self.tv.get_children())
        total = 0
        for p in sorted(self.app.productos, key=lambda x: x["nombre"].lower()):
            u = "kg" if p["pesable"] else "u"
            valor = max(p["stock"], 0) * p.get("costo", 0)
            total += valor
            bajo = p["stock"] <= p.get("stock_min", 0)
            self.tv.insert("", "end", iid=p["codigo"], tags=("bajo",) if bajo else (),
                           values=(p["codigo"], p["nombre"], f"{p['stock']:g} {u}", f"{p.get('stock_min', 0):g} {u}",
                                   pesos(p.get("costo", 0)), pesos(valor), "REPONER" if bajo else "OK"))
        if sel and self.tv.exists(sel[0]):
            self.tv.selection_set(sel[0])
        self.lbl_valor.config(text=f"Stock valorizado al costo: {pesos(total)}")

    def _producto_sel(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Stock", "Seleccioná un producto de la lista.", parent=self)
            return None
        return next((p for p in self.app.productos if p["codigo"] == sel[0]), None)

    def ingreso(self):
        p = self._producto_sel()
        if not p:
            return
        r = DialogoIngreso(self.app, p).mostrar()
        if r:
            datos.ingreso_mercaderia(p["codigo"], r["cantidad"], r["costo"], r["egreso"], r["medio"])
            self.app.productos_cambiaron()
            self.app.tab_caja.refrescar()

    def ajuste(self):
        p = self._producto_sel()
        if not p:
            return
        u = "kg" if p["pesable"] else "unidades"
        t = simpledialog.askstring("Ajuste de stock", f"{p['nombre']}\nStock actual: {p['stock']:g} {u}\n\n"
                                   f"Stock real contado ({u}):", parent=self)
        if t is None:
            return
        nuevo = pedir_numero(t, "Stock", self)
        if nuevo is None:
            return
        motivo = simpledialog.askstring("Ajuste de stock", "Motivo (merma, rotura, conteo...):",
                                        initialvalue="Merma", parent=self) or "Ajuste"
        datos.ajustar_stock(p["codigo"], nuevo, motivo)
        self.app.productos_cambiaron()


class DialogoIngreso(Dialogo):
    def __init__(self, padre, p):
        super().__init__(padre, "Ingreso de mercadería")
        u = "kg" if p["pesable"] else "unidades"
        etiqueta(self, p["nombre"], 18, True).grid(row=0, column=0, columnspan=2, pady=(0, 10))
        self.v_cant = tk.StringVar()
        self.v_costo = tk.StringVar(value=f"{p.get('costo', 0):g}")
        self.v_egreso = tk.BooleanVar(value=True)
        self.v_medio = tk.StringVar(value="Efectivo")
        etiqueta(self, f"Cantidad ({u}):", 12).grid(row=1, column=0, sticky="e", pady=4)
        e = entrada(self, self.v_cant, 12)
        e.grid(row=1, column=1, sticky="w", padx=8)
        etiqueta(self, f"Costo por {'kg' if p['pesable'] else 'unidad'} $:", 12).grid(row=2, column=0, sticky="e", pady=4)
        entrada(self, self.v_costo, 12).grid(row=2, column=1, sticky="w", padx=8)
        casilla(self, "Registrar el pago como egreso de caja", self.v_egreso).grid(row=3, column=0, columnspan=2, pady=6)
        etiqueta(self, "Pagado con:", 12).grid(row=4, column=0, sticky="e")
        ttk.Combobox(self, textvariable=self.v_medio, values=MEDIOS, state="readonly", width=16).grid(row=4, column=1, sticky="w", padx=8)
        fb = marco(self)
        fb.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        boton(fb, "Guardar", self.ok).pack(side="left", padx=4)
        boton(fb, "Cancelar", self.destroy, bg=T["rojo"]).pack(side="left", padx=4)
        self.bind("<Return>", lambda ev: self.ok())
        e.focus_set()

    def ok(self):
        cant = pedir_numero(self.v_cant.get(), "Cantidad", self)
        costo = pedir_numero(self.v_costo.get() or "0", "Costo", self)
        if cant is None or costo is None:
            return
        self.resultado = {"cantidad": cant, "costo": costo, "egreso": self.v_egreso.get(), "medio": self.v_medio.get()}
        self.destroy()


# ====================================================================== Ventas / Caja
class TabCaja(tk.Frame):
    def __init__(self, padre, app):
        super().__init__(padre, bg=T["fondo"])
        self.app = app
        self.fecha = date.today()
        self.filas = {}

        top = marco(self)
        top.pack(fill="x", padx=10, pady=(10, 0))
        boton(top, "◀", lambda: self.mover(-1), bg=T["secundario"]).pack(side="left")
        self.v_fecha = tk.StringVar()
        e = entrada(top, self.v_fecha, 11, 14, justify="center")
        e.pack(side="left", padx=6)
        e.bind("<Return>", lambda ev: self._ir_fecha())
        boton(top, "▶", lambda: self.mover(1), bg=T["secundario"]).pack(side="left")
        boton(top, "Hoy", self.hoy, bg=T["acento"], fg=T["acento_txt"], icono="hoy").pack(side="left", padx=6)
        boton(top, "Egreso", lambda: self.movimiento("egreso"), bg=T["rojo"], icono="egreso").pack(side="right")
        boton(top, "Ingreso", lambda: self.movimiento("ingreso"), icono="ingreso").pack(side="right", padx=6)

        cuerpo = marco(self)
        cuerpo.pack(fill="both", expand=True, padx=10, pady=10)
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.rowconfigure(0, weight=1)
        frame, self.tv = tabla(cuerpo, [("hora", "Hora", 70, "center"), ("tipo", "Tipo", 120, "w"),
                                         ("det", "Detalle", 320, "w"), ("medio", "Medio", 120, "center"),
                                         ("monto", "Monto", 120, "e"), ("estado", "Estado", 100, "center")])
        frame.grid(row=0, column=0, sticky="nsew")
        self.tv.tag_configure("anulada", foreground=T["gris"])
        self.tv.tag_configure("egreso", foreground=T["egreso_txt"])
        self.tv.tag_configure("ingreso", foreground=T["positivo"])
        self.tv.bind("<Double-1>", lambda e: self.ver_ticket())

        lado = marco(cuerpo, padx=12)
        lado.grid(row=0, column=1, sticky="n")
        boton(lado, "Ver ticket", self.ver_ticket, bg=T["secundario"], icono="ticket").pack(fill="x", pady=2)
        boton(lado, "Reimprimir ticket", self.reimprimir, icono="reimprimir").pack(fill="x", pady=2)
        boton(lado, "Anular venta", self.anular, bg=T["rojo"], icono="anular").pack(fill="x", pady=2)
        resumen = tk.Frame(lado, bg=T["cabecera"], padx=14, pady=12)
        resumen.pack(fill="x", pady=(16, 0))
        tk.Label(resumen, text="Resumen del día", font=(F, 14, "bold"), bg=T["cabecera"], fg=T["acento"]).pack(anchor="w")
        self.lbl_resumen = tk.Label(resumen, font=("Consolas", 12), bg=T["cabecera"], fg=T["cabecera_txt"], justify="left")
        self.lbl_resumen.pack(anchor="w", pady=(6, 0))
        self.refrescar()

    def al_mostrar(self):
        self.refrescar()

    def mover(self, dias):
        self.fecha += timedelta(days=dias)
        self.refrescar()

    def hoy(self):
        self.fecha = date.today()
        self.refrescar()

    def _ir_fecha(self):
        try:
            self.fecha = datetime.strptime(self.v_fecha.get().strip(), "%d/%m/%Y").date()
        except ValueError:
            messagebox.showerror("Fecha", "Usá el formato dd/mm/aaaa", parent=self)
        self.refrescar()

    def refrescar(self):
        self.v_fecha.set(self.fecha.strftime("%d/%m/%Y"))
        self.tv.delete(*self.tv.get_children())
        self.filas = {}
        ventas = datos.ventas_del_dia(self.fecha)
        movs = datos.movimientos_del_dia(self.fecha)
        filas = []
        for v in ventas:
            det = ", ".join(f"{i['nombre']} {cantidad_txt(i)}" for i in v["items"])
            filas.append((v["fecha"], f"v{v['numero']}", ("anulada",) if v["estado"] == "anulada" else (),
                          (v["fecha"][11:16], f"Venta #{v['numero']}", det, v["pago"]["medio"], pesos(v["total"]),
                           "ANULADA" if v["estado"] == "anulada" else ""), v))
        for m in movs:
            signo = "-" if m["tipo"] == "egreso" else "+"
            filas.append((m["fecha"], f"m{m['id']}", (m["tipo"],),
                          (m["fecha"][11:16], m["tipo"].capitalize(), m["concepto"], m["medio"],
                           signo + pesos(m["monto"]), ""), m))
        for _f, iid, tags, vals, obj in sorted(filas, key=lambda x: x[0]):
            self.tv.insert("", "end", iid=iid, tags=tags, values=vals)
            self.filas[iid] = obj

        r = datos.resumen(self.fecha, self.fecha)
        L = [f"Ventas: {r['ventas_cantidad']}  (anuladas: {r['anuladas']})",
             f"{'Total ventas':<16}{pesos(r['ventas_total']):>14}"]
        L += [f"  {m['medio']:<14}{pesos(m['total']):>14}" for m in r["medios"]]
        L += ["", f"{'Ganancia bruta':<16}{pesos(r['ganancia']):>14}", "",
              f"{'Otros ingresos':<16}{pesos(r['ingresos']):>14}", f"{'Egresos':<16}{'-' + pesos(r['egresos']):>14}",
              "-" * 30, f"{'SALDO DEL DÍA':<16}{pesos(r['balance']):>14}",
              f"{'Efectivo caja':<16}{pesos(r['efectivo']):>14}"]
        self.lbl_resumen.config(text="\n".join(L))

    def _venta_sel(self):
        sel = self.tv.selection()
        if not sel or not sel[0].startswith("v"):
            messagebox.showinfo("Ventas", "Seleccioná una venta de la lista.", parent=self)
            return None
        return self.filas[sel[0]]

    def ver_ticket(self):
        v = self._venta_sel()
        if v:
            VistaTicket(self.app, v).mostrar()

    def reimprimir(self):
        v = self._venta_sel()
        if v:
            self.app.imprimir_ticket(v, reimpresion=True)

    def anular(self):
        v = self._venta_sel()
        if not v:
            return
        if v["estado"] == "anulada":
            messagebox.showinfo("Anular", "Esa venta ya está anulada.", parent=self)
            return
        motivo = simpledialog.askstring("Anular venta", f"Venta #{v['numero']} por {pesos(v['total'])}\n\n"
                                        "Motivo de la anulación:", parent=self)
        if motivo is None:
            return
        try:
            datos.anular_venta(v, motivo or "Sin motivo")
        except ValueError as e:
            messagebox.showerror("Anular", str(e), parent=self)
            return
        self.app.productos_cambiaron()
        self.refrescar()
        messagebox.showinfo("Anular", f"Venta #{v['numero']} anulada. Se devolvió el stock.", parent=self)

    def movimiento(self, tipo):
        r = DialogoMovimiento(self.app, tipo).mostrar()
        if r:
            datos.registrar_movimiento(tipo, r["concepto"], r["monto"], r["medio"])
            self.hoy()


class DialogoMovimiento(Dialogo):
    def __init__(self, padre, tipo):
        super().__init__(padre, "Nuevo " + tipo)
        etiqueta(self, ("Egreso de caja" if tipo == "egreso" else "Ingreso de caja"), 16, True,
                 fg=T["egreso_txt"] if tipo == "egreso" else T["texto"]).grid(row=0, column=0, columnspan=2, pady=(0, 10))
        self.v_conc = tk.StringVar()
        self.v_monto = tk.StringVar()
        self.v_medio = tk.StringVar(value="Efectivo")
        etiqueta(self, "Concepto:", 12).grid(row=1, column=0, sticky="e", pady=4)
        e = entrada(self, self.v_conc, 28)
        e.grid(row=1, column=1, padx=8)
        etiqueta(self, "Monto $:", 12).grid(row=2, column=0, sticky="e", pady=4)
        entrada(self, self.v_monto, 12).grid(row=2, column=1, sticky="w", padx=8)
        etiqueta(self, "Medio:", 12).grid(row=3, column=0, sticky="e", pady=4)
        ttk.Combobox(self, textvariable=self.v_medio, values=MEDIOS, state="readonly", width=16).grid(row=3, column=1, sticky="w", padx=8)
        fb = marco(self)
        fb.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        boton(fb, "Guardar", self.ok).pack(side="left", padx=4)
        boton(fb, "Cancelar", self.destroy, bg=T["rojo"]).pack(side="left", padx=4)
        self.bind("<Return>", lambda ev: self.ok())
        e.focus_set()

    def ok(self):
        if not self.v_conc.get().strip():
            messagebox.showerror("Caja", "Escribí un concepto.", parent=self)
            return
        monto = pedir_numero(self.v_monto.get(), "Monto", self)
        if monto is None or monto <= 0:
            return
        self.resultado = {"concepto": self.v_conc.get().strip(), "monto": monto, "medio": self.v_medio.get()}
        self.destroy()


class VistaTicket(Dialogo):
    """Vista previa del ticket tal como sale impreso (con logo)."""

    def __init__(self, padre, venta, cfg=None):
        super().__init__(padre, f"Ticket #{venta['numero']}")
        cfg = cfg or padre.cfg
        texto = impresora.armar_ticket(venta, cfg)
        try:
            from PIL import ImageTk
            img = impresora.ticket_imagen(texto, cfg["impresora"])
            alto_max = max(300, self.winfo_screenheight() - 260)
            if img.height > alto_max:
                img = img.resize((round(img.width * alto_max / img.height), alto_max))
            self._foto = ImageTk.PhotoImage(img)
            tk.Label(self, image=self._foto, bd=0).pack()
        except Exception:
            ancho = int(cfg["impresora"]["ancho"])
            t = tk.Text(self, font=("Consolas", 11), width=ancho + 2, height=min(texto.count("\n") + 2, 30),
                        bg="white", fg="black", relief="flat", padx=8, pady=8)
            t.insert("1.0", texto)
            t.config(state="disabled")
            t.pack()
        if venta.get("anulacion"):
            etiqueta(self, f"Anulada: {venta['anulacion']['motivo']}", 11, fg=T["egreso_txt"]).pack(pady=(6, 0))
        fb = marco(self)
        fb.pack(pady=(10, 0))
        if venta.get("numero"):
            boton(fb, "Reimprimir", lambda: padre.imprimir_ticket(venta, reimpresion=True)).pack(side="left", padx=4)
        boton(fb, "Cerrar", self.destroy, bg=T["secundario"]).pack(side="left", padx=4)


class DialogoIcono(Dialogo):
    """Grilla con los íconos de frutas y verduras para elegir el de un producto."""

    def __init__(self, padre):
        super().__init__(padre, "Elegí un ícono")
        etiqueta(self, "Elegí el ícono del producto", 14, True).grid(row=0, column=0, columnspan=8, pady=(0, 10))
        for i, (cp, nombre, _) in enumerate(iconos.PRODUCTOS):
            img = IMG.icono(cp, 40)
            b = tk.Button(self, image=img or "", text=nombre, compound="top", font=(F, 9), width=86 if img else 10,
                          bg=T["superficie"], fg=T["texto"], relief="flat", bd=0, cursor="hand2", pady=4,
                          activebackground=T["acento"], command=lambda cp=cp: self._elegir(cp))
            b.grid(row=1 + i // 8, column=i % 8, padx=3, pady=3)

    def _elegir(self, cp):
        self.resultado = cp
        self.destroy()


class CapturaTecla(Dialogo):
    def __init__(self, padre, descripcion):
        super().__init__(padre, "Nuevo atajo", escape_cierra=False)
        etiqueta(self, descripcion, 14, True).pack()
        etiqueta(self, "Presioná la tecla o combinación (ej. F5, Ctrl+P)...", 12).pack(pady=12)
        self.lbl = etiqueta(self, " ", 22, True, fg=T["destacado"])
        self.lbl.pack()
        fb = marco(self)
        fb.pack(pady=(12, 0))
        boton(fb, "Usar esta tecla", self.ok).pack(side="left", padx=4)
        boton(fb, "Sin atajo", self.sin_atajo, bg=T["secundario"]).pack(side="left", padx=4)
        boton(fb, "Cancelar", self.destroy, bg=T["rojo"]).pack(side="left", padx=4)
        self.atajo = None
        self.bind("<KeyPress>", self._tecla)
        self.focus_force()

    def _tecla(self, e):
        a = atajo_desde_evento(e)
        if a:
            self.atajo = a
            self.lbl.config(text=nombre_atajo(a))
        return "break"

    def ok(self):
        if self.atajo:
            self.resultado = self.atajo
            self.destroy()

    def sin_atajo(self):
        self.resultado = ""
        self.destroy()


# ====================================================================== Configuración
class TabConfig(tk.Frame):
    def __init__(self, padre, app):
        super().__init__(padre, bg=T["fondo"])
        self.app = app
        self.vars = {}
        sub = ttk.Notebook(self, style="Sub.TNotebook")
        sub.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        general, bal, imp, web = (marco(sub, padx=10, pady=10) for _ in range(4))
        for f, t in ((general, "General y atajos"), (bal, "Balanza"), (imp, "Ticket y logo"), (web, "Servicio web")):
            sub.add(f, text=t)
        self._general(general)
        self._balanza(bal)
        self._impresora(imp)
        self._web(web)

        pie = marco(self)
        pie.pack(fill="x", padx=10, pady=8)
        boton(pie, "Guardar configuración", self.guardar, size=13, icono="guardar").pack(side="left", anchor="n")
        self.txt_det = tk.Text(pie, height=4, font=("Consolas", 10), bg=T["superficie"], fg=T["texto"], relief="flat")
        self.txt_det.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self._log("Los cambios se aplican al tocar 'Guardar configuración'.")
        self._mostrar_crudo()

    # ---------- secciones
    def _general(self, f):
        f.columnconfigure((0, 1), weight=1)
        neg = ttk.LabelFrame(f, text="Negocio (encabezado del ticket)", padding=10)
        neg.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        for i, (k, txt) in enumerate((("nombre", "Nombre"), ("linea1", "Línea 1"), ("linea2", "Línea 2 (dirección/tel)"),
                                      ("pie", "Pie del ticket"))):
            self._campo(neg, i, ("negocio", k), txt)
        inter = ttk.LabelFrame(f, text="Pantalla", padding=10)
        inter.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(10, 0))
        self._combo(inter, 0, ("interfaz", "tema"), "Tema", list(TEMAS))
        self._check(inter, 1, ("interfaz", "pantalla_completa"), "Abrir en pantalla completa")
        boton(inter, f"Pantalla completa ahora [{self.app.tecla('pantalla_completa')}]",
              self.app.alternar_pantalla_completa, bg=T["secundario"], size=10).grid(row=2, column=1, sticky="w", pady=4)

        at = ttk.LabelFrame(f, text="Atajos de teclado", padding=10)
        at.grid(row=0, column=1, rowspan=2, sticky="nsew")
        for i, (accion, desc) in enumerate(ACCIONES):
            etiqueta(at, desc, 11).grid(row=i, column=0, sticky="w", pady=2)
            tk.Label(at, text=self.app.tecla(accion), font=("Consolas", 12, "bold"), width=12,
                     bg=T["superficie"], fg=T["texto"]).grid(row=i, column=1, padx=8)
            boton(at, "Cambiar", lambda a=accion, d=desc: self._cambiar_atajo(a, d), bg=T["secundario"], size=9, icono="teclado").grid(row=i, column=2, pady=2)
        boton(at, "Restaurar predeterminados", self._atajos_defecto, bg=T["rojo"], size=10).grid(
            row=len(ACCIONES), column=0, columnspan=3, pady=(10, 0))

    def _balanza(self, f):
        f.columnconfigure(2, weight=1)
        self._check(f, 0, ("balanza", "activa"), "Usar balanza")
        self.cb_puerto_bal = self._combo(f, 1, ("balanza", "puerto"), "Puerto", puertos_disponibles())
        self._combo(f, 2, ("balanza", "baudios"), "Baudios", [1200, 2400, 4800, 9600, 19200])
        self._combo(f, 3, ("balanza", "bits"), "Bits de datos", [7, 8])
        self._combo(f, 4, ("balanza", "paridad"), "Paridad (N/E/O)", ["N", "E", "O"])
        self._combo(f, 5, ("balanza", "stop"), "Bits de stop", [1, 2])
        self._combo(f, 6, ("balanza", "modo"), "Modo", ["pedido", "continuo"])
        self._combo(f, 7, ("balanza", "comando"), "Comando de pedido", ["\\x05", "P", "W", "$", "\\r", "P\\r\\n"], editable=True)
        self._campo(f, 8, ("balanza", "divisor"), "Divisor si manda gramos")
        self._campo(f, 9, ("balanza", "intervalo_ms"), "Leer cada (ms)")
        fb = marco(f)
        fb.grid(row=10, column=0, columnspan=2, pady=(8, 0))
        boton(fb, "Actualizar puertos", self._puertos, bg=T["secundario"], size=10).pack(side="left", padx=2)
        boton(fb, "Detectar protocolo", self._detectar, bg=T["acento"], fg=T["acento_txt"], size=10, icono="balanza").pack(side="left", padx=2)
        info = marco(f, padx=20)
        info.grid(row=0, column=2, rowspan=11, sticky="nsew")
        etiqueta(info, "Lectura en vivo", 13, True).pack(anchor="w")
        self.lbl_crudo = tk.Label(info, font=("Consolas", 12), bg=T["superficie"], fg=T["texto"], justify="left",
                                  anchor="nw", padx=10, pady=10, wraplength=480)
        self.lbl_crudo.pack(fill="x", pady=(4, 10))
        etiqueta(info, "1. Activá 'Usar balanza', elegí el COM del adaptador USB y guardá.\n"
                       "2. Poné algo en el plato y mirá el dato crudo de arriba.\n"
                       "3. Si no llega nada: 'Detectar protocolo' prueba velocidades y comandos.\n"
                       "4. Si el peso sale 1000 veces más grande, ajustá el divisor.",
                 10, fg=T["texto_sec"], justify="left").pack(anchor="w")

    def _impresora(self, f):
        f.columnconfigure(2, weight=1)
        self._combo(f, 0, ("impresora", "tipo"), "Tipo", ["archivo", "serial", "windows", "ninguna"])
        self.cb_puerto_imp = self._combo(f, 1, ("impresora", "puerto"), "Puerto (serial)", puertos_disponibles())
        self._combo(f, 2, ("impresora", "baudios"), "Baudios (serial)", [9600, 19200, 38400, 115200, 4800, 2400])
        self._combo(f, 3, ("impresora", "nombre_windows"), "Impresora Windows", impresora.impresoras_windows())
        self._combo(f, 4, ("impresora", "ancho"), "Caracteres por línea", [32, 42, 48])
        self._check(f, 5, ("impresora", "cortar"), "Cortar papel al final")
        self._campo(f, 6, ("impresora", "logo"), "Logo (imagen)")
        self._campo(f, 7, ("impresora", "logo_ancho_px"), "Ancho del logo (puntos)")
        fb = marco(f)
        fb.grid(row=8, column=1, sticky="w", pady=4)
        boton(fb, "Logo de la verdulería", self._logo_propio, size=10, icono="logo").pack(side="left", padx=(6, 2))
        boton(fb, "Elegir otro...", self._elegir_logo, bg=T["secundario"], size=10).pack(side="left", padx=2)
        boton(fb, "Quitar logo", self._quitar_logo, bg=T["rojo"], size=10).pack(side="left", padx=2)
        etiqueta(f, "archivo = no imprime: guarda datos/ultimo_ticket.txt y .png (para probar)\n"
                    "serial = por puerto COM (impresora integrada a la balanza: el mismo puerto)\n"
                    "windows = impresora térmica instalada en Windows\n"
                    "Logo: papel de 58mm hasta 384 puntos de ancho, 80mm hasta 576.",
                 9, fg=T["texto_sec"], justify="left").grid(row=9, column=0, columnspan=2, sticky="w", pady=8)
        fb2 = marco(f)
        fb2.grid(row=10, column=0, columnspan=2)
        boton(fb2, "Vista previa del ticket", self._vista_previa, bg=T["secundario"], size=10, icono="ticket").pack(side="left", padx=2)
        boton(fb2, "Imprimir ticket de prueba", self._prueba, size=10, icono="reimprimir").pack(side="left", padx=2)

    def _web(self, f):
        etiqueta(f, "El servicio web aparece como un ícono con el logo junto al reloj de Windows.", 12, True).grid(
            row=0, column=0, columnspan=2, sticky="w")
        etiqueta(f, "Clic derecho en ese ícono: abrir panel, copiar link, iniciar / detener, configurar puerto,\n"
                    "permitir acceso desde la red e iniciar con Windows.", 10, fg=T["texto_sec"], justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 12))
        self._campo(f, 2, ("web", "clave"), "Clave (opcional)")
        etiqueta(f, "Si permitís el acceso desde la red, poné una clave. El navegador la pide (usuario: cualquiera).\n"
                    "Después de cambiar la clave: Guardar configuración y reiniciar el servicio.",
                 9, fg=T["texto_sec"], justify="left").grid(row=3, column=0, columnspan=2, sticky="w", pady=6)
        self.lbl_web = etiqueta(f, "", 13, True)
        self.lbl_web.grid(row=4, column=0, columnspan=2, sticky="w", pady=6)
        fb = marco(f)
        fb.grid(row=5, column=0, columnspan=2, sticky="w")
        boton(fb, "Iniciar servicio", self._iniciar_web, icono="ok").pack(side="left", padx=2)
        boton(fb, "Abrir panel en el navegador", self._abrir_web, bg=T["acento"], fg=T["acento_txt"], icono="web").pack(side="left", padx=2)
        self.v_autoinicio = tk.BooleanVar(value=servidor.autoinicio_activo())
        casilla(f, "Iniciar el servicio web automáticamente al prender la PC", self.v_autoinicio).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=10)
        self.v_autoinicio.trace_add("write", lambda *a: self._autoinicio())
        self._estado_web()

    # ---------- constructores de campos
    def _var(self, ruta, booleano=False):
        sec, k = ruta
        valor = self.app.cfg[sec][k]
        v = tk.BooleanVar(value=bool(valor)) if booleano else tk.StringVar(value=str(valor))
        self.vars[ruta] = v
        return v

    def _campo(self, padre, fila, ruta, txt):
        etiqueta(padre, txt, 11).grid(row=fila, column=0, sticky="e", pady=3)
        entrada(padre, self._var(ruta), 26, 11).grid(row=fila, column=1, sticky="w", padx=6)

    def _combo(self, padre, fila, ruta, txt, valores, editable=False):
        etiqueta(padre, txt, 11).grid(row=fila, column=0, sticky="e", pady=3)
        cb = ttk.Combobox(padre, textvariable=self._var(ruta), values=valores, width=24,
                          state="normal" if editable or ruta[1] in ("puerto", "nombre_windows") else "readonly")
        cb.grid(row=fila, column=1, sticky="w", padx=6)
        return cb

    def _check(self, padre, fila, ruta, txt):
        casilla(padre, txt, self._var(ruta, True), bold=True).grid(row=fila, column=1, sticky="w", pady=3)

    # ---------- acciones generales
    def _log(self, texto):
        self.txt_det.insert("end", texto + "\n")
        self.txt_det.see("end")

    def _leer_formulario(self):
        """Config actual + lo escrito en pantalla. Lanza ValueError si hay un número mal escrito."""
        enteros = {("balanza", "baudios"), ("balanza", "bits"), ("balanza", "stop"), ("balanza", "intervalo_ms"),
                   ("impresora", "baudios"), ("impresora", "ancho"), ("impresora", "logo_ancho_px"), ("web", "puerto")}
        nuevo = {sec: dict(vals) for sec, vals in self.app.cfg.items()}
        for (sec, k), v in self.vars.items():
            val = v.get()
            try:
                if (sec, k) in enteros:
                    val = int(val)
                elif (sec, k) == ("balanza", "divisor"):
                    val = num(val)
            except ValueError:
                raise ValueError(k)
            nuevo[sec][k] = val
        return nuevo

    def guardar(self):
        try:
            nuevo = self._leer_formulario()
        except ValueError as e:
            messagebox.showerror("Configuración", f"Valor inválido en '{e}'.", parent=self)
            return
        cfg = self.app.cfg
        tema_antes = cfg["interfaz"].get("tema")
        web = datos.cargar_config()["web"]
        web["clave"] = nuevo["web"]["clave"]
        nuevo["web"] = web
        cfg.update(nuevo)
        datos.guardar_config(cfg)
        self.app.balanza.reiniciar(cfg["balanza"])
        if cfg["interfaz"]["tema"] != tema_antes:
            self.after_idle(self.app.reconstruir)
        else:
            self._log("Configuración guardada.")

    def _cambiar_atajo(self, accion, desc):
        nuevo = CapturaTecla(self.app, desc).mostrar()
        if nuevo is None:
            return
        otros = {a: t for a, t in self.app.cfg["atajos"].items() if a != accion}
        if nuevo and nuevo in otros.values():
            usado = next(d for a, d in ACCIONES if otros.get(a) == nuevo)
            messagebox.showerror("Atajo", f"{nombre_atajo(nuevo)} ya se usa para '{usado}'.", parent=self)
            return
        self.app.cfg["atajos"][accion] = nuevo
        datos.guardar_config(self.app.cfg)
        self.after_idle(self.app.reconstruir)

    def _atajos_defecto(self):
        if messagebox.askyesno("Atajos", "¿Volver a los atajos de fábrica?", parent=self):
            self.app.cfg["atajos"] = dict(datos.ATAJOS_DEFECTO)
            datos.guardar_config(self.app.cfg)
            self.after_idle(self.app.reconstruir)

    # ---------- balanza
    def _puertos(self):
        ps = puertos_disponibles()
        self.cb_puerto_bal["values"] = ps
        self.cb_puerto_imp["values"] = ps
        self._log(f"Puertos encontrados: {', '.join(ps) or 'ninguno'}")

    def _mostrar_crudo(self):
        if not self.winfo_exists():
            return
        b = self.app.balanza
        if b.activa:
            peso = kg(b.peso) if b.peso is not None else "---"
            self.lbl_crudo.config(text=f"Peso: {peso}  {'(estable)' if b.estable else ''}\n{b.error}\n"
                                       f"Dato crudo: {b.crudo[-60:]!r}")
        else:
            self.lbl_crudo.config(text="Balanza desactivada")
        self.after(400, self._mostrar_crudo)

    def _detectar(self):
        puerto = self.vars[("balanza", "puerto")].get()
        if not messagebox.askyesno("Detectar protocolo", f"Se va a probar el puerto {puerto} (unos 30 segundos).\n"
                                   "Poné algo de peso en la balanza. ¿Continuar?", parent=self):
            return
        self.app.balanza.detener()
        self._log(f"Probando {puerto}...")

        def log_seguro(t):
            if self.winfo_exists():
                self._log(t)

        def trabajo():
            res = probar_protocolos(puerto, progreso=lambda t: self.after(0, log_seguro, t))
            self.after(0, fin, res)

        def fin(res):
            if res:
                log_seguro("RESPUESTAS RECIBIDAS (copiá baudios y comando en la configuración):")
                for baud, cmd, data in res:
                    log_seguro(f"  {baud} baudios | comando {cmd:<8} -> {data!r}")
            else:
                log_seguro("La balanza no respondió. Revisá cable (puede necesitar null-modem), puerto y que la "
                           "comunicación con PC esté habilitada en el menú de la balanza.")
            self.app.balanza.reiniciar(self.app.cfg["balanza"])

        threading.Thread(target=trabajo, daemon=True).start()

    # ---------- ticket y logo
    def _elegir_logo(self):
        path = filedialog.askopenfilename(parent=self, title="Elegí el logo",
                                          filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif"), ("Todos", "*.*")])
        if not path:
            return
        try:
            from PIL import Image
            os.makedirs(datos.DATOS, exist_ok=True)
            Image.open(path).save(os.path.join(datos.DATOS, "logo.png"))   # copia propia, por si borran el original
        except Exception as e:
            messagebox.showerror("Logo", f"No se pudo leer la imagen:\n{e}", parent=self)
            return
        self.vars[("impresora", "logo")].set("datos/logo.png")
        self._log("Logo cargado. Mirá la 'Vista previa' y tocá 'Guardar configuración'.")

    def _logo_propio(self):
        self.vars[("impresora", "logo")].set("img/logo_ticket.png")
        self._log("Logo de la verdulería elegido. Mirá la 'Vista previa' y tocá 'Guardar configuración'.")

    def _quitar_logo(self):
        self.vars[("impresora", "logo")].set("")
        self._log("Logo quitado. Tocá 'Guardar configuración'.")

    @staticmethod
    def _venta_prueba():
        return {"numero": 0, "fecha": datetime.now().isoformat(timespec="seconds"), "estado": "activa", "total": 3750,
                "pago": {"medio": "Efectivo", "paga_con": 5000, "vuelto": 1250},
                "items": [{"nombre": "Tomate", "pesable": True, "cantidad": 1.0, "precio": 2500, "importe": 2500},
                          {"nombre": "Papa", "pesable": True, "cantidad": 1.042, "precio": 1200, "importe": 1250}]}

    def _vista_previa(self):
        try:
            cfg = self._leer_formulario()
        except ValueError as e:
            messagebox.showerror("Configuración", f"Valor inválido en '{e}'.", parent=self)
            return
        VistaTicket(self.app, self._venta_prueba(), cfg).mostrar()

    def _prueba(self):
        if self.app.imprimir_ticket(self._venta_prueba()):
            self._log(f"Ticket de prueba enviado ({self.app.cfg['impresora']['tipo']}).")

    # ---------- servicio web (lo maneja bandeja.py)
    @staticmethod
    def _cfg_web():
        return datos.cargar_config()       # del disco: la bandeja puede haber cambiado el puerto

    def _web_activo(self):
        try:
            with socket.create_connection(("127.0.0.1", int(self._cfg_web()["web"]["puerto"])), timeout=0.3):
                return True
        except (OSError, ValueError):
            return False

    def _estado_web(self):
        if not self.winfo_exists():
            return
        if self._web_activo():
            self.lbl_web.config(text=f"● Servicio web funcionando: {servidor.url_panel(self._cfg_web())}", fg=T["positivo"])
        else:
            self.lbl_web.config(text="● Servicio web detenido", fg=T["egreso_txt"])
        self.after(3000, self._estado_web)

    def _iniciar_web(self):
        """Abre el ícono de la bandeja (que inicia el servicio). Si ya está abierto, no se duplica."""
        if self._web_activo():
            self._log("El servicio web ya está funcionando.")
            return
        flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0   # DETACHED_PROCESS | NEW_PROCESS_GROUP
        subprocess.Popen(servidor.comando_bandeja(), cwd=datos.BASE,
                         creationflags=flags, close_fds=True)
        self._log("Iniciando servicio web (mirá el ícono junto al reloj)...")
        self.after(1500, self._estado_web)

    def _abrir_web(self):
        if self._web_activo():
            webbrowser.open(servidor.url_panel(self._cfg_web()))
        else:
            self._iniciar_web()
            self.after(2000, lambda: webbrowser.open(servidor.url_panel(self._cfg_web())))

    def _autoinicio(self):
        try:
            servidor.poner_autoinicio(self.v_autoinicio.get())
            self._log("El servicio web se va a iniciar solo al prender la PC." if self.v_autoinicio.get()
                      else "Inicio automático desactivado.")
        except Exception as e:
            messagebox.showerror("Inicio automático", str(e), parent=self)

def un_solo_pos():
    if os.name != "nt":
        return True
    import win32api
    import win32event
    import winerror
    global _mutex
    _mutex = win32event.CreateMutex(None, False, "VerduleriaMargarita_POS")
    return win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    if un_solo_pos():
        App().mainloop()
    else:
        r = tk.Tk()
        r.withdraw()
        messagebox.showinfo("La Verdulería de Margarita", "El POS ya está abierto.")
