"""Armado e impresión del ticket (texto plano + comandos ESC/POS para impresoras térmicas)."""
import os
import unicodedata
from datetime import datetime

import serial

import datos
from formato import cantidad_txt, pesos


def _ascii(texto):
    """Las térmicas baratas no siempre traen acentos: 'Limón' -> 'Limon'."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def armar_ticket(venta, cfg, reimpresion=False):
    w = int(cfg["impresora"]["ancho"])
    neg = cfg["negocio"]
    linea = "-" * w

    def centro(s):
        return s[:w].center(w).rstrip()

    def dos(izq, der):
        esp = w - len(izq) - len(der)
        if esp < 1:
            return izq + "\n" + der.rjust(w)
        return izq + " " * esp + der

    # con logo, el nombre ya está en el sello: solo se escribe si no hay logo
    logo = datos.ruta_absoluta(cfg["impresora"].get("logo", ""))
    L = [] if logo and os.path.exists(logo) else [centro(neg["nombre"].upper())]
    L += [centro(x) for x in (neg.get("linea1"), neg.get("linea2")) if x]
    if venta.get("estado") == "anulada":
        L.append(centro("*** VENTA ANULADA ***"))
    if reimpresion:
        L.append(centro("-- REIMPRESION --"))
    L.append(linea)
    fecha = datetime.fromisoformat(venta["fecha"])
    L.append(dos(f"Ticket N {venta['numero']:06d}", f"{fecha:%d/%m/%Y %H:%M}"))
    L.append(linea)
    for it in venta["items"]:
        L.append(it["nombre"][:w])
        L.append(dos(f"  {cantidad_txt(it)} x {pesos(it['precio'])}", pesos(it["importe"])))
    L.append(linea)
    L.append(dos("TOTAL", pesos(venta["total"])))
    pago = venta.get("pago", {})
    L.append(dos("Pago:", pago.get("medio", "")))
    if pago.get("paga_con"):
        L.append(dos("Paga con:", pesos(pago["paga_con"])))
        L.append(dos("Vuelto:", pesos(pago.get("vuelto", 0))))
    L.append(linea)
    if neg.get("pie"):
        L.append(centro(neg["pie"]))
    L.append(centro("No valido como factura"))
    return "\n".join(L)


def cargar_logo(cfg_imp, ancho_px=None):
    """Devuelve el logo como imagen PIL blanco/negro lista para imprimir, o None."""
    path = datos.ruta_absoluta(cfg_imp.get("logo", ""))
    if not path or not os.path.exists(path):
        return None
    from PIL import Image
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        fondo = Image.new("RGBA", im.size, "white")
        fondo.alpha_composite(im)
        im = fondo
    im = im.convert("L")
    ancho = int(ancho_px or cfg_imp.get("logo_ancho_px", 300))
    if im.width != ancho:
        im = im.resize((ancho, max(1, round(im.height * ancho / im.width))), Image.LANCZOS)
    return im.convert("1")       # tramado (dithering) para que los grises se vean bien


def _logo_escpos(im):
    """Imagen raster ESC/POS (GS v 0), centrada."""
    from PIL import ImageOps
    ancho_bytes = (im.width + 7) // 8
    negro = ImageOps.invert(im.convert("L")).convert("1")   # en ESC/POS 1 = punto negro
    alto = im.height
    return (b"\x1ba\x01" + b"\x1dv0\x00" + bytes([ancho_bytes & 255, ancho_bytes >> 8, alto & 255, alto >> 8])
            + negro.tobytes() + b"\n\x1ba\x00")


def ticket_imagen(texto, cfg_imp):
    """Simula el ticket impreso (logo + texto) como imagen PIL: para vista previa y modo 'archivo'."""
    from PIL import Image, ImageDraw, ImageFont
    chars = int(cfg_imp.get("ancho", 32))
    papel = 384 if chars <= 32 else 576
    fuente, tam = None, 24
    for tam in range(24, 9, -1):
        try:
            fuente = ImageFont.truetype("consola.ttf", tam)
        except OSError:
            fuente = ImageFont.load_default()
            break
        if fuente.getlength("M" * chars) <= papel - 16:
            break
    try:
        logo = cargar_logo(cfg_imp, min(int(cfg_imp.get("logo_ancho_px", 300)), papel))
    except Exception:
        logo = None
    lineas = texto.split("\n")
    alto_linea = int(tam * 1.3)
    alto = 20 + (logo.height + 12 if logo else 0) + len(lineas) * alto_linea + 20
    img = Image.new("L", (papel, alto), 255)
    y = 20
    if logo:
        img.paste(logo.convert("L"), ((papel - logo.width) // 2, y))
        y += logo.height + 12
    d = ImageDraw.Draw(img)
    for linea in lineas:
        d.text((8, y), _ascii(linea), font=fuente, fill=0)
        y += alto_linea
    return img


def _bytes_escpos(texto, cfg_imp):
    b = b"\x1b@"                                  # inicializar
    try:
        logo = cargar_logo(cfg_imp)
        if logo:
            b += _logo_escpos(logo)
    except Exception:
        pass                                      # si el logo falla, el ticket sale igual
    b += _ascii(texto).encode("ascii", "replace")
    b += b"\n\n\n\n"
    if cfg_imp.get("cortar"):
        b += b"\x1dV\x01"                         # corte parcial
    return b


def imprimir(texto, cfg_imp, balanza=None):
    """Devuelve la ruta del archivo si el tipo es 'archivo'. Lanza excepción si falla."""
    tipo = cfg_imp["tipo"]
    if tipo == "ninguna":
        return None
    if tipo == "archivo":
        path = os.path.join(datos.DATOS, "ultimo_ticket.txt")
        os.makedirs(datos.DATOS, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(texto)
        try:
            ticket_imagen(texto, cfg_imp).save(os.path.join(datos.DATOS, "ultimo_ticket.png"))
        except Exception:
            pass
        return path

    data = _bytes_escpos(texto, cfg_imp)
    if tipo == "serial":
        # Si la impresora está en el mismo puerto que la balanza, reutilizamos esa conexión.
        if balanza and balanza.ser and str(balanza.cfg["puerto"]).upper() == str(cfg_imp["puerto"]).upper():
            with balanza.lock:
                balanza.ser.write(data)
                balanza.ser.flush()
        else:
            with serial.Serial(cfg_imp["puerto"], int(cfg_imp["baudios"]), timeout=2, write_timeout=10) as s:
                s.write(data)
                s.flush()
    elif tipo == "windows":
        import win32print
        nombre = cfg_imp.get("nombre_windows") or win32print.GetDefaultPrinter()
        h = win32print.OpenPrinter(nombre)
        try:
            win32print.StartDocPrinter(h, 1, ("Ticket", None, "RAW"))
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, data)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)
    else:
        raise ValueError(f"Tipo de impresora desconocido: {tipo}")
    return None


def impresoras_windows():
    try:
        import win32print
        return [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
    except Exception:
        return []
