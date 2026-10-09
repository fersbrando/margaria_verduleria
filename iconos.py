"""Íconos del sistema (Twemoji, CDN jsdelivr). Se guardan en img/iconos/ para funcionar sin internet.

Twemoji © Twitter, Inc. y colaboradores — licencia CC-BY 4.0 (https://github.com/twitter/twemoji).
"""
import os
import sys
import unicodedata
import urllib.request

# Carpeta del programa: junto al .exe cuando está instalado (PyInstaller), o la de este archivo en desarrollo
BASE = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
DIR_ICONOS = os.path.join(BASE, "img", "iconos")
CDN = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{}.png"

# ---- íconos de la interfaz (nombre -> código del emoji)
UI = {
    "pos": "1f6d2", "productos": "1f955", "stock": "1f4e6", "caja": "1f4b0", "config": "2699",
    "agregar": "2705", "cobrar": "1f4b5", "quitar": "2796", "reimprimir": "1f5a8", "cancelar": "1f5d1",
    "limpiar": "1f9f9", "buscar": "1f50d", "balanza": "2696", "pantalla": "1f5a5", "nuevo": "2795",
    "guardar": "1f4be", "eliminar": "1f5d1", "ingreso_merc": "1f69a", "ajuste": "270f", "ingreso": "1f4e5",
    "egreso": "1f4e4", "ticket": "1f9fe", "anular": "1f6ab", "hoy": "1f4c5", "web": "1f310",
    "logo": "1f5bc", "teclado": "2328", "ok": "2714", "atras": "25c0", "adelante": "25b6",
}

# ---- íconos para productos: (código, nombre, palabras que lo identifican en el nombre del producto)
PRODUCTOS = [
    ("1f345", "Tomate", ["tomate"]),
    ("1f954", "Papa", ["papa"]),
    ("1f360", "Batata", ["batata", "boniato"]),
    ("1f9c5", "Cebolla", ["cebolla", "verdeo", "puerro"]),
    ("1f9c4", "Ajo", ["ajo"]),
    ("1f955", "Zanahoria", ["zanahoria"]),
    ("1f96c", "Hoja verde", ["lechuga", "acelga", "espinaca", "rucula", "repollo", "radicheta", "kale", "hoja"]),
    ("1f966", "Brócoli", ["brocoli", "coliflor"]),
    ("1f952", "Pepino", ["pepino", "zucchini", "zuchini", "zapallito"]),
    ("1f383", "Zapallo", ["zapallo", "calabaza", "anco"]),
    ("1f346", "Berenjena", ["berenjena"]),
    ("1fad1", "Morrón", ["morron", "pimiento"]),
    ("1f336", "Ají", ["aji", "picante", "jalapeno"]),
    ("1f33d", "Choclo", ["choclo", "maiz"]),
    ("1f344", "Hongo", ["hongo", "champi", "girgola"]),
    ("1f33f", "Hierbas", ["perejil", "albahaca", "cilantro", "menta", "romero", "oregano", "hierba", "atado"]),
    ("1f951", "Palta", ["palta", "aguacate"]),
    ("1f34c", "Banana", ["banana"]),
    ("1f34e", "Manzana", ["manzana roja", "manzana"]),
    ("1f34f", "Manzana verde", ["manzana verde", "granny"]),
    ("1f350", "Pera", ["pera"]),
    ("1f34a", "Naranja", ["naranja", "mandarina", "pomelo"]),
    ("1f34b", "Limón", ["limon", "lima"]),
    ("1f347", "Uva", ["uva"]),
    ("1f353", "Frutilla", ["frutilla", "fresa"]),
    ("1f352", "Cereza", ["cereza"]),
    ("1fad0", "Arándano", ["arandano"]),
    ("1f351", "Durazno", ["durazno", "pelon", "damasco", "ciruela"]),
    ("1f34d", "Ananá", ["anana", "pina"]),
    ("1f96d", "Mango", ["mango"]),
    ("1f95d", "Kiwi", ["kiwi"]),
    ("1f349", "Sandía", ["sandia"]),
    ("1f348", "Melón", ["melon"]),
    ("1f965", "Coco", ["coco"]),
    ("1f95c", "Frutos secos", ["mani", "nuez", "almendra", "fruto seco", "pasa"]),
    ("1f95a", "Huevos", ["huevo", "maple"]),
    ("1fad2", "Aceitunas", ["aceituna"]),
    ("1f35e", "Pan", ["pan"]),
    ("1f9c0", "Queso", ["queso"]),
    ("1f36f", "Miel", ["miel"]),
    ("1f6cd", "Bolsa", ["bolsa"]),
    ("1f9fa", "Genérico", []),
]
GENERICO = "1f9fa"


def _normal(t):
    return unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()


def adivinar(nombre):
    """Elige un ícono según el nombre del producto (ej. 'Tomate perita' -> tomate)."""
    n = _normal(nombre)
    mejor, largo = GENERICO, 0
    for cp, _nom, palabras in PRODUCTOS:
        for p in palabras:
            if p in n and len(p) > largo:      # la coincidencia más larga gana ('manzana verde' > 'manzana')
                mejor, largo = cp, len(p)
    return mejor


def de_producto(p):
    return p.get("icono") or adivinar(p.get("nombre", ""))


def catalogo():
    return [{"cp": cp, "nombre": nom, "palabras": pal} for cp, nom, pal in PRODUCTOS]


def ruta(cp):
    return os.path.join(DIR_ICONOS, f"{cp}.png")


def descargar(cp, timeout=6):
    """Baja un ícono del CDN si no está en disco. Devuelve True si quedó disponible."""
    destino = ruta(cp)
    if os.path.exists(destino):
        return True
    os.makedirs(DIR_ICONOS, exist_ok=True)
    try:
        with urllib.request.urlopen(CDN.format(cp), timeout=timeout) as r:
            data = r.read()
        if not data.startswith(b"\x89PNG"):
            return False
        with open(destino + ".tmp", "wb") as f:
            f.write(data)
        os.replace(destino + ".tmp", destino)
        return True
    except OSError:
        return False


def todos():
    return sorted(set(UI.values()) | {cp for cp, _, _ in PRODUCTOS})


def descargar_faltantes():
    """Baja los íconos que falten. Devuelve cuántos se bajaron."""
    faltan = [cp for cp in todos() if not os.path.exists(ruta(cp))]
    return sum(1 for cp in faltan if descargar(cp))


if __name__ == "__main__":
    print("Descargados:", descargar_faltantes(), "· en disco:", sum(os.path.exists(ruta(c)) for c in todos()), "de", len(todos()))
