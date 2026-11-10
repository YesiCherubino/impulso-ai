"""Chat interno del equipo: canal #ventas, mensajes directos, estado de cada usuario y retención configurable.

Sin conexión permanente: el navegador consulta /api/chat/resumen cada pocos segundos (eso también registra
la actividad del usuario para calcular Activo / Ausente).
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .db import connect
from .business_v2 import current
from .escala import page_sql, conv_key

AUSENTE_MIN = 5       # sin actividad durante este tiempo: Ausente
INACTIVO_MIN = 30     # sin actividad durante este tiempo: Inactivo
CODIGO_RE = re.compile(r'\bCON-\d{4}-\d{5}\b')
_last_purge = {'at': None}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _add_column(con, table, col, sql):
    if col not in {r['name'] for r in con.execute(f'PRAGMA table_info({table})')}:
        con.execute(f'ALTER TABLE {table} ADD COLUMN {col} {sql}')


def init_equipo(db_path: Path) -> None:
    with connect(db_path) as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS chat_canales (
          id INTEGER PRIMARY KEY AUTOINCREMENT, clave TEXT NOT NULL UNIQUE, tipo TEXT NOT NULL, nombre TEXT NOT NULL DEFAULT '',
          creado_en TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chat_mensajes (
          id INTEGER PRIMARY KEY AUTOINCREMENT, canal_id INTEGER NOT NULL REFERENCES chat_canales(id), usuario TEXT NOT NULL,
          texto TEXT NOT NULL, ficha_id INTEGER, sistema INTEGER NOT NULL DEFAULT 0, creado_en TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_chat_mensajes_canal ON chat_mensajes(canal_id, id);
        CREATE INDEX IF NOT EXISTS idx_chat_mensajes_fecha ON chat_mensajes(creado_en);
        CREATE TABLE IF NOT EXISTS chat_lecturas (
          canal_id INTEGER NOT NULL, usuario TEXT NOT NULL, ultimo_leido_id INTEGER NOT NULL DEFAULT 0,
          silenciado INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (canal_id, usuario));
        CREATE TABLE IF NOT EXISTS usuarios_estado (
          usuario TEXT PRIMARY KEY, estado TEXT NOT NULL DEFAULT 'activo', mensaje TEXT NOT NULL DEFAULT '',
          no_molestar INTEGER NOT NULL DEFAULT 0, visto_en TEXT);
        ''')
        _add_column(con, 'empresa_config', 'chat_retencion_dias', 'INTEGER NOT NULL DEFAULT 90')
        if not con.execute("SELECT 1 FROM chat_canales WHERE clave='ventas'").fetchone():
            con.execute("INSERT INTO chat_canales(clave,tipo,nombre,creado_en) VALUES ('ventas','canal','ventas',?)", (now_iso(),))
        purge(con, force=True)


def purge(con, force=False):
    """Borra los mensajes más viejos que la retención configurada (0 = no se borran). Como máximo una vez por hora."""
    now = datetime.now(timezone.utc)
    if not force and _last_purge['at'] and now - _last_purge['at'] < timedelta(hours=1):
        return
    _last_purge['at'] = now
    row = con.execute('SELECT chat_retencion_dias FROM empresa_config WHERE id=1').fetchone()
    days = row['chat_retencion_dias'] if row else 90
    if days and days > 0:
        con.execute('DELETE FROM chat_mensajes WHERE creado_en<?', ((now - timedelta(days=days)).isoformat(),))


def dm_key(a: str, b: str) -> str:
    return 'dm:' + '|'.join(sorted([a, b]))


def dm_channel(con, a: str, b: str) -> int:
    key = dm_key(a, b)
    row = con.execute('SELECT id FROM chat_canales WHERE clave=?', (key,)).fetchone()
    if row:
        return row['id']
    return con.execute("INSERT INTO chat_canales(clave,tipo,creado_en) VALUES (?,'directo',?)", (key, now_iso())).lastrowid


def post(con, canal_id: int, usuario: str, texto: str, ficha_id=None, sistema=False) -> int:
    msg_id = con.execute('INSERT INTO chat_mensajes(canal_id,usuario,texto,ficha_id,sistema,creado_en) VALUES (?,?,?,?,?,?)',
                         (canal_id, usuario, texto, ficha_id, int(sistema), now_iso())).lastrowid
    # El que escribe ya leyó su propio mensaje.
    con.execute('''INSERT INTO chat_lecturas(canal_id,usuario,ultimo_leido_id) VALUES (?,?,?)
                   ON CONFLICT(canal_id,usuario) DO UPDATE SET ultimo_leido_id=MAX(ultimo_leido_id,excluded.ultimo_leido_id)''',
                (canal_id, usuario, msg_id))
    return msg_id


def notify_assignment(con, ficha_id: int, owner: str, by: str) -> None:
    """Mensaje directo automático cuando alguien te asigna una gestión."""
    if not owner or not by or owner == by:
        return
    if not con.execute('SELECT 1 FROM usuarios WHERE usuario=?', (owner,)).fetchone():
        return
    f = con.execute('SELECT codigo, cliente FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
    if f:
        post(con, dm_channel(con, owner, by), by, f"Te asigné {f['codigo']} ({f['cliente']})", ficha_id, sistema=True)


def status_of(row, now) -> str:
    if row is None or not row['visto_en']:
        return 'inactivo'
    if row['estado'] == 'inactivo':
        return 'inactivo'
    try:
        idle = now - datetime.fromisoformat(row['visto_en'])
    except ValueError:
        return 'inactivo'
    if idle > timedelta(minutes=INACTIVO_MIN):
        return 'inactivo'
    if row['estado'] == 'ausente' or idle > timedelta(minutes=AUSENTE_MIN):
        return 'ausente'
    return 'activo'


def team(con) -> list[dict]:
    now = datetime.now(timezone.utc)
    states = {r['usuario']: r for r in con.execute('SELECT * FROM usuarios_estado')}
    out = []
    for u in con.execute('SELECT usuario, nombre, rol FROM usuarios WHERE activo=1 ORDER BY nombre'):
        st = states.get(u['usuario'])
        out.append({'usuario': u['usuario'], 'nombre': u['nombre'], 'rol': u['rol'], 'estado': status_of(st, now),
                    'mensaje': st['mensaje'] if st else '', 'no_molestar': bool(st['no_molestar']) if st else False})
    return out


def my_channels(con, username: str) -> list[dict]:
    rows = con.execute('''SELECT c.*, COALESCE(l.ultimo_leido_id,0) AS leido, COALESCE(l.silenciado,0) AS silenciado,
               (SELECT MAX(id) FROM chat_mensajes m WHERE m.canal_id=c.id) AS ultimo_id
               FROM chat_canales c LEFT JOIN chat_lecturas l ON l.canal_id=c.id AND l.usuario=?
               WHERE c.tipo='canal' OR c.clave LIKE ? OR c.clave LIKE ?''',
                       (username, f'dm:{username}|%', f'dm:%|{username}')).fetchall()
    out = []
    for c in rows:
        unread = con.execute('SELECT COUNT(*) FROM chat_mensajes WHERE canal_id=? AND id>? AND usuario<>?',
                             (c['id'], c['leido'], username)).fetchone()[0]
        last = con.execute('SELECT * FROM chat_mensajes WHERE id=?', (c['ultimo_id'],)).fetchone() if c['ultimo_id'] else None
        other = ''
        if c['tipo'] == 'directo':
            a, b = c['clave'][3:].split('|')
            other = b if a == username else a
        out.append({'id': c['id'], 'tipo': c['tipo'], 'nombre': c['nombre'], 'con': other, 'no_leidos': unread,
                    'silenciado': bool(c['silenciado']), 'ultimo': dict(last) if last else None})
    out.sort(key=lambda c: (c['tipo'] != 'canal', -(c['ultimo']['id'] if c['ultimo'] else 0)))
    return out


def can_read(con, canal_id: int, username: str):
    c = con.execute('SELECT * FROM chat_canales WHERE id=?', (canal_id,)).fetchone()
    if not c:
        raise HTTPException(404, 'Canal no encontrado')
    if c['tipo'] == 'directo' and username not in c['clave'][3:].split('|'):
        raise HTTPException(403, 'No participás de esta conversación')
    return c


def message_dict(con, m, cache: dict) -> dict:
    d = dict(m)
    fid = m['ficha_id']
    if fid:
        if fid not in cache:
            f = con.execute('SELECT * FROM fichas_consulta WHERE id=?', (fid,)).fetchone()
            cache[fid] = {'id': f['id'], 'codigo': f['codigo'], 'cliente': f['cliente'], 'titulo': f['titulo'],
                          'conversacion': str(conv_key(f))} if f else None
        d['gestion'] = cache[fid]
    return d


class MensajeInput(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)
    ficha_id: int | None = None


class EstadoInput(BaseModel):
    estado: Literal['activo', 'ausente', 'inactivo'] = 'activo'
    mensaje: str = Field(default='', max_length=120)
    no_molestar: bool = False


class DirectoInput(BaseModel):
    usuario: str = Field(min_length=1, max_length=60)


class LeidoInput(BaseModel):
    ultimo_id: int = Field(ge=0)


class SilencioInput(BaseModel):
    silenciado: bool


class RetencionInput(BaseModel):
    dias: int = Field(ge=0, le=3650)


def _me(request, db_path) -> str:
    user = current(request, db_path)
    if not user:
        raise HTTPException(403, 'El chat del equipo requiere iniciar sesión')
    from .permisos import require
    require(db_path, user, 'chat')
    return user['username']


def register_equipo(app: FastAPI, db_path: Path):
    @app.get('/api/chat/resumen')
    def summary(request: Request, desde_id: int = -1):
        """Llamado periódico: registra actividad, devuelve canales con no leídos, equipo y mensajes nuevos para avisar."""
        me = _me(request, db_path)
        with connect(db_path) as con:
            con.execute('''INSERT INTO usuarios_estado(usuario,visto_en) VALUES (?,?)
                           ON CONFLICT(usuario) DO UPDATE SET visto_en=excluded.visto_en''', (me, now_iso()))
            purge(con)
            channels = my_channels(con, me)
            last_id = con.execute('SELECT COALESCE(MAX(id),0) FROM chat_mensajes').fetchone()[0]
            nuevos = []
            if desde_id >= 0:
                ids = [c['id'] for c in channels if not c['silenciado']]
                if ids:
                    rows = con.execute(page_sql(f'''SELECT * FROM chat_mensajes WHERE id>? AND usuario<>? AND canal_id IN ({','.join('?' * len(ids))})
                                                    ORDER BY id''', 20, 0), [desde_id, me, *ids]).fetchall()
                    kinds = {c['id']: c['tipo'] for c in channels}
                    for m in rows:
                        directo = kinds.get(m['canal_id']) == 'directo'
                        mencion = f'@{me}' in m['texto'].lower()
                        if directo or mencion:
                            nuevos.append({**dict(m), 'directo': directo, 'mencion': mencion})
            st = con.execute('SELECT * FROM usuarios_estado WHERE usuario=?', (me,)).fetchone()
            return {'yo': me, 'canales': channels, 'equipo': team(con), 'ultimo_id': last_id, 'nuevos': nuevos,
                    'no_leidos': sum(c['no_leidos'] for c in channels if not c['silenciado']),
                    'mi_estado': {'estado': st['estado'], 'mensaje': st['mensaje'], 'no_molestar': bool(st['no_molestar'])}}

    @app.post('/api/chat/estado')
    def set_status(request: Request, payload: EstadoInput):
        me = _me(request, db_path)
        with connect(db_path) as con:
            con.execute('''INSERT INTO usuarios_estado(usuario,estado,mensaje,no_molestar,visto_en) VALUES (?,?,?,?,?)
                           ON CONFLICT(usuario) DO UPDATE SET estado=excluded.estado, mensaje=excluded.mensaje,
                           no_molestar=excluded.no_molestar, visto_en=excluded.visto_en''',
                        (me, payload.estado, payload.mensaje.strip(), int(payload.no_molestar), now_iso()))
            return payload.model_dump()

    @app.get('/api/chat/canales/{canal_id}/mensajes')
    def messages(canal_id: int, request: Request, antes_de: int = 0, despues_de: int = 0, limite: int = 60):
        me = _me(request, db_path)
        limite = max(1, min(200, limite))
        with connect(db_path) as con:
            can_read(con, canal_id, me)
            if despues_de:
                rows = con.execute(page_sql('SELECT * FROM chat_mensajes WHERE canal_id=? AND id>? ORDER BY id', limite, 0),
                                   (canal_id, despues_de)).fetchall()
                more = False
            else:
                cond, args = ('AND id<?', [antes_de]) if antes_de else ('', [])
                rows = con.execute(page_sql(f'SELECT * FROM chat_mensajes WHERE canal_id=? {cond} ORDER BY id DESC', limite + 1, 0),
                                   [canal_id, *args]).fetchall()
                more = len(rows) > limite
                rows = list(reversed(rows[:limite]))
            cache = {}
            return {'mensajes': [message_dict(con, m, cache) for m in rows], 'hay_anteriores': more}

    @app.post('/api/chat/canales/{canal_id}/mensajes', status_code=201)
    def send(canal_id: int, request: Request, payload: MensajeInput):
        me = _me(request, db_path)
        texto = payload.texto.strip()
        if not texto:
            raise HTTPException(422, 'Escribí un mensaje')
        with connect(db_path) as con:
            can_read(con, canal_id, me)
            ficha_id = payload.ficha_id
            if not ficha_id:
                # Un código CON-… escrito en el texto queda enlazado a la gestión.
                code = CODIGO_RE.search(texto)
                if code:
                    f = con.execute('SELECT id FROM fichas_consulta WHERE codigo=?', (code.group(0),)).fetchone()
                    ficha_id = f['id'] if f else None
            elif not con.execute('SELECT 1 FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone():
                raise HTTPException(404, 'Gestión no encontrada')
            msg_id = post(con, canal_id, me, texto, ficha_id)
            return message_dict(con, con.execute('SELECT * FROM chat_mensajes WHERE id=?', (msg_id,)).fetchone(), {})

    @app.post('/api/chat/directo')
    def direct(request: Request, payload: DirectoInput):
        me = _me(request, db_path)
        with connect(db_path) as con:
            if not con.execute('SELECT 1 FROM usuarios WHERE usuario=? AND activo=1', (payload.usuario,)).fetchone():
                raise HTTPException(404, 'Usuario no encontrado')
            if payload.usuario == me:
                raise HTTPException(422, 'Elegí a otra persona')
            return {'id': dm_channel(con, me, payload.usuario)}

    @app.post('/api/chat/canales/{canal_id}/leido')
    def mark_read(canal_id: int, request: Request, payload: LeidoInput):
        me = _me(request, db_path)
        with connect(db_path) as con:
            can_read(con, canal_id, me)
            con.execute('''INSERT INTO chat_lecturas(canal_id,usuario,ultimo_leido_id) VALUES (?,?,?)
                           ON CONFLICT(canal_id,usuario) DO UPDATE SET ultimo_leido_id=MAX(ultimo_leido_id,excluded.ultimo_leido_id)''',
                        (canal_id, me, payload.ultimo_id))
            return {'ok': True}

    @app.post('/api/chat/canales/{canal_id}/silenciar')
    def mute(canal_id: int, request: Request, payload: SilencioInput):
        me = _me(request, db_path)
        with connect(db_path) as con:
            can_read(con, canal_id, me)
            con.execute('''INSERT INTO chat_lecturas(canal_id,usuario,silenciado) VALUES (?,?,?)
                           ON CONFLICT(canal_id,usuario) DO UPDATE SET silenciado=excluded.silenciado''',
                        (canal_id, me, int(payload.silenciado)))
            return {'ok': True}

    @app.get('/api/chat/retencion')
    def get_retention(request: Request):
        current(request, db_path)
        with connect(db_path) as con:
            return {'dias': con.execute('SELECT chat_retencion_dias FROM empresa_config WHERE id=1').fetchone()[0]}

    @app.post('/api/chat/retencion')
    def set_retention(request: Request, payload: RetencionInput):
        current(request, db_path, 'administrador')
        with connect(db_path) as con:
            con.execute('UPDATE empresa_config SET chat_retencion_dias=? WHERE id=1', (payload.dias,))
            purge(con, force=True)
            return {'dias': payload.dias}


def announce_close(con, ficha_id: int, usuario: str) -> None:
    """Cierre en #ventas: aviso automático cuando una gestión pasa a Concretada."""
    if not usuario:
        return
    f = con.execute('SELECT codigo, cliente, cotizacion_monto, cotizacion_moneda FROM fichas_consulta WHERE id=?', (ficha_id,)).fetchone()
    canal = con.execute("SELECT id FROM chat_canales WHERE clave='ventas'").fetchone()
    if not f or not canal:
        return
    monto = ''
    if f['cotizacion_monto'] is not None and f['cotizacion_moneda']:
        monto = f" · {f['cotizacion_moneda']} {f['cotizacion_monto']:,.0f}".replace(',', '.')
    post(con, canal['id'], usuario, f"Cerré {f['cliente']}{monto}", ficha_id, sistema=True)
