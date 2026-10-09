# PyInstaller: arma los dos programas en una sola carpeta (comparten Python y librerías).
#   VerduleriaMargarita.exe           -> POS (app.py)
#   VerduleriaMargarita-Servicio.exe  -> ícono de la bandeja + servicio web (bandeja.py)
# No ejecutar directo: usar  python empaquetar/construir.py
import os

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))
ICONO = os.path.join(RAIZ, "img", "icono.ico")
OCULTOS = ["pystray._win32", "PIL._tkinter_finder", "win32timezone", "serial.tools.list_ports_windows"]
EXCLUIR = ["pygame", "numpy", "pandas", "matplotlib", "scipy", "pytest", "IPython", "PyQt5", "PySide6"]


def analizar(script):
    return Analysis([os.path.join(RAIZ, script)], pathex=[RAIZ], hiddenimports=OCULTOS, excludes=EXCLUIR)


def programa(a, nombre, version):
    pyz = PYZ(a.pure)
    return EXE(pyz, a.scripts, [], exclude_binaries=True, name=nombre, icon=ICONO, console=False,
               version=os.path.join(SPECPATH, "build", version), upx=False)


a_pos = analizar("app.py")
a_srv = analizar("bandeja.py")
exe_pos = programa(a_pos, "VerduleriaMargarita", "version_pos.txt")
exe_srv = programa(a_srv, "VerduleriaMargarita-Servicio", "version_servicio.txt")

COLLECT(exe_pos, a_pos.binaries, a_pos.datas,
        exe_srv, a_srv.binaries, a_srv.datas,
        name="VerduleriaMargarita", upx=False)
