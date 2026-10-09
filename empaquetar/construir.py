"""Arma el instalador de La Verdulería de Margarita.

    python empaquetar/construir.py            (versión 1.0.0)
    python empaquetar/construir.py 1.0.1      (otra versión)

Pasos: íconos y logos -> datos de versión de los .exe -> PyInstaller (los dos .exe)
       -> copia img/ y servicioweb/ -> imágenes del asistente -> Inno Setup -> manual PDF + zip.
Resultado: empaquetar/salida/Instalar_VerduleriaMargarita_<versión>.exe
           descargas/VerduleriaMargarita_<versión>.zip   (instalador + manual PDF + LEEME PRIMERO, para subir a GitHub)
"""
import glob
import zipfile
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
BUILD, DIST = os.path.join(AQUI, "build"), os.path.join(AQUI, "dist")
DESTINO = os.path.join(DIST, "VerduleriaMargarita")
sys.path.insert(0, RAIZ)

EMPRESA = "eRios"
AUTOR = "Fernando S. Brandolini"
PRODUCTO = "La Verdulería de Margarita"

VERSION_TXT = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}), prodvers=({v}), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('0C0A04B0', [
      StringStruct('CompanyName', '{empresa}'),
      StringStruct('FileDescription', '{descripcion}'),
      StringStruct('FileVersion', '{vtxt}'),
      StringStruct('InternalName', '{interno}'),
      StringStruct('LegalCopyright', '© 2026 {autor} - {empresa}'),
      StringStruct('OriginalFilename', '{interno}.exe'),
      StringStruct('ProductName', '{producto}'),
      StringStruct('ProductVersion', '{vtxt}'),
      StringStruct('Comments', 'Desarrollado por {autor}')])]),
    VarFileInfo([VarStruct('Translation', [0x0C0A, 1200])])
  ]
)
"""


def paso(t):
    print(f"\n=== {t}", flush=True)


def buscar_iscc():
    candidatos = [os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\Inno Setup 6\ISCC.exe"),
                  os.path.join(os.environ.get("ProgramFiles(x86)", ""), r"Inno Setup 6\ISCC.exe"),
                  os.path.join(os.environ.get("ProgramFiles", ""), r"Inno Setup 6\ISCC.exe")]
    return next((c for c in candidatos if os.path.exists(c)), shutil.which("ISCC"))


def versiones(version):
    partes = [int(x) for x in version.split(".")] + [0] * 4
    v4 = ", ".join(str(x) for x in partes[:4])
    vtxt = ".".join(str(x) for x in partes[:4])
    os.makedirs(BUILD, exist_ok=True)
    for archivo, interno, desc in (("version_pos.txt", "VerduleriaMargarita", f"{PRODUCTO} - POS"),
                                   ("version_servicio.txt", "VerduleriaMargarita-Servicio", f"{PRODUCTO} - Servicio web")):
        with open(os.path.join(BUILD, archivo), "w", encoding="utf-8") as f:
            f.write(VERSION_TXT.format(v=v4, vtxt=vtxt, empresa=EMPRESA, autor=AUTOR, producto=PRODUCTO,
                                       descripcion=desc, interno=interno))


def imagenes_asistente():
    """Imágenes del instalador: panel lateral verde con el sello y logo chico arriba a la derecha."""
    from PIL import Image, ImageDraw, ImageFont
    sello = Image.open(os.path.join(RAIZ, "img", "icono.png")).convert("RGBA")
    for escala, sufijo in ((1, ""), (2, "_200")):
        W, H = 164 * escala, 314 * escala
        panel = Image.new("RGBA", (W, H), "#1B5E20")
        d = ImageDraw.Draw(panel)
        d.rectangle((0, H - 10 * escala, W, H), fill="#FDD835")
        lado = 136 * escala
        panel.alpha_composite(sello.resize((lado, lado), Image.LANCZOS), ((W - lado) // 2, 40 * escala))
        try:
            f1 = ImageFont.truetype("segoeuib.ttf", 15 * escala)
            f2 = ImageFont.truetype("segoeui.ttf", 11 * escala)
        except OSError:
            f1 = f2 = ImageFont.load_default()
        for texto, fuente, y, color in (("La Verdulería", f1, 196, "#FDD835"), ("de Margarita", f1, 216, "#FDD835"),
                                        ("POS · Balanza · Stock", f2, 250, "#E8F5E9"), ("Caja · Panel web", f2, 266, "#E8F5E9")):
            ancho = d.textlength(texto, font=fuente)
            d.text(((W - ancho) / 2, y * escala), texto, font=fuente, fill=color)
        panel.convert("RGB").save(os.path.join(BUILD, f"asistente{sufijo}.bmp"))
        chico = Image.new("RGBA", (55 * escala, 58 * escala), "white")
        l2 = 52 * escala
        chico.alpha_composite(sello.resize((l2, l2), Image.LANCZOS), ((55 * escala - l2) // 2, (58 * escala - l2) // 2))
        chico.convert("RGB").save(os.path.join(BUILD, f"asistente_chico{sufijo}.bmp"))


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "1.0.0"

    paso("1/7 Íconos y logos")
    import iconos
    iconos.descargar_faltantes()
    faltan = [c for c in iconos.todos() if not os.path.exists(iconos.ruta(c))]
    if faltan:
        sys.exit(f"Faltan íconos (¿sin internet?): {faltan}")
    subprocess.run([sys.executable, os.path.join(RAIZ, "img", "generar_logo.py")], check=True)

    paso("2/7 Datos de versión (empresa / desarrollador)")
    versiones(version)

    paso("3/7 PyInstaller: VerduleriaMargarita.exe y VerduleriaMargarita-Servicio.exe")
    shutil.rmtree(DESTINO, ignore_errors=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
                    "--distpath", DIST, "--workpath", os.path.join(BUILD, "pyinstaller"),
                    os.path.join(AQUI, "verduleria.spec")], check=True, cwd=AQUI)

    paso("4/7 Archivos del programa (img/, servicioweb/, LEEME)")
    ignorar = shutil.ignore_patterns("__pycache__", "*.pyc", "generar_logo.py")
    shutil.copytree(os.path.join(RAIZ, "img"), os.path.join(DESTINO, "img"), ignore=ignorar)
    shutil.copytree(os.path.join(RAIZ, "servicioweb"), os.path.join(DESTINO, "servicioweb"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "img"))   # la web usa ../img/
    shutil.copy(os.path.join(RAIZ, "LEEME.md"), DESTINO)
    os.makedirs(os.path.join(DESTINO, "datos"), exist_ok=True)   # vacía: se llena al usar el programa

    paso("5/7 Imágenes del asistente de instalación")
    imagenes_asistente()

    paso("6/7 Inno Setup")
    iscc = buscar_iscc()
    if not iscc:
        sys.exit("No encontré Inno Setup 6 (ISCC.exe). Instalalo con: winget install JRSoftware.InnoSetup")
    subprocess.run([iscc, "/Q", f"/DVersion={version}", os.path.join(AQUI, "instalador.iss")], check=True, cwd=AQUI)

    salida = glob.glob(os.path.join(AQUI, "salida", f"Instalar_VerduleriaMargarita_{version}.exe"))[0]
    print(f"Instalador: {salida}  ({os.path.getsize(salida) / 1e6:.1f} MB)")

    paso("7/7 Manual PDF y zip para descargar")
    pdf = os.path.join(BUILD, "Manual - La Verdulería de Margarita.pdf")
    subprocess.run([sys.executable, os.path.join(RAIZ, "docs", "generar_pdf.py"), pdf], check=True)
    leeme = open(os.path.join(AQUI, "LEEME PRIMERO.txt"), encoding="utf-8").read().replace("{version}", version)
    os.makedirs(os.path.join(RAIZ, "descargas"), exist_ok=True)
    archivo_zip = os.path.join(RAIZ, "descargas", f"VerduleriaMargarita_{version}.zip")
    with zipfile.ZipFile(archivo_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(salida, os.path.basename(salida))
        z.write(pdf, os.path.basename(pdf))
        # con BOM y CRLF para que el Bloc de notas muestre bien los acentos
        z.writestr("LEEME PRIMERO.txt", leeme.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8-sig"))
    print(f"\nLISTO: {archivo_zip}  ({os.path.getsize(archivo_zip) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
