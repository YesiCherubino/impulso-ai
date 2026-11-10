"""V4: mejoras comerciales para Pasmanter.

- Contexto completo para la IA (todos los mensajes de la gestión + datos de la ficha).
- Extracción determinística del formulario web.
- Fusión de gestiones y contactos duplicados (nunca borra datos).
- Pipeline único de estados, calificación, responsable, respuestas registradas y cotización.

Todas las migraciones son aditivas e idempotentes.
"""
import json
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .db import connect
from .business_v2 import current, stamp

# ---------------------------------------------------------------------------
# Constantes del pipeline
# ---------------------------------------------------------------------------
ESTADOS_ABIERTOS = ('sin_atender', 'calificada', 'cotizada', 'muestra_piloto')
ESTADOS_CERRADOS = ('concretada', 'no_concretada', 'resuelta')
ESTADOS_INACTIVOS = ESTADOS_CERRADOS + ('fusionada',)
ESTADOS_GESTION = ESTADOS_ABIERTOS + ESTADOS_CERRADOS
MOTIVOS_NO_CONCRETADA = ('Precio', 'Volumen bajo el mínimo', 'Plazo', 'Sin respuesta del cliente',
                         'Eligió otro proveedor', 'Otro')
TIPOS_CON_LOTE_MINIMO = ('fabricacion_terceros', 'produccion_terceros', 'elaboracion_envasado')
TIPOS_PRODUCCION = ('fabricacion_terceros', 'produccion_terceros', 'desarrollo_formula', 'elaboracion_envasado')
LOTE_MINIMO_DEFAULT = 10000
# Equivalencias del estado anterior "En gestión" y de la etapa del contacto (dato histórico).
ESTADO_LEGACY = {'en_gestion': 'calificada'}
ESTADO_CONTACTO_A_GESTION = {'nueva': 'sin_atender', 'contactada': 'calificada', 'cotizada': 'cotizada',
                             'negociacion': 'cotizada', 'ganada': 'concretada', 'perdida': 'no_concretada'}

TipoConsultaV4 = Literal['sin_clasificar', 'fabricacion_terceros', 'produccion_terceros', 'otros_servicios', 'desarrollo_formula', 'elaboracion_envasado',
                         'mayorista', 'exportacion', 'no_comercial', 'otro']
SiNo = Literal['si', 'no', 'sin_especificar']

# Campos de la ficha que la IA puede completar. Los que figuran en campos_editados_json
# (editados por una persona o tomados del formulario web) nunca se pisan.
CAMPOS_IA = ('producto', 'cantidad', 'presentacion', 'tipo_consulta', 'formula', 'marca_registrada',
             'registro_anmat', 'destino', 'pais_destino', 'plazo_deseado', 'localidad', 'packaging')

