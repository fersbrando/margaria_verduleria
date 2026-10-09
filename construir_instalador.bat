@echo off
cd /d "%~dp0"
rem Arma empaquetar\salida\Instalar_VerduleriaMargarita_<version>.exe
rem Uso: construir_instalador.bat [version]   (ej: construir_instalador.bat 1.0.1)
python empaquetar\construir.py %1
pause
