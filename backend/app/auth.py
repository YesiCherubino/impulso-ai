"""Autenticación sencilla para el backoffice: cuentas y sesiones persistidas en SQLite.

Los tokens se guardan exclusivamente como hashes SHA-256; las contraseñas con scrypt y sal.
"""
import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SESSION_HOURS = 8


def now():
    return datetime.now(timezone.utc)


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1)
    return f'scrypt${salt.hex()}${digest.hex()}'


def password_verify(password: str, stored: str) -> bool:
    try:
        algorithm, salt, digest = stored.split('$', 2)
        if algorithm != 'scrypt':
            return False
        guess = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
        return secrets.compare_digest(guess, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def init_auth(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript('''
          CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS sesiones (
            token_hash TEXT PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
            creado_en TEXT NOT NULL,
            expira_en TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS auth_intentos (
            usuario TEXT PRIMARY KEY,
            intentos INTEGER NOT NULL DEFAULT 0,
            bloqueo_hasta TEXT
          );
        ''')
        current_cols = {r[1] for r in con.execute('PRAGMA table_info(usuarios)')}
        if 'rol' not in current_cols:
            con.execute("ALTER TABLE usuarios ADD COLUMN rol TEXT NOT NULL DEFAULT 'ventas'")
        if 'tema' not in current_cols:
            con.execute("ALTER TABLE usuarios ADD COLUMN tema TEXT NOT NULL DEFAULT 'claro'")
        if os.getenv('AUTH_ENABLED', 'false').lower() != 'true':
            return
        username = os.getenv('ADMIN_USERNAME', '').strip().lower()
        password = os.getenv('ADMIN_PASSWORD', '')
        name = os.getenv('ADMIN_DISPLAY_NAME', 'Administrador comercial').strip()
        if not username or len(password) < 12:
            raise RuntimeError('AUTH_ENABLED requiere ADMIN_USERNAME y ADMIN_PASSWORD de al menos 12 caracteres')
        exists = con.execute('SELECT id FROM usuarios WHERE usuario=?', (username,)).fetchone()
        if not exists:
            con.execute('INSERT INTO usuarios (usuario,nombre,password_hash,creado_en) VALUES (?,?,?,?)',
                        (username, name, password_hash(password), now().isoformat()))
        con.execute("UPDATE usuarios SET rol='administrador' WHERE usuario=?", (username,))
        # IMPORTANTE: cambiar ADMIN_PASSWORD en Railway no cambia la contraseña de un usuario ya creado.


def authenticate(db_path: Path, username: str, password: str):
    username = username.strip().lower()
    with sqlite3.connect(db_path) as con:
        row = con.execute('SELECT id, usuario, nombre, password_hash FROM usuarios WHERE usuario=? AND activo=1', (username,)).fetchone()
        attempt = con.execute('SELECT intentos, bloqueo_hasta FROM auth_intentos WHERE usuario=?', (username,)).fetchone()
        if attempt and attempt[1] and datetime.fromisoformat(attempt[1]) > now():
            return None
        if not row or not password_verify(password, row[3]):
            failures = (attempt[0] if attempt else 0) + 1
            until = (now() + timedelta(minutes=15)).isoformat() if failures >= 5 else None
            con.execute('INSERT INTO auth_intentos (usuario,intentos,bloqueo_hasta) VALUES (?,?,?) ON CONFLICT(usuario) DO UPDATE SET intentos=?, bloqueo_hasta=?',
                        (username, failures, until, failures, until))
            return None
        con.execute('DELETE FROM auth_intentos WHERE usuario=?', (username,))
        token = secrets.token_urlsafe(48)
        created, expires = now(), now() + timedelta(hours=SESSION_HOURS)
        con.execute('DELETE FROM sesiones WHERE expira_en < ?', (created.isoformat(),))
        con.execute('INSERT INTO sesiones VALUES (?,?,?,?)', (token_hash(token), row[0], created.isoformat(), expires.isoformat()))
        user = con.execute('SELECT rol,tema FROM usuarios WHERE id=?',(row[0],)).fetchone()
        return {'token': token, 'user': {'id': row[0], 'username': row[1], 'name': row[2], 'role': user[0], 'theme': user[1]}, 'expires_at': expires.isoformat()}


def get_user(db_path: Path, token: str):
    if not token:
        return None
    with sqlite3.connect(db_path) as con:
        row = con.execute('''SELECT u.id, u.usuario, u.nombre, s.expira_en, u.rol, u.tema FROM sesiones s JOIN usuarios u ON s.usuario_id=u.id
                          WHERE s.token_hash=? AND s.expira_en>? AND u.activo=1''',
                          (token_hash(token), now().isoformat())).fetchone()
        return {'id': row[0], 'username': row[1], 'name': row[2], 'expires_at': row[3], 'role': row[4], 'theme': row[5]} if row else None


def logout(db_path: Path, token: str):
    if token:
        with sqlite3.connect(db_path) as con:
            con.execute('DELETE FROM sesiones WHERE token_hash=?', (token_hash(token),))