V4_FICHA_COLUMNS = {
    'formula': "TEXT NOT NULL DEFAULT 'sin_especificar'",
    'marca_registrada': "TEXT NOT NULL DEFAULT 'sin_especificar'",
    'registro_anmat': "TEXT NOT NULL DEFAULT 'sin_especificar'",
    'destino': "TEXT NOT NULL DEFAULT ''",
    'pais_destino': "TEXT NOT NULL DEFAULT ''",
    'plazo_deseado': "TEXT NOT NULL DEFAULT ''",
    'localidad': "TEXT NOT NULL DEFAULT ''",
    'responsable': "TEXT NOT NULL DEFAULT ''",
    'cotizacion_monto': 'REAL',
    'cotizacion_moneda': "TEXT NOT NULL DEFAULT ''",
    'cotizacion_fecha': 'TEXT',
    'cotizacion_validez_dias': 'INTEGER',
    'fusionada_en': 'INTEGER',
    'tipo_sugerido_ia': 'INTEGER NOT NULL DEFAULT 0',
    'campos_editados_json': "TEXT NOT NULL DEFAULT '[]'",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def norm_name(value: str) -> str:
    """Nombre de empresa normalizado: minúsculas, sin acentos ni signos."""
    text = unicodedata.normalize('NFKD', value or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def canal_base(canal: str) -> str:
    canal = canal or ''
    return 'WhatsApp' if canal.startswith('WhatsApp') else canal


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(value[:10])
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def lote_minimo(con) -> int:
    try:
        row = con.execute('SELECT lote_minimo FROM configuracion_comercial WHERE id=1').fetchone()
        if row and row['lote_minimo']:
            return int(row['lote_minimo'])
    except Exception:
        pass
    try:
        return int(os.getenv('LOTE_MINIMO_TERCEROS', LOTE_MINIMO_DEFAULT))
    except ValueError:
        return LOTE_MINIMO_DEFAULT


def es_bajo_minimo(tipo: str, cantidad, minimo: int) -> bool:
    return tipo in TIPOS_CON_LOTE_MINIMO and cantidad is not None and int(cantidad) < minimo


def _filled(value) -> bool:
    return value not in (None, '', 'sin_especificar', 'sin_clasificar')


def datos_a_confirmar(ficha: dict) -> list[str]:
    """Lista base de datos pendientes: sale de los campos vacíos de la ficha, no de la IA."""
    tipo = ficha.get('tipo_consulta') or 'sin_clasificar'
    if tipo == 'no_comercial':
        return []
    missing = []
    if tipo == 'sin_clasificar':
        missing.append('Tipo de servicio')
    checks = [('producto', 'Producto'), ('cantidad', 'Cantidad estimada'), ('presentacion', 'Presentación (ml/g)')]
    if tipo in TIPOS_PRODUCCION or tipo in ('sin_clasificar', 'otro'):
        checks += [('formula', '¿Fórmula propia o desarrollo de Pasmanter?'), ('packaging', 'Packaging'),
                   ('marca_registrada', '¿Tiene marca registrada?'), ('registro_anmat', 'Registro ANMAT')]
    checks += [('destino', 'Destino (mercado local o exportación)')]
    if ficha.get('destino') == 'exportacion' or tipo == 'exportacion':
        checks += [('pais_destino', 'País de destino')]
    checks += [('plazo_deseado', 'Plazo deseado')]
    for key, label in checks:
        if not _filled(ficha.get(key)):
            missing.append(label)
    return missing


def ficha_extras(row, minimo: int) -> dict:
    data = dict(row)
    try:
        editados = json.loads(data.get('campos_editados_json') or '[]')
    except ValueError:
        editados = []
    return {
        'bajo_minimo': es_bajo_minimo(data.get('tipo_consulta', ''), data.get('cantidad'), minimo),
        'lote_minimo': minimo,
        'datos_a_confirmar': datos_a_confirmar(data),
        'campos_editados': editados,
    }


# ---------------------------------------------------------------------------
# Formulario web: extracción determinística (sin IA)
# ---------------------------------------------------------------------------
FORM_PATTERNS = {
    'producto': re.compile(r'Producto\s*:\s*([^.\n]+?)\s*(?:\.\s|\.$|\n|$)', re.I),
    'cantidad': re.compile(r'Cantidad(?:\s+estimada)?\s*:\s*([\d.\s]+)\s*(?:unidades|u\.?)?', re.I),
    'localidad': re.compile(r'Localidad\s*:\s*([^.\n]+?)\s*(?:\.\s|\.$|\n|$)', re.I),
}


def parse_form_text(texto: str) -> dict:
    out = {}
    for key, pattern in FORM_PATTERNS.items():
        match = pattern.search(texto or '')
        if not match:
            continue
        value = match.group(1).strip()
        if key == 'cantidad':
            digits = re.sub(r'[^0-9]', '', value)
            if digits:
                out['cantidad'] = int(digits)
        elif value:
            out[key] = value[:150]
    return out


def apply_form_fields(con, message_id: int) -> dict:
    """Vuelca producto, cantidad y localidad del formulario en la ficha si están vacíos."""
    msg = con.execute('SELECT id,canal,texto,ficha_id FROM bandeja_consultas WHERE id=?', (message_id,)).fetchone()
    if not msg or msg['canal'] != 'Formulario web' or not msg['ficha_id']:
        return {}
    parsed = parse_form_text(msg['texto'])
    if not parsed:
        return {}
    ficha = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (msg['ficha_id'],)).fetchone()
    if not ficha:
        return {}
    editados = set(json.loads(ficha['campos_editados_json'] or '[]'))
    changes = {k: v for k, v in parsed.items() if not _filled(ficha[k])}
    if not changes:
        return {}
    editados.update(changes)
    sets = ', '.join(f'{k}=?' for k in changes)
    con.execute(f'UPDATE fichas_consulta SET {sets}, campos_editados_json=?, actualizada_en=? WHERE id=?',
                (*changes.values(), json.dumps(sorted(editados)), stamp(), ficha['id']))
    return changes


# ---------------------------------------------------------------------------
# Contexto para la IA
# ---------------------------------------------------------------------------
ETIQUETAS_FICHA = [
    ('producto', 'Producto'), ('cantidad', 'Cantidad (unidades)'), ('presentacion', 'Presentación'),
    ('tipo_consulta', 'Tipo de servicio'), ('formula', 'Fórmula'), ('packaging', 'Packaging'),
    ('marca_registrada', 'Marca registrada'), ('registro_anmat', 'Registro ANMAT'), ('destino', 'Destino'),
    ('pais_destino', 'País de destino'), ('plazo_deseado', 'Plazo deseado'), ('localidad', 'Localidad'),
]


def build_case_context(con, ficha_id: int, focus_message_id: int | None = None,
                       informar_lote_minimo: bool = False) -> str:
    ficha = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
    if not ficha:
        return ''
    lines = ['DATOS YA REGISTRADOS EN LA FICHA (informados por el cliente o confirmados por el vendedor; '
             'NO volver a preguntarlos):']
    known = 0
    for key, label in ETIQUETAS_FICHA:
        if _filled(ficha[key]):
            lines.append(f'- {label}: {ficha[key]}')
            known += 1
    if not known:
        lines.append('- (sin datos registrados todavía)')
    lines += ['', 'CONVERSACIÓN COMPLETA DE LA GESTIÓN (orden cronológico):']
    rows = con.execute('''SELECT * FROM bandeja_consultas WHERE ficha_id=? ORDER BY recibido_el,id''',
                       (ficha_id,)).fetchall()
    for m in rows:
        who = 'Pasmanter (respuesta ya enviada)' if m['direccion'] == 'saliente' else f"Cliente ({m['contacto']})"
        subject = f" · Asunto: {m['asunto']}" if m['asunto'] else ''
        marker = ' ← MENSAJE A RESPONDER' if focus_message_id and m['id'] == focus_message_id else ''
        lines.append(f"[{m['recibido_el'][:16].replace('T', ' ')} · {canal_base(m['canal'])} · {who}{subject}]{marker}")
        lines.append(m['texto'])
    minimo = lote_minimo(con)
    if informar_lote_minimo and es_bajo_minimo(ficha['tipo_consulta'], ficha['cantidad'], minimo):
        lines += ['', f'INDICACIÓN DEL VENDEDOR: en la respuesta, informá con cortesía que el lote mínimo de '
                      f'producción es de {minimo:,} unidades y ofrecé conversar alternativas.'.replace(',', '.')]
    return '\n'.join(lines)


FALTANTES_CLAVES = {
    'cantidad': ('cantidad', 'unidades', 'volumen'),
    'producto': ('producto',),
    'presentacion': ('presentación', 'presentacion', 'tamaño', 'capacidad'),
    'formula': ('fórmula', 'formula'),
    'packaging': ('packaging', 'envase'),
    'marca_registrada': ('marca',),
    'registro_anmat': ('anmat',),
    'destino': ('destino', 'mercado'),
    'pais_destino': ('país', 'pais'),
    'plazo_deseado': ('plazo', 'entrega', 'fecha'),
    'localidad': ('localidad', 'ciudad', 'ubicación'),
}


def filtrar_faltantes(items: list[str], ficha: dict) -> list[str]:
    """Quita de la lista de la IA los datos que la ficha ya tiene cargados."""
    out = []
    for item in items or []:
        low = item.casefold()
        if any(_filled(ficha.get(field)) and any(k in low for k in keys)
               for field, keys in FALTANTES_CLAVES.items()):
            continue
        out.append(item)
    return out


def apply_analysis(con, ficha_id: int, result: dict, regenerar: bool) -> dict:
    """Completa la ficha con lo extraído por la IA sin pisar datos editados a mano o del formulario.

    Devuelve el resultado corregido: la ficha es la fuente de verdad.
    """
    ficha = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
    if not ficha:
        return result
    editados = set(json.loads(ficha['campos_editados_json'] or '[]'))
    formula = {'si': 'desarrollo_pasmanter', 'no': 'propia'}.get(result.get('necesita_formula', ''), '')
    proposed = {
        'producto': (result.get('producto') or '').strip(),
        'cantidad': result.get('cantidad'),
        'presentacion': (result.get('presentacion') or '').strip(),
        'tipo_consulta': result.get('tipo_consulta') or '',
        'formula': formula,
        'marca_registrada': result.get('marca_registrada') or '',
        'registro_anmat': result.get('registro_anmat') or '',
        'destino': result.get('destino') or '',
        'pais_destino': (result.get('pais_destino') or '').strip(),
        'plazo_deseado': (result.get('plazo_deseado') or '').strip(),
        'localidad': (result.get('localidad') or '').strip(),
    }
    changes = {}
    for key, value in proposed.items():
        if not _filled(value) or key in editados:
            continue
        if not _filled(ficha[key]) or (regenerar and ficha[key] != value):
            changes[key] = value
    if not _filled(ficha['resumen']) and result.get('resumen'):
        changes['resumen'] = result['resumen'][:2000]
    if changes:
        if 'tipo_consulta' in changes:
            changes['tipo_sugerido_ia'] = 1
        sets = ', '.join(f'{k}=?' for k in changes)
        con.execute(f'UPDATE fichas_consulta SET {sets}, actualizada_en=? WHERE id=?',
                    (*changes.values(), stamp(), ficha_id))
        ficha = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
    data = dict(ficha)
    fixed = dict(result)
    for key in ('producto', 'cantidad', 'presentacion', 'tipo_consulta'):
        if _filled(data.get(key)):
            fixed[key] = data[key]
    fixed['datos_faltantes'] = filtrar_faltantes(result.get('datos_faltantes') or [], data)
    fixed['datos_a_confirmar'] = datos_a_confirmar(data)
    return fixed


# ---------------------------------------------------------------------------
# Fusión
# ---------------------------------------------------------------------------
def _merge_checklist(a: str, b: str) -> str:
    try:
        first, second = json.loads(a or '[]'), json.loads(b or '[]')
    except ValueError:
        return a or '[]'
    seen = {str(x.get('text', x) if isinstance(x, dict) else x).casefold() for x in first}
    for item in second:
        key = str(item.get('text', item) if isinstance(item, dict) else item).casefold()
        if key not in seen:
            first.append(item)
            seen.add(key)
    return json.dumps(first, ensure_ascii=False)


def merge_contacts(con, origen_id: int, destino_id: int) -> None:
    """Une dos contactos comerciales. El de origen queda marcado, no se borra."""
    if origen_id == destino_id:
        return
    src = con.execute('SELECT * FROM oportunidades WHERE id=?', (origen_id,)).fetchone()
    dst = con.execute('SELECT * FROM oportunidades WHERE id=?', (destino_id,)).fetchone()
    if not src or not dst:
        raise HTTPException(404, 'Contacto no encontrado')
    for table in ('fichas_consulta', 'bandeja_consultas', 'interacciones', 'actividades_comerciales'):
        con.execute(f'UPDATE {table} SET oportunidad_id=? WHERE oportunidad_id=?', (destino_id, origen_id))
    fill = {}
    for key in ('email', 'telefono', 'responsable', 'presentacion', 'packaging'):
        if not dst[key] and src[key]:
            fill[key] = src[key]
    if dst['cantidad'] is None and src['cantidad'] is not None:
        fill['cantidad'] = src['cantidad']
    if src['ultimo_contacto'] > dst['ultimo_contacto']:
        fill['ultimo_contacto'] = src['ultimo_contacto']
    if fill:
        con.execute(f"UPDATE oportunidades SET {', '.join(k + '=?' for k in fill)} WHERE id=?",
                    (*fill.values(), destino_id))
    con.execute('UPDATE oportunidades SET fusionada_con=? WHERE id=?', (destino_id, origen_id))
    con.execute("INSERT INTO interacciones (oportunidad_id,tipo,descripcion,fecha) VALUES (?, 'nota', ?, ?)",
                (destino_id, f"Se unificó el contacto duplicado #{origen_id} ({src['cliente']}).",
                 date.today().isoformat()))


def merge_fichas(con, origen_id: int, destino_id: int) -> dict:
    """Mueve mensajes, actividades, checklists y remitentes al destino. No borra nada."""
    if origen_id == destino_id:
        raise HTTPException(422, 'La gestión de origen y la de destino son la misma')
    src = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (origen_id,)).fetchone()
    dst = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (destino_id,)).fetchone()
    if not src or not dst:
        raise HTTPException(404, 'Gestión no encontrada')
    if src['estado_gestion'] == 'fusionada' or dst['estado_gestion'] == 'fusionada':
        raise HTTPException(409, 'Una de las gestiones ya fue fusionada')
    con.execute('UPDATE bandeja_consultas SET ficha_id=? WHERE ficha_id=?', (destino_id, origen_id))
    con.execute('UPDATE actividades_comerciales SET ficha_id=? WHERE ficha_id=?', (destino_id, origen_id))
    con.execute('UPDATE remitentes_gestiones SET ficha_id=? WHERE ficha_id=?', (destino_id, origen_id))
    fill = {}
    for key in ('producto', 'presentacion', 'packaging', 'resumen', 'formula', 'marca_registrada',
                'registro_anmat', 'destino', 'pais_destino', 'plazo_deseado', 'localidad', 'responsable',
                'cotizacion_moneda'):
        if not _filled(dst[key]) and _filled(src[key]):
            fill[key] = src[key]
    for key in ('cantidad', 'cotizacion_monto', 'cotizacion_fecha', 'cotizacion_validez_dias'):
        if dst[key] is None and src[key] is not None:
            fill[key] = src[key]
    if dst['tipo_consulta'] == 'sin_clasificar' and src['tipo_consulta'] != 'sin_clasificar':
        fill['tipo_consulta'] = src['tipo_consulta']
        fill['tipo_sugerido_ia'] = src['tipo_sugerido_ia']
    editados = sorted(set(json.loads(dst['campos_editados_json'] or '[]')) |
                      {k for k in json.loads(src['campos_editados_json'] or '[]') if k in fill})
    fill['campos_editados_json'] = json.dumps(editados)
    for col in ('requisitos_check_json', 'faltantes_check_json', 'requisitos_json', 'datos_faltantes_json'):
        fill[col] = _merge_checklist(dst[col], src[col])
    if dst['oportunidad_id'] is None and src['oportunidad_id'] is not None:
        fill['oportunidad_id'] = src['oportunidad_id']
    fill['actualizada_en'] = stamp()
    con.execute(f"UPDATE fichas_consulta SET {', '.join(k + '=?' for k in fill)} WHERE id=?",
                (*fill.values(), destino_id))
    dst_opp = fill.get('oportunidad_id', dst['oportunidad_id'])
    if dst_opp is not None:
        con.execute('UPDATE bandeja_consultas SET oportunidad_id=? WHERE ficha_id=?', (dst_opp, destino_id))
    if src['oportunidad_id'] and dst_opp and src['oportunidad_id'] != dst_opp:
        merge_contacts(con, src['oportunidad_id'], dst_opp)
    con.execute('''UPDATE fichas_consulta SET estado_gestion='fusionada', fusionada_en=?, cerrada_en=?,
                   motivo_cierre=?, actualizada_en=? WHERE id=?''',
                (destino_id, stamp(), f"Fusionada en {dst['codigo']}", stamp(), origen_id))
    from .escala import refresh_case_stats
    refresh_case_stats(con, [origen_id, destino_id])
    return {'origen': src['codigo'], 'destino': dst['codigo'], 'destino_id': destino_id}


