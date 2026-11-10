"""Todas las cotizaciones en un solo lugar: qué se cotizó, a quién, y en qué quedó.

Estados:
- enviada: vigente y sin respuesta.
- aceptada: el cliente la aceptó por el enlace, o la gestión se concretó con esta como última cotización.
- vencida: pasó la validez sin respuesta.
- no_concretada: la gestión se cerró sin venta.
- reemplazada: hay una cotización más nueva en la misma gestión (no cuenta en los totales).
"""
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from .db import connect

ESTADOS = ('enviada', 'aceptada', 'vencida', 'no_concretada', 'reemplazada')

ESTADO_SQL = '''CASE
  WHEN q.aceptada_en IS NOT NULL THEN 'aceptada'
  WHEN q.id <> (SELECT MAX(q2.id) FROM cotizaciones q2 WHERE q2.ficha_id=q.ficha_id) THEN 'reemplazada'
  WHEN f.estado_gestion='concretada' THEN 'aceptada'
  WHEN f.estado_gestion IN ('no_concretada','resuelta') THEN 'no_concretada'
  WHEN date(q.fecha, '+' || q.validez_dias || ' days') < date(?) THEN 'vencida'
  ELSE 'enviada' END'''


def _where(con, user, *, estado='', period='todos', vendedor='', q=''):
    from .metrics import period_since
    from .permisos import allowed
    where, args = ["f.estado_gestion<>'fusionada'"], []
    if user and not allowed(con, user, 'ver_todas'):
        where.append('(LOWER(q.creada_por)=LOWER(?) OR LOWER(f.responsable)=LOWER(?))')
        args += [user['username']] * 2
    elif vendedor:
        where.append('LOWER(q.creada_por)=LOWER(?)')
        args.append(vendedor)
    if period and period != 'todos':
        where.append('q.fecha>=?')
        args.append(period_since(period, date.today()).isoformat())
    if q.strip():
        where.append('(LOWER(f.cliente) LIKE ? OR LOWER(q.numero) LIKE ? OR LOWER(f.codigo) LIKE ? OR LOWER(f.titulo) LIKE ?)')
        args += [f'%{q.strip().lower()}%'] * 4
    return where, args


def listar(con, user, *, estado='', period='todos', vendedor='', q='', limit=50, offset=0) -> dict:
    if estado and estado not in ESTADOS:
        raise HTTPException(422, 'Estado desconocido')
    where, args = _where(con, user, period=period, vendedor=vendedor, q=q)
    today = date.today().isoformat()
    base = f'''SELECT q.*, f.codigo, f.cliente, f.titulo, f.responsable, f.oportunidad_id,
                      date(q.fecha, '+' || q.validez_dias || ' days') AS vence, {ESTADO_SQL} AS estado
               FROM cotizaciones q JOIN fichas_consulta f ON f.id=q.ficha_id WHERE {' AND '.join(where)}'''
    all_args = [today, *args]
    # Resumen sobre el mismo filtro (sin el de estado), sin contar las reemplazadas.
    resumen = {'cantidad': 0, 'aceptadas': 0, 'cotizado': {}, 'aceptado': {}, 'por_estado': {e: 0 for e in ESTADOS}}
    for r in con.execute(f'SELECT estado, moneda, COUNT(*) AS n, SUM(total) AS t FROM ({base}) GROUP BY estado, moneda', all_args):
        resumen['por_estado'][r['estado']] += r['n']
        if r['estado'] == 'reemplazada':
            continue
        resumen['cantidad'] += r['n']
        resumen['cotizado'][r['moneda']] = round(resumen['cotizado'].get(r['moneda'], 0) + (r['t'] or 0), 2)
        if r['estado'] == 'aceptada':
            resumen['aceptadas'] += r['n']
            resumen['aceptado'][r['moneda']] = round(resumen['aceptado'].get(r['moneda'], 0) + (r['t'] or 0), 2)
    cerradas = resumen['aceptadas'] + resumen['por_estado']['no_concretada'] + resumen['por_estado']['vencida']
    resumen['tasa'] = round(100 * resumen['aceptadas'] / cerradas) if cerradas else None
    sql = f'SELECT * FROM ({base}) WHERE {"estado=?" if estado else "1=1"}'
    filt = [*all_args, *([estado] if estado else [])]
    total = con.execute(f'SELECT COUNT(*) FROM ({sql})', filt).fetchone()[0]
    rows = con.execute(f'{sql} ORDER BY fecha DESC, id DESC LIMIT ? OFFSET ?', [*filt, int(limit), int(offset)]).fetchall()
    items = [{'id': r['id'], 'numero': r['numero'], 'fecha': r['fecha'], 'vence': r['vence'], 'estado': r['estado'],
              'moneda': r['moneda'], 'total': r['total'], 'creada_por': r['creada_por'], 'token': r['token'],
              'aceptada_en': r['aceptada_en'], 'aceptada_por': r['aceptada_por'], 'ficha_id': r['ficha_id'],
              'codigo': r['codigo'], 'cliente': r['cliente'], 'titulo': r['titulo'], 'responsable': r['responsable'],
              'conversacion': str(r['oportunidad_id'] if r['oportunidad_id'] else -r['ficha_id'])} for r in rows]
    return {'total': total, 'items': items, 'resumen': resumen}


def register_cotizaciones_lista(app: FastAPI, db_path: Path):
    from .business_v2 import current
    from .comercial_v5 import b64file, xlsx

    @app.get('/api/cotizaciones')
    def list_quotes(request: Request, estado: str = '', period: str = 'todos', vendedor: str = '', q: str = '',
                    limit: int = 50, offset: int = 0):
        user = current(request, db_path)
        with connect(db_path) as con:
            return listar(con, user, estado=estado, period=period, vendedor=vendedor, q=q,
                          limit=max(1, min(limit, 200)), offset=max(0, offset))

    @app.get('/api/export/cotizaciones')
    def export_quotes(request: Request, estado: str = '', period: str = 'todos', vendedor: str = '', q: str = ''):
        from .permisos import require
        user = current(request, db_path)
        require(db_path, user, 'exportar')
        nombres = {'enviada': 'Enviada', 'aceptada': 'Aceptada', 'vencida': 'Vencida', 'no_concretada': 'No concretada',
                   'reemplazada': 'Reemplazada'}
        with connect(db_path) as con:
            data = listar(con, user, estado=estado, period=period, vendedor=vendedor, q=q, limit=100000)
        rows = [[i['numero'], i['fecha'], i['vence'], nombres[i['estado']], i['cliente'], i['codigo'], i['titulo'], i['moneda'],
                 i['total'], i['creada_por'], i['aceptada_en'] or '', i['aceptada_por'] or ''] for i in data['items']]
        headers = ['Número', 'Fecha', 'Vence', 'Estado', 'Cliente', 'Gestión', 'Asunto', 'Moneda', 'Total', 'Cotizó',
                   'Aceptada el', 'Aceptada por']
        return b64file(xlsx([('Cotizaciones', headers, rows)]), f'impulso_cotizaciones_{date.today().isoformat()}.xlsx',
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
