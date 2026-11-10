"""Permisos editables por perfil y la vista "Ver como" del administrador.

El perfil Administrador tiene siempre todos los permisos y no se edita. Ventas y Gerencia arrancan con los
valores de PERMISOS y el administrador los cambia en Ajustes → Usuarios y permisos.
"""
from pathlib import Path

from fastapi import HTTPException

from .db import connect

PERFILES_EDITABLES = ('ventas', 'gerencia')
# clave, descripción, (ventas, gerencia) por defecto
PERMISOS = [
    ('ver_todas', 'Ver todas las consultas (no solo las propias y sin asignar)', (True, True)),
    ('responder', 'Responder y registrar respuestas', (True, False)),
    ('gestionar', 'Cambiar estado, cotizar y cerrar gestiones', (True, False)),
    ('asignar', 'Asignar o reasignar gestiones', (True, False)),
    ('contactos', 'Crear y editar contactos', (True, False)),
    ('reportes_todos', 'Ver reportes de todos los vendedores', (False, True)),
    ('reporte_ia', 'Usar el reporte con IA', (True, True)),
    ('exportar', 'Exportar a Excel', (True, True)),
    ('chat', 'Usar el chat del equipo', (True, True)),
    ('tablero_otros', 'Ver el tablero de otro vendedor en Mi día', (False, True)),
]
CLAVES = [p[0] for p in PERMISOS]
VER_COMO_HEADER = 'x-ver-como'


def init_permisos(db_path: Path) -> None:
    with connect(db_path) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS permisos_perfil (
            rol TEXT NOT NULL, permiso TEXT NOT NULL, permitido INTEGER NOT NULL, PRIMARY KEY (rol, permiso))''')
        for key, _, (ventas, gerencia) in PERMISOS:
            for rol, val in (('ventas', ventas), ('gerencia', gerencia)):
                con.execute('INSERT OR IGNORE INTO permisos_perfil(rol,permiso,permitido) VALUES (?,?,?)', (rol, key, int(val)))


def perms_for(con, role: str) -> dict:
    if role == 'administrador':
        return {k: True for k in CLAVES}
    stored = {r['permiso']: bool(r['permitido']) for r in con.execute('SELECT permiso, permitido FROM permisos_perfil WHERE rol=?', (role,))}
    defaults = {k: (v[0] if role == 'ventas' else v[1]) for k, _, v in PERMISOS}
    return {k: stored.get(k, defaults[k]) for k in CLAVES}


def allowed(con, user, perm: str) -> bool:
    """Sin sesión (demo sin inicio de sesión) todo está permitido."""
    if not user:
        return True
    return perms_for(con, user['role']).get(perm, False)


def require(db_path: Path, user, perm: str, message: str = 'Tu perfil no tiene permiso para esta acción'):
    if not user:
        return user
    with connect(db_path) as con:
        if not allowed(con, user, perm):
            raise HTTPException(403, message)
    return user


def apply_view_as(user: dict | None, header_value: str | None) -> dict | None:
    """El administrador puede ver el sistema como Ventas o Gerencia: se reemplaza el perfil, no el usuario."""
    if not user or not header_value:
        return user
    value = header_value.strip().lower()
    if user.get('role') == 'administrador' and value in PERFILES_EDITABLES:
        return {**user, 'role': value, 'rol_real': 'administrador', 'viendo_como': value}
    return user


def register_permisos(app, db_path: Path):
    from fastapi import Request
    from pydantic import BaseModel
    from .business_v2 import current

    class PermisoInput(BaseModel):
        rol: str
        permiso: str
        permitido: bool

    @app.get('/api/permisos')
    def permission_matrix(request: Request):
        current(request, db_path, 'administrador')
        with connect(db_path) as con:
            return {'permisos': [{'clave': k, 'nombre': n} for k, n, _ in PERMISOS],
                    'perfiles': {r: perms_for(con, r) for r in PERFILES_EDITABLES}}

    @app.post('/api/permisos')
    def set_permission(request: Request, payload: PermisoInput):
        current(request, db_path, 'administrador')
        if payload.rol not in PERFILES_EDITABLES or payload.permiso not in CLAVES:
            raise HTTPException(422, 'Perfil o permiso inválido')
        with connect(db_path) as con:
            con.execute('''INSERT INTO permisos_perfil(rol,permiso,permitido) VALUES (?,?,?)
                           ON CONFLICT(rol,permiso) DO UPDATE SET permitido=excluded.permitido''',
                        (payload.rol, payload.permiso, int(payload.permitido)))
            return perms_for(con, payload.rol)
