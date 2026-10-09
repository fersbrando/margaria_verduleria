"""Formatos de números al estilo argentino ($1.234,50 / 1,235 kg)."""


def num(texto):
    """Convierte lo que escribe el usuario a float. Acepta '1200', '1200,50', '1.200,50', '0.350'.
    Lanza ValueError si no es un número."""
    t = str(texto).strip().replace("$", "").replace(" ", "")
    if not t:
        raise ValueError("vacío")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return float(t)


def pesos(valor):
    s = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-$" if valor < 0 else "$") + s


def kg(valor):
    return f"{valor:.3f}".replace(".", ",") + " kg"


def cantidad_txt(item):
    if item["pesable"]:
        return kg(item["cantidad"])
    return f"{item['cantidad']:g} u"
