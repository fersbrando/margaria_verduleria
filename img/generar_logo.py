"""Genera las versiones del logo a partir de la imagen original (ejecutar: python img/generar_logo.py).

Original:  img/logo.jpg   (si cambiás el logo, reemplazá ese archivo y volvé a ejecutar esto)

icono.png        sello recortado en redondo, fondo transparente (encabezado del POS, panel web)
icono_64.png     igual, chico (ícono de la ventana y favicon)
logo_ticket.png  blanco y negro con buen contraste para la impresora térmica
"""
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

AQUI = os.path.dirname(os.path.abspath(__file__))
ORIGINALES = ["logo.jpg", "logo.jpeg", "logo.png.original"]


def cargar_original():
    for nombre in ORIGINALES:
        path = os.path.join(AQUI, nombre)
        if os.path.exists(path):
            return Image.open(path).convert("RGB")
    raise SystemExit(f"No encontré el logo original en img/ ({', '.join(ORIGINALES)})")


def recortar_sello(im):
    """Busca el anillo oscuro del sello y recorta un círculo justo alrededor."""
    oscuro = im.convert("L").point(lambda v: 255 if v < 110 else 0)
    x0, y0, x1, y1 = oscuro.getbbox()
    lado = max(x1 - x0, y1 - y0) + 8
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    caja = (cx - lado // 2, cy - lado // 2, cx - lado // 2 + lado, cy - lado // 2 + lado)
    sello = im.crop(caja)
    # máscara redonda con bordes suaves (se dibuja 4 veces más grande y se achica)
    mascara = Image.new("L", (lado * 4, lado * 4), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, lado * 4 - 1, lado * 4 - 1), fill=255)
    sello.putalpha(mascara.resize((lado, lado), Image.LANCZOS))
    return sello


def version_ticket(sello, ancho=320):
    """Blanco y negro: el papel crema pasa a blanco y el verde a negro."""
    fondo = Image.new("RGBA", sello.size, "white")
    fondo.alpha_composite(sello)
    g = ImageOps.autocontrast(fondo.convert("L"), cutoff=1)
    g = ImageEnhance.Contrast(g).enhance(1.6)
    g = g.point(lambda v: 255 if v > 200 else v)          # saca la textura del papel
    return g.resize((ancho, round(g.height * ancho / g.width)), Image.LANCZOS)


if __name__ == "__main__":
    sello = recortar_sello(cargar_original())
    sello.resize((512, 512), Image.LANCZOS).save(os.path.join(AQUI, "icono.png"))
    sello.resize((64, 64), Image.LANCZOS).save(os.path.join(AQUI, "icono_64.png"))
    version_ticket(sello).save(os.path.join(AQUI, "logo_ticket.png"))
    print("Listo: icono.png, icono_64.png y logo_ticket.png en", AQUI)
