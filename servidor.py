"""Servicio web de La Verdulería de Margarita: panel de gestión (todo menos el POS).

Iniciar:   python servidor.py            (o doble clic en iniciar_servicio.bat)
Abrir:     http://localhost:8085/servicioweb/

API (la usa servicioweb/app.js; también la reenvía servicioweb/api.php desde Apache/XAMPP):
  GET  api.php?r=info | resumen | ventas | ticket | ticket_png | movimientos | productos | historial_stock | logo
  POST api.php?r=anular | movimiento | producto | producto_eliminar | stock_ingreso | stock_ajuste   (cuerpo JSON)
"""
import base64
import hmac
import io
import json
import mimetypes
import os
import sys
import traceback
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import datos
import iconos
import impresora

WEB = os.path.join(datos.BASE, "servicioweb")
IMG = os.path.join(datos.BASE, "img")
LOG = os.path.join(datos.BASE, "servidor.log")
MAX_DIAS = 400

# con pythonw no hay consola: los mensajes van a servidor.log
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(LOG, "a", encoding="utf-8", buffering=1)


def _log(texto):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {texto}", flush=True)


# ---------------------------------------------------------------- API
def _param(q, k, defecto=None):
    return q.get(k, [defecto])[0]


def _rango(q):
    hoy = date.today()
    desde = date.fromisoformat(_param(q, "desde") or hoy.isoformat())
    hasta = date.fromisoformat(_param(q, "hasta") or desde.isoformat())
    if hasta < desde:
        desde, hasta = hasta, desde
    if (hasta - desde).days > MAX_DIAS:
        raise ValueError(f"El período máximo es de {MAX_DIAS} días")
    return desde, hasta


def _venta(q):
    v = datos.leer_venta(int(_param(q, "numero")), _param(q, "fecha"))
    if not v:
        raise LookupError("Venta no encontrada")
    return v


def api_get(ruta, q):
    if ruta == "info":
        cfg = datos.cargar_config()
        logo = datos.ruta_absoluta(cfg["impresora"].get("logo", ""))
        return {"negocio": cfg["negocio"], "tema": cfg["interfaz"].get("tema", "claro"),
                "logo": bool(logo and os.path.exists(logo)), "hoy": date.today().isoformat()}
    if ruta == "resumen":
        r = datos.resumen(*_rango(q))
        por_codigo = {p["codigo"]: iconos.de_producto(p) for p in datos.cargar_productos()}
        for p in r["productos"]:
            p["icono_ver"] = por_codigo.get(p["codigo"]) or iconos.adivinar(p["nombre"])
        return r
    if ruta == "ventas":
        return datos.ventas_rango(*_rango(q))
    if ruta == "ticket":
        return {"texto": impresora.armar_ticket(_venta(q), datos.cargar_config())}
    if ruta == "movimientos":
        return datos.movimientos_rango(*_rango(q))
    if ruta == "productos":
        return [dict(p, icono_ver=iconos.de_producto(p)) for p in datos.cargar_productos()]
    if ruta == "iconos":
        return iconos.catalogo()
    if ruta == "historial_stock":
        return datos.historial_stock(min(int(_param(q, "limite", "300")), 5000))
    raise LookupError("Ruta desconocida")


def api_binaria(ruta, q):
    """Devuelve (bytes, content-type) o None si la ruta no es binaria."""
    if ruta == "logo":
        cfg = datos.cargar_config()
        path = datos.ruta_absoluta(cfg["impresora"].get("logo", ""))
        if not path or not os.path.exists(path):
            raise LookupError("No hay logo cargado")
        with open(path, "rb") as f:
            return f.read(), mimetypes.guess_type(path)[0] or "image/png"
    if ruta == "ticket_png":
        cfg = datos.cargar_config()
        img = impresora.ticket_imagen(impresora.armar_ticket(_venta(q), cfg), cfg["impresora"])
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue(), "image/png"
    return None


def _texto(b, k):
    t = str(b.get(k, "")).strip()
    if not t:
        raise ValueError(f"Falta '{k}'")
    return t


def _positivo(b, k):
    n = float(b[k])
    if n <= 0:
        raise ValueError(f"'{k}' tiene que ser mayor a cero")
    return n


