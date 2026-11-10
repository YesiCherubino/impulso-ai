"""Escalabilidad: datos resumidos por gestión y consultas paginadas.

Para que la bandeja, los contactos, Finalizados y Reportes respondan igual con 5 años de historia:
- Cada gestión guarda datos resumidos de sus mensajes (cantidad, no leídos, primer y último mensaje,
  última respuesta, desde cuándo espera respuesta, canal de origen). Se recalculan desde el código
  cada vez que cambia un mensaje (refresh_case_stats), con SQL estándar: no usa triggers ni funciones
  propias de SQLite, para facilitar una futura migración a SQL Server o PostgreSQL.
- Las pantallas piden páginas (limit/offset) y filtran en la base, no en el navegador.
La única sintaxis específica es LIMIT/OFFSET, concentrada en page_sql().
"""
import json
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query, Request

from .db import connect
from .business_v2 import current, stamp, row_ficha
from .business_v4 import (ESTADOS_ABIERTOS, ESTADOS_CERRADOS, TIPOS_CON_LOTE_MINIMO, canal_base, lote_minimo,
                          parse_dt, plan_case_merges, plan_contact_merges, apply_merge_plan)

STATS_COLUMNS = {
    'mensajes_count': 'INTEGER NOT NULL DEFAULT 0',
    'no_leidos_count': 'INTEGER NOT NULL DEFAULT 0',
    'primer_entrante_en': 'TEXT',
    'ultimo_mensaje_en': 'TEXT',
    'ultimo_entrante_en': 'TEXT',
    'ultima_respuesta_en': 'TEXT',
    'primera_respuesta_en': 'TEXT',
    'primera_respuesta_usuario': "TEXT NOT NULL DEFAULT ''",
    'pendiente_desde': 'TEXT',
    'canal_origen': "TEXT NOT NULL DEFAULT ''",
    'ultimo_mensaje_id': 'INTEGER',
    'tiene_whatsapp': 'INTEGER NOT NULL DEFAULT 0',
    'tiene_correo': 'INTEGER NOT NULL DEFAULT 0',
    'tiene_web': 'INTEGER NOT NULL DEFAULT 0',
}
INDEXES = [
    'CREATE INDEX IF NOT EXISTS idx_inbox_ficha_fecha ON bandeja_consultas(ficha_id, recibido_el)',
    'CREATE INDEX IF NOT EXISTS idx_inbox_fecha ON bandeja_consultas(recibido_el)',
    'CREATE INDEX IF NOT EXISTS idx_fichas_estado_ultimo ON fichas_consulta(estado_gestion, ultimo_mensaje_en)',
    'CREATE INDEX IF NOT EXISTS idx_fichas_responsable ON fichas_consulta(responsable)',
    'CREATE INDEX IF NOT EXISTS idx_fichas_cerrada ON fichas_consulta(cerrada_en)',
    'CREATE INDEX IF NOT EXISTS idx_fichas_creada ON fichas_consulta(creada_en)',
    'CREATE INDEX IF NOT EXISTS idx_fichas_pendiente ON fichas_consulta(pendiente_desde)',
    'CREATE INDEX IF NOT EXISTS idx_actividades_tipo ON actividades_comerciales(tipo, estado, inicio)',
    'CREATE INDEX IF NOT EXISTS idx_actividades_inicio ON actividades_comerciales(inicio)',
    'CREATE INDEX IF NOT EXISTS idx_oportunidades_ultimo ON oportunidades(ultimo_contacto)',
]
OPEN_SQL = "('sin_atender','calificada','cotizada','muestra_piloto')"
MAX_PAGE = 200


def page_sql(sql: str, limit: int, offset: int) -> str:
    """Único punto con sintaxis de paginación (en SQL Server sería OFFSET … ROWS FETCH NEXT … ROWS ONLY)."""
    return f'{sql} LIMIT {int(limit)} OFFSET {int(offset)}'


def init_escala(con) -> None:
    cols = {r['name'] for r in con.execute('PRAGMA table_info(fichas_consulta)')}
    for col, sql in STATS_COLUMNS.items():
        if col not in cols:
            con.execute(f'ALTER TABLE fichas_consulta ADD COLUMN {col} {sql}')
    for sql in INDEXES:
        con.execute(sql)
    refresh_case_stats(con)


