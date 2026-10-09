"""Convierte docs/MANUAL.md en un PDF con tapa (usa Microsoft Edge para imprimir).

    python docs/generar_pdf.py [salida.pdf]
"""
import os
import subprocess
import sys
import tempfile

import markdown
from markdown.extensions.toc import slugify_unicode

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]

CSS = """
@page { size: A4; margin: 16mm 15mm 18mm; }
body { font: 10.5pt/1.5 "Segoe UI", Arial, sans-serif; color: #1F2D21; }
h1 { display: none; }
h2 { color: #1B5E20; border-bottom: 3px solid #FDD835; padding-bottom: 4px; margin-top: 0; break-before: page; font-size: 19pt; }
h3 { color: #2E7D32; font-size: 13pt; margin-top: 18px; }
a { color: #2E7D32; text-decoration: none; }
img { max-width: 100%; max-height: 112mm; object-fit: contain; border-radius: 6px; box-shadow: 0 1px 6px rgba(0,0,0,.18); break-inside: avoid; }
p:has(> img) { text-align: center; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; break-inside: avoid; font-size: 9.5pt; }
th { background: #2E7D32; color: #fff; text-align: left; padding: 6px 8px; }
td { border-bottom: 1px solid #D7E7D6; padding: 5px 8px; vertical-align: top; }
tr:nth-child(even) td { background: #F5FAF4; }
blockquote { background: #FFF8C4; border-left: 5px solid #FDD835; margin: 10px 0; padding: 6px 14px; border-radius: 4px; }
code { background: #EEF5EE; padding: 1px 5px; border-radius: 4px; font-size: 9.5pt; }
pre { background: #EEF5EE; padding: 10px 12px; border-radius: 6px; font-size: 9pt; break-inside: avoid; }
pre code { background: none; padding: 0; }
hr { display: none; }
.tapa { height: 255mm; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.tapa img { width: 85mm; box-shadow: none; }
.tapa .titulo { font-size: 30pt; font-weight: 800; color: #1B5E20; margin-top: 14mm; }
.tapa .sub { font-size: 15pt; color: #2E7D32; margin-top: 3mm; }
.tapa .franja { width: 60mm; height: 4px; background: #FDD835; margin: 8mm auto; }
.tapa .autor { font-size: 11pt; color: #5E6F60; }
.indice h2 { break-before: auto; }
"""


def main():
    salida = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(AQUI, "Manual - La Verdulería de Margarita.pdf")
    texto = open(os.path.join(AQUI, "MANUAL.md"), encoding="utf-8").read()
    # la primera parte (título, logo, intro) se reemplaza por la tapa
    cuerpo = texto.split("## Índice", 1)[1]
    html = markdown.markdown("## Índice" + cuerpo, extensions=["tables", "fenced_code", "toc"],
                             extension_configs={"toc": {"slugify": slugify_unicode}})
    html = html.replace("<h2 id=\"índice\">", "<div class=\"indice\"><h2 id=\"índice\">", 1)
    html = html.replace("<h2 id=\"1-qué-incluye\">", "</div><h2 id=\"1-qué-incluye\">", 1)
    tapa = f"""<div class="tapa">
      <img src="file:///{os.path.join(RAIZ, 'img', 'icono.png').replace(os.sep, '/')}">
      <div class="titulo">Manual de uso</div>
      <div class="sub">La Verdulería de Margarita · versión 1.0.0</div>
      <div class="franja"></div>
      <div class="autor">POS con balanza · Tickets · Productos · Stock · Caja · Panel web<br><br>
      Desarrollado por Fernando S. Brandolini · eRios</div></div>"""
    base = "file:///" + AQUI.replace(os.sep, "/") + "/"
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><base href="{base}">
    <title>Manual - La Verdulería de Margarita</title><style>{CSS}</style></head><body>{tapa}{html}</body></html>"""
    tmp = os.path.join(tempfile.mkdtemp(), "manual.html")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(doc)
    edge = next(e for e in EDGE if os.path.exists(e))
    subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
                    f"--user-data-dir={tempfile.mkdtemp()}", "--virtual-time-budget=5000",
                    f"--print-to-pdf={salida}", "file:///" + tmp.replace(os.sep, "/")], check=True, capture_output=True, timeout=120)
    print(f"PDF: {salida} ({os.path.getsize(salida) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