def api_post(ruta, b):
    if ruta == "anular":
        v = datos.anular_venta({"numero": int(b["numero"]), "fecha": _texto(b, "fecha")},
                               str(b.get("motivo") or "").strip() or "Anulada desde el panel web")
        _log(f"Venta #{v['numero']} anulada desde el panel web")
        return v
    if ruta == "movimiento":
        return datos.registrar_movimiento(_texto(b, "tipo"), _texto(b, "concepto"), _positivo(b, "monto"),
                                          b.get("medio") or "Efectivo")
    if ruta == "producto":
        if float(b.get("precio", 0)) < 0 or float(b.get("costo", 0)) < 0:
            raise ValueError("Precio y costo no pueden ser negativos")
        return datos.guardar_producto(b, b.get("codigo_original") or None)
    if ruta == "producto_eliminar":
        datos.eliminar_producto(_texto(b, "codigo"))
        return {"ok": True}
    if ruta == "stock_ingreso":
        datos.ingreso_mercaderia(_texto(b, "codigo"), _positivo(b, "cantidad"), float(b.get("costo", 0)),
                                 bool(b.get("egreso", True)), b.get("medio") or "Efectivo")
        return {"ok": True}
    if ruta == "stock_ajuste":
        datos.ajustar_stock(_texto(b, "codigo"), float(b["stock"]), str(b.get("motivo") or "").strip() or "Ajuste")
        return {"ok": True}
    raise LookupError("Ruta desconocida")


