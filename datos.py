"""Persistencia en archivos JSON (la usan el POS y el servidor web).

datos/productos/productos.json            -> lista de productos
datos/productos/movimientos_stock.jsonl   -> historial de cambios de stock
datos/ventas/contador.json                -> último número de ticket
datos/ventas/aaaa/mm/dd/venta_000123.json -> una venta por archivo
datos/ventas/aaaa/mm/dd/egreso_*.json     -> egresos de caja
datos/ventas/aaaa/mm/dd/ingreso_*.json    -> otros ingresos de caja
"""
import copy
import glob
import json
import os
import sys
import threading
import time
from datetime import date, datetime, timedelta

# Carpeta del programa: junto al .exe cuando está instalado (PyInstaller), o la de este archivo en desarrollo
BASE = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(BASE, "datos")
DIR_PRODUCTOS = os.path.join(DATOS, "productos")
DIR_VENTAS = os.path.join(DATOS, "ventas")
ARCH_PRODUCTOS = os.path.join(DIR_PRODUCTOS, "productos.json")
ARCH_STOCK_LOG = os.path.join(DIR_PRODUCTOS, "movimientos_stock.jsonl")
ARCH_CONTADOR = os.path.join(DIR_VENTAS, "contador.json")
ARCH_CONFIG = os.path.join(BASE, "config.json")

ATAJOS_DEFECTO = {
    "agregar": "Return",
    "cobrar": "F12",
    "quitar": "Delete",
    "deseleccionar": "Escape",
    "buscar": "F2",
    "cancelar": "F8",
    "reimprimir": "F9",
    "ir_pos": "F1",
    "pantalla_completa": "F11",
}

CONFIG_DEFECTO = {
    "negocio": {
        "nombre": "La Verdulería de Margarita",
        "linea1": "Frutas y verduras frescas",
        "linea2": "",
        "pie": "¡Gracias por su compra!",
    },
    "interfaz": {
        "tema": "claro",            # claro | gris | oscuro
        "pantalla_completa": False,
    },
    "atajos": dict(ATAJOS_DEFECTO),
    "balanza": {
        "activa": False,
        "puerto": "COM3",
        "baudios": 9600,
        "bits": 8,
        "paridad": "N",
        "stop": 1,
        "modo": "pedido",      # "pedido": la PC manda un comando y la balanza responde / "continuo": la balanza transmite sola
        "comando": "\\x05",    # ENQ. Otros comunes: P  W  $  \\r
        "divisor": 1000,       # si la balanza manda gramos sin punto (ej. 01235) se divide por esto
        "intervalo_ms": 300,
    },
    "impresora": {
        "tipo": "archivo",     # archivo | serial | windows | ninguna
        "puerto": "COM3",
        "baudios": 9600,
        "nombre_windows": "",
        "ancho": 32,           # 32 = papel 58mm, 48 = papel 80mm
        "cortar": True,
        "logo": "img/logo_ticket.png",  # ruta relativa a la carpeta del programa
        "logo_ancho_px": 300,  # 58mm imprime hasta 384 puntos, 80mm hasta 576
    },
    "web": {
        "host": "127.0.0.1",   # 0.0.0.0 para entrar desde otras PCs de la red
        "puerto": 8085,
        "clave": "",           # si se completa, el navegador pide usuario (cualquiera) y esta clave
    },
}

