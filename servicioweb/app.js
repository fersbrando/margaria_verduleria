/* La Verdulería de Margarita · Panel web (Vue 3). Habla con servidor.py a través de api.php?r=... */
'use strict';

const moneda = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 });
const monedaCorta = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 });
const numero = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 3 });
const numero1 = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 1 });
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const MEDIOS = ['Efectivo', 'Débito', 'Crédito', 'Transferencia', 'Mercado Pago'];

const ICONOS = {
  resumen: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  ventas: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
  caja: '<path d="M3 7h18v12H3zM3 11h18M7 15h3" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
  productos: '<path d="M12 21c-5 0-8-4-8-9 4 0 8 2 8 6 0-4 4-6 8-6 0 5-3 9-8 9zM12 18V8M12 8c0-3 2-5 4-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  stock: '<path d="M3 8l9-5 9 5v8l-9 5-9-5zM3 8l9 5 9-5M12 13v8" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
};

function iso(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
function sumarDias(fechaIso, n) {
  const d = new Date(fechaIso + 'T00:00:00');
  d.setDate(d.getDate() + n);
  return iso(d);
}
function escalaRedonda(max) {
  if (max <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(max)));
  const n = max / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
}
function abreviar(v) {
  if (v >= 1e6) return '$' + numero1.format(v / 1e6) + 'M';
  if (v >= 1e3) return '$' + numero1.format(v / 1e3) + 'k';
  return '$' + Math.round(v);
}
function leerLocal(k, defecto) {
  try { return localStorage.getItem(k) || defecto; } catch (e) { return defecto; }
}
function guardarLocal(k, v) {
  try { localStorage.setItem(k, v); } catch (e) { /* modo privado */ }
}

// mismo criterio que iconos.adivinar() en Python: la palabra más larga que aparezca en el nombre
function adivinarIcono(nombre, catalogo) {
  const n = nombre.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  let mejor = '1f9fa', largo = 0;
  for (const i of catalogo) for (const p of i.palabras || []) if (n.includes(p) && p.length > largo) { mejor = i.cp; largo = p.length; }
  return mejor;
}

async function api(ruta, params = {}, cuerpo = null) {
  const qs = new URLSearchParams({ r: ruta, ...params }).toString();
  const opciones = cuerpo
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo) }
    : {};
  let res;
  try {
    res = await fetch('api.php?' + qs, opciones);
  } catch (e) {
    throw new Error('No hay conexión con el servicio. ¿Está iniciado servidor.py?');
  }
  const data = await res.json().catch(() => ({ error: 'Respuesta inválida del servidor (' + res.status + ')' }));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