# ---------------------------------------------------------------- HTTP
class Manejador(BaseHTTPRequestHandler):
    server_version = "VerduleriaMargarita/1.0"

    def log_message(self, *args):
        pass   # no registrar cada pedido

    def do_GET(self):
        self._atender("GET")

    def do_POST(self):
        self._atender("POST")

    def _auth_ok(self):
        clave = self.server.cfg["web"].get("clave", "")
        if not clave:
            return True
        h = self.headers.get("Authorization", "")
        if not h.startswith("Basic "):
            return False
        try:
            _usuario, _, pw = base64.b64decode(h[6:]).decode("utf-8").partition(":")
        except Exception:
            return False
        return hmac.compare_digest(pw.encode(), clave.encode())

    def _enviar(self, codigo, cuerpo, tipo, extra=None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        if "Cache-Control" not in (extra or {}):
            self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def _json(self, codigo, data):
        self._enviar(codigo, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _atender(self, metodo):
        if not self._auth_ok():
            return self._enviar(401, b"Clave requerida", "text/plain; charset=utf-8",
                                {"WWW-Authenticate": 'Basic realm="La Verduleria de Margarita", charset="UTF-8"'})
        u = urlparse(self.path)
        if u.path in ("/", "/servicioweb"):
            return self._enviar(302, b"", "text/plain", {"Location": "/servicioweb/"})
        if u.path == "/servicioweb/api.php":
            return self._api(metodo, parse_qs(u.query))
        if metodo == "GET" and u.path.startswith("/servicioweb/"):
            return self._estatico(WEB, u.path[len("/servicioweb/"):])
        if metodo == "GET" and u.path.startswith("/img/"):      # logos e íconos compartidos con el POS
            return self._estatico(IMG, u.path[len("/img/"):], solo=(".png", ".svg"))
        self._enviar(404, b"No encontrado", "text/plain; charset=utf-8")

    def _api(self, metodo, q):
        ruta = _param(q, "r", "")
        try:
            if metodo == "GET":
                binario = api_binaria(ruta, q)
                if binario:
                    return self._enviar(200, binario[0], binario[1])
                return self._json(200, api_get(ruta, q))
            # exigir JSON evita que un formulario de otra página pueda escribir datos
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._json(415, {"error": "Se espera JSON"})
            largo = int(self.headers.get("Content-Length", 0))
            if largo > 1_000_000:
                return self._json(413, {"error": "Pedido demasiado grande"})
            cuerpo = json.loads(self.rfile.read(largo) or b"{}")
            return self._json(200, api_post(ruta, cuerpo))
        except LookupError as e:
            self._json(404, {"error": str(e) or "No encontrado"})
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except (KeyError, TypeError) as e:
            self._json(400, {"error": f"Falta o es inválido el dato {e}"})
        except Exception as e:
            _log(f"ERROR {metodo} {self.path}\n{traceback.format_exc()}")
            self._json(500, {"error": f"Error interno: {e}"})

    def _estatico(self, raiz, rel, solo=None):
        destino = os.path.normpath(os.path.join(raiz, rel or "index.html"))
        if destino != raiz and not destino.startswith(raiz + os.sep):
            return self._enviar(404, b"No encontrado", "text/plain")
        if os.path.isdir(destino):
            destino = os.path.join(destino, "index.html")
        if not os.path.isfile(destino) or destino.endswith(".php") or (solo and not destino.endswith(solo)):
            return self._enviar(404, b"No encontrado", "text/plain")
        tipo = mimetypes.guess_type(destino)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/json"):
            tipo += "; charset=utf-8"
        with open(destino, "rb") as f:
            extra = {"Cache-Control": "max-age=86400"} if raiz == IMG else None
            self._enviar(200, f.read(), tipo, extra)


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    # En Windows SO_REUSEADDR deja que DOS programas escuchen el mismo puerto (y los pedidos se reparten
    # al azar). Así, si el puerto está ocupado, el segundo falla en vez de quedar duplicado.
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt":
            import socket
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def ip_local():
    """IP de esta PC en la red local (para entrar desde otra PC o el celular)."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))    # no envía nada: solo elige la interfaz de red
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def url_panel(cfg, para_compartir=False):
    host = cfg["web"]["host"] or "127.0.0.1"
    if host == "0.0.0.0":
        host = ip_local() if para_compartir else "127.0.0.1"
    return f"http://{host}:{int(cfg['web']['puerto'])}/servicioweb/"


def crear_servidor(cfg):
    """Crea el servidor (sin arrancarlo). Lanza OSError si el puerto está ocupado."""
    mimetypes.add_type("application/javascript", ".js")
    srv = Servidor((cfg["web"]["host"] or "127.0.0.1", int(cfg["web"]["puerto"])), Manejador)
    srv.cfg = cfg
    return srv


# ---------------------------------------------------------------- inicio automático con Windows
ARCH_AUTOINICIO = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup",
                               "La Verdulería de Margarita - Servicio web.lnk")
VIEJOS_AUTOINICIO = [os.path.join(os.path.dirname(ARCH_AUTOINICIO), "LoDeMargarita_servicio_web.bat")]


EXE_POS = "VerduleriaMargarita.exe"
EXE_SERVICIO = "VerduleriaMargarita-Servicio.exe"


def pythonw():
    w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return w if os.path.exists(w) else sys.executable


def comando_bandeja():
    """Cómo se abre el ícono del servicio: el .exe instalado, o pythonw bandeja.py en desarrollo."""
    if getattr(sys, "frozen", False):
        return [os.path.join(datos.BASE, EXE_SERVICIO)]
    return [pythonw(), os.path.join(datos.BASE, "bandeja.py")]


def autoinicio_activo():
    return os.path.exists(ARCH_AUTOINICIO)


def poner_autoinicio(activar):
    """Crea o borra el acceso directo en la carpeta Inicio de Windows (abre la bandeja del servicio)."""
    for viejo in VIEJOS_AUTOINICIO:
        if os.path.exists(viejo):
            os.remove(viejo)
    if not activar:
        if os.path.exists(ARCH_AUTOINICIO):
            os.remove(ARCH_AUTOINICIO)
        return
    import win32com.client
    acceso = win32com.client.Dispatch("WScript.Shell").CreateShortCut(ARCH_AUTOINICIO)
    comando = comando_bandeja()
    acceso.TargetPath = comando[0]
    acceso.Arguments = " ".join(f'"{a}"' for a in comando[1:])
    acceso.WorkingDirectory = datos.BASE
    acceso.IconLocation = os.path.join(datos.BASE, "img", "icono.ico")
    acceso.Description = "Servicio web de La Verdulería de Margarita"
    acceso.save()


def main():
    """Modo consola (sin bandeja): python servidor.py"""
    cfg = datos.cargar_config()
    url = url_panel(cfg)
    try:
        srv = crear_servidor(cfg)
    except OSError as e:
        _log(f"No se pudo usar el puerto {cfg['web']['puerto']} ({e}). ¿El servicio ya está iniciado?")
        if "--abrir" in sys.argv:
            webbrowser.open(url)
        sys.exit(1)
    _log(f"Servicio web iniciado: {url}")
    if "--abrir" in sys.argv:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        _log("Servicio detenido.")


if __name__ == "__main__":
    main()