PRODUCTOS_EJEMPLO = [
    {"codigo": "1", "nombre": "Tomate", "pesable": True, "precio": 2500, "costo": 1600, "stock": 20, "stock_min": 5},
    {"codigo": "2", "nombre": "Papa", "pesable": True, "precio": 1200, "costo": 800, "stock": 50, "stock_min": 10},
    {"codigo": "3", "nombre": "Cebolla", "pesable": True, "precio": 1100, "costo": 700, "stock": 30, "stock_min": 8},
    {"codigo": "4", "nombre": "Zanahoria", "pesable": True, "precio": 1300, "costo": 800, "stock": 15, "stock_min": 5},
    {"codigo": "5", "nombre": "Lechuga", "pesable": True, "precio": 3000, "costo": 1900, "stock": 6, "stock_min": 3},
    {"codigo": "6", "nombre": "Zapallo", "pesable": True, "precio": 1500, "costo": 900, "stock": 25, "stock_min": 5},
    {"codigo": "7", "nombre": "Banana", "pesable": True, "precio": 2200, "costo": 1500, "stock": 18, "stock_min": 5},
    {"codigo": "8", "nombre": "Manzana", "pesable": True, "precio": 2800, "costo": 1800, "stock": 20, "stock_min": 5},
    {"codigo": "9", "nombre": "Naranja", "pesable": True, "precio": 1800, "costo": 1100, "stock": 30, "stock_min": 8},
    {"codigo": "10", "nombre": "Limón", "pesable": True, "precio": 2000, "costo": 1200, "stock": 10, "stock_min": 3},
    {"codigo": "11", "nombre": "Huevos x docena", "pesable": False, "precio": 4500, "costo": 3500, "stock": 12, "stock_min": 4},
    {"codigo": "12", "nombre": "Atado de perejil", "pesable": False, "precio": 800, "costo": 400, "stock": 10, "stock_min": 3},
]


# ---------------------------------------------------------------- bloqueo entre procesos
class _Candado:
    """Lock reentrante que además bloquea un archivo, para que el POS y el servidor web
    no pisen sus escrituras."""

    def __init__(self):
        self._r = threading.RLock()
        self._n = 0
        self._fh = None

    def __enter__(self):
        self._r.acquire()
        if self._n == 0:
            os.makedirs(DATOS, exist_ok=True)
            self._fh = open(os.path.join(DATOS, ".lock"), "a+")
            self._fh.seek(0)
            if os.name == "nt":
                import msvcrt
                while True:
                    try:
                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_LOCK, 1)
                        break
                    except OSError:
                        time.sleep(0.05)
            else:
                import fcntl
                fcntl.flock(self._fh, fcntl.LOCK_EX)
        self._n += 1
        return self

    def __exit__(self, *exc):
        self._n -= 1
        if self._n == 0:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self._fh.close()
                self._fh = None
        self._r.release()


_lock = _Candado()


# ---------------------------------------------------------------- utilidades
def leer_json(path, defecto=None):
    for intento in range(5):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return copy.deepcopy(defecto)
        except (PermissionError, json.JSONDecodeError):
            if intento == 4:
                raise
            time.sleep(0.05)


