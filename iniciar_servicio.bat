@echo off
cd /d "%~dp0"
rem Abre el icono del servicio web junto al reloj (inicia el servicio y abre el panel)
start "" pythonw bandeja.py --abrir
