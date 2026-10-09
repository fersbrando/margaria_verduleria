"""Servicio web en la bandeja de Windows (junto al reloj), con el logo de la verdulería.

Clic derecho: abrir panel, copiar link, iniciar / detener servicio, configurar puerto,
acceso desde la red, iniciar con Windows y salir. Doble clic: abre el panel.

Ejecutar:  pythonw bandeja.py        (o doble clic en iniciar_servicio.bat)
"""
import os
import queue
import socket
import sys
import threading
import time
import tkinter as tk
import webbrowser

import pystray
from PIL import Image, ImageOps, ImageTk

import datos
import servidor

NOMBRE = "La Verdulería de Margarita"
MUTEX = "VerduleriaMargarita_ServicioWeb"
VERDE, VERDE_OSC, FONDO, ROJO = "#2E7D32", "#1B5E20", "#E8F5E9", "#C62828"


def una_sola_instancia():
    """Evita abrir dos íconos (y dos servicios) a la vez."""
    if os.name != "nt":
        return True
    import win32api
    import win32event
    import winerror
    global _mutex
    _mutex = win32event.CreateMutex(None, False, MUTEX)
    return win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS


def copiar_al_portapapeles(texto):
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(texto, win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


def puerto_libre(puerto):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if os.name == "nt":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            s.bind(("127.0.0.1", puerto))
            return True
        except OSError:
            return False


class Bandeja:
    def __init__(self):
        self.srv = None
        self.error = ""
        self.tareas = queue.Queue()     # lo que necesita ventanas se hace en el hilo de tkinter
        logo = Image.open(os.path.join(datos.BASE, "img", "icono_64.png")).convert("RGBA")
        gris = ImageOps.grayscale(logo).convert("RGBA")
        gris.putalpha(logo.getchannel("A").point(lambda a: int(a * 0.55)))
        self.img_activo, self.img_detenido = logo, gris
        self.icono = pystray.Icon("verduleria_margarita", self.img_detenido, NOMBRE, menu=self._menu())
        self.root = tk.Tk()
        self.root.withdraw()
        try:
            self.root.iconbitmap(os.path.join(datos.BASE, "img", "icono.ico"))
        except tk.TclError:
            pass

    # ------------------------------------------------------------ estado
    @staticmethod
    def cfg():
        return datos.cargar_config()

    @property
    def activo(self):
        return self.srv is not None

    def avisar(self, texto):
        try:
            self.icono.notify(texto, NOMBRE)
        except Exception:
            pass

    def _refrescar(self):
        cfg = self.cfg()
        self.icono.icon = self.img_activo if self.srv else self.img_detenido
        estado = f"Funcionando en puerto {cfg['web']['puerto']}" if self.srv else "Servicio web detenido"
        self.icono.title = f"{NOMBRE}\n{estado}"[:127]
        self.icono.update_menu()

    # ------------------------------------------------------------ servicio
    def iniciar(self, avisar=True):
        if self.srv:
            return
        cfg = self.cfg()
        try:
            self.srv = servidor.crear_servidor(cfg)
        except OSError:
            self.error = f"el puerto {cfg['web']['puerto']} está ocupado"
            self._refrescar()
            self.avisar(f"No se pudo iniciar: {self.error}.\nClic derecho → Configurar puerto.")
            return
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.error = ""
        servidor._log(f"Servicio web iniciado (bandeja): {servidor.url_panel(cfg)}")
        self._refrescar()
        if avisar:
            self.avisar(f"Servicio iniciado\n{servidor.url_panel(cfg)}")

    def detener(self, avisar=True):
        if not self.srv:
            return
        srv, self.srv = self.srv, None
        srv.shutdown()
        srv.server_close()
        servidor._log("Servicio web detenido (bandeja)")
        self._refrescar()
        if avisar:
            self.avisar("Servicio web detenido")

    def reiniciar(self):
        self.detener(avisar=False)
        self.iniciar()

    # ------------------------------------------------------------ menú
    def _menu(self):
        M, sep = pystray.MenuItem, pystray.Menu.SEPARATOR

        def estado(_item):
            if self.srv:
                return f"● Funcionando · {servidor.url_panel(self.cfg())}"
            return "○ Detenido" + (f" ({self.error})" if self.error else "")

        return pystray.Menu(
            M(NOMBRE, None, enabled=False),
            M(estado, None, enabled=False),
            sep,
            M("Abrir panel", self._abrir, default=True, enabled=lambda i: self.activo),
            M("Copiar link", self._copiar, enabled=lambda i: self.activo),
            sep,
            M("Iniciar servicio", lambda: self.iniciar(), enabled=lambda i: not self.activo),
            M("Detener servicio", lambda: self.detener(), enabled=lambda i: self.activo),
            M("Configurar puerto...", lambda: self.tareas.put(self._dialogo_puerto)),
            M("Permitir acceso desde la red", self._alternar_red,
              checked=lambda i: self.cfg()["web"]["host"] == "0.0.0.0"),
            M("Iniciar con Windows", self._alternar_autoinicio, checked=lambda i: servidor.autoinicio_activo()),
            sep,
            M("Salir", self._salir),
        )

    def _abrir(self):
        if not self.activo:
            self.iniciar(avisar=False)
        if self.activo:
            webbrowser.open(servidor.url_panel(self.cfg()))

    def _copiar(self):
        url = servidor.url_panel(self.cfg(), para_compartir=True)
        try:
            copiar_al_portapapeles(url)
            self.avisar(f"Link copiado:\n{url}")
        except Exception as e:
            self.avisar(f"No se pudo copiar el link: {e}")

    def _alternar_red(self):
        cfg = self.cfg()
        abrir = cfg["web"]["host"] != "0.0.0.0"
        cfg["web"]["host"] = "0.0.0.0" if abrir else "127.0.0.1"
        datos.guardar_config(cfg)
        if self.activo:
            self.reiniciar()
        else:
            self._refrescar()
        if abrir and not cfg["web"].get("clave"):
            self.avisar("Ahora se puede entrar desde otras PCs o el celular.\n"
                        "Recomendado: poné una clave en el POS → Configuración → Servicio web.")
        elif abrir:
            self.avisar(f"Acceso desde la red activado:\n{servidor.url_panel(cfg, para_compartir=True)}")
        else:
            self.avisar("Acceso solo desde esta PC.")

    def _alternar_autoinicio(self):
        try:
            servidor.poner_autoinicio(not servidor.autoinicio_activo())
            self.avisar("Se va a iniciar solo al prender la PC." if servidor.autoinicio_activo()
                        else "Ya no se inicia solo con Windows.")
        except Exception as e:
            self.avisar(f"No se pudo cambiar el inicio automático: {e}")
        self.icono.update_menu()

    def _salir(self):
        self.detener(avisar=False)
        self.icono.stop()
        self.tareas.put(self.root.quit)

    # ------------------------------------------------------------ ventana para el puerto
    def _dialogo_puerto(self):
        cfg = self.cfg()
        actual = int(cfg["web"]["puerto"])
        d = tk.Toplevel(self.root)
        d.title("Puerto del servicio web")
        d.configure(bg=FONDO, padx=22, pady=18)
        d.resizable(False, False)
        d.attributes("-topmost", True)
        try:
            self._logo_tk = ImageTk.PhotoImage(self.img_activo)
            tk.Label(d, image=self._logo_tk, bg=FONDO).grid(row=0, column=0, rowspan=3, padx=(0, 16), sticky="n")
        except Exception:
            pass
        tk.Label(d, text="Puerto del servicio web", font=("Segoe UI", 14, "bold"), bg=FONDO, fg=VERDE_OSC).grid(row=0, column=1, sticky="w")
        tk.Label(d, text="Número entre 1024 y 65535 (por defecto 8085)", font=("Segoe UI", 10), bg=FONDO,
                 fg="#5E6F60").grid(row=1, column=1, sticky="w")
        var = tk.StringVar(value=str(actual))
        e = tk.Entry(d, textvariable=var, font=("Segoe UI", 16), width=8, justify="center", relief="solid", bd=1)
        e.grid(row=2, column=1, sticky="w", pady=8)
        msj = tk.Label(d, text="", font=("Segoe UI", 10, "bold"), bg=FONDO, fg=ROJO)
        msj.grid(row=3, column=0, columnspan=2, sticky="w")

        def guardar(_e=None):
            try:
                p = int(var.get().strip())
                if not 1024 <= p <= 65535:
                    raise ValueError
            except ValueError:
                msj.config(text="Escribí un número entre 1024 y 65535.")
                return
            if p != actual and not puerto_libre(p):
                msj.config(text=f"El puerto {p} lo está usando otro programa. Probá otro.")
                return
            d.destroy()
            if p == actual:
                return
            c = self.cfg()
            c["web"]["puerto"] = p
            datos.guardar_config(c)
            if self.activo:
                threading.Thread(target=self.reiniciar, daemon=True).start()
            else:
                self.error = ""
                self._refrescar()
                self.avisar(f"Puerto cambiado a {p}.")

        fb = tk.Frame(d, bg=FONDO)
        fb.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        for texto, cmd, color in (("Cancelar", d.destroy, "#607D8B"), ("Guardar", guardar, VERDE)):
            tk.Button(fb, text=texto, command=cmd, bg=color, fg="white", font=("Segoe UI", 11, "bold"),
                      relief="flat", padx=14, pady=4, cursor="hand2").pack(side="left", padx=4)
        d.bind("<Return>", guardar)
        d.bind("<Escape>", lambda _e: d.destroy())
        d.update_idletasks()
        x = (d.winfo_screenwidth() - d.winfo_width()) // 2
        y = (d.winfo_screenheight() - d.winfo_height()) // 3
        d.geometry(f"+{x}+{y}")
        d.focus_force()
        e.focus_set()
        e.select_range(0, "end")

    # ------------------------------------------------------------ bucle
    def _atender_tareas(self):
        while not self.tareas.empty():
            try:
                self.tareas.get_nowait()()
            except Exception as e:
                servidor._log(f"Error en la bandeja: {e}")
        self.root.after(150, self._atender_tareas)

    def ejecutar(self, abrir=False):
        self.icono.run_detached()
        time.sleep(0.3)
        self.iniciar(avisar=False)
        if abrir:
            self._abrir()
        self.root.after(150, self._atender_tareas)
        self.root.mainloop()


def main():
    abrir = "--abrir" in sys.argv
    if not una_sola_instancia():
        # ya hay un ícono en la bandeja: solo abrimos el panel
        if abrir:
            webbrowser.open(servidor.url_panel(datos.cargar_config()))
        return
    Bandeja().ejecutar(abrir)


if __name__ == "__main__":
    main()
