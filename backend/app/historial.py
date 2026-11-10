"""Historial de cada gestión (quién cambió qué y cuándo) y su línea de vida por etapas."""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from .db import connect

ETAPAS = ('sin_atender', 'calificada', 'cotizada', 'muestra_piloto', 'concretada')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def init_historial(db_path: Path) -> None:
    with connect(db_path) as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS gestion_eventos (
          id INTEGER PRIMARY KEY AUTOINCREMENT, ficha_id INTEGER NOT NULL, tipo TEXT NOT NULL, valor TEXT NOT NULL DEFAULT '',
          detalle TEXT NOT NULL DEFAULT '', usuario TEXT NOT NULL DEFAULT '', creado_en TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_gestion_eventos_ficha ON gestion_eventos(ficha_id, id);
        ''')


def log(con, ficha_id: int, tipo: str, valor: str = '', detalle: str = '', usuario: str = '') -> None:
    con.execute('INSERT INTO gestion_eventos(ficha_id,tipo,valor,detalle,usuario,creado_en) VALUES (?,?,?,?,?,?)',
                (ficha_id, tipo, valor or '', detalle or '', usuario or '', now_iso()))


def _dt(s):
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def timeline(con, ficha_id: int) -> dict:
    f = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
    if not f:
        raise HTTPException(404, 'Gestión no encontrada')
    events = [dict(r) for r in con.execute('SELECT * FROM gestion_eventos WHERE ficha_id=? ORDER BY id', (ficha_id,))]
    # Etapas: desde la creación, cada cambio de estado abre un tramo nuevo.
    start = _dt(f['creada_en']) or datetime.now(timezone.utc)
    changes = [(e['valor'], _dt(e['creado_en'])) for e in events if e['tipo'] == 'estado' and _dt(e['creado_en'])]
    first = 'sin_atender' if changes else (f['estado_gestion'] or 'sin_atender')
    tramos, current, since = [], first, start
    for estado, when in changes:
        if estado == current:
            continue
        tramos.append({'estado': current, 'desde': since.isoformat(), 'hasta': when.isoformat(), 'dias': max(0, (when - since).days)})
        current, since = estado, when
    now = datetime.now(timezone.utc)
    cerrada = current in ('concretada', 'no_concretada', 'resuelta')
    tramos.append({'estado': current, 'desde': since.isoformat(), 'hasta': None if not cerrada else since.isoformat(),
                   'dias': 0 if cerrada else max(0, (now - since).days), 'actual': True})
    return {'estado': f['estado_gestion'], 'creada_en': f['creada_en'], 'tramos': tramos, 'eventos': list(reversed(events))}


def register_historial(app: FastAPI, db_path: Path):
    from .business_v2 import current

    @app.get('/api/fichas/{ficha_id}/historial')
    def history(ficha_id: int, request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            return timeline(con, ficha_id)
