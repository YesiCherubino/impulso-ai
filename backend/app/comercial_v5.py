"""V5 (demo comercial): Mi día, seguimiento sugerido, importación de Excel, cotizador con PDF, respuestas
rápidas, búsqueda global, exportación a Excel, notas internas y derivación, documentos para adjuntar,
metas y pronóstico, y herramientas de texto con IA.

Las descargas viajan en base64 dentro de JSON (el proxy de Next solo reenvía texto) y todas las acciones
son GET/POST. Todo el SQL es estándar salvo LIMIT/OFFSET (escala.page_sql).
"""
import base64
import io
import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape as esc

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .db import connect
from .business_v2 import current, stamp, row_ficha
from .business_v4 import ESTADOS_ABIERTOS, TIPOS_CON_LOTE_MINIMO, lote_minimo, parse_dt, norm_name
from .escala import page_sql, response_from_row, conv_key, refresh_case_stats

OPEN_SQL = "('sin_atender','calificada','cotizada','muestra_piloto')"
AREAS = ('I+D / Desarrollo de fórmulas', 'Comercio exterior', 'Laboratorio y calidad', 'Asuntos regulatorios (ANMAT)',
         'Producción', 'Administración y cobranzas')
PROB_DEFAULT = {'sin_atender': 5, 'calificada': 15, 'cotizada': 35, 'muestra_piloto': 60}
MAX_DOC_BYTES = 8 * 1024 * 1024
MAX_IMPORT_BYTES = 10 * 1024 * 1024

PLANTILLAS_INICIALES = [
    ('datos', 'Pedir datos para cotizar',
     'Hola {contacto}, gracias por contactarte con Empresa S.A. Para preparar la cotización de {producto} necesitamos: '
     'cantidad estimada, presentación (ml/g) y tipo de envase, si cuentan con fórmula propia o prefieren nuestro desarrollo, '
     'y el plazo en que lo necesitan.'),
    ('anmat', 'Requisitos ANMAT',
     'Para productos cosméticos, el registro ante ANMAT puede quedar a nombre de su marca o gestionarse con nuestro equipo de '
     'asuntos regulatorios. ¿Ya cuentan con marca registrada y registro propio? Así les indicamos la documentación necesaria.'),
    ('mayorista', 'Condiciones mayoristas',
     'Gracias por el interés en nuestras marcas. Para enviarte las condiciones mayoristas necesitamos la razón social, el CUIT, '
     'la localidad y los productos que te interesan. Un asesor comercial te contacta con la lista de precios vigente.'),
    ('catalogo', 'Envío de catálogo',
     'Te compartimos nuestro catálogo con las líneas disponibles. Cualquier consulta sobre presentaciones o envases, quedamos a disposición.'),
    ('minimo', 'Lote mínimo',
     'Para fabricación a terceros trabajamos con un lote mínimo de {lote_minimo} unidades por producto. Si tu proyecto está por '
     'debajo, contanos y vemos juntos alternativas.'),
    ('muestra', 'Envío de muestras',
     'Podemos preparar una muestra para que la evalúen antes de avanzar con el primer lote. ¿Nos confirmás la dirección de envío '
     'y la persona que la recibe?'),
    ('exportacion', 'Consulta de exportación',
     'Exportamos a distintos países de la región. Para cotizar necesitamos el país de destino, los productos de interés, los '
     'volúmenes estimados y si cuentan con registro sanitario en destino.'),
    ('fullservice', 'Full Service',
     'Hola {contacto}, con Full Service nos ocupamos de todo el proceso: desarrollo de fórmula, diseño de packaging, abastecimiento, '
     'elaboración, envasado, codificado, estuchado y entrega. Para cotizar {producto} contanos la cantidad, la presentación y si ya '
     'tenés fórmula o marca registrada.'),
    ('marcapropia', 'Marca propia para cadenas',
     'Hola {contacto}, producimos productos de marca propia para cadenas de supermercados y farmacias. Contanos qué líneas te '
     'interesan, los volúmenes estimados y si ya tienen especificaciones o fórmula definida.'),
    ('etiqueta', 'Diseño de etiquetas',
     'También podemos encargarnos del diseño de etiquetas y del acondicionamiento final. Si ya tenés el diseño, pasanos el archivo '
     'y la medida del envase; si no, lo armamos con vos.'),
    ('gracias', 'Cierre cordial',
     'Muchas gracias, {contacto}. Quedamos atentos a tu respuesta. Saludos, {vendedor} – Empresa S.A.'),
]

PRODUCTOS_EJEMPLO = [
    ('MA-CC250', 'Marca A Crema corporal 250 ml', 'unidad', 'Marca A', 2850, 'ARS'),
    ('MA-CF50', 'Marca A Crema facial 50 ml', 'unidad', 'Marca A', 3900, 'ARS'),
    ('MA-SH350', 'Marca A Shampoo 350 ml', 'unidad', 'Marca A', 2400, 'ARS'),
    ('MA-AC350', 'Marca A Acondicionador 350 ml', 'unidad', 'Marca A', 2450, 'ARS'),
    ('MB-EDT100', 'Marca B Eau de toilette 100 ml', 'unidad', 'Marca B', 6900, 'ARS'),
    ('MB-BS200', 'Marca B Body splash 200 ml', 'unidad', 'Marca B', 3300, 'ARS'),
    ('MC-JL500', 'Marca C Jabón líquido 500 ml', 'unidad', 'Marca C', 1650, 'ARS'),
    ('MC-AG250', 'Marca C Alcohol en gel 250 ml', 'unidad', 'Marca C', 1200, 'ARS'),
    ('SV-DESA', 'Desarrollo de fórmula (por proyecto)', 'proyecto', 'Servicios', 1800, 'USD'),
    ('SV-PILOTO', 'Lote piloto y muestras', 'lote', 'Servicios', 450, 'USD'),
    ('SV-ELAB', 'Elaboración y envasado (por unidad)', 'unidad', 'Servicios', 0.85, 'USD'),
    ('SV-COD', 'Codificado (por unidad)', 'unidad', 'Servicios', 0.03, 'USD'),
    ('SV-EST', 'Estuchado y celofanado (por unidad)', 'unidad', 'Servicios', 0.12, 'USD'),
    ('SV-ETIQ', 'Diseño de etiqueta', 'diseño', 'Servicios', 350, 'USD'),
    ('SV-ANMAT', 'Gestión de trámite ANMAT', 'trámite', 'Servicios', 600, 'USD'),
]

# Columnas reconocidas al importar: nombres habituales en exportaciones de Tango Gestión y planillas comunes.
CAMPOS_IMPORT = {
    'clientes': {
        'codigo': ['cod_client', 'codigo', 'código', 'cod cliente', 'codigo cliente', 'código cliente', 'cliente codigo', 'cod'],
        'cliente': ['razon_soci', 'razón social', 'razon social', 'nombre', 'cliente', 'empresa', 'denominacion', 'denominación'],
        'cuit': ['cuit', 'cuit/cuil', 'n_cuit', 'nro cuit', 'documento'],
        'email': ['e_mail', 'email', 'e-mail', 'mail', 'correo'],
        'telefono': ['telefono_1', 'telefono', 'teléfono', 'tel', 'celular', 'whatsapp'],
        'contacto': ['contacto', 'persona de contacto', 'nom_contacto', 'atencion'],
        'localidad': ['localidad', 'ciudad', 'localidad_entrega'],
        'provincia': ['provincia', 'nom_provin', 'prov'],
        'vendedor': ['cod_vended', 'vendedor', 'nombre_vendedor'],
        'lista_precios': ['nro_lista', 'lista', 'lista de precios', 'lista_precios'],
    },
    'articulos': {
        'codigo': ['cod_articu', 'codigo', 'código', 'cod articulo', 'código artículo', 'sku', 'cod'],
        'descripcion': ['descripcio', 'descripción', 'descripcion', 'articulo', 'artículo', 'producto', 'nombre'],
        'precio': ['precio', 'precio_lista', 'precio lista', 'precio unitario', 'pvp', 'importe'],
        'moneda': ['moneda', 'cod_moneda', 'mon'],
        'unidad': ['unidad', 'unidad_med', 'u. medida', 'unidad de medida', 'um'],
        'linea': ['linea', 'línea', 'familia', 'rubro', 'marca', 'cod_rubro'],
    },
}
OBLIGATORIOS = {'clientes': ('cliente',), 'articulos': ('codigo', 'descripcion')}


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------
def _add_columns(con, table, cols):
    have = {r['name'] for r in con.execute(f'PRAGMA table_info({table})')}
    for col, sql in cols.items():
        if col not in have:
            con.execute(f'ALTER TABLE {table} ADD COLUMN {col} {sql}')


