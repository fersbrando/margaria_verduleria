"""Lectura de peso por puerto serie (RS232 o adaptador USB-RS232).

Se lee en un hilo aparte; la pantalla consulta `balanza.peso` cada 200 ms.
Soporta dos modos:
  - pedido:   la PC envía un comando (ej. ENQ = \\x05) y la balanza contesta con el peso.
  - continuo: la balanza transmite el peso todo el tiempo sola.
"""
import re
import threading
import time

import serial
from serial.tools import list_ports

COMANDOS_COMUNES = ["\\x05", "P", "W", "$", "\\r", "P\\r\\n"]
BAUDIOS_COMUNES = [9600, 4800, 2400, 19200, 1200]
_NUM = re.compile(rb"[-+]?\d+(?:[.,]\d+)?")
_FIN = (b"\r", b"\n", b"\x03")


def puertos_disponibles():
    return [p.device for p in list_ports.comports()]


def comando_bytes(texto):
    """'\\x05' -> b'\\x05' ; 'P\\r' -> b'P\\r'"""
    return texto.encode("latin-1").decode("unicode_escape").encode("latin-1")


def parsear_peso(data, divisor=1):
    """Saca el primer número de la trama. Si viene sin punto decimal (gramos) se divide por `divisor`."""
    m = _NUM.search(data)
    if not m:
        return None
    t = m.group().replace(b",", b".")
    valor = float(t)
    if b"." not in t and divisor:
        valor /= float(divisor)
    return round(valor, 3)


def _ultima_trama(data):
    """En modo continuo llegan varias tramas juntas: nos quedamos con la última completa."""
    partes = re.split(rb"[\r\n\x02\x03]+", data)
    completas = partes[:-1] if not data.endswith(_FIN) else partes
    for p in reversed(completas):
        if _NUM.search(p):
            return p
    return data


class Balanza:
    def __init__(self, cfg):
        self.cfg = cfg
        self.peso = None
        self.estable = False
        self.error = ""
        self.crudo = b""
        self.ser = None
        self.lock = threading.Lock()   # la impresora puede compartir el mismo puerto
        self._stop = threading.Event()
        self._hilo = None
        self._ultimos = []

    @property
    def activa(self):
        return bool(self.cfg.get("activa"))

    def iniciar(self):
        if not self.activa:
            self.error = "Balanza desactivada"
            return
        self._stop.clear()
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()

    def detener(self):
        self._stop.set()
        if self._hilo:
            self._hilo.join(2)
            self._hilo = None
        self._cerrar()
        self.peso = None

    def reiniciar(self, cfg):
        self.detener()
        self.cfg = cfg
        self.error = ""
        self.crudo = b""
        self.iniciar()

    def _abrir(self):
        c = self.cfg
        self.ser = serial.Serial(c["puerto"], int(c["baudios"]), bytesize=int(c["bits"]),
                                 parity=c["paridad"], stopbits=int(c["stop"]), timeout=0.05)

    def _cerrar(self):
        with self.lock:
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None

    def _leer(self, espera, tramas=1):
        fin = time.time() + espera
        buf = b""
        while time.time() < fin and not self._stop.is_set():
            chunk = self.ser.read(64)
            if chunk:
                buf += chunk
                if sum(buf.count(t) for t in (b"\r", b"\x03")) >= tramas or buf.count(b"\n") >= tramas:
                    break
        return buf

    def _bucle(self):
        while not self._stop.is_set():
            try:
                if self.ser is None:
                    self._abrir()
                    self.error = ""
                c = self.cfg
                with self.lock:
                    self.ser.reset_input_buffer()
                    if c["modo"] == "pedido":
                        self.ser.write(comando_bytes(c["comando"]))
                        data = self._leer(0.6)
                    else:
                        data = _ultima_trama(self._leer(0.8, tramas=2))
                if data:
                    self.crudo = data
                    p = parsear_peso(data, c.get("divisor", 1))
                    if p is not None:
                        self._nuevo_peso(p)
                        self.error = ""
                    else:
                        self.error = "No entiendo lo que manda la balanza"
                else:
                    self.peso = None
                    self.error = "Sin respuesta de la balanza"
                self._stop.wait(int(c.get("intervalo_ms", 300)) / 1000)
            except (serial.SerialException, OSError, ValueError) as e:
                self.peso = None
                self.error = f"Error de puerto: {e}"
                self._cerrar()
                self._stop.wait(2)

    def _nuevo_peso(self, p):
        self._ultimos = (self._ultimos + [p])[-3:]
        self.estable = len(self._ultimos) == 3 and len(set(self._ultimos)) == 1
        self.peso = p


def probar_protocolos(puerto, bits=8, paridad="N", stop=1, progreso=print):
    """Prueba velocidades y comandos comunes y devuelve lo que respondió la balanza.
    Ponga algo de peso en el plato antes de probar."""
    resultados = []
    for baud in BAUDIOS_COMUNES:
        try:
            with serial.Serial(puerto, baud, bytesize=bits, parity=paridad, stopbits=stop, timeout=0.1) as s:
                progreso(f"{baud} baudios: escuchando (modo continuo)...")
                s.reset_input_buffer()
                time.sleep(0.8)
                data = s.read(s.in_waiting or 1)
                if data:
                    resultados.append((baud, "continuo", data))
                for cmd in COMANDOS_COMUNES:
                    progreso(f"{baud} baudios: enviando {cmd}")
                    s.reset_input_buffer()
                    s.write(comando_bytes(cmd))
                    time.sleep(0.5)
                    data = s.read(s.in_waiting or 1)
                    if data:
                        resultados.append((baud, cmd, data))
        except serial.SerialException as e:
            progreso(f"No se pudo abrir {puerto}: {e}")
            break
    return resultados
