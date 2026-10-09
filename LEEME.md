# La Verdulería de Margarita — Sistema de gestión

Dos programas que comparten los mismos datos (`datos/`):

| Programa | Para qué | Cómo se abre |
|---|---|---|
| **POS** (`app.py`) | Vender, pesar, cobrar, imprimir | `iniciar.bat` |
| **Servicio web** (`servidor.py` + `servicioweb/`) | Balance, ventas, caja, productos y costos, stock (todo menos el POS) | `iniciar_servicio.bat` → http://localhost:8085/servicioweb/ |

Requiere Python 3: `pip install -r requirements.txt` (pyserial, pywin32, Pillow).

## POS
1. Tocar el producto (o escribir el código + Enter).
2. Si es pesable, apoyarlo en la balanza: el peso aparece en pantalla → **Enter**.
   Si es por unidad, escribir la cantidad → Enter. Sin balanza se puede escribir el peso a mano (`0,850`).
3. **F12** cobrar → medio de pago → Enter. Se guarda la venta y sale el ticket.

### Atajos (se cambian en Configuración → General y atajos)
| Acción | Tecla de fábrica |
|---|---|
| Agregar | Enter |
| Cobrar | F12 |
| Quitar ítem | Supr |
| Deseleccionar | Esc |
| Ir al buscador | F2 |
| Cancelar venta | F8 |
| Reimprimir último | F9 |
| Ir al POS | F1 |
| Pantalla completa | F11 |

### Pantalla
Configuración → General: tema **claro / gris / oscuro** y "Abrir en pantalla completa". F11 entra y sale de pantalla completa.

### Logo
El logo original está en `img/logo.jpg`. De ahí salen (con `python img/generar_logo.py`):
- `img/icono.png` / `img/icono_64.png`: sello redondo para el encabezado del POS, la ventana y el panel web.
- `img/logo_ticket.png`: blanco y negro para la impresora térmica (es el logo del ticket por defecto).

Si cambiás el logo: reemplazá `img/logo.jpg` y volvé a ejecutar `python img/generar_logo.py`.
En Configuración → Ticket y logo podés elegir otra imagen para el ticket y ver la *Vista previa*.
Ancho del logo en el ticket: papel de 58mm hasta 384 puntos, 80mm hasta 576.

### Íconos
Los íconos de botones y productos son Twemoji (CDN jsdelivr), guardados en `img/iconos/` para funcionar sin internet.
Si falta alguno, el POS lo baja solo al arrancar (o `python iconos.py`).
Cada producto toma el ícono según su nombre ("Tomate perita" → 🍅); en Productos → *Elegir ícono* se puede cambiar.

Tipo de impresora:
- `archivo`: no imprime, guarda `datos/ultimo_ticket.txt` y `datos/ultimo_ticket.png` (para probar).
- `serial`: por puerto COM. **Impresora integrada a la balanza: poner el mismo puerto COM de la balanza.**
- `windows`: impresora térmica instalada en Windows.

## Servicio web
Se inicia con `iniciar_servicio.bat` (o desde el POS: Configuración → Servicio web → *Iniciar servicio*).
Aparece un **ícono con el logo junto al reloj de Windows** (a color = funcionando, gris = detenido).
Si no lo ves, tocá la flechita ^ de la barra de tareas; podés arrastrarlo afuera para que quede siempre visible.

**Clic derecho en el ícono:**
| Opción | Qué hace |
|---|---|
| Abrir panel (o doble clic) | Abre el panel en el navegador |
| Copiar link | Copia la dirección del panel (con acceso desde la red, copia la IP de la PC para usarla en el celular) |
| Iniciar / Detener servicio | Prende o apaga el servicio web (el POS sigue funcionando igual) |
| Configurar puerto... | Cambia el puerto (por defecto 8085) y reinicia el servicio |
| Permitir acceso desde la red | Deja entrar desde otras PCs o el celular en la misma red WiFi |
| Iniciar con Windows | El ícono aparece solo al prender la PC |
| Salir | Detiene el servicio y saca el ícono |

- Si permitís el acceso desde la red, poné una **clave** en el POS → Configuración → Servicio web.
- Con XAMPP/Apache también se puede abrir en http://localhost/margaria_verduleria/servicioweb/ (`api.php` reenvía al servicio, que tiene que estar iniciado).
- Errores del servicio: `servidor.log`.
- Funciona sin internet: Vue 3.4.38 está en `servicioweb/vendor/`.

## Instalador
`construir_instalador.bat` (o `python empaquetar/construir.py 1.0.1`) arma
`empaquetar/salida/Instalar_VerduleriaMargarita_<versión>.exe`:
- Instala en `C:\VerduleriaMargarita` (pide permiso de administrador una vez).
- Accesos directos con el logo en el escritorio y el menú Inicio: **POS** y **Servicio web**.
- Opción "Iniciar el servicio web con Windows".
- Aparece en *Configuración → Aplicaciones* (empresa eRios). Al desinstalar **no se borra `datos/`**.
- Para actualizar: instalar la versión nueva encima (se conservan datos y configuración).
- Para pasar datos de otra PC: copiar `datos/` y `config.json` a `C:\VerduleriaMargarita`.

## Dónde se guarda todo
```
config.json                               configuración
datos/productos/productos.json            productos (precio, costo, stock)
datos/productos/movimientos_stock.jsonl   historial de stock
datos/ventas/aaaa/mm/dd/venta_000123.json una venta por archivo
datos/ventas/aaaa/mm/dd/egreso_*.json     egresos de caja
datos/ventas/aaaa/mm/dd/ingreso_*.json    otros ingresos
img/                                      logo e íconos
```
Backup: copiar la carpeta `datos` y `config.json`.

En el balance, los egresos que se cargan con "Ingreso de mercadería" son **compras**: ya están dentro del costo de lo vendido, así que el *resultado* solo resta los demás gastos (luz, bolsas, flete...). El *balance de caja* sí resta todo lo que salió.

## Configurar la balanza (Kretz/Krenz Aura Eco)
1. Ver qué COM le asignó Windows al adaptador USB-RS232 (Administrador de dispositivos → Puertos).
2. Configuración → Balanza: tildar *Usar balanza*, elegir el puerto → *Guardar configuración*.
3. Poner algo en el plato y mirar *Lectura en vivo*.
4. Si no llega nada: *Detectar protocolo* prueba velocidades y comandos comunes. Copiar baudios/comando y guardar.
   - Si la balanza transmite sola: modo `continuo`.
   - Si el peso sale 1000 veces más grande: ajustar *Divisor*.
5. Puede hacer falta habilitar la comunicación con PC en el menú de la balanza y/o un cable null-modem.