def duplicate_candidates(con, ficha_id: int) -> list[dict]:
    """Otras gestiones abiertas de la misma empresa (nombre normalizado o mismo contacto)."""
    me = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
    if not me:
        return []
    key = norm_name(me['cliente'])
    rows = con.execute(f'''SELECT f.id,f.codigo,f.titulo,f.cliente,f.producto,f.estado_gestion,f.oportunidad_id,
                (SELECT COUNT(*) FROM bandeja_consultas b WHERE b.ficha_id=f.id) AS mensajes
                FROM fichas_consulta f WHERE f.id<>? AND f.estado_gestion IN ({','.join('?' * len(ESTADOS_ABIERTOS))})''',
                       (ficha_id, *ESTADOS_ABIERTOS)).fetchall()
    return [dict(r) for r in rows
            if (key and norm_name(r['cliente']) == key) or
            (me['oportunidad_id'] and r['oportunidad_id'] == me['oportunidad_id'])]


def plan_case_merges(con) -> list[tuple[dict, dict]]:
    """Gestiones ABIERTAS de la misma empresa (nombre normalizado): quedan en la que tiene contacto y más mensajes."""
    marks = ','.join('?' * len(ESTADOS_ABIERTOS))
    rows = con.execute(f'''SELECT f.id,f.codigo,f.cliente,f.oportunidad_id,
                (SELECT COUNT(*) FROM bandeja_consultas b WHERE b.ficha_id=f.id) AS mensajes
                FROM fichas_consulta f WHERE f.estado_gestion IN ({marks}) ORDER BY f.id''', ESTADOS_ABIERTOS).fetchall()
    groups = {}
    for r in rows:
        groups.setdefault(norm_name(r['cliente']), []).append(dict(r))
    plan = []
    for items in groups.values():
        if len(items) > 1:
            items.sort(key=lambda f: (f['oportunidad_id'] is None, -f['mensajes'], f['id']))
            plan += [(f, items[0]) for f in items[1:]]
    return plan