const app = Vue.createApp({
  template: '#tpl',
  data() {
    const hoy = iso(new Date());
    return {
      secciones: [
        { id: 'resumen', nombre: 'Balance', periodo: true, icono: ICONOS.resumen },
        { id: 'ventas', nombre: 'Ventas', periodo: true, icono: ICONOS.ventas },
        { id: 'caja', nombre: 'Caja', periodo: true, icono: ICONOS.caja },
        { id: 'productos', nombre: 'Productos y costos', periodo: false, icono: ICONOS.productos },
        { id: 'stock', nombre: 'Stock', periodo: false, icono: ICONOS.stock },
      ],
      presets: [
        { id: 'hoy', nombre: 'Hoy' }, { id: 'ayer', nombre: 'Ayer' }, { id: '7d', nombre: '7 días' },
        { id: 'mes', nombre: 'Este mes' }, { id: 'mesant', nombre: 'Mes anterior' }, { id: 'anio', nombre: 'Este año' },
      ],
      medios: MEDIOS,
      seccion: 'resumen', menuAbierto: false, tema: leerLocal('tema', ''),
      info: { negocio: { nombre: 'La Verdulería de Margarita' }, logo: false },
      preset: 'hoy', desde: hoy, hasta: hoy,
      cargando: false, guardando: false, error: '', aviso: '',
      res: null, ventas: [], movs: [], productos: [], historial: [],
      fv: { texto: '', estado: '', medio: '' }, fm: '', fp: '', verInactivos: false, soloReponer: false,
      ordenProd: { campo: 'nombre', asc: true }, ordenRent: { campo: 'importe', asc: false },
      colsProd: [
        { k: 'codigo', t: 'Código' }, { k: 'nombre', t: 'Nombre' }, { k: 'pesable', t: 'Se vende' },
        { k: 'precio', t: 'Precio', cls: 'num' }, { k: 'costo', t: 'Costo', cls: 'num' },
        { k: 'ganancia', t: 'Ganancia', cls: 'num' }, { k: 'margen', t: 'Margen s/costo', cls: 'num' },
        { k: 'stock', t: 'Stock', cls: 'num' }, { k: 'activo', t: 'Activo' },
      ],
      colsRent: [
        { k: 'nombre', t: 'Producto' }, { k: 'cantidad', t: 'Vendido', cls: 'num' }, { k: 'importe', t: 'Ventas', cls: 'num' },
        { k: 'costo', t: 'Costo', cls: 'num' }, { k: 'ganancia', t: 'Ganancia', cls: 'num' },
        { k: 'margen', t: 'Margen s/costo', cls: 'num' }, { k: 'participacion', t: '% ventas', cls: 'num' },
      ],
      modal: null, form: {}, catalogo: [],
      G: { W: 760, H: 260, izq: 56, der: 10, arriba: 12, abajo: 26 },
    };
  },
  computed: {
    seccionActual() { return this.secciones.find(s => s.id === this.seccion); },
    iconoAuto() { return adivinarIcono(this.form.nombre || '', this.catalogo); },

    // ---------- balance
    graf() {
      const G = this.G;
      if (!this.res) return { barras: [], ticks: [], unidad: 'día' };
      let puntos = this.res.por_dia.map(d => ({ clave: d.fecha, ventas: d.ventas, ganancia: d.ventas - d.costo }));
      let unidad = 'día';
      if (puntos.length > 62) {               // períodos largos: agrupar por mes
        const meses = {};
        for (const p of puntos) {
          const k = p.clave.slice(0, 7);
          meses[k] = meses[k] || { clave: k, ventas: 0, ganancia: 0 };
          meses[k].ventas += p.ventas;
          meses[k].ganancia += p.ganancia;
        }
        puntos = Object.values(meses);
        unidad = 'mes';
      }
      const max = escalaRedonda(Math.max(1, ...puntos.map(p => p.ventas)));
      const alto = G.H - G.arriba - G.abajo, ancho = G.W - G.izq - G.der;
      const paso = ancho / Math.max(puntos.length, 1);
      const cadaCuanto = Math.ceil(puntos.length / 12);
      const y = v => G.arriba + alto - (Math.max(v, 0) / max) * alto;
      const barras = puntos.map((p, i) => {
        const etiqueta = unidad === 'mes'
          ? MESES[+p.clave.slice(5, 7) - 1] + ' ' + p.clave.slice(2, 4)
          : p.clave.slice(8, 10) + '/' + p.clave.slice(5, 7);
        return {
          clave: p.clave, x: G.izq + i * paso + paso * 0.12, w: Math.max(paso * 0.76, 1),
          yV: y(p.ventas), hV: G.arriba + alto - y(p.ventas), yG: y(p.ganancia), hG: G.arriba + alto - y(p.ganancia),
          etiqueta: i % cadaCuanto === 0 ? etiqueta : '',
          titulo: `${etiqueta}: ventas ${moneda.format(p.ventas)} · ganancia ${moneda.format(p.ganancia)}`,
        };
      });
      const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => ({ y: y(max * f), txt: abreviar(max * f) }));
      return { barras, ticks, unidad };
    },
    horas() {
      if (!this.res || !this.res.por_hora.length) return [];
      const hs = this.res.por_hora;
      const min = Math.min(...hs.map(h => h.hora)), max = Math.max(...hs.map(h => h.hora));
      const tope = Math.max(...hs.map(h => h.ventas)) || 1;
      const lista = [];
      for (let h = min; h <= max; h++) {
        const d = hs.find(x => x.hora === h) || { hora: h, ventas: 0, cantidad: 0 };
        lista.push({ ...d, alto: Math.max(d.ventas / tope * 100, d.ventas ? 3 : 0) });
      }
      return lista;
    },
    rentabilidad() {
      return this.res ? this.ordenada(this.res.productos.map(p => ({ ...p, participacion: p.importe })), this.ordenRent) : [];
    },

    // ---------- ventas
    ventasFiltradas() {
      const t = this.fv.texto.trim().toLowerCase().replace('#', '');
      return this.ventas.filter(v =>
        (!this.fv.estado || v.estado === this.fv.estado) &&
        (!this.fv.medio || v.pago.medio === this.fv.medio) &&
        (!t || String(v.numero) === t || v.items.some(i => i.nombre.toLowerCase().includes(t)))
      ).slice().reverse();
    },
    totalFiltrado() {
      return this.ventasFiltradas.filter(v => v.estado !== 'anulada').reduce((s, v) => s + v.total, 0);
    },

    // ---------- caja
    movsFiltrados() {
      return this.movs.filter(m => !this.fm || m.tipo === this.fm).slice().reverse();
    },

    // ---------- productos y stock
    productosConMargen() {
      return this.productos.map(p => ({
        ...p, ganancia: p.precio - p.costo, margen: p.costo ? (p.precio - p.costo) / p.costo * 100 : null,
      }));
    },
    productosFiltrados() {
      const t = this.fp.trim().toLowerCase();
      const lista = this.productosConMargen.filter(p =>
        (this.verInactivos || p.activo) && (!t || p.nombre.toLowerCase().includes(t) || String(p.codigo) === t));
      return this.ordenada(lista, this.ordenProd);
    },
    stockFiltrado() {
      const t = this.fp.trim().toLowerCase();
      return this.productos
        .filter(p => (!t || p.nombre.toLowerCase().includes(t)) && (!this.soloReponer || p.stock <= p.stock_min))
        .slice().sort((a, b) => (a.stock <= a.stock_min) === (b.stock <= b.stock_min)
          ? a.nombre.localeCompare(b.nombre) : (a.stock <= a.stock_min ? -1 : 1));
    },
    aReponer() {
      if (!this.productos.length) return this.res ? this.res.stock_bajo : 0;
      return this.productos.filter(p => p.activo && p.stock <= p.stock_min).length;
    },
    stockValorizado() { return this.productos.reduce((s, p) => s + Math.max(p.stock, 0) * p.costo, 0); },
    stockVenta() { return this.productos.reduce((s, p) => s + Math.max(p.stock, 0) * p.precio, 0); },
  },
  watch: {
    tema(v) {
      document.documentElement.dataset.tema = v || 'claro';
      if (v) guardarLocal('tema', v);
    },
  },
  methods: {
    // ---------- formato
    ico(cp) { return '../img/iconos/' + (cp || '1f9fa') + '.png'; },
    plata(v) { return moneda.format(v || 0); },
    n1(v) { return numero1.format(v || 0); },
    n3(v) { return numero.format(v || 0); },
    cant(v, pesable) { return pesable ? numero.format(v) + ' kg' : numero.format(v) + ' u'; },
    pct(v, total) { return total ? numero1.format(v / total * 100) : '0'; },
    fecha(f) { return f.slice(8, 10) + '/' + f.slice(5, 7) + '/' + f.slice(0, 4); },
    claseMargen(m) { return m === null ? '' : m < 20 ? 'anulada' : m < 40 ? 'medio' : 'activa'; },
    ordenada(lista, orden) {
      const k = orden.campo, s = orden.asc ? 1 : -1;
      return lista.slice().sort((a, b) => {
        const x = a[k], y = b[k];
        if (typeof x === 'string') return x.localeCompare(y, 'es', { numeric: true }) * s;
        return ((x ?? -Infinity) - (y ?? -Infinity)) * s;
      });
    },
    ordenar(orden, campo) {
      if (orden.campo === campo) orden.asc = !orden.asc;
      else { orden.campo = campo; orden.asc = ['nombre', 'codigo'].includes(campo); }
    },
    avisar(t) {
      this.aviso = t;
      clearTimeout(this._tAviso);
      this._tAviso = setTimeout(() => (this.aviso = ''), 3500);
    },

    // ---------- navegación y período
    ir(id) {
      this.seccion = id;
      this.menuAbierto = false;
      if (location.hash !== '#' + id) history.replaceState(null, '', '#' + id);
      this.cargar();
    },
    elegirPreset(id) {
      const hoy = new Date(), h = iso(hoy);
      const y = hoy.getFullYear(), m = hoy.getMonth();
      const rangos = {
        hoy: [h, h], ayer: [sumarDias(h, -1), sumarDias(h, -1)], '7d': [sumarDias(h, -6), h],
        mes: [iso(new Date(y, m, 1)), h], mesant: [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))],
        anio: [iso(new Date(y, 0, 1)), h],
      };
      this.preset = id;
      [this.desde, this.hasta] = rangos[id];
      this.cargar();
    },
    fechaManual() {
      this.preset = '';
      if (this.desde && this.hasta) this.cargar();
    },
    async cargar() {
      this.cargando = true;
      this.error = '';
      const p = { desde: this.desde, hasta: this.hasta };
      try {
        if (this.seccion === 'resumen') {
          this.res = await api('resumen', p);
        } else if (this.seccion === 'ventas') {
          this.ventas = await api('ventas', p);
        } else if (this.seccion === 'caja') {
          [this.movs, this.res] = await Promise.all([api('movimientos', p), api('resumen', p)]);
        } else if (this.seccion === 'productos') {
          this.productos = await api('productos');
        } else if (this.seccion === 'stock') {
          [this.productos, this.historial] = await Promise.all([api('productos'), api('historial_stock', { limite: 300 })]);
        }
      } catch (e) {
        this.error = e.message;
      } finally {
        this.cargando = false;
      }
    },

    // ---------- modales
    abrir(tipo, extra = {}, form = {}) {
      this.form = form;
      this.modal = { tipo, ...extra };
      this.$nextTick(() => { const r = this.$refs.primero; if (r) r.focus(); });
    },
    cerrarModal() { if (!this.guardando) this.modal = null; },
    async guardar(fn, mensaje) {
      this.guardando = true;
      try {
        await fn();
        this.guardando = false;
        this.modal = null;
        this.avisar(mensaje);
        await this.cargar();
      } catch (e) {
        alert(e.message);
      } finally {
        this.guardando = false;
      }
    },

    // ventas
    verVenta(v) { this.abrir('venta', { venta: v }); },
    urlTicket(v) {
      return 'api.php?' + new URLSearchParams({ r: 'ticket_png', numero: v.numero, fecha: v.fecha, e: v.estado }).toString();
    },
    anular(v) {
      const motivo = prompt(`¿Anular la venta #${v.numero} por ${moneda.format(v.total)}?\nSe devuelve el stock.\n\nMotivo:`);
      if (motivo === null) return;
      this.guardar(() => api('anular', {}, { numero: v.numero, fecha: v.fecha, motivo }), `Venta #${v.numero} anulada`);
    },
    exportarVentas() {
      const filas = [['Numero', 'Fecha', 'Hora', 'Estado', 'Medio', 'Producto', 'Cantidad', 'Unidad', 'Precio', 'Importe', 'Costo']];
      for (const v of this.ventasFiltradas.slice().reverse()) {
        for (const i of v.items) {
          filas.push([v.numero, this.fecha(v.fecha), v.fecha.slice(11, 16), v.estado, v.pago.medio, i.nombre,
            i.cantidad, i.pesable ? 'kg' : 'u', i.precio, i.importe, +(i.cantidad * (i.costo || 0)).toFixed(2)]);
        }
      }
      const csv = filas.map(f => f.map(c => {
        const s = typeof c === 'number' ? String(c).replace('.', ',') : String(c);
        return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
      }).join(';')).join('\r\n');
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
      a.download = `ventas_${this.desde}_a_${this.hasta}.csv`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    },

    // caja
    abrirMovimiento(tipo) { this.abrir('movimiento', {}, { tipo, concepto: '', monto: null, medio: 'Efectivo' }); },
    guardarMovimiento() {
      this.guardar(() => api('movimiento', {}, this.form), this.form.tipo === 'ingreso' ? 'Ingreso registrado' : 'Egreso registrado');
    },

    // productos
    abrirProducto(p) {
      const f = p ? { ...p, icono: p.icono || '' } : { codigo: '', nombre: '', precio: null, costo: null, stock: 0, stock_min: 0, pesable: true, activo: true, icono: '' };
      this.abrir('producto', { original: p ? p.codigo : null }, f);
    },
    guardarProducto() {
      const cuerpo = { ...this.form, codigo_original: this.modal.original };
      this.guardar(() => api('producto', {}, cuerpo), 'Producto guardado');
    },
    eliminarProducto() {
      if (!confirm(`¿Eliminar "${this.form.nombre}"?\nLas ventas anteriores no cambian. Si solo querés ocultarlo del POS, destildá "Activo".`)) return;
      this.guardar(() => api('producto_eliminar', {}, { codigo: this.modal.original }), 'Producto eliminado');
    },
    abrirAumento() { this.abrir('aumento', {}, { pct: null, campo: 'precio', redondeo: 0 }); },
    nuevoPrecio(p) {
      let v = p.precio * (1 + (this.form.pct || 0) / 100);
      if (this.form.redondeo) v = Math.round(v / this.form.redondeo) * this.form.redondeo;
      return Math.max(Math.round(v * 100) / 100, 0);
    },
    aplicarAumento() {
      const lista = this.productosFiltrados.slice();
      const f = 1 + this.form.pct / 100;
      if (!confirm(`¿Aplicar ${this.form.pct}% a ${lista.length} productos?`)) return;
      this.guardar(async () => {
        for (const p of lista) {
          const nuevo = { ...p, codigo_original: p.codigo };
          if (this.form.campo !== 'costo') nuevo.precio = this.nuevoPrecio(p);
          if (this.form.campo !== 'precio') nuevo.costo = Math.round(p.costo * f * 100) / 100;
          await api('producto', {}, nuevo);
        }
      }, `Precios actualizados en ${lista.length} productos`);
    },

    // stock
    abrirIngreso(p) { this.abrir('ingreso', { p }, { codigo: p.codigo, cantidad: null, costo: p.costo, egreso: true, medio: 'Efectivo' }); },
    guardarIngreso() { this.guardar(() => api('stock_ingreso', {}, this.form), 'Ingreso de mercadería registrado'); },
    abrirAjuste(p) { this.abrir('ajuste', { p }, { codigo: p.codigo, stock: p.stock, motivo: '' }); },
    guardarAjuste() { this.guardar(() => api('stock_ajuste', {}, this.form), 'Stock ajustado'); },
  },
  async mounted() {
    document.addEventListener('keydown', e => { if (e.key === 'Escape') this.cerrarModal(); });
    try {
      this.info = await api('info');
      if (!this.tema) this.tema = this.info.tema || 'claro';
      this.catalogo = await api('iconos');
    } catch (e) {
      this.error = e.message;
    }
    // la dirección puede traer tema y período: ?tema=oscuro&periodo=mes#ventas
    const qs = new URLSearchParams(location.search);
    if (['claro', 'gris', 'oscuro'].includes(qs.get('tema'))) this.tema = qs.get('tema');
    document.documentElement.dataset.tema = this.tema || 'claro';
    const h = location.hash.slice(1);
    if (this.secciones.some(s => s.id === h)) this.seccion = h;
    if (this.presets.some(p => p.id === qs.get('periodo'))) this.elegirPreset(qs.get('periodo'));
    else this.cargar();
    if (this.seccion !== 'stock') api('productos').then(p => (this.productos = p)).catch(() => {});
    // refresco automático cada minuto si se está mirando el día de hoy
    setInterval(() => {
      if (!this.modal && !this.cargando && this.hasta >= iso(new Date()) && document.visibilityState === 'visible') this.cargar();
    }, 60000);
  },
});
app.mount('#app');
