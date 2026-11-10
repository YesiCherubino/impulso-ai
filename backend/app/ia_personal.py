"""Preferencias personales del asistente de IA.

La empresa define la base (tono, tratamiento, extensión, signos e indicaciones generales). Cada usuario puede
cambiar su tono, extensión, signos de apertura y su firma; lo que deja sin tocar usa la base. Las indicaciones
generales y el tratamiento quedan solo para el administrador, así todos responden con el mismo criterio.
"""
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from .db import connect

usuario_actual: ContextVar[str] = ContextVar('impulso_usuario_ia', default='')


def init_ia_personal(db_path: Path) -> None:
    with connect(db_path) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS ia_preferencias_usuario (
            usuario TEXT PRIMARY KEY, tono TEXT, extension TEXT, signos_apertura INTEGER, firma TEXT NOT NULL DEFAULT '')''')


def base(con) -> dict:
    try:
        row = con.execute('SELECT * FROM ia_configuracion WHERE id=1').fetchone()
        return dict(row) if row else {}
    except Exception:
        return {}


def propias(con, usuario: str) -> dict:
    if not usuario:
        return {}
    row = con.execute('SELECT tono,extension,signos_apertura,firma FROM ia_preferencias_usuario WHERE LOWER(usuario)=LOWER(?)',
                      (usuario,)).fetchone()
    return dict(row) if row else {}


def perfil(db_path: Path, usuario: str | None = None) -> dict:
    """Configuración efectiva: la base de la empresa con lo que el usuario cambió encima."""
    with connect(db_path) as con:
        p = base(con)
        own = propias(con, usuario if usuario is not None else usuario_actual.get())
    for k in ('tono', 'extension', 'signos_apertura'):
        if own.get(k) is not None:
            p[k] = own[k]
    p['firma'] = own.get('firma') or ''
    return p


class MisPreferencias(BaseModel):
    tono: Literal['formal', 'profesional', 'cercano'] | None = None
    extension: Literal['breve', 'media', 'detallada'] | None = None
    signos_apertura: bool | None = None
    firma: str = Field(default='', max_length=200)


def register_ia_personal(app: FastAPI, db_path: Path):
    from .business_v2 import current

    @app.get('/api/ai/mis-preferencias')
    def mine(request: Request):
        user = current(request, db_path)
        with connect(db_path) as con:
            b = base(con)
            own = propias(con, user['username'] if user else '')
        return {'base': {k: b.get(k) for k in ('tono', 'tratamiento', 'extension', 'signos_apertura')},
                'propias': {'tono': own.get('tono'), 'extension': own.get('extension'),
                            'signos_apertura': None if own.get('signos_apertura') is None else bool(own['signos_apertura']),
                            'firma': own.get('firma') or ''}}

    @app.post('/api/ai/mis-preferencias')
    def save_mine(request: Request, payload: MisPreferencias):
        user = current(request, db_path)
        usuario = user['username'] if user else ''
        if not usuario:
            return {'ok': False}
        with connect(db_path) as con:
            con.execute('''INSERT INTO ia_preferencias_usuario(usuario,tono,extension,signos_apertura,firma) VALUES (?,?,?,?,?)
                           ON CONFLICT(usuario) DO UPDATE SET tono=excluded.tono, extension=excluded.extension,
                           signos_apertura=excluded.signos_apertura, firma=excluded.firma''',
                        (usuario, payload.tono, payload.extension,
                         None if payload.signos_apertura is None else int(payload.signos_apertura), payload.firma.strip()))
        return {'ok': True}