def refresh_case_stats(con, ids=None) -> None:
    """Recalcula los datos resumidos de las gestiones indicadas (o de todas)."""
    if ids is not None:
        ids = sorted({int(i) for i in ids if i})
        if not ids:
            return
    where = '' if ids is None else f" WHERE id IN ({','.join(str(i) for i in ids)})"
    b = 'SELECT {fn} FROM bandeja_consultas b WHERE b.ficha_id=fichas_consulta.id'
    entrante = " AND b.direccion<>'saliente'"
    saliente = " AND b.direccion='saliente'"
    con.execute(f'''UPDATE fichas_consulta SET
        mensajes_count=({b.format(fn='COUNT(*)')}),
        no_leidos_count=({b.format(fn='COUNT(*)')}{entrante} AND b.leido_en IS NULL),
        primer_entrante_en=({b.format(fn='MIN(b.recibido_el)')}{entrante}),
        ultimo_mensaje_en=({b.format(fn='MAX(b.recibido_el)')}),
        ultimo_entrante_en=({b.format(fn='MAX(b.recibido_el)')}{entrante}),
        ultima_respuesta_en=({b.format(fn='MAX(b.recibido_el)')}{saliente}),
        tiene_whatsapp=CASE WHEN EXISTS({b.format(fn='1')}{entrante} AND b.canal LIKE 'WhatsApp%') THEN 1 ELSE 0 END,
        tiene_correo=CASE WHEN EXISTS({b.format(fn='1')}{entrante} AND b.canal='Correo') THEN 1 ELSE 0 END,
        tiene_web=CASE WHEN EXISTS({b.format(fn='1')}{entrante} AND b.canal='Formulario web') THEN 1 ELSE 0 END
        {where}''')
    # Segunda pasada: valores que dependen de los anteriores.
    con.execute(f'''UPDATE fichas_consulta SET
        canal_origen=COALESCE(({b.format(fn='MIN(b.canal)')}{entrante} AND b.recibido_el=fichas_consulta.primer_entrante_en),''),
        ultimo_mensaje_id=({b.format(fn='MAX(b.id)')} AND b.recibido_el=fichas_consulta.ultimo_mensaje_en),
        primera_respuesta_en=({b.format(fn='MIN(b.recibido_el)')}{saliente} AND b.recibido_el>=fichas_consulta.primer_entrante_en),
        pendiente_desde=({b.format(fn='MIN(b.recibido_el)')}{entrante} AND b.estado<>'resuelta'
                         AND (fichas_consulta.ultima_respuesta_en IS NULL OR b.recibido_el>fichas_consulta.ultima_respuesta_en))
        {where}''')
    con.execute(f'''UPDATE fichas_consulta SET primera_respuesta_usuario=COALESCE(({b.format(fn='MIN(b.usuario)')}{saliente}
        AND b.recibido_el=fichas_consulta.primera_respuesta_en),'') {where}''')


def touch_messages(con, *message_ids) -> None:
    """Refresca las gestiones de los mensajes indicados."""
    ids = [i for i in message_ids if i]
    if not ids:
        return
    rows = con.execute(f"SELECT DISTINCT ficha_id FROM bandeja_consultas WHERE id IN ({','.join('?' * len(ids))})", ids)
    refresh_case_stats(con, [r['ficha_id'] for r in rows])


