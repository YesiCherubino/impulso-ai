"""Indicadores comerciales: una sola fuente para Reportes, Finalizados, Agenda y el asistente.

Reglas:
- El estado comercial vive en la gestión (fichas_consulta.estado_gestion).
- Las gestiones fusionadas y las consultas no comerciales no cuentan en los KPIs de ventas.
- Los indicadores de flujo (consultas recibidas, cierres) usan el período; los de situación
  actual (sin atender, en gestión, vencidos, sin respuesta) muestran el estado de hoy.

Escalabilidad: todo se calcula con agregaciones SQL estándar sobre los datos resumidos de cada
gestión (ver escala.py); no se recorren los mensajes en Python.
"""
from datetime import date, datetime, timedelta, timezone

from .business_v4 import ESTADOS_ABIERTOS, ESTADOS_GESTION, TIPOS_CON_LOTE_MINIMO, canal_base, lote_minimo, parse_dt

PERIODOS = ('mes', 'semana', 'trimestre', 'todos')
HORAS_ALERTA = 24
DIAS_SIN_CONTACTO = 7
OPEN_SQL = "('sin_atender','calificada','cotizada','muestra_piloto')"


def period_since(period: str, today: date | None = None) -> date:
    today = today or date.today()
    if period == 'mes':
        return today.replace(day=1)
    if period == 'semana':
        return today - timedelta(days=6)
    if period == 'trimestre':
        return today - timedelta(days=89)
    return date(1900, 1, 1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def response_status(incoming: list[dict], outgoing: list[dict], estado: str, now: datetime | None = None) -> dict:
    """Versión en memoria (la usa el endpoint histórico /api/inbox/threads)."""
    now = now or _now()
    if estado not in ESTADOS_ABIERTOS or not incoming:
        return {'pendiente': False, 'horas': 0, 'desde': None}
    last_out = parse_dt(outgoing[-1]['recibido_el']) if outgoing else None
    pending = [m for m in incoming if m.get('estado') != 'resuelta' and
               (last_out is None or (parse_dt(m['recibido_el']) or now) > last_out)]
    if not pending:
        return {'pendiente': False, 'horas': 0, 'desde': None}
    since = parse_dt(pending[0]['recibido_el']) or now
    return {'pendiente': True, 'horas': max(0, int((now - since).total_seconds() // 3600)), 'desde': pending[0]['recibido_el']}


def case_filter(canal='todos', responsable='', alias='f') -> tuple[str, list]:
    """Filtro base de gestiones para los KPIs de ventas."""
    where = [f"{alias}.estado_gestion<>'fusionada'", f"{alias}.tipo_consulta<>'no_comercial'"]
    args = []
    if canal == 'WhatsApp':
        where.append(f"{alias}.canal_origen LIKE 'WhatsApp%'")
    elif canal and canal != 'todos':
        where.append(f'{alias}.canal_origen=?'); args.append(canal)
    if responsable:
        where.append(f'LOWER({alias}.responsable)=LOWER(?)'); args.append(responsable)
    return ' AND '.join(where), args


def list_seguimientos_vencidos(con, responsable: str = '', now: datetime | None = None) -> list[dict]:
    """Seguimientos de agenda programados y vencidos (misma fuente que la Agenda)."""
    now = now or _now()
    # Prefiltro en la base (con margen de un día por las zonas horarias) y verificación exacta en Python.
    limit = (now + timedelta(days=1)).isoformat()
    args = [limit]
    extra = ''
    if responsable:
        extra = ' AND LOWER(a.responsable)=LOWER(?)'
        args.append(responsable)
    rows = con.execute(f'''SELECT a.*, f.codigo AS ficha_codigo, COALESCE(o.cliente, f.cliente, '') AS cliente,
                          CASE WHEN f.oportunidad_id IS NOT NULL THEN f.oportunidad_id ELSE -f.id END AS conv
                          FROM actividades_comerciales a
                          LEFT JOIN fichas_consulta f ON f.id=a.ficha_id
                          LEFT JOIN oportunidades o ON o.id=a.oportunidad_id
                          WHERE a.tipo='seguimiento' AND a.estado='programada' AND a.inicio<?{extra} ORDER BY a.inicio''', args).fetchall()
    out = []
    for r in rows:
        start = parse_dt(r['inicio'])
        if start and start <= now:
            out.append(dict(r))
    return out


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def report_data(con, *, period='mes', canal='todos', responsable='', user=None) -> dict:
    today = date.today()
    now = _now()
    since_iso = period_since(period, today).isoformat()
    role = user['role'] if user else 'administrador'
    responsible = (responsable or '').strip()
    from .permisos import allowed
    if user and not allowed(con, user, 'reportes_todos'):
        responsible = user['username']
    base, args = case_filter(canal, responsible)
    open_base = f'{base} AND f.estado_gestion IN {OPEN_SQL}'

    def one(sql, extra_args=()):
        return con.execute(sql, [*args, *extra_args]).fetchone()[0] or 0

    # Mensajes entrantes del período, por canal (las respuestas registradas no son consultas).
    canales_rows = con.execute(f'''SELECT b.canal, COUNT(*) AS n FROM bandeja_consultas b JOIN fichas_consulta f ON f.id=b.ficha_id
                                   WHERE {base} AND b.direccion<>'saliente' AND b.recibido_el>=? GROUP BY b.canal''',
                               [*args, since_iso]).fetchall()
    channel_counts = {'WhatsApp': 0, 'Correo': 0, 'Formulario web': 0}
    recibidas = 0
    for r in canales_rows:
        recibidas += r['n']
        key = canal_base(r['canal'])
        if key in channel_counts:
            channel_counts[key] += r['n']

    threshold = (now - timedelta(hours=HORAS_ALERTA)).isoformat()
    limit_contact = (today - timedelta(days=DIAS_SIN_CONTACTO)).isoformat()
    lote = lote_minimo(con)
    lotes = ','.join(f"'{t}'" for t in TIPOS_CON_LOTE_MINIMO)
    vencidos = list_seguimientos_vencidos(con, responsible)

    indicadores = {
        'consultas_recibidas': recibidas,
        'no_leidas': one(f'SELECT SUM(f.no_leidos_count) FROM fichas_consulta f WHERE {base}'),
        'sin_atender': one(f"SELECT COUNT(*) FROM fichas_consulta f WHERE {base} AND f.estado_gestion='sin_atender'"),
        'en_gestion': one(f"SELECT COUNT(*) FROM fichas_consulta f WHERE {open_base} AND f.estado_gestion<>'sin_atender'"),
        'contactos_activos': one(f'SELECT COUNT(DISTINCT f.oportunidad_id) FROM fichas_consulta f WHERE {open_base}'),
        'concretadas': one(f"SELECT COUNT(*) FROM fichas_consulta f WHERE {base} AND f.estado_gestion='concretada' AND f.cerrada_en>=?", [since_iso]),
        'no_concretadas': one(f"SELECT COUNT(*) FROM fichas_consulta f WHERE {base} AND f.estado_gestion='no_concretada' AND f.cerrada_en>=?", [since_iso]),
        'seguimientos_vencidos': len(vencidos),
        'sin_respuesta_24h': one(f'SELECT COUNT(*) FROM fichas_consulta f WHERE {open_base} AND f.pendiente_desde IS NOT NULL AND f.pendiente_desde<=?', [threshold]),
        'sin_contacto_7_dias': con.execute(
            f'''SELECT COUNT(*) FROM oportunidades o WHERE o.fusionada_con IS NULL AND o.fecha_seguimiento IS NULL
                AND o.ultimo_contacto<=? {"AND LOWER(o.responsable)=LOWER(?)" if responsible else ""}
                AND EXISTS (SELECT 1 FROM fichas_consulta f WHERE f.oportunidad_id=o.id AND {open_base})''',
            [limit_contact, *([responsible] if responsible else []), *args]).fetchone()[0],
        'bajo_minimo_abiertas': one(f'SELECT COUNT(*) FROM fichas_consulta f WHERE {open_base} AND f.tipo_consulta IN ({lotes}) AND f.cantidad<?', [lote]),
    }

    productos = con.execute(page(f'''SELECT COALESCE(NULLIF(TRIM(f.producto),''),'No especificado') AS p, COUNT(*) AS n
                              FROM fichas_consulta f WHERE {base} AND f.creada_en>=? GROUP BY COALESCE(NULLIF(TRIM(f.producto),''),'No especificado')
                              ORDER BY n DESC''', 12), [*args, since_iso]).fetchall()

    # Embudo: gestiones creadas en el período, por estado, con montos cotizados por moneda.
    embudo_rows = con.execute(f'''SELECT f.estado_gestion AS e, f.cotizacion_moneda AS m, COUNT(*) AS n, SUM(f.cotizacion_monto) AS monto
                                  FROM fichas_consulta f WHERE {base} AND f.creada_en>=? GROUP BY f.estado_gestion, f.cotizacion_moneda''',
                              [*args, since_iso]).fetchall()
    embudo = []
    for estado in ESTADOS_GESTION:
        if estado == 'resuelta':
            continue
        group = [r for r in embudo_rows if r['e'] == estado]
        montos = {r['m']: round(r['monto'], 2) for r in group if r['m'] and r['monto'] is not None}
        embudo.append({'estado': estado, 'cantidad': sum(r['n'] for r in group), 'montos': montos})

    def conversion(column):
        rows = con.execute(f'''SELECT {column} AS k, f.estado_gestion AS e, COUNT(*) AS n FROM fichas_consulta f
                               WHERE {base} AND f.estado_gestion IN ('concretada','no_concretada') AND f.cerrada_en>=?
                               GROUP BY {column}, f.estado_gestion''', [*args, since_iso]).fetchall()
        groups = {}
        for r in rows:
            key = canal_base(r['k']) if column == 'f.canal_origen' else r['k']
            g = groups.setdefault(key or 'sin_dato', {'concretadas': 0, 'no_concretadas': 0})
            g['concretadas' if r['e'] == 'concretada' else 'no_concretadas'] += r['n']
        for g in groups.values():
            total = g['concretadas'] + g['no_concretadas']
            g['tasa'] = round(100 * g['concretadas'] / total) if total else None
        return groups

    motivos = {(r['k'] or 'Sin motivo'): r['n'] for r in con.execute(
        f'''SELECT f.motivo_cierre AS k, COUNT(*) AS n FROM fichas_consulta f WHERE {base} AND f.estado_gestion='no_concretada'
            AND f.cerrada_en>=? GROUP BY f.motivo_cierre''', [*args, since_iso])}

    # Tiempo de primera respuesta: gestiones cuyo primer mensaje entró en el período.
    first = con.execute(f'''SELECT f.canal_origen, f.primer_entrante_en, f.primera_respuesta_en, f.primera_respuesta_usuario
                            FROM fichas_consulta f WHERE {base} AND f.primer_entrante_en>=?''', [*args, since_iso]).fetchall()
    by_channel, by_user, all_hours, answered = {}, {}, [], 0
    for r in first:
        t0, t1 = parse_dt(r['primer_entrante_en']), parse_dt(r['primera_respuesta_en'])
        hours = round((t1 - t0).total_seconds() / 3600, 1) if t0 and t1 else None
        all_hours.append(hours)
        by_channel.setdefault(canal_base(r['canal_origen']) or 'Sin dato', []).append(hours)
        if hours is not None:
            answered += 1
            by_user.setdefault(r['primera_respuesta_usuario'] or 'Sin usuario', []).append(hours)
    tiempo = {
        'promedio_horas': _avg(all_hours), 'respondidas': answered, 'sin_respuesta_registrada': len(first) - answered,
        'por_canal': {k: {'promedio_horas': _avg(v), 'gestiones': len(v)} for k, v in by_channel.items()},
        'por_vendedor': {k: {'promedio_horas': _avg(v), 'gestiones': len(v)} for k, v in by_user.items()},
    }

    alert_rows = con.execute(page(f'''SELECT f.id, f.codigo, f.cliente, f.responsable, f.pendiente_desde,
                    CASE WHEN f.oportunidad_id IS NOT NULL THEN f.oportunidad_id ELSE -f.id END AS conv
                    FROM fichas_consulta f WHERE {open_base} AND f.pendiente_desde IS NOT NULL AND f.pendiente_desde<=?
                    ORDER BY f.pendiente_desde''', 20), [*args, threshold]).fetchall()
    alertas = []
    for r in alert_rows:
        since = parse_dt(r['pendiente_desde'])
        alertas.append({'ficha_id': r['id'], 'codigo': r['codigo'], 'cliente': r['cliente'], 'responsable': r['responsable'] or '',
                        'horas': int((now - since).total_seconds() // 3600) if since else 0, 'conversacion': str(r['conv'])})

    return {
        'periodo': period, 'desde': since_iso, 'hasta': today.isoformat(), 'canal': canal,
        'responsable': responsible or 'Todos',
        'indicadores': indicadores,
        # Monto de las gestiones concretadas en el período, por moneda (no se suman monedas distintas).
        'monto_concretado': {r['m']: round(r['t'], 2) for r in con.execute(
            f'''SELECT f.cotizacion_moneda AS m, SUM(f.cotizacion_monto) AS t FROM fichas_consulta f WHERE {base}
                AND f.estado_gestion='concretada' AND f.cerrada_en>=? AND f.cotizacion_monto IS NOT NULL
                AND COALESCE(f.cotizacion_moneda,'')<>'' GROUP BY f.cotizacion_moneda''', [*args, since_iso]) if r['t']},
        'canales': channel_counts,
        'productos_consultados': [(r['p'], r['n']) for r in productos],
        'embudo': embudo,
        'conversion_por_tipo': conversion('f.tipo_consulta'),
        'conversion_por_canal': conversion('f.canal_origen'),
        'motivos_no_concretadas': motivos,
        'tiempo_primera_respuesta': tiempo,
        'alertas_sin_respuesta': alertas,
        'seguimientos_vencidos_detalle': [{'id': v['id'], 'titulo': v['titulo'], 'inicio': v['inicio'], 'cliente': v['cliente'],
                                           'ficha_codigo': v['ficha_codigo'],
                                           'conversacion': str(v['conv']) if v['conv'] is not None else ''} for v in vencidos[:20]],
        'gestiones_consideradas': one(f'SELECT COUNT(*) FROM fichas_consulta f WHERE {base}'),
        'origen_datos': ('Entrada y resultado según el período elegido; seguimiento, situación actual. '
                         'No incluye consultas no comerciales.'),
    }


def page(sql: str, limit: int) -> str:
    from .escala import page_sql
    return page_sql(sql, limit, 0)


INDICADORES_DETALLE = ('consultas_recibidas', 'no_leidas', 'sin_atender', 'en_gestion', 'contactos_activos', 'concretadas',
                       'no_concretadas', 'seguimientos_vencidos', 'sin_contacto_7_dias', 'monto_concretado')


def report_detail(con, indicador: str, *, period='mes', canal='todos', responsable='', user=None, limit=50) -> dict:
    """Las gestiones que forman cada número del resumen comercial (mismos filtros que report_data)."""
    from .permisos import allowed
    today = date.today()
    since_iso = period_since(period, today).isoformat()
    responsible = (responsable or '').strip()
    if user and not allowed(con, user, 'reportes_todos'):
        responsible = user['username']
    base, args = case_filter(canal, responsible)
    open_base = f'{base} AND f.estado_gestion IN {OPEN_SQL}'
    cond, extra, order = None, [], 'f.actualizada_en DESC'
    if indicador == 'consultas_recibidas':
        cond = f'''{base} AND EXISTS (SELECT 1 FROM bandeja_consultas b WHERE b.ficha_id=f.id AND b.direccion<>'saliente' AND b.recibido_el>=?)'''
        extra, order = [since_iso], 'f.ultimo_entrante_en DESC'
    elif indicador == 'no_leidas':
        cond, order = f'{base} AND f.no_leidos_count>0', 'f.ultimo_entrante_en DESC'
    elif indicador == 'sin_atender':
        cond, order = f"{base} AND f.estado_gestion='sin_atender'", 'f.creada_en'
    elif indicador == 'en_gestion':
        cond = f"{open_base} AND f.estado_gestion<>'sin_atender'"
    elif indicador == 'contactos_activos':
        cond = f'{open_base} AND f.oportunidad_id IS NOT NULL'
    elif indicador in ('concretadas', 'no_concretadas', 'monto_concretado'):
        estado = 'no_concretada' if indicador == 'no_concretadas' else 'concretada'
        cond, extra, order = f"{base} AND f.estado_gestion='{estado}' AND f.cerrada_en>=?", [since_iso], 'f.cerrada_en DESC'
        if indicador == 'monto_concretado':
            cond += " AND f.cotizacion_monto IS NOT NULL AND COALESCE(f.cotizacion_moneda,'')<>''"
    elif indicador == 'seguimientos_vencidos':
        rows = list_seguimientos_vencidos(con, responsible)
        return {'total': len(rows), 'items': [{'ficha_id': r['ficha_id'], 'codigo': r['ficha_codigo'] or '', 'cliente': r['cliente'],
                                               'titulo': r['titulo'], 'estado_gestion': '', 'responsable': r['responsable'],
                                               'fecha': r['inicio'], 'conversacion': str(r['conv']) if r['conv'] is not None else ''}
                                              for r in rows[:limit]]}
    elif indicador == 'sin_contacto_7_dias':
        limit_contact = (today - timedelta(days=DIAS_SIN_CONTACTO)).isoformat()
        rows = con.execute(f'''SELECT o.* FROM oportunidades o WHERE o.fusionada_con IS NULL AND o.fecha_seguimiento IS NULL
                AND o.ultimo_contacto<=? {"AND LOWER(o.responsable)=LOWER(?)" if responsible else ""}
                AND EXISTS (SELECT 1 FROM fichas_consulta f WHERE f.oportunidad_id=o.id AND {open_base}) ORDER BY o.ultimo_contacto''',
                           [limit_contact, *([responsible] if responsible else []), *args]).fetchall()
        return {'total': len(rows), 'items': [{'ficha_id': None, 'oportunidad_id': r['id'], 'codigo': '', 'cliente': r['cliente'],
                                               'titulo': r['contacto'], 'estado_gestion': '', 'responsable': r['responsable'],
                                               'fecha': r['ultimo_contacto'], 'conversacion': str(r['id'])} for r in rows[:limit]]}
    else:
        raise ValueError('Indicador desconocido')
    total = con.execute(f'SELECT COUNT(*) FROM fichas_consulta f WHERE {cond}', [*args, *extra]).fetchone()[0]
    from .escala import page_sql
    rows = con.execute(page_sql(f'SELECT f.* FROM fichas_consulta f WHERE {cond} ORDER BY {order}', int(limit), 0), [*args, *extra]).fetchall()
    return {'total': total, 'items': [{'ficha_id': r['id'], 'codigo': r['codigo'], 'cliente': r['cliente'], 'titulo': r['titulo'],
                                       'estado_gestion': r['estado_gestion'], 'responsable': r['responsable'],
                                       'fecha': r['cerrada_en'] if indicador in ('concretadas', 'no_concretadas', 'monto_concretado') else (r['ultimo_mensaje_en'] or r['actualizada_en']),
                                       'monto': r['cotizacion_monto'], 'moneda': r['cotizacion_moneda'],
                                       'conversacion': str(r['oportunidad_id'] if r['oportunidad_id'] else -r['id'])} for r in rows]}
