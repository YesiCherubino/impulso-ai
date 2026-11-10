"""Indicadores comerciales: una sola fuente para Reportes, Finalizados, Agenda y el asistente.

Reglas:
- El estado comercial vive en la gestión (fichas_consulta.estado_gestion).
- Las gestiones fusionadas y las consultas no comerciales no cuentan en los KPIs de ventas.
- Los indicadores de flujo (consultas recibidas, cierres) usan el período; los de situación
  actual (sin atender, en gestión, vencidos, sin respuesta) muestran el estado de hoy.
"""
from datetime import date, datetime, timedelta, timezone

from .business_v4 import (ESTADOS_ABIERTOS, ESTADOS_GESTION, canal_base, es_bajo_minimo, lote_minimo,
                          parse_dt)

PERIODOS = ('mes', 'semana', 'trimestre', 'todos')
HORAS_ALERTA = 24
DIAS_SIN_CONTACTO = 7


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


def load_cases(con, *, include_non_commercial=False) -> list[dict]:
    """Gestiones vigentes (no fusionadas) con canal de origen y estado de respuesta."""
    cases = {r['id']: dict(r) for r in con.execute("SELECT * FROM fichas_consulta WHERE estado_gestion<>'fusionada'")}
    for c in cases.values():
        c['mensajes'] = []
    for m in con.execute('SELECT * FROM bandeja_consultas WHERE ficha_id IS NOT NULL ORDER BY recibido_el,id'):
        if m['ficha_id'] in cases:
            cases[m['ficha_id']]['mensajes'].append(dict(m))
    contacts = {r['id']: dict(r) for r in con.execute('SELECT id,canal_origen FROM oportunidades')}
    now = _now()
    out = []
    for c in cases.values():
        if not include_non_commercial and c['tipo_consulta'] == 'no_comercial':
            continue
        incoming = [m for m in c['mensajes'] if m.get('direccion', 'entrante') != 'saliente']
        outgoing = [m for m in c['mensajes'] if m.get('direccion') == 'saliente']
        first_in = incoming[0] if incoming else None
        c['canal_origen'] = canal_base(first_in['canal']) if first_in else \
            canal_base((contacts.get(c['oportunidad_id']) or {}).get('canal_origen', '') or '')
        c['respuesta'] = response_status(incoming, outgoing, c['estado_gestion'], now)
        c['primera_respuesta_horas'] = None
        c['primera_respuesta_usuario'] = ''
        if first_in:
            t0 = parse_dt(first_in['recibido_el'])
            for o in outgoing:
                t1 = parse_dt(o['recibido_el'])
                if t0 and t1 and t1 >= t0:
                    c['primera_respuesta_horas'] = round((t1 - t0).total_seconds() / 3600, 1)
                    c['primera_respuesta_usuario'] = o.get('usuario') or ''
                    break
        out.append(c)
    return out


def response_status(incoming: list[dict], outgoing: list[dict], estado: str, now: datetime | None = None) -> dict:
    """¿El último mensaje del cliente está sin responder? Solo aplica a gestiones abiertas."""
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


def _match(c: dict, canal: str, responsable: str) -> bool:
    if canal != 'todos' and c['canal_origen'].casefold() != canal.casefold():
        return False
    if responsable and (c.get('responsable') or '').casefold() != responsable.casefold():
        return False
    return True


def filter_cases(cases, canal='todos', responsable=''):
    return [c for c in cases if _match(c, canal, responsable)]


def count_concretadas(cases, since_iso: str) -> int:
    return sum(1 for c in cases if c['estado_gestion'] == 'concretada' and (c['cerrada_en'] or c['actualizada_en'])[:10] >= since_iso)


def count_no_concretadas(cases, since_iso: str) -> int:
    return sum(1 for c in cases if c['estado_gestion'] == 'no_concretada' and (c['cerrada_en'] or c['actualizada_en'])[:10] >= since_iso)


def list_seguimientos_vencidos(con, responsable: str = '', now: datetime | None = None) -> list[dict]:
    """Seguimientos de agenda programados y vencidos (misma fuente que la Agenda)."""
    now = now or _now()
    rows = con.execute('''SELECT a.*, f.codigo AS ficha_codigo, COALESCE(o.cliente, f.cliente, '') AS cliente
                          FROM actividades_comerciales a
                          LEFT JOIN fichas_consulta f ON f.id=a.ficha_id
                          LEFT JOIN oportunidades o ON o.id=a.oportunidad_id
                          WHERE a.tipo='seguimiento' AND a.estado='programada' ORDER BY a.inicio''').fetchall()
    out = []
    for r in rows:
        start = parse_dt(r['inicio'])
        if not start or start > now:
            continue
        if responsable and (r['responsable'] or '').casefold() != responsable.casefold():
            continue
        out.append(dict(r))
    return out