def init_v5(db_path: Path) -> None:
    with connect(db_path) as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS productos (
          id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT NOT NULL UNIQUE, descripcion TEXT NOT NULL,
          unidad TEXT NOT NULL DEFAULT 'unidad', linea TEXT NOT NULL DEFAULT '', precio REAL, moneda TEXT NOT NULL DEFAULT 'ARS',
          activo INTEGER NOT NULL DEFAULT 1, origen TEXT NOT NULL DEFAULT 'manual', actualizado_en TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cotizaciones (
          id INTEGER PRIMARY KEY AUTOINCREMENT, ficha_id INTEGER NOT NULL REFERENCES fichas_consulta(id), numero TEXT NOT NULL,
          fecha TEXT NOT NULL, validez_dias INTEGER NOT NULL DEFAULT 30, moneda TEXT NOT NULL, incluye_iva INTEGER NOT NULL DEFAULT 1,
          iva_pct REAL NOT NULL DEFAULT 21, condiciones TEXT NOT NULL DEFAULT '', notas TEXT NOT NULL DEFAULT '',
          subtotal REAL NOT NULL, iva REAL NOT NULL, total REAL NOT NULL, creada_por TEXT NOT NULL DEFAULT '', creada_en TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cotizacion_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT, cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id),
          producto_id INTEGER, codigo TEXT NOT NULL DEFAULT '', descripcion TEXT NOT NULL, unidad TEXT NOT NULL DEFAULT 'unidad',
          cantidad REAL NOT NULL, precio_unitario REAL NOT NULL, descuento_pct REAL NOT NULL DEFAULT 0, importe REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_cotizaciones_ficha ON cotizaciones(ficha_id);
        CREATE TABLE IF NOT EXISTS empresa_config (
          id INTEGER PRIMARY KEY CHECK(id=1), razon_social TEXT NOT NULL DEFAULT 'Empresa S.A.',
          domicilio TEXT NOT NULL DEFAULT '', telefono TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT 'ventas@empresa.com.ar',
          web TEXT NOT NULL DEFAULT 'www.empresa.com.ar', cuit TEXT NOT NULL DEFAULT '',
          condiciones TEXT NOT NULL DEFAULT 'Precios sujetos a confirmación de disponibilidad. Forma de pago y plazo de entrega a convenir.',
          iva_pct REAL NOT NULL DEFAULT 21, dias_seguimiento INTEGER NOT NULL DEFAULT 5,
          probabilidades_json TEXT NOT NULL DEFAULT '{"sin_atender":5,"calificada":15,"cotizada":35,"muestra_piloto":60}');
        INSERT OR IGNORE INTO empresa_config(id) VALUES (1);
        CREATE TABLE IF NOT EXISTS plantillas (
          id INTEGER PRIMARY KEY AUTOINCREMENT, atajo TEXT NOT NULL UNIQUE, titulo TEXT NOT NULL, texto TEXT NOT NULL,
          activa INTEGER NOT NULL DEFAULT 1, actualizada_en TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notas_internas (
          id INTEGER PRIMARY KEY AUTOINCREMENT, ficha_id INTEGER NOT NULL REFERENCES fichas_consulta(id), usuario TEXT NOT NULL DEFAULT '',
          texto TEXT NOT NULL, area TEXT NOT NULL DEFAULT '', creada_en TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_notas_ficha ON notas_internas(ficha_id);
        CREATE TABLE IF NOT EXISTS documentos (
          id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, descripcion TEXT NOT NULL DEFAULT '', mime TEXT NOT NULL,
          tamano INTEGER NOT NULL, contenido BLOB NOT NULL, subido_por TEXT NOT NULL DEFAULT '', creado_en TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS metas (
          usuario TEXT NOT NULL, mes TEXT NOT NULL, moneda TEXT NOT NULL, monto REAL NOT NULL,
          PRIMARY KEY (usuario, mes, moneda));
        ''')
        _add_columns(con, 'cotizaciones', {'token': "TEXT", 'aceptada_en': 'TEXT', 'aceptada_por': "TEXT NOT NULL DEFAULT ''"})
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_cotizaciones_token ON cotizaciones(token)')
        _add_columns(con, 'oportunidades', {'codigo_tango': "TEXT NOT NULL DEFAULT ''", 'cuit': "TEXT NOT NULL DEFAULT ''",
                                            'localidad': "TEXT NOT NULL DEFAULT ''", 'provincia': "TEXT NOT NULL DEFAULT ''",
                                            'lista_precios': "TEXT NOT NULL DEFAULT ''", 'es_cliente': 'INTEGER NOT NULL DEFAULT 0',
                                            'importado_en': 'TEXT'})
        _add_columns(con, 'fichas_consulta', {'derivada_a': "TEXT NOT NULL DEFAULT ''", 'rubro': "TEXT NOT NULL DEFAULT ''",
                                              'envase': "TEXT NOT NULL DEFAULT ''", 'tipo_cliente': "TEXT NOT NULL DEFAULT ''",
                                              'etapas_json': "TEXT NOT NULL DEFAULT '[]'"})
        # Color de acento del cliente (Impulso mantiene su identidad; cada empresa elige su color).
        _add_columns(con, 'empresa_config', {'color_acento': "TEXT NOT NULL DEFAULT '#2e6a57'"})
        _add_columns(con, 'bandeja_consultas', {'adjuntos_json': "TEXT NOT NULL DEFAULT '[]'"})
        con.execute('CREATE INDEX IF NOT EXISTS idx_oportunidades_codigo ON oportunidades(codigo_tango)')
        # Tono por defecto: voseo. Se aplica una sola vez si nadie cambió la configuración de la IA.
        con.execute('CREATE TABLE IF NOT EXISTS migraciones (clave TEXT PRIMARY KEY)')
        if not con.execute("SELECT 1 FROM migraciones WHERE clave='ia_voseo'").fetchone():
            con.execute("UPDATE ia_configuracion SET tratamiento='vos' WHERE id=1 AND tratamiento='ustedes' AND instrucciones=''")
            con.execute("INSERT INTO migraciones(clave) VALUES ('ia_voseo')")
        # Lista de precios de ejemplo para que el cotizador funcione desde el primer uso (se reemplaza al importar).
        # Lista de ejemplo mientras no se importe una real; reemplaza los servicios genéricos anteriores.
        if not con.execute("SELECT 1 FROM productos WHERE origen<>'ejemplo'").fetchone():
            con.execute("DELETE FROM productos WHERE origen='ejemplo' AND codigo LIKE 'FT-%'")
            load_example_products(con)
        # Se agregan las plantillas de ejemplo que falten (no se pisan las editadas).
        # Cada plantilla de ejemplo se siembra una sola vez: si el administrador la borra, no vuelve.
        con.execute('CREATE TABLE IF NOT EXISTS plantillas_semilla (atajo TEXT PRIMARY KEY)')
        if not con.execute('SELECT 1 FROM plantillas_semilla').fetchone():
            con.executemany('INSERT OR IGNORE INTO plantillas_semilla(atajo) SELECT atajo FROM plantillas WHERE atajo=?',
                            [(a,) for a, _, _ in PLANTILLAS_INICIALES])
        for a, t, x in PLANTILLAS_INICIALES:
            if not con.execute('SELECT 1 FROM plantillas_semilla WHERE atajo=?', (a,)).fetchone():
                con.execute('INSERT OR IGNORE INTO plantillas(atajo,titulo,texto,actualizada_en) VALUES (?,?,?,?)', (a, t, x, stamp()))
                con.execute('INSERT INTO plantillas_semilla(atajo) VALUES (?)', (a,))
        neutralizar_marca(con)


# Antes los ejemplos usaban el nombre y las marcas de un cliente real; ahora son genéricos.
MARCAS_REEMPLAZO = (('Roberto Pasmanter S.A.', 'Empresa S.A.'), ('Roberto Pasmanter', 'Empresa S.A.'),
                    ('formulario de Pasmanter', 'formulario web'), ('Pasmanter', 'Empresa S.A.'),
                    ('Dermogreen', 'Marca A'), ('Acqua Di Fiore', 'Marca B'))
CODIGOS_REEMPLAZO = {'DG-CC250': 'MA-CC250', 'DG-CF50': 'MA-CF50', 'DG-SH350': 'MA-SH350', 'DG-AC350': 'MA-AC350',
                     'AF-EDT100': 'MB-EDT100', 'AF-BS200': 'MB-BS200', 'TG-JL500': 'MC-JL500', 'TG-AG250': 'MC-AG250'}


def neutralizar_marca(con) -> None:
    """Una sola vez: reemplaza el nombre y las marcas del cliente en los datos de ejemplo ya cargados."""
    if con.execute("SELECT 1 FROM migraciones WHERE clave='sin_marca_cliente'").fetchone():
        return
    con.execute('''UPDATE empresa_config SET
        razon_social=CASE WHEN razon_social='Roberto Pasmanter S.A.' THEN 'Empresa S.A.' ELSE razon_social END,
        email=CASE WHEN email='ventas@pasmanter.com.ar' THEN 'ventas@empresa.com.ar' ELSE email END,
        web=CASE WHEN web='www.pasmanter.com.ar' THEN 'www.empresa.com.ar' ELSE web END WHERE id=1''')
    nuevos = {c: (d, u, l, p, m) for c, d, u, l, p, m in PRODUCTOS_EJEMPLO}
    for old, new in CODIGOS_REEMPLAZO.items():
        row = con.execute("SELECT id FROM productos WHERE codigo=? AND origen='ejemplo'", (old,)).fetchone()
        if not row:
            continue
        dest = con.execute('SELECT id FROM productos WHERE codigo=?', (new,)).fetchone()
        if dest:
            con.execute('UPDATE cotizacion_items SET producto_id=? WHERE producto_id=?', (dest['id'], row['id']))
            con.execute('DELETE FROM productos WHERE id=?', (row['id'],))
        else:
            d, u, l, p, m = nuevos[new]
            con.execute('UPDATE productos SET codigo=?, descripcion=?, linea=? WHERE id=?', (new, d, l, row['id']))
    for table, cols in (('plantillas', ('texto',)), ('bandeja_consultas', ('texto', 'asunto')),
                        ('fichas_consulta', ('titulo', 'producto', 'resumen')), ('oportunidades', ('producto', 'notas')),
                        ('cotizacion_items', ('descripcion',))):
        have = {r[1] for r in con.execute(f'PRAGMA table_info({table})')}
        for col in cols:
            if col not in have:
                continue
            for a, b in MARCAS_REEMPLAZO:
                con.execute(f"UPDATE {table} SET {col}=REPLACE({col}, ?, ?) WHERE {col} LIKE ?", (a, b, f'%{a}%'))
    con.execute("UPDATE fichas_consulta SET formula='desarrollo_empresa' WHERE formula='desarrollo_pasmanter'")
    con.execute("INSERT INTO migraciones(clave) VALUES ('sin_marca_cliente')")


def load_example_products(con) -> int:
    n = 0
    for code, desc, unit, line, price, cur in PRODUCTOS_EJEMPLO:
        exists = con.execute('SELECT id FROM productos WHERE codigo=?', (code,)).fetchone()
        if not exists:
            con.execute('''INSERT INTO productos(codigo,descripcion,unidad,linea,precio,moneda,origen,actualizado_en)
                           VALUES (?,?,?,?,?,?,'ejemplo',?)''', (code, desc, unit, line, price, cur, stamp()))
            n += 1
    return n


def empresa(con) -> dict:
    row = dict(con.execute('SELECT * FROM empresa_config WHERE id=1').fetchone())
    try:
        row['probabilidades'] = {**PROB_DEFAULT, **json.loads(row.pop('probabilidades_json') or '{}')}
    except ValueError:
        row['probabilidades'] = dict(PROB_DEFAULT)
    return row


def b64file(data: bytes, filename: str, mime: str) -> dict:
    return {'filename': filename, 'mime': mime, 'contenido_base64': base64.b64encode(data).decode()}


# ---------------------------------------------------------------------------
# Mi día y seguimiento sugerido
# ---------------------------------------------------------------------------
def quote_expiry(row) -> date | None:
    if not row['cotizacion_fecha']:
        return None
    try:
        return date.fromisoformat(row['cotizacion_fecha'][:10]) + timedelta(days=int(row['cotizacion_validez_dias'] or 30))
    except ValueError:
        return None


def followups_due(con, owner_clause: str, args: list, days: int) -> list[dict]:
    """Cotizaciones enviadas sin respuesta del cliente desde hace `days` días."""
    limit = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = con.execute(f'''SELECT f.* FROM fichas_consulta f WHERE f.estado_gestion IN ('cotizada','muestra_piloto')
               AND f.pendiente_desde IS NULL AND f.ultima_respuesta_en IS NOT NULL AND f.ultima_respuesta_en<=? {owner_clause}
               ORDER BY f.ultima_respuesta_en''', [limit, *args]).fetchall()
    out = []
    for r in rows:
        last = parse_dt(r['ultima_respuesta_en'])
        out.append({'ficha_id': r['id'], 'codigo': r['codigo'], 'cliente': r['cliente'], 'titulo': r['titulo'],
                    'dias': (datetime.now(timezone.utc) - last).days if last else days,
                    'cotizacion': {'monto': r['cotizacion_monto'], 'moneda': r['cotizacion_moneda']},
                    'conversacion': str(conv_key(r)), 'mensaje_id': r['ultimo_mensaje_id']})
    return out


def board_item(r, lote) -> dict:
    resp = response_from_row(r)
    return {'ficha_id': r['id'], 'codigo': r['codigo'], 'cliente': r['cliente'], 'contacto': r['contacto'], 'titulo': r['titulo'],
            'estado_gestion': r['estado_gestion'], 'tipo_consulta': r['tipo_consulta'], 'cantidad': r['cantidad'],
            'responsable': r['responsable'], 'pendiente': resp['pendiente'], 'horas': resp['horas'],
            'ultimo_mensaje_en': r['ultimo_mensaje_en'], 'canal': r['canal_origen'],
            'bajo_minimo': r['tipo_consulta'] in TIPOS_CON_LOTE_MINIMO and r['cantidad'] is not None and r['cantidad'] < lote,
            'conversacion': str(conv_key(r))}


def my_day(con, user, usuario: str = '') -> dict:
    """Tablero personal: asignadas al usuario y sin asignar, más seguimientos y actividades del día.
    Administración y gerencia pueden ver el tablero de otro vendedor."""
    me = user['username'] if user else ''
    role = user['role'] if user else 'administrador'
    from .permisos import allowed
    target = usuario if usuario and allowed(con, user, 'tablero_otros') else me
    lote = lote_minimo(con)
    cfg = empresa(con)
    pend_first = 'ORDER BY CASE WHEN f.pendiente_desde IS NULL THEN 1 ELSE 0 END, f.pendiente_desde, f.ultimo_mensaje_en DESC'

    def column(cond, args):
        rows = con.execute(page_sql(f'SELECT f.* FROM fichas_consulta f WHERE f.estado_gestion IN {OPEN_SQL} AND {cond} {pend_first}', 150, 0),
                           args).fetchall()
        counts = con.execute(f'''SELECT COUNT(*) AS n, SUM(CASE WHEN f.pendiente_desde IS NOT NULL THEN 1 ELSE 0 END) AS p
                                FROM fichas_consulta f WHERE f.estado_gestion IN {OPEN_SQL} AND {cond}''', args).fetchone()
        return [board_item(r, lote) for r in rows], counts['n'], counts['p'] or 0

    mias, n_mias, p_mias = column('f.responsable=?', [target])
    libres, n_libres, p_libres = column("f.responsable=''", [])
    start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc) - timedelta(hours=3)
    end = start + timedelta(days=1)
    acts = con.execute('''SELECT a.*, f.codigo AS ficha_codigo, COALESCE(o.cliente,f.cliente,'') AS cliente,
               CASE WHEN f.oportunidad_id IS NOT NULL THEN f.oportunidad_id ELSE -f.id END AS conv
               FROM actividades_comerciales a LEFT JOIN fichas_consulta f ON f.id=a.ficha_id
               LEFT JOIN oportunidades o ON o.id=a.oportunidad_id
               WHERE a.estado='programada' AND a.inicio<? AND a.responsable=? ORDER BY a.inicio''',
                       [end.isoformat(), target]).fetchall()
    hoy, vencidas = [], []
    for a in acts:
        t = parse_dt(a['inicio'])
        if not t:
            continue
        item = {'id': a['id'], 'titulo': a['titulo'], 'tipo': a['tipo'], 'inicio': a['inicio'], 'fin': a['fin'], 'cliente': a['cliente'],
                'ficha_id': a['ficha_id'], 'oportunidad_id': a['oportunidad_id'], 'responsable': a['responsable'], 'notas': a['notas'],
                'ficha_codigo': a['ficha_codigo'], 'conversacion': str(a['conv']) if a['conv'] is not None else ''}
        (hoy if t >= start else vencidas).append(item)
    usuarios = []
    if allowed(con, user, 'tablero_otros'):
        usuarios = [{'usuario': r['usuario'], 'nombre': r['nombre']} for r in con.execute(
            "SELECT usuario, nombre FROM usuarios WHERE activo=1 AND rol IN ('ventas','administrador') ORDER BY nombre")]
    return {
        'usuario': target, 'propio': target == me, 'fecha': date.today().isoformat(), 'usuarios': usuarios,
        'resumen': {'asignadas': n_mias, 'asignadas_sin_responder': p_mias, 'sin_asignar': n_libres, 'sin_asignar_sin_responder': p_libres,
                    'actividades_hoy': len(hoy), 'vencidas': len(vencidas)},
        'asignadas': mias, 'sin_asignar': libres,
        'actividades_hoy': hoy, 'actividades_vencidas': vencidas[:15],
        'seguimientos_sugeridos': followups_due(con, 'AND f.responsable=?', [target], int(cfg['dias_seguimiento']))[:15],
        'dias_seguimiento': int(cfg['dias_seguimiento']),
    }


# ---------------------------------------------------------------------------
# Importación de Excel / CSV
# ---------------------------------------------------------------------------
def _norm_header(h) -> str:
    text = unicodedata.normalize('NFKD', str(h or '')).encode('ascii', 'ignore').decode().strip().lower()
    return re.sub(r'\s+', ' ', text)


def read_table(nombre: str, data: bytes) -> tuple[list[str], list[list]]:
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(413, 'El archivo supera los 10 MB')
    low = nombre.lower()
    if low.endswith('.csv') or low.endswith('.txt'):
        import csv
        text = None
        for enc in ('utf-8-sig', 'latin-1'):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=';,\t') if text else csv.excel
        rows = list(csv.reader(io.StringIO(text), dialect))
    elif low.endswith('.xlsx') or low.endswith('.xlsm'):
        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception:
            raise HTTPException(422, 'No se pudo leer el archivo de Excel')
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
    else:
        raise HTTPException(422, 'Formato no soportado: usá .xlsx o .csv (en Excel: Guardar como → Libro de Excel o CSV)')
    rows = [r for r in rows if any(c not in (None, '') for c in r)]
    if not rows:
        raise HTTPException(422, 'El archivo está vacío')
    # La fila de encabezados es la primera con al menos dos textos.
    header_idx = next((i for i, r in enumerate(rows[:10]) if sum(1 for c in r if isinstance(c, str) and c.strip()) >= 2), 0)
    headers = [str(c).strip() if c is not None else f'Columna {i + 1}' for i, c in enumerate(rows[header_idx])]
    return headers, rows[header_idx + 1:]


def suggest_mapping(tipo: str, headers: list[str]) -> dict:
    normalized = [_norm_header(h) for h in headers]
    mapping = {}
    for field, names in CAMPOS_IMPORT[tipo].items():
        for name in names:
            n = _norm_header(name)
            if n in normalized and normalized.index(n) not in mapping.values():
                mapping[field] = normalized.index(n)
                break
        else:
            for i, h in enumerate(normalized):
                if i not in mapping.values() and any(_norm_header(x) in h for x in names if len(x) > 3):
                    mapping[field] = i
                    break
    return mapping


def _cell(row, idx):
    if idx is None or idx >= len(row) or row[idx] is None:
        return ''
    value = row[idx]
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _price(text: str):
    if not text:
        return None
    t = re.sub(r'[^0-9,.\-]', '', text)
    if ',' in t and '.' in t:
        t = t.replace('.', '').replace(',', '.') if t.rfind(',') > t.rfind('.') else t.replace(',', '')
    elif ',' in t:
        t = t.replace(',', '.')
    try:
        return round(float(t), 4)
    except ValueError:
        return None


def build_records(tipo: str, rows, mapping: dict) -> tuple[list[dict], list[str]]:
    records, errors = [], []
    for n, row in enumerate(rows, start=2):
        rec = {f: _cell(row, mapping.get(f)) for f in CAMPOS_IMPORT[tipo]}
        missing = [f for f in OBLIGATORIOS[tipo] if not rec.get(f)]
        if missing:
            if len(errors) < 20:
                errors.append(f'Fila {n}: falta {", ".join(missing)}')
            continue
        if tipo == 'articulos':
            rec['precio'] = _price(rec['precio'])
            rec['moneda'] = 'USD' if rec['moneda'].upper() in ('USD', 'U$S', 'US$', 'DOLAR', 'DÓLAR', '2') else 'ARS'
            rec['unidad'] = rec['unidad'] or 'unidad'
        else:
            rec['email'] = rec['email'].lower()
            rec['telefono'] = re.sub(r'[^0-9+]', '', rec['telefono'])
        records.append(rec)
    return records, errors


def _find_client(con, rec):
    if rec.get('codigo'):
        row = con.execute("SELECT id FROM oportunidades WHERE codigo_tango=? AND fusionada_con IS NULL", (rec['codigo'],)).fetchone()
        if row:
            return row['id']
    if rec.get('cuit'):
        row = con.execute("SELECT id FROM oportunidades WHERE cuit=? AND cuit<>'' AND fusionada_con IS NULL", (rec['cuit'],)).fetchone()
        if row:
            return row['id']
    key = norm_name(rec['cliente'])
    for row in con.execute('SELECT id, cliente FROM oportunidades WHERE fusionada_con IS NULL AND LOWER(cliente)=LOWER(?)', (rec['cliente'],)):
        if norm_name(row['cliente']) == key:
            return row['id']
    return None


def apply_import(con, tipo: str, records: list[dict], dry_run: bool) -> dict:
    new = updated = 0
    today = date.today().isoformat()
    for rec in records:
        if tipo == 'articulos':
            exists = con.execute('SELECT id FROM productos WHERE codigo=?', (rec['codigo'],)).fetchone()
            if exists:
                updated += 1
                if not dry_run:
                    con.execute('''UPDATE productos SET descripcion=?, unidad=?, linea=?, precio=COALESCE(?,precio), moneda=?, activo=1,
                                   origen='importado', actualizado_en=? WHERE id=?''',
                                (rec['descripcion'], rec['unidad'], rec['linea'], rec['precio'], rec['moneda'], stamp(), exists['id']))
            else:
                new += 1
                if not dry_run:
                    con.execute('''INSERT INTO productos(codigo,descripcion,unidad,linea,precio,moneda,origen,actualizado_en)
                                   VALUES (?,?,?,?,?,?,'importado',?)''',
                                (rec['codigo'], rec['descripcion'], rec['unidad'], rec['linea'], rec['precio'], rec['moneda'], stamp()))
            continue
        found = _find_client(con, rec)
        if found:
            updated += 1
            if not dry_run:
                fields = {'codigo_tango': rec['codigo'], 'cuit': rec['cuit'], 'localidad': rec['localidad'], 'provincia': rec['provincia'],
                          'lista_precios': rec['lista_precios'], 'email': rec['email'], 'telefono': rec['telefono']}
                fields = {k: v for k, v in fields.items() if v}
                sets = ', '.join(f'{k}=?' for k in fields)
                con.execute(f"UPDATE oportunidades SET {sets + ', ' if sets else ''}es_cliente=1, importado_en=? WHERE id=?",
                            (*fields.values(), stamp(), found))
        else:
            new += 1
            if not dry_run:
                con.execute('''INSERT INTO oportunidades (cliente,contacto,email,telefono,producto,cantidad,estado,ultimo_contacto,creada_el,
                               responsable,canal_origen,notas,codigo_tango,cuit,localidad,provincia,lista_precios,es_cliente,importado_en)
                               VALUES (?,?,?,?,'Sin especificar',NULL,'nueva',?,?,?,'Importación',?,?,?,?,?,?,1,?)''',
                            (rec['cliente'], rec['contacto'] or rec['cliente'], rec['email'], rec['telefono'], today, today,
                             rec['vendedor'].lower() if rec['vendedor'] else '', 'Importado desde Excel', rec['codigo'], rec['cuit'],
                             rec['localidad'], rec['provincia'], rec['lista_precios'], stamp()))
    return {'nuevos': new, 'actualizados': updated}


def template_xlsx(tipo: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    if tipo == 'articulos':
        ws.title = 'Artículos'
        ws.append(['COD_ARTICU', 'DESCRIPCIO', 'PRECIO', 'MONEDA', 'UNIDAD', 'LINEA'])
        for code, desc, unit, line, price, cur in PRODUCTOS_EJEMPLO[:6]:
            ws.append([code, desc, price, cur, unit, line])
    else:
        ws.title = 'Clientes'
        ws.append(['COD_CLIENT', 'RAZON_SOCI', 'CUIT', 'E_MAIL', 'TELEFONO_1', 'CONTACTO', 'LOCALIDAD', 'PROVINCIA', 'COD_VENDED', 'NRO_LISTA'])
        ws.append(['000123', 'Ejemplo Cosmética SRL', '30-00000000-0', 'compras@ejemplo.test', '1150000000', 'Ana Pérez', 'Rosario', 'Santa Fe', '', '1'])
        ws.append(['000124', 'Farmacia Modelo', '30-00000001-0', 'farmacia@ejemplo.test', '1150000001', 'Juan Gómez', 'CABA', 'Buenos Aires', '', '2'])
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='2F5D62')
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = max(12, max(len(str(c.value or '')) for c in col) + 2)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Cotizaciones
# ---------------------------------------------------------------------------
class QuoteItem(BaseModel):
    producto_id: int | None = None
    codigo: str = Field(default='', max_length=60)
    descripcion: str = Field(min_length=1, max_length=300)
    unidad: str = Field(default='unidad', max_length=30)
    cantidad: float = Field(gt=0, le=100_000_000)
    precio_unitario: float = Field(ge=0, le=1_000_000_000)
    descuento_pct: float = Field(default=0, ge=0, le=100)


class QuoteInput(BaseModel):
    moneda: Literal['ARS', 'USD'] = 'ARS'
    validez_dias: int = Field(default=30, ge=1, le=365)
    incluye_iva: bool = True
    iva_pct: float = Field(default=21, ge=0, le=50)
    condiciones: str = Field(default='', max_length=2000)
    notas: str = Field(default='', max_length=2000)
    items: list[QuoteItem] = Field(min_length=1, max_length=60)
    actualizar_estado: bool = True


def quote_totals(items: list[QuoteItem], incluye_iva: bool, iva_pct: float):
    rows, subtotal = [], 0.0
    for it in items:
        importe = round(it.cantidad * it.precio_unitario * (1 - it.descuento_pct / 100), 2)
        subtotal += importe
        rows.append((it, importe))
    subtotal = round(subtotal, 2)
    iva = round(subtotal * iva_pct / 100, 2) if incluye_iva else 0.0
    return rows, subtotal, iva, round(subtotal + iva, 2)


def money(v: float, cur: str) -> str:
    s = f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'{cur} {s}'


def quote_pdf(con, quote_id: int) -> tuple[bytes, str]:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    q = con.execute('SELECT * FROM cotizaciones WHERE id=?', (quote_id,)).fetchone()
    if not q:
        raise HTTPException(404, 'Cotización no encontrada')
    f = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (q['ficha_id'],)).fetchone()
    contact = con.execute('SELECT * FROM oportunidades WHERE id=?', (f['oportunidad_id'],)).fetchone() if f['oportunidad_id'] else None
    items = con.execute('SELECT * FROM cotizacion_items WHERE cotizacion_id=? ORDER BY id', (quote_id,)).fetchall()
    cfg = empresa(con)
    ink, accent, muted = colors.HexColor('#243b42'), colors.HexColor('#2f5d62'), colors.HexColor('#6a777b')
    small = ParagraphStyle('s', fontName='Helvetica', fontSize=8.5, leading=11.5, textColor=ink)
    smallm = ParagraphStyle('sm', parent=small, textColor=muted)
    title = ParagraphStyle('t', fontName='Helvetica-Bold', fontSize=15, leading=19, textColor=ink)
    brand = ParagraphStyle('b', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=accent)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                            title=f"Cotización {q['numero']}", author=cfg['razon_social'])
    W = doc.width
    cfg = {k: esc(v) if isinstance(v, str) else v for k, v in cfg.items()}
    company = '<br/>'.join(x for x in [cfg['domicilio'], ' · '.join(y for y in [cfg['telefono'], cfg['email']] if y),
                                        cfg['web'], f"CUIT {cfg['cuit']}" if cfg['cuit'] else ''] if x)
    head = Table([[Paragraph(cfg['razon_social'], brand), Paragraph(f"<b>COTIZACIÓN</b><br/>N.º {q['numero']}", ParagraphStyle('r', parent=small, alignment=2, fontSize=10, leading=13))],
                  [Paragraph(company, smallm), Paragraph(f"Fecha: {date.fromisoformat(q['fecha']).strftime('%d/%m/%Y')}<br/>Válida por {q['validez_dias']} días<br/>Gestión {f['codigo']}", ParagraphStyle('r2', parent=smallm, alignment=2))]],
                 colWidths=[W * .6, W * .4])
    head.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 1), (-1, 1), .8, accent),
                              ('BOTTOMPADDING', (0, 1), (-1, 1), 10), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
    client_lines = [f"<b>{esc(f['cliente'])}</b>"]
    if f['contacto']:
        client_lines.append(f"Atención: {esc(f['contacto'])}")
    if contact:
        extra = [f"CUIT {contact['cuit']}" if contact['cuit'] else '', contact['email'], contact['telefono'],
                 ', '.join(x for x in [contact['localidad'], contact['provincia']] if x)]
        client_lines += [esc(x) for x in extra if x]
    story = [head, Spacer(1, 10), Paragraph('Cliente', ParagraphStyle('h', parent=small, fontName='Helvetica-Bold', textColor=muted)),
             Paragraph('<br/>'.join(client_lines), small), Spacer(1, 12)]
    data = [['Código', 'Descripción', 'Cant.', 'Precio unit.', 'Desc.', 'Importe']]
    for it in items:
        qty = f"{it['cantidad']:,.0f}".replace(',', '.') if float(it['cantidad']).is_integer() else f"{it['cantidad']:.2f}".replace('.', ',')
        data.append([it['codigo'], Paragraph(f"{esc(it['descripcion'])}<br/><font color='#6a777b'>{esc(it['unidad'])}</font>", small), qty,
                     money(it['precio_unitario'], q['moneda']), f"{it['descuento_pct']:g}%" if it['descuento_pct'] else '—',
                     money(it['importe'], q['moneda'])])
    table = Table(data, colWidths=[W * .13, W * .37, W * .09, W * .15, W * .08, W * .18], repeatRows=1)
    table.setStyle(TableStyle([('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8.5), ('FONT', (0, 1), (-1, -1), 'Helvetica', 8.5),
                               ('TEXTCOLOR', (0, 0), (-1, -1), ink), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8f1ef')),
                               ('ALIGN', (2, 0), (-1, -1), 'RIGHT'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                               ('LINEBELOW', (0, 0), (-1, -1), .4, colors.HexColor('#dfe5e6')), ('TOPPADDING', (0, 0), (-1, -1), 6),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    story += [table, Spacer(1, 8)]
    totals = [['Subtotal', money(q['subtotal'], q['moneda'])]]
    if q['incluye_iva']:
        totals.append([f"IVA {q['iva_pct']:g}%", money(q['iva'], q['moneda'])])
    totals.append(['Total', money(q['total'], q['moneda'])])
    tt = Table(totals, colWidths=[W * .2, W * .2], hAlign='RIGHT')
    tt.setStyle(TableStyle([('FONT', (0, 0), (-1, -1), 'Helvetica', 9), ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 10.5),
                            ('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('LINEABOVE', (0, -1), (-1, -1), .8, accent), ('TEXTCOLOR', (0, 0), (-1, -1), ink)]))
    story += [tt, Spacer(1, 14)]
    if not q['incluye_iva']:
        story.append(Paragraph('Los precios no incluyen IVA.', smallm))
    if q['condiciones']:
        story += [Paragraph('<b>Condiciones</b>', small), Paragraph(esc(q['condiciones']).replace('\n', '<br/>'), small), Spacer(1, 8)]
    if q['notas']:
        story += [Paragraph('<b>Observaciones</b>', small), Paragraph(esc(q['notas']).replace('\n', '<br/>'), small)]
    doc.build(story)
    return buf.getvalue(), f"Cotizacion_{q['numero']}.pdf"


# ---------------------------------------------------------------------------
# Exportación a Excel
# ---------------------------------------------------------------------------
def xlsx(sheets: list[tuple[str, list[str], list[list]]]) -> bytes:
    """Excel en modo de solo escritura: rápido y con poca memoria aun con años de gestiones."""
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook(write_only=True)
    bold, fill = Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor='2F5D62')
    for name, headers, rows in sheets:
        ws = wb.create_sheet(name[:31])
        for i, h in enumerate(headers):
            width = max([len(str(h))] + [len(str(r[i])) for r in rows[:300] if i < len(r) and r[i] is not None])
            ws.column_dimensions[get_column_letter(i + 1)].width = min(60, max(10, width + 2))
        ws.freeze_panes = 'A2'
        head = []
        for h in headers:
            c = WriteOnlyCell(ws, value=h)
            c.font, c.fill = bold, fill
            head.append(c)
        ws.append(head)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


ESTADO_NOMBRE = {'sin_atender': 'Sin atender', 'calificada': 'Calificada', 'cotizada': 'Cotizada', 'muestra_piloto': 'Muestra / piloto',
                 'concretada': 'Concretada', 'no_concretada': 'No concretada', 'resuelta': 'Resuelta'}
TIPO_NOMBRE = {'sin_clasificar': 'Sin clasificar', 'fabricacion_terceros': 'Full Service', 'produccion_terceros': 'Producción a terceros', 'otros_servicios': 'Otros servicios', 'desarrollo_formula': 'Desarrollo de fórmula',
               'elaboracion_envasado': 'Elaboración y envasado', 'mayorista': 'Compra mayorista', 'exportacion': 'Exportación',
               'no_comercial': 'No comercial', 'otro': 'Otra consulta'}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
class ImportInput(BaseModel):
    tipo: Literal['clientes', 'articulos']
    nombre: str = Field(min_length=1, max_length=200)
    contenido_base64: str = Field(min_length=1)
    mapeo: dict[str, int | None] | None = None


class EmpresaInput(BaseModel):
    razon_social: str = Field(min_length=2, max_length=150)
    domicilio: str = Field(default='', max_length=200)
    telefono: str = Field(default='', max_length=60)
    email: str = Field(default='', max_length=120)
    web: str = Field(default='', max_length=120)
    cuit: str = Field(default='', max_length=20)
    condiciones: str = Field(default='', max_length=2000)
    iva_pct: float = Field(default=21, ge=0, le=50)
    dias_seguimiento: int = Field(default=5, ge=1, le=60)
    probabilidades: dict[str, int] = Field(default_factory=lambda: dict(PROB_DEFAULT))
    color_acento: str = Field(default='#2e6a57', pattern=r'^#[0-9a-fA-F]{6}$')


class PlantillaInput(BaseModel):
    atajo: str = Field(min_length=2, max_length=30, pattern=r'^[a-z0-9_-]+$')
    titulo: str = Field(min_length=2, max_length=80)
    texto: str = Field(min_length=2, max_length=3000)
    activa: bool = True


class NotaInput(BaseModel):
    texto: str = Field(min_length=1, max_length=3000)


class DerivarInput(BaseModel):
    area: str = Field(min_length=2, max_length=80)
    nota: str = Field(default='', max_length=3000)


class DocumentoInput(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: str = Field(default='', max_length=300)
    mime: str = Field(default='application/octet-stream', max_length=120)
    contenido_base64: str = Field(min_length=1)


class MetaInput(BaseModel):
    usuario: str = Field(min_length=1, max_length=60)
    mes: str = Field(pattern=r'^\d{4}-\d{2}$')
    moneda: Literal['ARS', 'USD'] = 'ARS'
    monto: float = Field(ge=0, le=1e13)


class TextoIAInput(BaseModel):
    accion: Literal['mejorar', 'traducir_en', 'traducir_pt', 'resumir']
    texto: str = Field(default='', max_length=7000)
    conversacion: str = Field(default='', max_length=30)


def _not_readonly(request, db_path, perm='gestionar'):
    from .permisos import require
    return require(db_path, current(request, db_path), perm)


def register_v5(app: FastAPI, db_path: Path):
    # --------------------------------------------------------------- Mi día
    @app.get('/api/mi-dia')
    def mi_dia(request: Request, usuario: str = ''):
        user = current(request, db_path)
        with connect(db_path) as con:
            return my_day(con, user, usuario.strip())

    # --------------------------------------------------------------- Detalle de los números del resumen
    @app.get('/api/reports/detalle')
    def report_detail_endpoint(request: Request, indicador: str, period: str = 'mes', channel: str = 'todos', responsable: str = ''):
        user = current(request, db_path)
        from .metrics import report_detail, INDICADORES_DETALLE
        if indicador not in INDICADORES_DETALLE or period not in ('mes', 'semana', 'trimestre', 'todos'):
            raise HTTPException(422, 'Indicador o período inválido')
        with connect(db_path) as con:
            return report_detail(con, indicador, period=period, canal=channel, responsable=responsable, user=user)

    # --------------------------------------------------------------- Empresa / reglas
    @app.get('/api/empresa')
    def get_empresa(request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            return {**empresa(con), 'areas': list(AREAS)}

    @app.post('/api/empresa')
    def save_empresa(request: Request, payload: EmpresaInput):
        current(request, db_path, 'administrador')
        probs = {k: max(0, min(100, int(payload.probabilidades.get(k, v)))) for k, v in PROB_DEFAULT.items()}
        with connect(db_path) as con:
            con.execute('''UPDATE empresa_config SET razon_social=?,domicilio=?,telefono=?,email=?,web=?,cuit=?,condiciones=?,iva_pct=?,
                           dias_seguimiento=?,probabilidades_json=?,color_acento=? WHERE id=1''',
                        (payload.razon_social, payload.domicilio, payload.telefono, payload.email, payload.web, payload.cuit,
                         payload.condiciones, payload.iva_pct, payload.dias_seguimiento, json.dumps(probs), payload.color_acento.lower()))
            return empresa(con)

    # --------------------------------------------------------------- Importación
    @app.post('/api/import/preview')
    def import_preview(request: Request, payload: ImportInput):
        current(request, db_path, 'administrador')
        data = base64.b64decode(payload.contenido_base64.split(',')[-1])
        headers, rows = read_table(payload.nombre, data)
        mapping = payload.mapeo if payload.mapeo is not None else suggest_mapping(payload.tipo, headers)
        mapping = {k: v for k, v in mapping.items() if v is not None and 0 <= v < len(headers)}
        records, errors = build_records(payload.tipo, rows, mapping)
        with connect(db_path) as con:
            counts = apply_import(con, payload.tipo, records, dry_run=True)
        return {'columnas': headers, 'campos': list(CAMPOS_IMPORT[payload.tipo]), 'obligatorios': list(OBLIGATORIOS[payload.tipo]),
                'mapeo': mapping, 'total_filas': len(rows), 'validas': len(records), 'errores': errors,
                'muestra': records[:8], **counts}

    @app.post('/api/import/aplicar')
    def import_apply(request: Request, payload: ImportInput):
        current(request, db_path, 'administrador')
        data = base64.b64decode(payload.contenido_base64.split(',')[-1])
        headers, rows = read_table(payload.nombre, data)
        mapping = {k: v for k, v in (payload.mapeo or suggest_mapping(payload.tipo, headers)).items() if v is not None}
        missing = [f for f in OBLIGATORIOS[payload.tipo] if f not in mapping]
        if missing:
            raise HTTPException(422, 'Asigná una columna para: ' + ', '.join(missing))
        records, errors = build_records(payload.tipo, rows, mapping)
        with connect(db_path) as con:
            con.execute('BEGIN IMMEDIATE')
            result = apply_import(con, payload.tipo, records, dry_run=False)
        return {**result, 'omitidas': len(rows) - len(records), 'errores': errors}

    @app.get('/api/import/plantilla')
    def import_template(request: Request, tipo: Literal['clientes', 'articulos'] = 'clientes'):
        current(request, db_path)
        return b64file(template_xlsx(tipo), f'plantilla_{tipo}.xlsx',
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # --------------------------------------------------------------- Productos y cotizaciones
    @app.get('/api/productos')
    def products(request: Request, q: str = '', limit: int = 20):
        current(request, db_path)
        limit = max(1, min(100, limit))
        with connect(db_path) as con:
            where, args = 'activo=1', []
            if q.strip():
                where += ' AND (LOWER(codigo) LIKE ? OR LOWER(descripcion) LIKE ? OR LOWER(linea) LIKE ?)'
                args = [f'%{q.strip().lower()}%'] * 3
            total = con.execute(f'SELECT COUNT(*) FROM productos WHERE {where}', args).fetchone()[0]
            rows = con.execute(page_sql(f'SELECT * FROM productos WHERE {where} ORDER BY linea, descripcion', limit, 0), args).fetchall()
            return {'items': [dict(r) for r in rows], 'total': total}

    @app.post('/api/productos/ejemplo')
    def example_products(request: Request):
        current(request, db_path, 'administrador')
        with connect(db_path) as con:
            return {'agregados': load_example_products(con)}

    @app.get('/api/fichas/{ficha_id}/cotizaciones')
    def list_quotes(ficha_id: int, request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            quotes = [dict(r) for r in con.execute('SELECT * FROM cotizaciones WHERE ficha_id=? ORDER BY id DESC', (ficha_id,))]
            for q in quotes:
                q['items'] = [dict(r) for r in con.execute('SELECT * FROM cotizacion_items WHERE cotizacion_id=? ORDER BY id', (q['id'],))]
            return quotes

    @app.post('/api/fichas/{ficha_id}/cotizaciones', status_code=201)
    def create_quote(ficha_id: int, request: Request, payload: QuoteInput):
        user = _not_readonly(request, db_path)
        rows, subtotal, iva, total = quote_totals(payload.items, payload.incluye_iva, payload.iva_pct)
        with connect(db_path) as con:
            con.execute('BEGIN IMMEDIATE')
            f = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
            if not f or f['estado_gestion'] == 'fusionada':
                raise HTTPException(404, 'Gestión no encontrada')
            today = date.today().isoformat()
            seq = con.execute('SELECT COUNT(*) FROM cotizaciones WHERE ficha_id=?', (ficha_id,)).fetchone()[0] + 1
            numero = f"{f['codigo'].replace('CON-', 'COT-')}-{seq}"
            import secrets
            cur = con.execute('''INSERT INTO cotizaciones(ficha_id,numero,fecha,validez_dias,moneda,incluye_iva,iva_pct,condiciones,notas,
                                 subtotal,iva,total,creada_por,creada_en,token) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                              (ficha_id, numero, today, payload.validez_dias, payload.moneda, int(payload.incluye_iva), payload.iva_pct,
                               payload.condiciones, payload.notas, subtotal, iva, total, user['username'] if user else '', stamp(),
                               secrets.token_urlsafe(18)))
            for it, importe in rows:
                con.execute('''INSERT INTO cotizacion_items(cotizacion_id,producto_id,codigo,descripcion,unidad,cantidad,precio_unitario,
                               descuento_pct,importe) VALUES (?,?,?,?,?,?,?,?,?)''',
                            (cur.lastrowid, it.producto_id, it.codigo, it.descripcion, it.unidad, it.cantidad, it.precio_unitario,
                             it.descuento_pct, importe))
            if payload.actualizar_estado and f['estado_gestion'] in ('sin_atender', 'calificada', 'cotizada'):
                con.execute('''UPDATE fichas_consulta SET estado_gestion='cotizada', cotizacion_monto=?, cotizacion_moneda=?,
                               cotizacion_fecha=?, cotizacion_validez_dias=?, actualizada_en=? WHERE id=?''',
                            (total, payload.moneda, today, payload.validez_dias, stamp(), ficha_id))
            elif payload.actualizar_estado and f['estado_gestion'] == 'muestra_piloto':
                con.execute('''UPDATE fichas_consulta SET cotizacion_monto=?, cotizacion_moneda=?, cotizacion_fecha=?, cotizacion_validez_dias=?,
                               actualizada_en=? WHERE id=?''', (total, payload.moneda, today, payload.validez_dias, stamp(), ficha_id))
            from .historial import log
            log(con, ficha_id, 'cotizacion', numero, money(total, payload.moneda), user['username'] if user else '')
            if payload.actualizar_estado and f['estado_gestion'] in ('sin_atender', 'calificada'):
                log(con, ficha_id, 'estado', 'cotizada', money(total, payload.moneda), user['username'] if user else '')
            token = con.execute('SELECT token FROM cotizaciones WHERE id=?', (cur.lastrowid,)).fetchone()['token']
            return {'id': cur.lastrowid, 'numero': numero, 'total': total, 'moneda': payload.moneda, 'token': token}

    @app.get('/api/cotizaciones/{quote_id}/pdf')
    def quote_pdf_endpoint(quote_id: int, request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            data, name = quote_pdf(con, quote_id)
        return b64file(data, name, 'application/pdf')

    # --------------------------------------------------------------- Cotización online (sin sesión, por enlace)
    def public_quote(con, token: str):
        if not token or len(token) < 16:
            raise HTTPException(404, 'Cotización no encontrada')
        q = con.execute('SELECT * FROM cotizaciones WHERE token=?', (token,)).fetchone()
        if not q:
            raise HTTPException(404, 'Cotización no encontrada')
        return q

    def public_view(con, q) -> dict:
        f = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (q['ficha_id'],)).fetchone()
        cfg = empresa(con)
        vence = date.fromisoformat(q['fecha']) + timedelta(days=int(q['validez_dias']))
        estado = 'aceptada' if q['aceptada_en'] else ('vencida' if vence < date.today() else 'pendiente')
        items = [{k: r[k] for k in ('codigo', 'descripcion', 'unidad', 'cantidad', 'precio_unitario', 'descuento_pct', 'importe')}
                 for r in con.execute('SELECT * FROM cotizacion_items WHERE cotizacion_id=? ORDER BY id', (q['id'],))]
        return {'empresa': {k: cfg[k] for k in ('razon_social', 'email', 'telefono', 'web', 'domicilio', 'color_acento') if k in cfg},
                'numero': q['numero'], 'fecha': q['fecha'], 'vence': vence.isoformat(), 'estado': estado, 'aceptada_en': q['aceptada_en'],
                'cliente': f['cliente'] if f else '', 'contacto': f['contacto'] if f else '', 'moneda': q['moneda'], 'items': items,
                'subtotal': q['subtotal'], 'iva': q['iva'], 'iva_pct': q['iva_pct'], 'incluye_iva': bool(q['incluye_iva']),
                'total': q['total'], 'condiciones': q['condiciones'], 'notas': q['notas']}

    class AceptarInput(BaseModel):
        nombre: str = Field(default='', max_length=120)

    @app.get('/api/publico/cotizaciones/{token}')
    def public_quote_get(token: str):
        with connect(db_path) as con:
            return public_view(con, public_quote(con, token))

    @app.get('/api/publico/cotizaciones/{token}/pdf')
    def public_quote_pdf(token: str):
        with connect(db_path) as con:
            data, name = quote_pdf(con, public_quote(con, token)['id'])
        return b64file(data, name, 'application/pdf')

    @app.post('/api/publico/cotizaciones/{token}/aceptar')
    def public_quote_accept(token: str, payload: AceptarInput):
        with connect(db_path) as con:
            con.execute('BEGIN IMMEDIATE')
            q = public_quote(con, token)
            view = public_view(con, q)
            if view['estado'] == 'vencida':
                raise HTTPException(409, 'La cotización está vencida. Pedí una nueva.')
            if view['estado'] == 'aceptada':
                return view
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            quien = payload.nombre.strip() or view['contacto'] or view['cliente']
            con.execute('UPDATE cotizaciones SET aceptada_en=?, aceptada_por=? WHERE id=?', (now, quien, q['id']))
            f = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (q['ficha_id'],)).fetchone()
            owner = f['responsable'] or q['creada_por']
            con.execute('''UPDATE fichas_consulta SET estado_gestion='concretada', cerrada_en=?, motivo_cierre='', cotizacion_monto=?,
                           cotizacion_moneda=?, cotizacion_fecha=?, actualizada_en=? WHERE id=?''',
                        (now, q['total'], q['moneda'], q['fecha'], now, q['ficha_id']))
            from .historial import log
            log(con, q['ficha_id'], 'aceptacion', q['numero'], f'Aceptada online por {quien}', '')
            log(con, q['ficha_id'], 'estado', 'concretada', money(q['total'], q['moneda']), '')
            con.execute('INSERT INTO notas_internas(ficha_id,usuario,texto,creada_en) VALUES (?,?,?,?)',
                        (q['ficha_id'], '', f"{quien} aceptó la cotización {q['numero']} ({money(q['total'], q['moneda'])}) desde el enlace.", now))
            from .equipo import post
            canal = con.execute("SELECT id FROM chat_canales WHERE clave='ventas'").fetchone()
            if canal and owner:
                post(con, canal['id'], owner, f"{f['cliente']} aceptó la cotización {q['numero']} · {money(q['total'], q['moneda'])}",
                     q['ficha_id'], sistema=True)
            return public_view(con, con.execute('SELECT * FROM cotizaciones WHERE id=?', (q['id'],)).fetchone())

    # --------------------------------------------------------------- Respuestas rápidas
    @app.get('/api/plantillas')
    def templates(request: Request, todas: bool = False):
        current(request, db_path)
        with connect(db_path) as con:
            where = '' if todas else 'WHERE activa=1'
            return [dict(r) for r in con.execute(f'SELECT * FROM plantillas {where} ORDER BY atajo')]

    @app.post('/api/plantillas')
    def save_template(request: Request, payload: PlantillaInput):
        current(request, db_path, 'administrador')
        with connect(db_path) as con:
            con.execute('''INSERT INTO plantillas(atajo,titulo,texto,activa,actualizada_en) VALUES (?,?,?,?,?)
                           ON CONFLICT(atajo) DO UPDATE SET titulo=excluded.titulo, texto=excluded.texto, activa=excluded.activa,
                           actualizada_en=excluded.actualizada_en''',
                        (payload.atajo, payload.titulo, payload.texto, int(payload.activa), stamp()))
            return dict(con.execute('SELECT * FROM plantillas WHERE atajo=?', (payload.atajo,)).fetchone())

    @app.post('/api/plantillas/{plantilla_id}/borrar')
    def delete_template(plantilla_id: int, request: Request):
        current(request, db_path, 'administrador')
        with connect(db_path) as con:
            con.execute('DELETE FROM plantillas WHERE id=?', (plantilla_id,))
            return {'ok': True}

    # --------------------------------------------------------------- Búsqueda global
    @app.get('/api/buscar')
    def global_search(request: Request, q: str = ''):
        current(request, db_path)
        term = q.strip().lower()
        if len(term) < 2:
            return {'contactos': [], 'gestiones': []}
        like = f'%{term}%'
        with connect(db_path) as con:
            contacts = con.execute(page_sql('''SELECT id, cliente, contacto, codigo_tango, localidad FROM oportunidades
                       WHERE fusionada_con IS NULL AND (LOWER(cliente) LIKE ? OR LOWER(contacto) LIKE ? OR LOWER(email) LIKE ?
                       OR LOWER(codigo_tango) LIKE ? OR cuit LIKE ?) ORDER BY ultimo_contacto DESC''', 6, 0), [like] * 5).fetchall()
            cases = con.execute(page_sql('''SELECT * FROM fichas_consulta WHERE estado_gestion<>'fusionada'
                       AND (LOWER(codigo) LIKE ? OR LOWER(cliente) LIKE ? OR LOWER(titulo) LIKE ? OR LOWER(producto) LIKE ?)
                       ORDER BY CASE WHEN estado_gestion IN ('sin_atender','calificada','cotizada','muestra_piloto') THEN 0 ELSE 1 END,
                       actualizada_en DESC''', 8, 0), [like] * 4).fetchall()
            return {'contactos': [dict(r) for r in contacts],
                    'gestiones': [{'id': r['id'], 'codigo': r['codigo'], 'cliente': r['cliente'], 'titulo': r['titulo'],
                                   'estado_gestion': r['estado_gestion'], 'conversacion': str(conv_key(r)),
                                   'tiene_mensajes': bool(r['mensajes_count'])} for r in cases]}

    # --------------------------------------------------------------- Exportar a Excel
    @app.get('/api/export/gestiones')
    def export_cases(request: Request, estado: str = 'abiertas', q: str = ''):
        current(request, db_path)
        from .permisos import require as _req; _req(db_path, current(request, db_path), 'exportar')
        from .escala import search_fichas
        with connect(db_path) as con:
            data = search_fichas(con, {'estado': estado, 'q': q}, 100000, 0)['items']
        rows = [[f['codigo'], f['cliente'], f['contacto'], f['titulo'], TIPO_NOMBRE.get(f['tipo_consulta'], f['tipo_consulta']), f['producto'],
                 f['cantidad'], ESTADO_NOMBRE.get(f['estado_gestion'] or '', f['estado_gestion']), f.get('responsable') or '',
                 f.get('cotizacion_moneda') or '', f.get('cotizacion_monto'), f.get('motivo_cierre') or '', f.get('canal_origen') or '',
                 (f['creada_en'] or '')[:10], (f.get('cerrada_en') or '')[:10], f.get('mensajes')] for f in data]
        headers = ['Código', 'Cliente', 'Contacto', 'Título', 'Tipo de servicio', 'Producto', 'Cantidad', 'Estado', 'Responsable',
                   'Moneda', 'Monto cotizado', 'Motivo de cierre', 'Canal de origen', 'Creada', 'Cerrada', 'Mensajes']
        return b64file(xlsx([('Gestiones', headers, rows)]), f'impulso_gestiones_{estado}_{date.today().isoformat()}.xlsx',
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @app.get('/api/export/contactos')
    def export_contacts(request: Request, q: str = '', activos: bool = False):
        current(request, db_path)
        from .permisos import require as _req; _req(db_path, current(request, db_path), 'exportar')
        where, args = ['o.fusionada_con IS NULL'], []
        if activos:
            where.append(f'EXISTS (SELECT 1 FROM fichas_consulta f WHERE f.oportunidad_id=o.id AND f.estado_gestion IN {OPEN_SQL})')
        if q.strip():
            where.append('(LOWER(o.cliente) LIKE ? OR LOWER(o.contacto) LIKE ? OR LOWER(o.producto) LIKE ?)')
            args += [f'%{q.strip().lower()}%'] * 3
        with connect(db_path) as con:
            rows = con.execute(f'''SELECT o.*, (SELECT COUNT(*) FROM fichas_consulta f WHERE f.oportunidad_id=o.id AND f.estado_gestion IN {OPEN_SQL}) AS abiertas
                                   FROM oportunidades o WHERE {' AND '.join(where)} ORDER BY o.cliente''', args).fetchall()
        data = [[r['cliente'], r['contacto'], r['email'], r['telefono'], r['codigo_tango'], r['cuit'], r['localidad'], r['provincia'],
                 r['responsable'], r['abiertas'], r['ultimo_contacto'], 'Sí' if r['es_cliente'] else 'No'] for r in rows]
        headers = ['Empresa', 'Contacto', 'Email', 'Teléfono', 'Código Tango', 'CUIT', 'Localidad', 'Provincia', 'Responsable',
                   'Gestiones abiertas', 'Último contacto', 'Cliente Tango']
        return b64file(xlsx([('Contactos', headers, data)]), f'impulso_contactos_{date.today().isoformat()}.xlsx',
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @app.get('/api/export/reporte')
    def export_report(request: Request, period: str = 'mes', canal: str = 'todos', responsable: str = ''):
        user = current(request, db_path)
        from .permisos import require as _req; _req(db_path, current(request, db_path), 'exportar')
        from .metrics import report_data
        with connect(db_path) as con:
            d = report_data(con, period=period, canal=canal, responsable=responsable, user=user)
        ind = [[k.replace('_', ' ').capitalize(), v] for k, v in d['indicadores'].items()]
        emb = [[ESTADO_NOMBRE.get(e['estado'], e['estado']), e['cantidad'], e['montos'].get('ARS'), e['montos'].get('USD')] for e in d['embudo']]
        conv = [[TIPO_NOMBRE.get(k, k), v['concretadas'], v['no_concretadas'], v['tasa']] for k, v in d['conversion_por_tipo'].items()]
        convc = [[k, v['concretadas'], v['no_concretadas'], v['tasa']] for k, v in d['conversion_por_canal'].items()]
        mot = [[k, v] for k, v in d['motivos_no_concretadas'].items()]
        alerts = [[a['codigo'], a['cliente'], a['horas'], a['responsable']] for a in d['alertas_sin_respuesta']]
        sheets = [('Indicadores', ['Indicador', 'Valor'], ind + [['Período', f"{d['desde']} a {d['hasta']}"], ['Canal', d['canal']], ['Responsable', d['responsable']]]),
                  ('Embudo', ['Estado', 'Gestiones', 'Monto ARS', 'Monto USD'], emb),
                  ('Conversión por tipo', ['Tipo de servicio', 'Concretadas', 'No concretadas', 'Conversión %'], conv),
                  ('Conversión por canal', ['Canal', 'Concretadas', 'No concretadas', 'Conversión %'], convc),
                  ('Motivos', ['Motivo', 'Cantidad'], mot),
                  ('Sin respuesta +24h', ['Gestión', 'Cliente', 'Horas', 'Responsable'], alerts)]
        return b64file(xlsx(sheets), f'impulso_reporte_{period}_{date.today().isoformat()}.xlsx',
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # --------------------------------------------------------------- Notas internas y derivación
    @app.get('/api/fichas/{ficha_id}/notas')
    def notes(ficha_id: int, request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            return [dict(r) for r in con.execute('SELECT * FROM notas_internas WHERE ficha_id=? ORDER BY creada_en, id', (ficha_id,))]

    @app.post('/api/fichas/{ficha_id}/notas', status_code=201)
    def add_note(ficha_id: int, request: Request, payload: NotaInput):
        user = _not_readonly(request, db_path)
        with connect(db_path) as con:
            if not con.execute('SELECT 1 FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone():
                raise HTTPException(404, 'Gestión no encontrada')
            cur = con.execute('INSERT INTO notas_internas(ficha_id,usuario,texto,creada_en) VALUES (?,?,?,?)',
                              (ficha_id, user['username'] if user else '', payload.texto.strip(),
                               datetime.now(timezone.utc).isoformat(timespec='seconds')))
            return dict(con.execute('SELECT * FROM notas_internas WHERE id=?', (cur.lastrowid,)).fetchone())

    @app.post('/api/fichas/{ficha_id}/derivar')
    def derive(ficha_id: int, request: Request, payload: DerivarInput):
        user = _not_readonly(request, db_path)
        area = payload.area.strip()
        with connect(db_path) as con:
            if not con.execute('SELECT 1 FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone():
                raise HTTPException(404, 'Gestión no encontrada')
            con.execute('UPDATE fichas_consulta SET derivada_a=?, actualizada_en=? WHERE id=?', (area, stamp(), ficha_id))
            from .historial import log
            log(con, ficha_id, 'derivacion', area, payload.nota.strip(), user['username'] if user else '')
            text = payload.nota.strip() or ('Derivada a ' + area if area else 'Se quitó la derivación')
            con.execute('INSERT INTO notas_internas(ficha_id,usuario,texto,area,creada_en) VALUES (?,?,?,?,?)',
                        (ficha_id, user['username'] if user else '', text, area, datetime.now(timezone.utc).isoformat(timespec='seconds')))
            return {'id': ficha_id, 'derivada_a': area}

    # --------------------------------------------------------------- Documentos para adjuntar
    @app.get('/api/documentos')
    def documents(request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            return [dict(r) for r in con.execute('SELECT id,nombre,descripcion,mime,tamano,subido_por,creado_en FROM documentos ORDER BY nombre')]

    @app.post('/api/documentos', status_code=201)
    def upload_document(request: Request, payload: DocumentoInput):
        user = current(request, db_path, 'administrador')
        data = base64.b64decode(payload.contenido_base64.split(',')[-1])
        if len(data) > MAX_DOC_BYTES:
            raise HTTPException(413, 'El archivo supera los 8 MB')
        with connect(db_path) as con:
            cur = con.execute('INSERT INTO documentos(nombre,descripcion,mime,tamano,contenido,subido_por,creado_en) VALUES (?,?,?,?,?,?,?)',
                              (payload.nombre, payload.descripcion, payload.mime, len(data), data, user['username'] if user else '', stamp()))
            return {'id': cur.lastrowid, 'nombre': payload.nombre, 'tamano': len(data)}

    @app.get('/api/documentos/{doc_id}')
    def download_document(doc_id: int, request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            r = con.execute('SELECT * FROM documentos WHERE id=?', (doc_id,)).fetchone()
            if not r:
                raise HTTPException(404, 'Documento no encontrado')
            return b64file(bytes(r['contenido']), r['nombre'], r['mime'])

    @app.post('/api/documentos/{doc_id}/borrar')
    def delete_document(doc_id: int, request: Request):
        current(request, db_path, 'administrador')
        with connect(db_path) as con:
            con.execute('DELETE FROM documentos WHERE id=?', (doc_id,))
            return {'ok': True}

    # --------------------------------------------------------------- Metas y pronóstico
    @app.get('/api/metas')
    def goals(request: Request, mes: str = ''):
        user = current(request, db_path)
        mes = mes or date.today().strftime('%Y-%m')
        start = f'{mes}-01'
        y, m = int(mes[:4]), int(mes[5:7])
        end = date(y + (m == 12), m % 12 + 1, 1).isoformat()
        with connect(db_path) as con:
            cfg = empresa(con)
            sellers = [dict(r) for r in con.execute("SELECT usuario, nombre FROM usuarios WHERE activo=1 AND rol IN ('ventas','administrador') ORDER BY nombre")]
            if user and user['role'] == 'ventas':
                sellers = [s for s in sellers if s['usuario'] == user['username']]
            targets = {(r['usuario'], r['moneda']): r['monto'] for r in con.execute('SELECT * FROM metas WHERE mes=?', (mes,))}
            out = []
            for s in sellers:
                won = con.execute('''SELECT cotizacion_moneda AS m, SUM(cotizacion_monto) AS t, COUNT(*) AS n FROM fichas_consulta
                                     WHERE responsable=? AND estado_gestion='concretada' AND cerrada_en>=? AND cerrada_en<?
                                     GROUP BY cotizacion_moneda''', (s['usuario'], start, end)).fetchall()
                lost = con.execute('''SELECT COUNT(*) FROM fichas_consulta WHERE responsable=? AND estado_gestion='no_concretada'
                                      AND cerrada_en>=? AND cerrada_en<?''', (s['usuario'], start, end)).fetchone()[0]
                won_n = sum(r['n'] for r in won)
                real = {r['m']: round(r['t'] or 0, 2) for r in won if r['m']}
                resp = con.execute('''SELECT primer_entrante_en, primera_respuesta_en FROM fichas_consulta WHERE responsable=?
                                      AND primer_entrante_en>=? AND primer_entrante_en<? AND primera_respuesta_en IS NOT NULL''',
                                   (s['usuario'], start, end)).fetchall()
                hours = [((parse_dt(r['primera_respuesta_en']) - parse_dt(r['primer_entrante_en'])).total_seconds() / 3600) for r in resp
                         if parse_dt(r['primera_respuesta_en']) and parse_dt(r['primer_entrante_en'])]
                out.append({'usuario': s['usuario'], 'nombre': s['nombre'],
                            'metas': {cur: targets[(s['usuario'], cur)] for cur in ('ARS', 'USD') if (s['usuario'], cur) in targets},
                            'real': real, 'concretadas': won_n, 'no_concretadas': lost,
                            'conversion': round(100 * won_n / (won_n + lost)) if won_n + lost else None,
                            'tiempo_respuesta_horas': round(sum(hours) / len(hours), 1) if hours else None})
            probs = cfg['probabilidades']
            rows = con.execute(f'''SELECT estado_gestion AS e, cotizacion_moneda AS m, SUM(cotizacion_monto) AS t, COUNT(*) AS n
                                   FROM fichas_consulta WHERE estado_gestion IN {OPEN_SQL} AND tipo_consulta<>'no_comercial'
                                   {"AND responsable=?" if user and user['role'] == 'ventas' else ''}
                                   GROUP BY estado_gestion, cotizacion_moneda''',
                               [user['username']] if user and user['role'] == 'ventas' else []).fetchall()
            forecast = {'ARS': 0.0, 'USD': 0.0}
            detail = []
            for r in rows:
                if r['m'] and r['t']:
                    forecast[r['m']] = round(forecast[r['m']] + r['t'] * probs.get(r['e'], 0) / 100, 2)
                    detail.append({'estado': r['e'], 'moneda': r['m'], 'monto': round(r['t'], 2), 'probabilidad': probs.get(r['e'], 0)})
            return {'mes': mes, 'vendedores': out, 'pronostico': forecast, 'pronostico_detalle': detail, 'probabilidades': probs,
                    'nota': 'Monto cotizado de cada gestión abierta por la probabilidad de su etapa.'}

    @app.post('/api/metas')
    def save_goal(request: Request, payload: MetaInput):
        current(request, db_path, 'administrador')
        with connect(db_path) as con:
            con.execute('''INSERT INTO metas(usuario,mes,moneda,monto) VALUES (?,?,?,?)
                           ON CONFLICT(usuario,mes,moneda) DO UPDATE SET monto=excluded.monto''',
                        (payload.usuario, payload.mes, payload.moneda, payload.monto))
            return payload.model_dump()

    # --------------------------------------------------------------- IA de texto
    @app.post('/api/ia/texto')
    def ai_text(request: Request, payload: TextoIAInput):
        _not_readonly(request, db_path, 'responder')
        texto = payload.texto.strip()
        if payload.accion == 'resumir':
            if not payload.conversacion:
                raise HTTPException(422, 'Indicá la conversación a resumir')
            conv = int(payload.conversacion)
            with connect(db_path) as con:
                from .escala import conversation_case_ids
                ids = conversation_case_ids(con, conv)
                if not ids:
                    raise HTTPException(404, 'Conversación no encontrada')
                msgs = con.execute(page_sql(f"SELECT * FROM bandeja_consultas WHERE ficha_id IN ({','.join('?' * len(ids))}) ORDER BY recibido_el DESC, id DESC",
                                            80, 0), ids).fetchall()
                texto = '\n'.join(f"[{m['recibido_el'][:16]} · {'Empresa' if m['direccion'] == 'saliente' else 'Cliente'}] {m['texto']}"
                                  for m in reversed(msgs))
        if not texto:
            raise HTTPException(422, 'No hay texto para procesar')
        app.state.reserve_ai_call()
        try:
            result = app.state.transformar_texto(payload.accion, texto)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, 'No se pudo usar la IA en este momento')
        return {'texto': result}