def plan_contact_merges(con) -> list[tuple[dict, dict]]:
    """Contactos de la misma empresa: quedan en el que tiene más gestiones."""
    rows = con.execute('''SELECT o.id,o.cliente,(SELECT COUNT(*) FROM fichas_consulta f WHERE f.oportunidad_id=o.id) AS gestiones
                          FROM oportunidades o WHERE o.fusionada_con IS NULL ORDER BY o.id''').fetchall()
    groups = {}
    for r in rows:
        groups.setdefault(norm_name(r['cliente']), []).append(dict(r))
    plan = []
    for items in groups.values():
        if len(items) > 1:
            items.sort(key=lambda r: (-r['gestiones'], r['id']))
            plan += [(r, items[0]) for r in items[1:]]
    return plan


def apply_merge_plan(con) -> dict:
    """Unifica gestiones abiertas y contactos duplicados. Idempotente; no borra datos."""
    cases = plan_case_merges(con)
    for src, dst in cases:
        merge_fichas(con, src['id'], dst['id'])
    contacts = plan_contact_merges(con)
    for src, dst in contacts:
        merge_contacts(con, src['id'], dst['id'])
    return {'gestiones_fusionadas': len(cases), 'contactos_unificados': len(contacts)}


# ---------------------------------------------------------------------------
# Seguimientos programados ↔ agenda
# ---------------------------------------------------------------------------
def sync_contact_followup(con, opportunity_id: int, due: str | None, reason: str, cliente: str) -> None:
    """Un seguimiento programado del contacto es una actividad de agenda (una sola fuente)."""
    row = con.execute('''SELECT id FROM actividades_comerciales WHERE oportunidad_id=? AND origen='seguimiento_contacto'
                         AND estado='programada' ORDER BY id DESC LIMIT 1''', (opportunity_id,)).fetchone()
    if not due:
        if row:
            con.execute("UPDATE actividades_comerciales SET estado='cancelada', actualizada_en=? WHERE id=?",
                        (stamp(), row['id']))
        return
    ficha = con.execute(f'''SELECT id,responsable FROM fichas_consulta WHERE oportunidad_id=? AND estado_gestion IN
                ({','.join('?' * len(ESTADOS_ABIERTOS))}) ORDER BY actualizada_en DESC LIMIT 1''',
                        (opportunity_id, *ESTADOS_ABIERTOS)).fetchone()
    opp = con.execute('SELECT responsable FROM oportunidades WHERE id=?', (opportunity_id,)).fetchone()
    owner = (ficha['responsable'] if ficha else '') or (opp['responsable'] if opp else '')
    start = f'{due}T12:00:00+00:00'
    title = f'Seguimiento · {cliente}'
    if row:
        con.execute('''UPDATE actividades_comerciales SET inicio=?, titulo=?, notas=?, ficha_id=COALESCE(ficha_id,?),
                       actualizada_en=? WHERE id=?''', (start, title, reason, ficha['id'] if ficha else None,
                                                        stamp(), row['id']))
    else:
        con.execute('''INSERT INTO actividades_comerciales(ficha_id,oportunidad_id,titulo,tipo,inicio,responsable,notas,
                       estado,creada_en,actualizada_en,origen) VALUES (?,?,?,?,?,?,?,'programada',?,?,'seguimiento_contacto')''',
                    (ficha['id'] if ficha else None, opportunity_id, title, 'seguimiento', start, owner, reason,
                     stamp(), stamp()))


