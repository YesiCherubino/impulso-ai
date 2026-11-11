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
    # Con el nombre de quien lo hizo, aunque el usuario ya no esté (dado de baja).
    events = [dict(r) for r in con.execute('''SELECT e.*, COALESCE(u.nombre, '') AS usuario_nombre,
                                              COALESCE(v.nombre, '') AS valor_nombre FROM gestion_eventos e
                                              LEFT JOIN usuarios u ON LOWER(u.usuario)=LOWER(e.usuario)
                                              LEFT JOIN usuarios v ON e.tipo='responsable' AND LOWER(v.usuario)=LOWER(e.valor)
                                              WHERE e.ficha_id=? ORDER BY e.id''', (ficha_id,))]
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

    @app.post('/api/fichas/{ficha_id}/crear-contacto')
    def create_contact(ficha_id: int, request: Request):
        """Crea (o vincula, si coincide exacto por correo o teléfono) el contacto de una gestión que no lo tiene."""
        from .business_v2 import sender_email, sender_phone
        from .permisos import require
        user = current(request, db_path)
        require(db_path, user, 'contactos')
        with connect(db_path) as con:
            f = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
            if not f:
                raise HTTPException(404, 'Gestión no encontrada')
            if f['oportunidad_id']:
                return {'oportunidad_id': f['oportunidad_id'], 'creado': False}
            m = con.execute('''SELECT email_remitente, telefono_remitente, canal FROM bandeja_consultas
                               WHERE ficha_id=? ORDER BY id LIMIT 1''', (ficha_id,)).fetchone()
            email = sender_email((m['email_remitente'] if m else '') or '')
            phone = sender_phone((m['telefono_remitente'] if m else '') or '')
            hits = con.execute('''SELECT id FROM oportunidades WHERE (? <> '' AND LOWER(email)=?) OR (? <> '' AND telefono=?)''',
                               (email, email, phone, phone)).fetchall()
            creado = False
            if len(hits) == 1:
                opp = hits[0]['id']
            else:
                today = now_iso()[:10]
                cur = con.execute('''INSERT INTO oportunidades
                  (cliente,contacto,producto,cantidad,monto_estimado_usd,estado,creada_el,ultimo_contacto,notas,
                   tipo_consulta,canal_origen,presentacion,packaging,responsable,email,telefono)
                  VALUES (?,?,?,?,NULL,'nueva',?,?,'',?,?,?,?,?,?,?)''',
                  (f['cliente'] or 'Sin nombre', f['contacto'] or '', f['producto'] or 'Sin especificar', f['cantidad'],
                   today, today, f['tipo_consulta'] or 'sin_clasificar', (m['canal'] if m else '') or 'Manual',
                   f['presentacion'] or '', f['packaging'] or '', f['responsable'] or '', email, phone))
                opp = cur.lastrowid
                con.execute("INSERT INTO interacciones (oportunidad_id,tipo,descripcion,fecha) VALUES (?,'consulta',?,?)",
                            (opp, f'Contacto creado desde la gestión {f["codigo"]}', today))
                creado = True
            con.execute('UPDATE fichas_consulta SET oportunidad_id=? WHERE id=?', (opp, ficha_id))
            con.execute('UPDATE bandeja_consultas SET oportunidad_id=? WHERE ficha_id=?', (opp, ficha_id))
            log(con, ficha_id, 'contacto', str(opp), 'creó el contacto' if creado else 'vinculó el contacto', user.get('username', '') if user else '')
            return {'oportunidad_id': opp, 'creado': creado}