def hours_since(value: str | None, now: datetime | None = None) -> int:
    t = parse_dt(value)
    if not t:
        return 0
    return max(0, int(((now or datetime.now(timezone.utc)) - t).total_seconds() // 3600))


def msg_dict(r) -> dict:
    d = dict(r)
    raw = d.pop('adjuntos_json', None)
    try:
        d['adjuntos'] = json.loads(raw) if raw else []
    except ValueError:
        d['adjuntos'] = []
    return d


def response_from_row(r) -> dict:
    """Estado de respuesta desde los datos resumidos de la gestión (sin leer mensajes)."""
    if r['estado_gestion'] not in ESTADOS_ABIERTOS or not r['pendiente_desde']:
        return {'pendiente': False, 'horas': 0, 'desde': None}
    return {'pendiente': True, 'horas': hours_since(r['pendiente_desde']), 'desde': r['pendiente_desde']}


def conv_key(row) -> int:
    """Conversación = contacto (si la gestión tiene contacto) o la propia gestión (número negativo)."""
    return row['oportunidad_id'] if row['oportunidad_id'] else -row['id']


# ---------------------------------------------------------------------------
# Bandeja paginada
# ---------------------------------------------------------------------------
CONV_EXPR = 'CASE WHEN {a}.oportunidad_id IS NOT NULL THEN {a}.oportunidad_id ELSE -{a}.id END'


def conv_cte(prefilter: str = '') -> str:
    """CTE de conversaciones. prefilter acota primero las conversaciones candidatas (con índice), para no
    ordenar toda la historia en cada pedido."""
    pre = ''
    if prefilter:
        pre = (f" AND {CONV_EXPR.format(a='fc')} IN (SELECT {CONV_EXPR.format(a='p')} FROM fichas_consulta p "
               f"WHERE p.estado_gestion<>'fusionada' AND p.mensajes_count>0 AND ({prefilter}))")
    return f'''WITH f AS (
  SELECT fc.id, {CONV_EXPR.format(a='fc')} AS conv,
         CASE WHEN fc.estado_gestion IN {OPEN_SQL} THEN 1 ELSE 0 END AS abierta,
         fc.ultimo_mensaje_en, fc.ultimo_mensaje_id, fc.mensajes_count, fc.no_leidos_count,
         fc.tiene_whatsapp, fc.tiene_correo, fc.tiene_web
  FROM fichas_consulta fc WHERE fc.estado_gestion<>'fusionada' AND fc.mensajes_count>0{pre}),
r AS (
  SELECT f.id, f.conv, ROW_NUMBER() OVER (PARTITION BY conv ORDER BY abierta DESC, ultimo_mensaje_en DESC, id DESC) AS rn,
         FIRST_VALUE(ultimo_mensaje_id) OVER (PARTITION BY conv ORDER BY ultimo_mensaje_en DESC, id DESC) AS conv_ultimo_id
  FROM f),
a AS (
  SELECT conv, MAX(ultimo_mensaje_en) AS ultimo, SUM(mensajes_count) AS total_mensajes, SUM(no_leidos_count) AS no_leidos,
         MAX(abierta) AS alguna_abierta, MAX(tiene_whatsapp) AS c_whatsapp, MAX(tiene_correo) AS c_correo, MAX(tiene_web) AS c_web
  FROM f GROUP BY conv)'''


# La gestión activa de cada conversación se une como "x" (datos completos solo para las filas elegidas).
CONV_FROM = 'FROM a JOIN r ON r.conv=a.conv AND r.rn=1 JOIN fichas_consulta x ON x.id=r.id'
X_OPEN = f'(x.estado_gestion IN {OPEN_SQL})'


PREFILTERS = {
    'abiertas': f'p.estado_gestion IN {OPEN_SQL} OR (p.cerrada_en IS NOT NULL AND p.ultimo_entrante_en>p.cerrada_en)',
    'sin_leer': 'p.no_leidos_count>0',
    'sin_atender': "p.estado_gestion='sin_atender'",
    'sin_responder': f'p.estado_gestion IN {OPEN_SQL} AND p.pendiente_desde IS NOT NULL',
}


def _conversation_filters(params: dict, user, lote: int):
    where, args = ['1=1'], []
    estado = params.get('estado') or 'abiertas'
    tras_cierre = "(a.alguna_abierta=0 AND x.cerrada_en IS NOT NULL AND x.ultimo_entrante_en>x.cerrada_en)"
    if estado == 'abiertas':
        where.append(f'(a.alguna_abierta=1 OR {tras_cierre})')
    elif estado == 'sin_leer':
        where.append('a.no_leidos>0')
    elif estado == 'sin_atender':
        where.append("x.estado_gestion='sin_atender'")
    elif estado == 'sin_responder':
        where.append(f'({X_OPEN} AND x.pendiente_desde IS NOT NULL)')
    elif estado == 'cerradas':
        where.append('a.alguna_abierta=0')
    canal = params.get('canal') or 'todos'
    if canal == 'WhatsApp':
        where.append('a.c_whatsapp=1')
    elif canal == 'Correo':
        where.append('a.c_correo=1')
    elif canal == 'Formulario web':
        where.append('a.c_web=1')
    owner = params.get('responsable') or 'todos'
    me = user['username'] if user else ''
    if params.get('_solo_propias'):
        where.append("(x.responsable=? OR x.responsable='')"); args.append(me)
    if owner == 'mias':
        where.append('x.responsable=?'); args.append(me)
    elif owner == 'mias_y_libres':
        where.append("(x.responsable=? OR x.responsable='')"); args.append(me)
    elif owner == 'sin_asignar':
        where.append("x.responsable=''")
    elif owner.startswith('u:'):
        where.append('x.responsable=?'); args.append(owner[2:])
    tipo = params.get('tipo') or 'todos'
    if tipo != 'todos':
        where.append('x.tipo_consulta=?'); args.append(tipo)
    q = (params.get('q') or '').strip().lower()
    if q:
        like = f'%{q}%'
        where.append(f'''a.conv IN (
            SELECT {CONV_EXPR.format(a='f2')} FROM fichas_consulta f2
              WHERE LOWER(f2.cliente) LIKE ? OR LOWER(f2.contacto) LIKE ? OR LOWER(f2.codigo) LIKE ?
            UNION SELECT {CONV_EXPR.format(a='f3')} FROM fichas_consulta f3 JOIN bandeja_consultas b ON b.ficha_id=f3.id
              WHERE LOWER(b.texto) LIKE ? OR LOWER(b.asunto) LIKE ? OR LOWER(b.email_remitente) LIKE ?)''')
        args += [like] * 6
    if params.get('conv') is not None:
        where.append('a.conv=?'); args.append(int(params['conv']))
    return ' AND '.join(where), args


def list_conversations(con, params: dict, user=None, limit=50, offset=0) -> dict:
    from .permisos import allowed
    if user and not allowed(con, user, 'ver_todas'):
        params = {**params, '_solo_propias': True}
    lote = lote_minimo(con)
    where, args = _conversation_filters(params, user, lote)
    prefilter = PREFILTERS.get(params.get('estado') or 'abiertas', '')
    if params.get('conv') is not None:
        prefilter = f"{CONV_EXPR.format(a='p')}={int(params['conv'])}"
    cte = conv_cte(prefilter)
    base = f'{cte} SELECT a.*, r.conv_ultimo_id, x.* {CONV_FROM} WHERE {where}'
    total = con.execute(f'{cte} SELECT COUNT(*) {CONV_FROM} WHERE {where}', args).fetchone()[0]
    lotes = ','.join(f"'{t}'" for t in TIPOS_CON_LOTE_MINIMO)
    if params.get('orden') == 'prioridad':
        order = f'''ORDER BY CASE WHEN x.tipo_consulta='no_comercial' OR (x.tipo_consulta IN ({lotes}) AND x.cantidad<{int(lote)}) THEN 1 ELSE 0 END,
                    CASE WHEN {X_OPEN} AND x.pendiente_desde IS NOT NULL THEN 0 ELSE 1 END,
                    x.pendiente_desde, COALESCE(x.cantidad,0) DESC, a.ultimo DESC'''
    else:
        order = 'ORDER BY a.ultimo DESC, a.conv'
    rows = con.execute(page_sql(f'{base} {order}', limit, offset), args).fetchall()
    last_ids = [r['conv_ultimo_id'] for r in rows if r['conv_ultimo_id']]
    previews = {}
    if last_ids:
        for m in con.execute(f"SELECT id,texto,direccion,canal FROM bandeja_consultas WHERE id IN ({','.join('?' * len(last_ids))})", last_ids):
            previews[m['id']] = dict(m)
    items = [conversation_summary(r, previews.get(r['conv_ultimo_id']), lote) for r in rows]
    return {'items': items, 'total': total, 'limit': limit, 'offset': offset}


def conversation_summary(r, preview, lote) -> dict:
    tras_cierre = bool(not r['alguna_abierta'] and r['cerrada_en'] and r['ultimo_entrante_en']
                       and r['ultimo_entrante_en'] > r['cerrada_en'])
    return {
        'key': str(r['conv']), 'cliente': r['cliente'], 'contacto': r['contacto'], 'ultimo': r['ultimo'],
        'mensajes_count': r['total_mensajes'], 'no_leidos': r['no_leidos'],
        'cerrada': not r['alguna_abierta'], 'mensaje_tras_cierre': tras_cierre,
        'respuesta': response_from_row(r),
        'ultimo_texto': (preview or {}).get('texto', '')[:220],
        'ultimo_saliente': (preview or {}).get('direccion') == 'saliente',
        'gestion': {
            'id': r['id'], 'codigo': r['codigo'], 'titulo': r['titulo'], 'estado_gestion': r['estado_gestion'],
            'tipo_consulta': r['tipo_consulta'], 'tipo_sugerido_ia': r['tipo_sugerido_ia'], 'cantidad': r['cantidad'],
            'producto': r['producto'], 'responsable': r['responsable'], 'cerrada_en': r['cerrada_en'],
            'cotizacion_monto': r['cotizacion_monto'], 'cotizacion_moneda': r['cotizacion_moneda'],
            'bajo_minimo': r['tipo_consulta'] in TIPOS_CON_LOTE_MINIMO and r['cantidad'] is not None and r['cantidad'] < lote,
        },
    }


def conversation_case_ids(con, conv: int) -> list[int]:
    if conv > 0:
        rows = con.execute("SELECT id FROM fichas_consulta WHERE oportunidad_id=? AND estado_gestion<>'fusionada'", (conv,))
    else:
        rows = con.execute("SELECT id FROM fichas_consulta WHERE id=? AND estado_gestion<>'fusionada'", (-conv,))
    return [r['id'] for r in rows]


def search_fichas(con, params: dict, limit: int, offset: int) -> dict:
    filters = [("f.estado_gestion<>'fusionada'", [])]
    if params.get('oportunidad_id'):
        filters.append(('f.oportunidad_id=?', [int(params['oportunidad_id'])]))
    if params.get('cliente'):
        filters.append(('LOWER(f.cliente)=LOWER(?)', [params['cliente']]))
    if params.get('responsable'):
        filters.append(('f.responsable=?', [params['responsable']]))
    q = (params.get('q') or '').strip().lower()
    if q:
        filters.append(('(LOWER(f.cliente) LIKE ? OR LOWER(f.contacto) LIKE ? OR LOWER(f.codigo) LIKE ? '
                        'OR LOWER(f.titulo) LIKE ? OR LOWER(f.producto) LIKE ?)', [f'%{q}%'] * 5))
    estado = params.get('estado') or 'todas'
    if estado == 'abiertas':
        state = (f'f.estado_gestion IN {OPEN_SQL}', [])
    elif estado == 'cerradas':
        state = ("f.estado_gestion IN ('concretada','no_concretada','resuelta')", [])
    elif estado != 'todas':
        state = ('f.estado_gestion=?', [estado])
    else:
        state = None

    def build(items):
        return ' AND '.join(c for c, _ in items), [a for _, args in items for a in args]

    base_where, base_args = build(filters)
    where, args = build(filters + ([state] if state else []))
    # Conteos por estado con los mismos filtros, salvo el de estado (para las pestañas de Finalizados).
    conteos = {r['estado_gestion']: r['n'] for r in con.execute(
        f'SELECT f.estado_gestion, COUNT(*) AS n FROM fichas_consulta f WHERE {base_where} GROUP BY f.estado_gestion', base_args)}
    total = con.execute(f'SELECT COUNT(*) FROM fichas_consulta f WHERE {where}', args).fetchone()[0]
    closed = estado == 'cerradas' or estado in ESTADOS_CERRADOS
    order = 'ORDER BY f.cerrada_en DESC, f.id DESC' if closed else 'ORDER BY f.actualizada_en DESC, f.id DESC'
    rows = con.execute(page_sql(f'SELECT f.* FROM fichas_consulta f WHERE {where} {order}', limit, offset), args).fetchall()
    lote = lote_minimo(con)
    items = []
    for r in rows:
        item = row_ficha(r, lote)
        item['mensajes'] = r['mensajes_count']
        item['canal_origen'] = canal_base(r['canal_origen'])
        item['respuesta'] = response_from_row(r)
        items.append(item)
    return {'items': items, 'total': total, 'limit': limit, 'offset': offset, 'conteos': conteos}


def _page(limit, offset):
    return max(1, min(MAX_PAGE, int(limit))), max(0, int(offset))


def register_escala(app: FastAPI, db_path):
    @app.get('/api/inbox/conversations')
    def conversations(request: Request, estado: str = 'abiertas', canal: str = 'todos', responsable: str = 'todos',
                      tipo: str = 'todos', q: str = '', orden: str = 'reciente', limit: int = 50, offset: int = 0):
        user = current(request, db_path)
        limit, offset = _page(limit, offset)
        with connect(db_path) as con:
            return list_conversations(con, {'estado': estado, 'canal': canal, 'responsable': responsable, 'tipo': tipo,
                                            'q': q, 'orden': orden}, user, limit, offset)

    @app.get('/api/inbox/conversations/{conv}')
    def conversation_detail(conv: int, request: Request, limite: int = 200, antes_de: str = ''):
        user = current(request, db_path)
        limite = max(1, min(500, limite))
        with connect(db_path) as con:
            found = list_conversations(con, {'estado': 'todas', 'conv': conv}, user, 1, 0)['items']
            if not found:
                raise HTTPException(404, 'Conversación no encontrada')
            ids = conversation_case_ids(con, conv)
            marks = ','.join('?' * len(ids))
            args = list(ids)
            extra = ''
            if antes_de:
                extra = ' AND recibido_el<?'
                args.append(antes_de)
            rows = con.execute(page_sql(f'SELECT * FROM bandeja_consultas WHERE ficha_id IN ({marks}){extra} ORDER BY recibido_el DESC, id DESC',
                                        limite + 1, 0), args).fetchall()
            more = len(rows) > limite
            messages = [msg_dict(r) for r in reversed(rows[:limite])]
            lote = lote_minimo(con)
            fichas = []
            for r in con.execute(f'SELECT * FROM fichas_consulta WHERE id IN ({marks}) ORDER BY ultimo_mensaje_en DESC', ids):
                item = row_ficha(r, lote)
                item['mensajes'] = r['mensajes_count']
                item['respuesta'] = response_from_row(r)
                fichas.append(item)
            return {**found[0], 'mensajes': messages, 'hay_anteriores': more, 'fichas': fichas}

    @app.post('/api/inbox/conversations/{conv}/read')
    def conversation_read(conv: int, request: Request):
        user = current(request, db_path)
        from .permisos import allowed
        with connect(db_path) as con:
            if not allowed(con, user, 'responder'):
                return {'ok': True}  # Quien solo consulta no cambia el estado de lectura.
        with connect(db_path) as con:
            ids = conversation_case_ids(con, conv)
            if ids:
                con.execute(f"""UPDATE bandeja_consultas SET leido_en=? WHERE ficha_id IN ({','.join('?' * len(ids))})
                               AND leido_en IS NULL AND direccion<>'saliente'""", (stamp(), *ids))
                refresh_case_stats(con, ids)
            return {'ok': True}

    @app.get('/api/inbox/{message_id}/conversation')
    def message_conversation(message_id: int, request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            row = con.execute('''SELECT f.id, f.oportunidad_id FROM bandeja_consultas b JOIN fichas_consulta f ON f.id=b.ficha_id
                                 WHERE b.id=?''', (message_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Mensaje no encontrado')
            return {'key': str(conv_key(row))}

    @app.get('/api/fichas/{ficha_id}/conversation')
    def case_conversation(ficha_id: int, request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            row = con.execute('SELECT id, oportunidad_id FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Gestión no encontrada')
            return {'key': str(conv_key(row))}

    @app.get('/api/fichas-search')
    def fichas_search(request: Request, estado: str = 'todas', q: str = '', oportunidad_id: int | None = None,
                      cliente: str = '', responsable: str = '', limit: int = 50, offset: int = 0):
        current(request, db_path)
        limit, offset = _page(limit, offset)
        with connect(db_path) as con:
            return search_fichas(con, {'estado': estado, 'q': q, 'oportunidad_id': oportunidad_id, 'cliente': cliente,
                                       'responsable': responsable}, limit, offset)

    @app.get('/api/contacts/search')
    def contacts_search(request: Request, q: str = '', activos: bool = True, limit: int = 50, offset: int = 0):
        current(request, db_path)
        limit, offset = _page(limit, offset)
        rank = "CASE f.estado_gestion WHEN 'muestra_piloto' THEN 4 WHEN 'cotizada' THEN 3 WHEN 'calificada' THEN 2 WHEN 'sin_atender' THEN 1 ELSE 0 END"
        where, args = ['o.fusionada_con IS NULL'], []
        if activos:
            where.append(f'EXISTS (SELECT 1 FROM fichas_consulta f WHERE f.oportunidad_id=o.id AND f.estado_gestion IN {OPEN_SQL})')
        q = q.strip().lower()
        if q:
            where.append('(LOWER(o.cliente) LIKE ? OR LOWER(o.contacto) LIKE ? OR LOWER(o.producto) LIKE ? OR LOWER(o.email) LIKE ?)')
            args += [f'%{q}%'] * 4
        sql_where = ' AND '.join(where)
        with connect(db_path) as con:
            total = con.execute(f'SELECT COUNT(*) FROM oportunidades o WHERE {sql_where}', args).fetchone()[0]
            rows = con.execute(page_sql(f'''SELECT o.*,
                    (SELECT MAX({rank}) FROM fichas_consulta f WHERE f.oportunidad_id=o.id AND f.estado_gestion IN {OPEN_SQL}) AS rango,
                    (SELECT COUNT(*) FROM fichas_consulta f WHERE f.oportunidad_id=o.id AND f.estado_gestion IN {OPEN_SQL}) AS abiertas,
                    (SELECT COUNT(*) FROM fichas_consulta f WHERE f.oportunidad_id=o.id AND f.estado_gestion<>'fusionada') AS gestiones
                    FROM oportunidades o WHERE {sql_where} ORDER BY o.ultimo_contacto DESC, o.id DESC''', limit, offset), args).fetchall()
            names = {4: 'muestra_piloto', 3: 'cotizada', 2: 'calificada', 1: 'sin_atender'}
            items = []
            for r in rows:
                item = {k: r[k] for k in ('id', 'cliente', 'contacto', 'email', 'telefono', 'producto', 'cantidad', 'tipo_consulta',
                                          'responsable', 'ultimo_contacto', 'fecha_seguimiento', 'canal_origen')}
                item['estado_gestion_actual'] = names.get(r['rango'] or 0, '')
                item['gestiones_abiertas'] = r['abiertas']
                item['gestiones'] = r['gestiones']
                items.append(item)
            return {'items': items, 'total': total, 'limit': limit, 'offset': offset}

    @app.get('/api/admin/duplicados')
    def duplicates_preview(request: Request):
        current(request, db_path, 'administrador')
        with connect(db_path) as con:
            cases = plan_case_merges(con)
            contacts = plan_contact_merges(con)
            return {'gestiones': [{'origen': s['codigo'], 'destino': d['codigo'], 'cliente': s['cliente']} for s, d in cases],
                    'contactos': [{'origen': s['id'], 'destino': d['id'], 'cliente': s['cliente']} for s, d in contacts]}

    @app.post('/api/admin/duplicados/unificar')
    def duplicates_apply(request: Request):
        current(request, db_path, 'administrador')
        with connect(db_path) as con:
            con.execute('BEGIN IMMEDIATE')
            result = apply_merge_plan(con)
            refresh_case_stats(con)
            return result