def complete_contact_followup(con, opportunity_id: int) -> None:
    con.execute('''UPDATE actividades_comerciales SET estado='realizada', actualizada_en=?
                   WHERE oportunidad_id=? AND origen='seguimiento_contacto' AND estado='programada' ''',
                (stamp(), opportunity_id))


# ---------------------------------------------------------------------------
# Migración
# ---------------------------------------------------------------------------
def create_case_for_contact(con, opp) -> int:
    estado = ESTADO_CONTACTO_A_GESTION.get(opp['estado'], 'sin_atender')
    created = opp['creada_el'] or date.today().isoformat()
    closed = estado in ESTADOS_CERRADOS
    cur = con.execute('''INSERT INTO fichas_consulta (codigo,oportunidad_id,titulo,cliente,contacto,producto,cantidad,
             tipo_consulta,presentacion,packaging,responsable,estado_gestion,cerrada_en,motivo_cierre,
             cotizacion_monto,cotizacion_moneda,cotizacion_fecha,creada_en,actualizada_en)
             VALUES ('PENDIENTE',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (opp['id'], f"Gestión de {opp['cliente']}", opp['cliente'], opp['contacto'],
                       opp['producto'] if opp['producto'] != 'Sin especificar' else '', opp['cantidad'],
                       opp['tipo_consulta'], opp['presentacion'], opp['packaging'], opp['responsable'], estado,
                       (opp['fecha_cierre'] or opp['ultimo_contacto']) if closed else None,
                       'Otro' if estado == 'no_concretada' else '',
                       opp['monto_estimado_usd'] if estado == 'cotizada' else None,
                       'USD' if estado == 'cotizada' and opp['monto_estimado_usd'] is not None else '',
                       opp['ultimo_contacto'] if estado == 'cotizada' else None, created, created))
    code = f'CON-{created[:4]}-{cur.lastrowid:05d}'
    con.execute('UPDATE fichas_consulta SET codigo=? WHERE id=?', (code, cur.lastrowid))
    return cur.lastrowid


def init_v4(db_path: Path) -> None:
    with connect(db_path) as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS configuracion_comercial (
          id INTEGER PRIMARY KEY CHECK(id = 1),
          lote_minimo INTEGER NOT NULL DEFAULT 10000
        );
        INSERT OR IGNORE INTO configuracion_comercial(id) VALUES (1);
        ''')
        cols = {r['name'] for r in con.execute('PRAGMA table_info(fichas_consulta)')}
        for col, sql in V4_FICHA_COLUMNS.items():
            if col not in cols:
                con.execute(f'ALTER TABLE fichas_consulta ADD COLUMN {col} {sql}')
        inbox = {r['name'] for r in con.execute('PRAGMA table_info(bandeja_consultas)')}
        if 'direccion' not in inbox:
            con.execute("ALTER TABLE bandeja_consultas ADD COLUMN direccion TEXT NOT NULL DEFAULT 'entrante'")
        if 'usuario' not in inbox:
            con.execute("ALTER TABLE bandeja_consultas ADD COLUMN usuario TEXT NOT NULL DEFAULT ''")
        opps = {r['name'] for r in con.execute('PRAGMA table_info(oportunidades)')}
        if 'fusionada_con' not in opps:
            con.execute('ALTER TABLE oportunidades ADD COLUMN fusionada_con INTEGER')
        acts = {r['name'] for r in con.execute('PRAGMA table_info(actividades_comerciales)')}
        if 'origen' not in acts:
            con.execute("ALTER TABLE actividades_comerciales ADD COLUMN origen TEXT NOT NULL DEFAULT ''")
        con.execute('CREATE INDEX IF NOT EXISTS idx_fichas_estado ON fichas_consulta(estado_gestion)')
        # Pipeline único: "En gestión" pasa a "Calificada".
        con.execute("UPDATE fichas_consulta SET estado_gestion='calificada' WHERE estado_gestion='en_gestion'")
        # Contactos sin gestión (históricos): se les crea una, con el estado equivalente, para que entren al
        # pipeline y para que Reportes y Finalizados coincidan.
        # Los clientes importados desde Tango no generan gestión: solo la tienen cuando escriben.
        imported = "AND o.importado_en IS NULL" if 'importado_en' in opps else ''
        legacy = con.execute(f'''SELECT * FROM oportunidades o WHERE o.fusionada_con IS NULL {imported}
                 AND NOT EXISTS (SELECT 1 FROM fichas_consulta f WHERE f.oportunidad_id=o.id)''').fetchall()
        for opp in legacy:
            create_case_for_contact(con, opp)
        # El responsable del contacto pasa a la gestión si esta no tiene uno.
        con.execute('''UPDATE fichas_consulta SET responsable=(SELECT o.responsable FROM oportunidades o WHERE o.id=fichas_consulta.oportunidad_id)
                       WHERE responsable='' AND oportunidad_id IS NOT NULL
                       AND COALESCE((SELECT o.responsable FROM oportunidades o WHERE o.id=fichas_consulta.oportunidad_id),'')<>'' ''')
        # Formulario web: datos estructurados a la ficha (solo campos vacíos).
        for row in con.execute("SELECT id FROM bandeja_consultas WHERE canal='Formulario web' AND ficha_id IS NOT NULL").fetchall():
            apply_form_fields(con, row['id'])
        # Seguimientos programados existentes → agenda.
        for opp in con.execute('''SELECT o.id,o.cliente,o.fecha_seguimiento,o.motivo_seguimiento FROM oportunidades o
                 WHERE o.fecha_seguimiento IS NOT NULL AND o.estado NOT IN ('ganada','perdida') AND o.fusionada_con IS NULL
                 AND NOT EXISTS (SELECT 1 FROM actividades_comerciales a WHERE a.oportunidad_id=o.id
                                 AND a.origen='seguimiento_contacto')''').fetchall():
            sync_contact_followup(con, opp['id'], opp['fecha_seguimiento'], opp['motivo_seguimiento'], opp['cliente'])
        # Datos resumidos por gestión e índices (escalabilidad).
        from .escala import init_escala
        init_escala(con)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