def list_sin_respuesta(cases, horas: int = HORAS_ALERTA) -> list[dict]:
    rows = [c for c in cases if c['respuesta']['pendiente'] and c['respuesta']['horas'] >= horas]
    rows.sort(key=lambda c: -c['respuesta']['horas'])
    return [{'ficha_id': c['id'], 'codigo': c['codigo'], 'cliente': c['cliente'], 'horas': c['respuesta']['horas'],
             'responsable': c.get('responsable') or ''} for c in rows]


def contacts_without_contact(con, cases, responsable='') -> int:
    """Contactos con gestión abierta, sin seguimiento programado y +7 días sin contacto."""
    open_contacts = {c['oportunidad_id'] for c in cases if c['estado_gestion'] in ESTADOS_ABIERTOS and c['oportunidad_id']}
    limit = (date.today() - timedelta(days=DIAS_SIN_CONTACTO)).isoformat()
    count = 0
    for r in con.execute('SELECT * FROM oportunidades WHERE fusionada_con IS NULL'):
        if r['id'] not in open_contacts or r['fecha_seguimiento']:
            continue
        if responsable and (r['responsable'] or '').casefold() != responsable.casefold():
            continue
        if r['ultimo_contacto'] <= limit:
            count += 1
    return count


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def report_data(con, *, period='mes', canal='todos', responsable='', user=None) -> dict:
    today = date.today()
    since = period_since(period, today)
    since_iso = since.isoformat()
    role = user['role'] if user else 'administrador'
    responsible = (responsable or '').strip()
    if role == 'ventas':
        responsible = user['username']
    all_cases = load_cases(con)
    cases = filter_cases(all_cases, canal, responsible)
    case_ids = {c['id'] for c in cases}
    open_cases = [c for c in cases if c['estado_gestion'] in ESTADOS_ABIERTOS]

    # Mensajes entrantes del período (las respuestas registradas no son consultas).
    messages = []
    for c in cases:
        for m in c['mensajes']:
            if m.get('direccion', 'entrante') == 'saliente':
                continue
            if m['recibido_el'][:10] >= since_iso:
                messages.append(m)
    if not responsible:
        for m in con.execute("SELECT * FROM bandeja_consultas WHERE ficha_id IS NULL AND direccion<>'saliente'"):
            if m['recibido_el'][:10] >= since_iso and (canal == 'todos' or canal_base(m['canal']).casefold() == canal.casefold()):
                messages.append(dict(m))
    unread = sum(1 for c in cases for m in c['mensajes'] if m.get('direccion', 'entrante') != 'saliente' and not m['leido_en'])

    channel_counts = {key: sum(1 for m in messages if canal_base(m['canal']) == key) for key in ('WhatsApp', 'Correo', 'Formulario web')}
    product_counts = {}
    for c in cases:
        if (c['creada_en'] or '')[:10] >= since_iso:
            name = (c['producto'] or '').strip() or 'No especificado'
            product_counts[name] = product_counts.get(name, 0) + 1

    vencidos = list_seguimientos_vencidos(con, responsible)
    sin_respuesta = list_sin_respuesta(open_cases)
    minimo = lote_minimo(con)

    # Embudo por estado: gestiones creadas en el período.
    period_cases = [c for c in cases if (c['creada_en'] or '')[:10] >= since_iso]
    embudo = []
    for estado in ESTADOS_GESTION:
        if estado == 'resuelta':
            continue
        group = [c for c in period_cases if c['estado_gestion'] == estado]
        montos = {}
        for c in group:
            if c['cotizacion_monto'] is not None and c['cotizacion_moneda']:
                montos[c['cotizacion_moneda']] = round(montos.get(c['cotizacion_moneda'], 0) + c['cotizacion_monto'], 2)
        embudo.append({'estado': estado, 'cantidad': len(group), 'montos': montos})

    # Conversión: gestiones cerradas en el período.
    closed = [c for c in cases if c['estado_gestion'] in ('concretada', 'no_concretada')
              and (c['cerrada_en'] or c['actualizada_en'])[:10] >= since_iso]

    def conversion(key):
        groups = {}
        for c in closed:
            g = groups.setdefault(c[key] or 'sin_dato', {'concretadas': 0, 'no_concretadas': 0})
            g['concretadas' if c['estado_gestion'] == 'concretada' else 'no_concretadas'] += 1
        for g in groups.values():
            total = g['concretadas'] + g['no_concretadas']
            g['tasa'] = round(100 * g['concretadas'] / total) if total else None
        return groups

    motivos = {}
    for c in closed:
        if c['estado_gestion'] == 'no_concretada':
            motivo = (c['motivo_cierre'] or 'Sin motivo').strip() or 'Sin motivo'
            motivos[motivo] = motivos.get(motivo, 0) + 1

    # Tiempo de primera respuesta: gestiones cuyo primer mensaje entró en el período.
    first = [c for c in cases if c['mensajes'] and any(m.get('direccion', 'entrante') != 'saliente' for m in c['mensajes'])
             and next(m for m in c['mensajes'] if m.get('direccion', 'entrante') != 'saliente')['recibido_el'][:10] >= since_iso]
    by_channel, by_user = {}, {}
    for c in first:
        by_channel.setdefault(c['canal_origen'] or 'Sin dato', []).append(c['primera_respuesta_horas'])
        if c['primera_respuesta_horas'] is not None:
            by_user.setdefault(c['primera_respuesta_usuario'] or 'Sin usuario', []).append(c['primera_respuesta_horas'])
    tiempo = {
        'promedio_horas': _avg([c['primera_respuesta_horas'] for c in first]),
        'respondidas': sum(1 for c in first if c['primera_respuesta_horas'] is not None),
        'sin_respuesta_registrada': sum(1 for c in first if c['primera_respuesta_horas'] is None),
        'por_canal': {k: {'promedio_horas': _avg(v), 'gestiones': len(v)} for k, v in by_channel.items()},
        'por_vendedor': {k: {'promedio_horas': _avg(v), 'gestiones': len(v)} for k, v in by_user.items()},
    }

    return {
        'periodo': period, 'desde': since_iso, 'hasta': today.isoformat(), 'canal': canal,
        'responsable': responsible or 'Todos',
        'indicadores': {
            'consultas_recibidas': len(messages),
            'no_leidas': unread,
            'sin_atender': sum(1 for c in open_cases if c['estado_gestion'] == 'sin_atender'),
            'en_gestion': sum(1 for c in open_cases if c['estado_gestion'] != 'sin_atender'),
            'contactos_activos': len({c['oportunidad_id'] for c in open_cases if c['oportunidad_id']}),
            'concretadas': count_concretadas(cases, since_iso),
            'no_concretadas': count_no_concretadas(cases, since_iso),
            'seguimientos_vencidos': len(vencidos),
            'sin_respuesta_24h': len(sin_respuesta),
            'sin_contacto_7_dias': contacts_without_contact(con, cases, responsible),
            'bajo_minimo_abiertas': sum(1 for c in open_cases if es_bajo_minimo(c['tipo_consulta'], c['cantidad'], minimo)),
        },
        'canales': channel_counts,
        'productos_consultados': sorted(product_counts.items(), key=lambda x: -x[1])[:12],
        'embudo': embudo,
        'conversion_por_tipo': conversion('tipo_consulta'),
        'conversion_por_canal': conversion('canal_origen'),
        'motivos_no_concretadas': motivos,
        'tiempo_primera_respuesta': tiempo,
        'alertas_sin_respuesta': sin_respuesta[:20],
        'seguimientos_vencidos_detalle': [{'id': v['id'], 'titulo': v['titulo'], 'inicio': v['inicio'],
                                           'cliente': v['cliente'], 'ficha_codigo': v['ficha_codigo']} for v in vencidos[:20]],
        'gestiones_consideradas': len(case_ids),
        'origen_datos': ('Registros actuales de Impulso. Consultas recibidas y cierres usan el período elegido; '
                         'sin atender, en gestión, vencidos y sin respuesta muestran la situación de hoy. '
                         'Las gestiones no comerciales o fusionadas no se cuentan. Los mensajes externos no se '
                         'reciben automáticamente; el tiempo de respuesta se mide con las respuestas registradas en Impulso.'),
    }