def escribir_json(path, data):
    """Escritura atómica: si se corta la luz no queda el archivo a medias."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    for intento in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:      # Windows: otro proceso lo está leyendo justo ahora
            if intento == 19:
                raise
            time.sleep(0.05)


def _mezclar(defecto, actual):
    res = copy.deepcopy(defecto)
    for k, v in (actual or {}).items():
        if isinstance(v, dict) and isinstance(res.get(k), dict):
            res[k] = _mezclar(res[k], v)
        else:
            res[k] = v
    return res


def ruta_absoluta(ruta):
    if not ruta:
        return ""
    # las rutas relativas (ej. "datos/logo.png") son relativas a la carpeta que contiene "datos"
    return ruta if os.path.isabs(ruta) else os.path.join(os.path.dirname(DATOS), ruta)


# ---------------------------------------------------------------- configuración
def cargar_config():
    cfg = _mezclar(CONFIG_DEFECTO, leer_json(ARCH_CONFIG, {}))
    escribir_json(ARCH_CONFIG, cfg)
    return cfg


def guardar_config(cfg):
    escribir_json(ARCH_CONFIG, cfg)


# ---------------------------------------------------------------- productos y stock
def cargar_productos():
    with _lock:
        if not os.path.exists(ARCH_PRODUCTOS):
            escribir_json(ARCH_PRODUCTOS, PRODUCTOS_EJEMPLO)
        prods = leer_json(ARCH_PRODUCTOS, [])
        for p in prods:
            p.setdefault("activo", True)
            p.setdefault("stock", 0)
            p.setdefault("stock_min", 0)
            p.setdefault("costo", 0)
        return prods


def guardar_productos(lista):
    with _lock:
        escribir_json(ARCH_PRODUCTOS, lista)


def siguiente_codigo(lista):
    nums = [int(p["codigo"]) for p in lista if str(p["codigo"]).isdigit()]
    return str(max(nums, default=0) + 1)


def guardar_producto(prod, codigo_original=None):
    """Alta (codigo_original=None) o modificación. El stock solo se toma en el alta;
    después se cambia con ingreso_mercaderia / ajustar_stock."""
    nombre = str(prod.get("nombre", "")).strip()
    cod = str(prod.get("codigo", "")).strip()
    if not nombre:
        raise ValueError("El nombre es obligatorio")
    with _lock:
        prods = cargar_productos()
        if not cod:
            cod = siguiente_codigo(prods)
        if any(p["codigo"] == cod and p["codigo"] != codigo_original for p in prods):
            raise ValueError(f"Ya existe un producto con código {cod}")
        campos = {"codigo": cod, "nombre": nombre, "pesable": bool(prod.get("pesable", True)),
                  "activo": bool(prod.get("activo", True)), "precio": float(prod.get("precio", 0)),
                  "costo": float(prod.get("costo", 0)), "stock_min": float(prod.get("stock_min", 0)),
                  "icono": str(prod.get("icono") or "")}   # vacío = se elige solo según el nombre
        if codigo_original:
            p = next((x for x in prods if x["codigo"] == codigo_original), None)
            if not p:
                raise ValueError("El producto no existe")
            p.update(campos)
        else:
            campos["stock"] = float(prod.get("stock", 0))
            prods.append(campos)
        guardar_productos(prods)
        return campos


def eliminar_producto(codigo):
    with _lock:
        guardar_productos([p for p in cargar_productos() if p["codigo"] != codigo])


def mover_stock(cambios, motivo):
    """cambios: lista de (codigo, delta). Suma/resta stock y deja registro."""
    with _lock:
        prods = cargar_productos()
        idx = {p["codigo"]: p for p in prods}
        ahora = datetime.now().isoformat(timespec="seconds")
        os.makedirs(DIR_PRODUCTOS, exist_ok=True)
        with open(ARCH_STOCK_LOG, "a", encoding="utf-8") as log:
            for cod, delta in cambios:
                p = idx.get(cod)
                if not p:
                    continue
                p["stock"] = round(p.get("stock", 0) + delta, 3)
                log.write(json.dumps({"fecha": ahora, "codigo": cod, "nombre": p["nombre"],
                                      "cantidad": round(delta, 3), "stock": p["stock"],
                                      "motivo": motivo}, ensure_ascii=False) + "\n")
        guardar_productos(prods)


def ajustar_stock(codigo, stock_real, motivo):
    with _lock:
        p = next((x for x in cargar_productos() if x["codigo"] == codigo), None)
        if not p:
            raise ValueError("El producto no existe")
        mover_stock([(codigo, stock_real - p["stock"])], f"Ajuste: {motivo}")


def ingreso_mercaderia(codigo, cantidad, costo, registrar_egreso, medio="Efectivo"):
    with _lock:
        prods = cargar_productos()
        p = next((x for x in prods if x["codigo"] == codigo), None)
        if not p:
            raise ValueError("El producto no existe")
        p["costo"] = costo
        guardar_productos(prods)
        mover_stock([(codigo, cantidad)], "Ingreso de mercadería")
        if registrar_egreso and cantidad * costo > 0:
            registrar_movimiento("egreso", f"Compra: {p['nombre']} x {cantidad:g}", round(cantidad * costo, 2), medio)


def historial_stock(limite=300):
    try:
        with open(ARCH_STOCK_LOG, encoding="utf-8") as f:
            lineas = f.readlines()[-limite:]
    except FileNotFoundError:
        return []
    return [json.loads(x) for x in reversed(lineas) if x.strip()]


# ---------------------------------------------------------------- ventas
def carpeta_dia(fecha):
    return os.path.join(DIR_VENTAS, f"{fecha:%Y}", f"{fecha:%m}", f"{fecha:%d}")


def archivo_venta(venta):
    fecha = datetime.fromisoformat(venta["fecha"])
    return os.path.join(carpeta_dia(fecha), f"venta_{venta['numero']:06d}.json")


def registrar_venta(venta):
    """Asigna número y fecha, guarda la venta y descuenta stock."""
    with _lock:
        ahora = datetime.now()
        cont = leer_json(ARCH_CONTADOR, {"ultimo": 0})
        venta["numero"] = cont["ultimo"] + 1
        venta["fecha"] = ahora.isoformat(timespec="seconds")
        venta["estado"] = "activa"
        escribir_json(archivo_venta(venta), venta)
        escribir_json(ARCH_CONTADOR, {"ultimo": venta["numero"], "fecha": venta["fecha"]})
        mover_stock([(i["codigo"], -i["cantidad"]) for i in venta["items"]], f"Venta #{venta['numero']}")
        return venta


def leer_venta(numero, fecha_iso):
    return leer_json(archivo_venta({"numero": int(numero), "fecha": fecha_iso}))


def anular_venta(venta, motivo):
    """Marca la venta como anulada (no se borra) y devuelve el stock."""
    with _lock:
        path = archivo_venta(venta)
        v = leer_json(path)
        if not v:
            raise ValueError("La venta no existe")
        if v["estado"] == "anulada":
            raise ValueError("La venta ya estaba anulada")
        v["estado"] = "anulada"
        v["anulacion"] = {"fecha": datetime.now().isoformat(timespec="seconds"), "motivo": motivo}
        escribir_json(path, v)
        mover_stock([(i["codigo"], i["cantidad"]) for i in v["items"]], f"Anulación venta #{v['numero']}")
        return v


def ultima_venta():
    cont = leer_json(ARCH_CONTADOR, {"ultimo": 0})
    if not cont.get("ultimo"):
        return None
    return leer_venta(cont["ultimo"], cont["fecha"])


def ventas_del_dia(fecha):
    archivos = sorted(glob.glob(os.path.join(carpeta_dia(fecha), "venta_*.json")))
    return [leer_json(a) for a in archivos]


# ---------------------------------------------------------------- ingresos / egresos de caja
def registrar_movimiento(tipo, concepto, monto, medio="Efectivo"):
    if tipo not in ("ingreso", "egreso"):
        raise ValueError("Tipo inválido")
    ahora = datetime.now()
    mov = {"id": ahora.strftime("%H%M%S%f"), "tipo": tipo, "fecha": ahora.isoformat(timespec="seconds"),
           "concepto": concepto, "monto": round(monto, 2), "medio": medio}
    escribir_json(os.path.join(carpeta_dia(ahora), f"{tipo}_{mov['id']}.json"), mov)
    return mov


def movimientos_del_dia(fecha):
    carpeta = carpeta_dia(fecha)
    archivos = glob.glob(os.path.join(carpeta, "ingreso_*.json")) + glob.glob(os.path.join(carpeta, "egreso_*.json"))
    movs = [leer_json(a) for a in archivos]
    return sorted(movs, key=lambda m: m["fecha"])


# ---------------------------------------------------------------- consultas por período
def dias(desde, hasta):
    d = desde
    while d <= hasta:
        yield d
        d += timedelta(days=1)


def ventas_rango(desde, hasta):
    return [v for d in dias(desde, hasta) for v in ventas_del_dia(d)]


def movimientos_rango(desde, hasta):
    return [m for d in dias(desde, hasta) for m in movimientos_del_dia(d)]


def resumen(desde: date, hasta: date):
    """Balance del período: ventas, costos, ganancia, caja, por día, por medio, por producto."""
    ventas = ventas_rango(desde, hasta)
    movs = movimientos_rango(desde, hasta)
    activas = [v for v in ventas if v["estado"] != "anulada"]

    por_dia = {d.isoformat(): {"fecha": d.isoformat(), "ventas": 0.0, "costo": 0.0, "cantidad": 0, "egresos": 0.0}
               for d in dias(desde, hasta)}
    por_hora = {h: {"hora": h, "ventas": 0.0, "cantidad": 0} for h in range(24)}
    medios, productos = {}, {}
    for v in activas:
        dia = por_dia[v["fecha"][:10]]
        dia["ventas"] += v["total"]
        dia["costo"] += v.get("costo_total", 0)
        dia["cantidad"] += 1
        h = por_hora[int(v["fecha"][11:13])]
        h["ventas"] += v["total"]
        h["cantidad"] += 1
        medio = v.get("pago", {}).get("medio", "?")
        medios[medio] = medios.get(medio, 0) + v["total"]
        for it in v["items"]:
            p = productos.setdefault(it["codigo"], {"codigo": it["codigo"], "nombre": it["nombre"],
                                                    "pesable": it["pesable"], "cantidad": 0.0,
                                                    "importe": 0.0, "costo": 0.0})
            p["cantidad"] += it["cantidad"]
            p["importe"] += it["importe"]
            p["costo"] += it["cantidad"] * it.get("costo", 0)
    for m in movs:
        if m["tipo"] == "egreso" and m["fecha"][:10] in por_dia:
            por_dia[m["fecha"][:10]]["egresos"] += m["monto"]

    total = sum(v["total"] for v in activas)
    costo = sum(v.get("costo_total", 0) for v in activas)
    ingresos = sum(m["monto"] for m in movs if m["tipo"] == "ingreso")
    egresos = sum(m["monto"] for m in movs if m["tipo"] == "egreso")
    # las compras de mercadería ya están en el costo de lo vendido: para el resultado solo restan los demás gastos
    compras = sum(m["monto"] for m in movs if m["tipo"] == "egreso" and m["concepto"].startswith("Compra:"))
    gastos = egresos - compras
    egresos_concepto = {}
    for m in movs:
        if m["tipo"] == "egreso":
            clave = "Compras de mercadería" if m["concepto"].startswith("Compra:") else m["concepto"]
            egresos_concepto[clave] = egresos_concepto.get(clave, 0) + m["monto"]
    efectivo = (medios.get("Efectivo", 0)
                + sum(m["monto"] for m in movs if m["tipo"] == "ingreso" and m["medio"] == "Efectivo")
                - sum(m["monto"] for m in movs if m["tipo"] == "egreso" and m["medio"] == "Efectivo"))
    prods_stock = cargar_productos()
    r2 = lambda x: round(x, 2)
    for p in productos.values():
        p["ganancia"] = r2(p["importe"] - p["costo"])
        p["margen"] = r2((p["importe"] - p["costo"]) / p["costo"] * 100) if p["costo"] else None
        p["cantidad"] = round(p["cantidad"], 3)
        p["importe"], p["costo"] = r2(p["importe"]), r2(p["costo"])
    for d in por_dia.values():
        d["ventas"], d["costo"], d["egresos"] = r2(d["ventas"]), r2(d["costo"]), r2(d["egresos"])
    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "ventas_total": r2(total), "ventas_cantidad": len(activas), "anuladas": len(ventas) - len(activas),
        "ticket_promedio": r2(total / len(activas)) if activas else 0,
        "costo": r2(costo), "ganancia": r2(total - costo),
        "margen": r2((total - costo) / total * 100) if total else 0,
        "ingresos": r2(ingresos), "egresos": r2(egresos),
        "compras": r2(compras), "gastos": r2(gastos),
        "egresos_concepto": [{"concepto": k, "total": r2(x)} for k, x in sorted(egresos_concepto.items(), key=lambda i: -i[1])],
        "balance": r2(total + ingresos - egresos), "resultado": r2(total - costo + ingresos - gastos),
        "efectivo": r2(efectivo),
        "medios": [{"medio": k, "total": r2(x)} for k, x in sorted(medios.items(), key=lambda i: -i[1])],
        "por_dia": list(por_dia.values()),
        "por_hora": [h for h in por_hora.values() if h["cantidad"]],
        "productos": sorted(productos.values(), key=lambda p: -p["importe"]),
        "stock_valorizado": r2(sum(max(p["stock"], 0) * p.get("costo", 0) for p in prods_stock)),
        "stock_bajo": sum(1 for p in prods_stock if p.get("activo", True) and p["stock"] <= p.get("stock_min", 0)),
    }