class MergeInput(BaseModel):
    destino_id: int


class OwnerInput(BaseModel):
    responsable: str = Field(default='', max_length=60)


class ReplyInput(BaseModel):
    texto: str = Field(min_length=1, max_length=7000)
    canal: Literal['WhatsApp', 'Correo'] = 'WhatsApp'
    adjuntos: list[int] = Field(default_factory=list, max_length=10)


class CommercialSettings(BaseModel):
    lote_minimo: int = Field(ge=1, le=10_000_000)


def _not_readonly(request: Request, db_path: Path, perm: str = 'gestionar'):
    from .permisos import require
    return require(db_path, current(request, db_path), perm)


def register_business_v4(app: FastAPI, db_path: Path):
    @app.get('/api/commercial/settings')
    def get_commercial_settings(request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            return {'lote_minimo': lote_minimo(con), 'motivos_no_concretada': list(MOTIVOS_NO_CONCRETADA)}

    @app.post('/api/commercial/settings')
    def save_commercial_settings(request: Request, payload: CommercialSettings):
        current(request, db_path, 'administrador')
        with connect(db_path) as con:
            con.execute('UPDATE configuracion_comercial SET lote_minimo=? WHERE id=1', (payload.lote_minimo,))
        return {'lote_minimo': payload.lote_minimo}

    @app.get('/api/users/responsables')
    def responsables(request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            try:
                rows = con.execute('''SELECT usuario AS username,nombre AS name,rol AS role FROM usuarios
                                      WHERE activo=1 AND rol IN ('ventas','administrador') ORDER BY nombre''').fetchall()
            except Exception:
                rows = []
            return [dict(r) for r in rows]

    @app.post('/api/fichas/{ficha_id}/merge')
    def merge(ficha_id: int, request: Request, payload: MergeInput):
        _not_readonly(request, db_path)
        with connect(db_path) as con:
            con.execute('BEGIN IMMEDIATE')
            return merge_fichas(con, ficha_id, payload.destino_id)

    @app.get('/api/fichas/{ficha_id}/duplicates')
    def duplicates(ficha_id: int, request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            return duplicate_candidates(con, ficha_id)

    @app.post('/api/fichas/{ficha_id}/responsable')
    def set_owner(ficha_id: int, request: Request, payload: OwnerInput):
        user = _not_readonly(request, db_path, 'asignar')
        # Cualquier vendedor puede tomar, liberar o pasarle una gestión a un compañero (por ejemplo, si está ausente).
        owner = payload.responsable.strip().casefold()
        with connect(db_path) as con:
            row = con.execute('SELECT responsable FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Gestión no encontrada')
            if owner and not con.execute('SELECT 1 FROM usuarios WHERE usuario=? AND activo=1', (owner,)).fetchone() and user:
                raise HTTPException(422, 'Usuario no encontrado')
            con.execute('UPDATE fichas_consulta SET responsable=?, actualizada_en=? WHERE id=?', (owner, stamp(), ficha_id))
            if owner != row['responsable']:
                from .historial import log
                log(con, ficha_id, 'responsable', owner, row['responsable'], user['username'] if user else '')
            if user and owner != row['responsable']:
                from .equipo import notify_assignment
                notify_assignment(con, ficha_id, owner, user['username'])
            return {'id': ficha_id, 'responsable': owner}

    class DeshacerNoComercial(BaseModel):
        tipo_consulta: TipoConsultaV4 = 'sin_clasificar'
        estado_gestion: Literal['sin_atender', 'calificada', 'cotizada', 'muestra_piloto'] = 'sin_atender'

    @app.post('/api/fichas/{ficha_id}/no-comercial/deshacer')
    def undo_non_commercial(ficha_id: int, request: Request, payload: DeshacerNoComercial):
        user = _not_readonly(request, db_path)
        with connect(db_path) as con:
            if not con.execute('SELECT 1 FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone():
                raise HTTPException(404, 'Gestión no encontrada')
            con.execute('''UPDATE fichas_consulta SET tipo_consulta=?, estado_gestion=?, cerrada_en=NULL, motivo_cierre='', actualizada_en=?
                           WHERE id=?''', (payload.tipo_consulta, payload.estado_gestion, stamp(), ficha_id))
            from .historial import log
            log(con, ficha_id, 'estado', payload.estado_gestion, 'Se deshizo el archivo', user['username'] if user else '')
            return {'id': ficha_id}

    @app.post('/api/fichas/{ficha_id}/no-comercial')
    def archive_non_commercial(ficha_id: int, request: Request):
        _not_readonly(request, db_path)
        with connect(db_path) as con:
            row = con.execute('SELECT campos_editados_json FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Gestión no encontrada')
            editados = sorted(set(json.loads(row['campos_editados_json'] or '[]')) | {'tipo_consulta'})
            con.execute('''UPDATE fichas_consulta SET tipo_consulta='no_comercial', tipo_sugerido_ia=0, estado_gestion='resuelta',
                           cerrada_en=?, motivo_cierre='Consulta no comercial', campos_editados_json=?, actualizada_en=? WHERE id=?''',
                        (stamp(), json.dumps(editados), stamp(), ficha_id))
            from .historial import log
            log(con, ficha_id, 'estado', 'resuelta', 'No comercial', '')
            return {'id': ficha_id, 'estado': 'resuelta', 'tipo_consulta': 'no_comercial'}

    @app.post('/api/inbox/{message_id}/reply', status_code=201)
    def register_reply(message_id: int, request: Request, payload: ReplyInput):
        """Registra una respuesta enviada fuera de Impulso (copiada y pegada). No envía nada."""
        user = _not_readonly(request, db_path, 'responder')
        with connect(db_path) as con:
            con.execute('BEGIN IMMEDIATE')
            msg = con.execute('SELECT * FROM bandeja_consultas WHERE id=?', (message_id,)).fetchone()
            if not msg:
                raise HTTPException(404, 'Mensaje no encontrado')
            # Misma precisión (segundos) que los mensajes entrantes, para comparar fechas como texto.
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            cur = con.execute('''INSERT INTO bandeja_consultas (cliente,contacto,canal,texto,recibido_el,estado,leido_en,
                     email_remitente,telefono_remitente,asunto,ficha_id,oportunidad_id,direccion,usuario)
                     VALUES (?,?,?,?,?,'resuelta',?,?,?,?,?,?,'saliente',?)''',
                              (msg['cliente'], msg['contacto'], payload.canal, payload.texto.strip(), now, now,
                               msg['email_remitente'], msg['telefono_remitente'],
                               ('Re: ' + msg['asunto']) if msg['asunto'] and payload.canal == 'Correo' else '',
                               msg['ficha_id'], msg['oportunidad_id'], user['username'] if user else ''))
            # Los mensajes del cliente hasta ahora quedan respondidos.
            if msg['ficha_id']:
                con.execute('''UPDATE bandeja_consultas SET estado='resuelta', leido_en=COALESCE(leido_en,?)
                               WHERE ficha_id=? AND direccion='entrante' AND recibido_el<=?''', (now, msg['ficha_id'], now))
                con.execute('UPDATE fichas_consulta SET actualizada_en=? WHERE id=?', (now, msg['ficha_id']))
                # Quien responde una consulta libre queda como responsable (se puede cambiar después).
                if user:
                    con.execute("UPDATE fichas_consulta SET responsable=? WHERE id=? AND responsable=''", (user['username'], msg['ficha_id']))
            else:
                con.execute("UPDATE bandeja_consultas SET estado='resuelta' WHERE id=?", (message_id,))
            opp_id = msg['oportunidad_id']
            if not opp_id and msg['ficha_id']:
                f = con.execute('SELECT oportunidad_id FROM fichas_consulta WHERE id=?', (msg['ficha_id'],)).fetchone()
                opp_id = f['oportunidad_id'] if f else None
            if opp_id:
                today = date.today().isoformat()
                con.execute("UPDATE oportunidades SET ultimo_contacto=? WHERE id=? AND ultimo_contacto<?", (today, opp_id, today))
                con.execute("INSERT INTO interacciones (oportunidad_id,tipo,descripcion,fecha) VALUES (?,?,?,?)",
                            (opp_id, 'correo' if payload.canal == 'Correo' else 'nota',
                             f'Respuesta registrada por {payload.canal}: {payload.texto.strip()[:300]}', today))
            if payload.adjuntos:
                marks = ','.join('?' * len(payload.adjuntos))
                docs = [{'id': d['id'], 'nombre': d['nombre'], 'mime': d['mime'], 'tamano': d['tamano']} for d in con.execute(
                    f'SELECT id,nombre,mime,tamano FROM documentos WHERE id IN ({marks})', payload.adjuntos)]
                con.execute('UPDATE bandeja_consultas SET adjuntos_json=? WHERE id=?', (json.dumps(docs, ensure_ascii=False), cur.lastrowid))
            from .escala import touch_messages, msg_dict
            touch_messages(con, cur.lastrowid, message_id)
            return msg_dict(con.execute('SELECT * FROM bandeja_consultas WHERE id=?', (cur.lastrowid,)).fetchone())
