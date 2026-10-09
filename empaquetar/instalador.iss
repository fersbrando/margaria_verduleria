; Instalador de La Verdulería de Margarita (Inno Setup 6).
; No compilar directo: usar  python empaquetar/construir.py  (arma los .exe y después esto).

#ifndef Version
  #define Version "1.0.0"
#endif
#define Nombre "La Verdulería de Margarita"
#define Empresa "eRios"
#define Autor "Fernando S. Brandolini"
#define ExePOS "VerduleriaMargarita.exe"
#define ExeServicio "VerduleriaMargarita-Servicio.exe"

[Setup]
AppId={{6E3B7A52-4C1D-4E8B-9C2A-7D51F0A3B9E4}
AppName={#Nombre}
AppVersion={#Version}
AppVerName={#Nombre} {#Version}
AppPublisher={#Empresa}
AppCopyright=© 2026 {#Autor} - {#Empresa}
AppComments=Sistema de gestión para verdulería: POS con balanza, stock, caja y panel web. Desarrollado por {#Autor}.
VersionInfoCompany={#Empresa}
VersionInfoCopyright=© 2026 {#Autor} - {#Empresa}
VersionInfoDescription=Instalador de {#Nombre}
VersionInfoProductName={#Nombre}
VersionInfoVersion={#Version}
DefaultDirName=C:\VerduleriaMargarita
DisableDirPage=no
DirExistsWarning=no
DefaultGroupName={#Nombre}
DisableProgramGroupPage=yes
#ifdef Prueba
; variante solo para probar el instalador sin permisos de administrador (ISCC /DPrueba)
PrivilegesRequired=lowest
OutputDir=build\prueba
OutputBaseFilename=Prueba_instalador
#else
PrivilegesRequired=admin
OutputDir=salida
OutputBaseFilename=Instalar_VerduleriaMargarita_{#Version}
#endif
SetupIconFile=..\img\icono.ico
UninstallDisplayIcon={app}\{#ExePOS}
UninstallDisplayName={#Nombre}
WizardStyle=modern
WizardImageFile=build\asistente.bmp,build\asistente_200.bmp
WizardSmallImageFile=build\asistente_chico.bmp,build\asistente_chico_200.bmp
Compression=lzma2/max
SolidCompression=yes
; si el POS o el servicio están abiertos, se avisa para cerrarlos antes de actualizar
AppMutex=VerduleriaMargarita_POS,VerduleriaMargarita_ServicioWeb
CloseApplications=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear accesos directos en el escritorio (POS y Servicio web)"; GroupDescription: "Accesos directos:"
Name: "autoinicio"; Description: "Iniciar el servicio web automáticamente con Windows"; GroupDescription: "Servicio web:"

[Dirs]
; el programa guarda ventas, productos y configuración en su carpeta: todos los usuarios pueden escribir
Name: "{app}"; Permissions: users-modify
Name: "{app}\datos"; Permissions: users-modify

[Files]
Source: "dist\VerduleriaMargarita\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#Nombre}"; Filename: "{app}\{#ExePOS}"; WorkingDir: "{app}"; IconFilename: "{app}\img\icono.ico"; Comment: "POS: vender, pesar y cobrar"; Tasks: escritorio
Name: "{autodesktop}\{#Nombre} - Servicio web"; Filename: "{app}\{#ExeServicio}"; WorkingDir: "{app}"; IconFilename: "{app}\img\icono.ico"; Comment: "Panel web: balance, ventas, caja, stock"; Tasks: escritorio
Name: "{group}\{#Nombre}"; Filename: "{app}\{#ExePOS}"; WorkingDir: "{app}"; IconFilename: "{app}\img\icono.ico"
Name: "{group}\{#Nombre} - Servicio web"; Filename: "{app}\{#ExeServicio}"; WorkingDir: "{app}"; IconFilename: "{app}\img\icono.ico"
Name: "{group}\Carpeta de datos (backup)"; Filename: "{app}\datos"
Name: "{group}\Desinstalar {#Nombre}"; Filename: "{uninstallexe}"
; mismo nombre que usa el programa para "Iniciar con Windows", así el menú del ícono lo muestra tildado
Name: "{userstartup}\{#Nombre} - Servicio web"; Filename: "{app}\{#ExeServicio}"; WorkingDir: "{app}"; IconFilename: "{app}\img\icono.ico"; Tasks: autoinicio

[Run]
Filename: "{app}\{#ExeServicio}"; Description: "Iniciar el servicio web (ícono junto al reloj)"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#ExePOS}"; Description: "Abrir el POS"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im {#ExeServicio}"; Flags: runhidden; RunOnceId: "CerrarServicio"
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im {#ExePOS}"; Flags: runhidden; RunOnceId: "CerrarPOS"

[UninstallDelete]
; se borra lo que genera el programa, pero NUNCA la carpeta datos (ventas y productos)
Type: files; Name: "{userstartup}\{#Nombre} - Servicio web.lnk"
Type: files; Name: "{app}\servidor.log"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  { en [Messages] no se pueden usar rutas como app, por eso el texto final se arma acá }
  if CurPageID = wpFinished then
    WizardForm.FinishedLabel.Caption :=
      'Listo. Se instaló {#Nombre}.' + #13#10#13#10 +
      'En el escritorio tenés el POS y el Servicio web.' + #13#10 +
      'Tus ventas y productos se guardan en ' + ExpandConstant('{app}\datos') + '.';
end;
