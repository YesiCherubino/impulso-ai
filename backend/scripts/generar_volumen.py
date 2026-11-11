"""Genera una base de DEMO DE ESCALA: años de actividad comercial simulada para mostrar que Impulso
responde igual con mucha historia. Todos los datos son ficticios.

Uso (desde la carpeta backend):

    python scripts/generar_volumen.py                        # 5 años, ~11 consultas por día → data/impulso_escala.sqlite3
    python scripts/generar_volumen.py --anios 3 --por-dia 20
    python scripts/generar_volumen.py --db otra.sqlite3

Después, para usarla:

    $env:IMPULSO_DB_PATH="data/impulso_escala.sqlite3"   (PowerShell)
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8001 --env-file .env

Al terminar mide los tiempos de las pantallas principales. No toca la base demo habitual.
"""
import argparse
import math
import random
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# En Windows, si la salida se redirige (a un archivo o a otro programa), Python usa cp1252 y no puede
# escribir caracteres como "→" o "·". Se fuerza UTF-8 para que el script no falle.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

from app import auth  # noqa: E402
from app.db import connect, init_db  # noqa: E402
from app.business_v3 import init_v3  # noqa: E402
from app.business_v4 import init_v4  # noqa: E402
from app.escala import refresh_case_stats  # noqa: E402

PREFIJOS = ['Aurora', 'Nova', 'Botánica', 'Luna', 'Esencia', 'Oliva', 'Vita', 'Cielo', 'Brisa', 'Dalia', 'Prisma', 'Marea',
            'Nativa', 'Pampa', 'Ámbar', 'Verde', 'Andina', 'Raíz', 'Alma', 'Flor', 'Terra', 'Nube', 'Lumen', 'Coral',
            'Arena', 'Musgo', 'Salvia', 'Lavanda', 'Cardón', 'Ceibo', 'Jacarandá', 'Quebracho', 'Malbec', 'Yerba', 'Lino']
SUFIJOS = ['Cosmética', 'Beauty', 'Natural', 'Care', 'Labs', 'Studio', 'Skin', 'Botanics', 'Laboratorios', 'Farma',
           'Dermo', 'Organics', 'Essentials', 'Distribuciones', 'Perfumería', 'Spa', 'Pharma', 'Clínica']
CIUDADES = ['', '', '', 'Rosario', 'Córdoba', 'Mendoza', 'La Plata', 'Mar del Plata', 'Neuquén', 'Salta', 'Tucumán',
            'Asunción', 'Montevideo', 'Santiago', 'Bahía Blanca', 'Paraná']
NOMBRES = ['Lucía', 'Martín', 'Sofía', 'Diego', 'Valentina', 'Joaquín', 'Camila', 'Tomás', 'Florencia', 'Matías',
           'Julieta', 'Nicolás', 'Agustina', 'Federico', 'Carolina', 'Santiago', 'Paula', 'Andrés', 'Micaela', 'Ramiro']
APELLIDOS = ['López', 'Álvarez', 'Ríos', 'Molina', 'Vega', 'Ponce', 'Paz', 'Acosta', 'Fernández', 'Rivera', 'Beltrán',
             'Navarro', 'Gallo', 'Quiroga', 'Torres', 'Díaz', 'Gómez', 'Peralta', 'Ruiz', 'Sosa', 'Herrera', 'Benítez']
PRODUCTOS = ['Crema corporal de 250 ml', 'Shampoo de 350 ml', 'Acondicionador de 350 ml', 'Jabón líquido de 500 ml',
             'Máscara capilar de 300 ml', 'Crema facial de 50 ml', 'Sérum facial de 30 ml', 'Gel de ducha de 400 ml',
             'Protector labial', 'Perfume de 100 ml', 'Body splash de 200 ml', 'Crema de manos de 75 ml',
             'Desodorante roll-on', 'Protector solar FPS 50', 'Shampoo sólido', 'Línea Marca A', 'Fragancias Marca B',
             'Alcohol en gel de 250 ml', 'Toallitas desmaquillantes', 'Aceite corporal de 120 ml']
TIPOS = [('fabricacion_terceros', 35), ('mayorista', 25), ('desarrollo_formula', 10), ('elaboracion_envasado', 10),
         ('exportacion', 7), ('no_comercial', 8), ('sin_clasificar', 5)]
CANALES = [('WhatsApp', 50), ('Correo', 35), ('Formulario web', 15)]
MOTIVOS = [('Precio', 35), ('Volumen bajo el mínimo', 22), ('Plazo', 12), ('Sin respuesta del cliente', 18),
           ('Eligió otro proveedor', 10), ('Otro', 3)]
VENDEDORES = [('lucia', 'Lucía Paredes'), ('martin', 'Martín Carrizo'), ('sofia', 'Sofía Benegas'), ('diego', 'Diego Ocampo')]
PEDIDOS = ['Hola, queremos cotizar {p}. ¿Qué datos necesitan?',
           'Buen día. Somos una marca nueva y nos interesa {p}, unas {q} unidades.',
           'Les escribo por {p}. ¿Trabajan con fórmula propia del cliente?',
           'Necesitamos precio y plazo para {p}. Cantidad estimada: {q} unidades.',
           '¿Pueden enviarnos condiciones para {p}? Queremos definir presentación y envase.']
SEGUIMIENTOS = ['¿Pudieron avanzar con la propuesta?', 'Les comparto las especificaciones del envase.',
                'Gracias, revisamos la cotización y tenemos algunas dudas.', 'Confirmamos la cantidad y el packaging.',
                '¿Cuál sería el plazo de entrega del primer lote?']
RESPUESTAS = ['Gracias por escribirnos. Para cotizar necesitamos cantidad, presentación y si cuentan con fórmula propia.',
              'Les enviamos la propuesta con las condiciones y el plazo estimado.',
              'Recibido. Lo revisamos con el área técnica y les respondemos a la brevedad.',
              'Perfecto, avanzamos con la muestra y les confirmamos la fecha de entrega.']


def pick(rng, weighted):
    total = sum(w for _, w in weighted)
    x = rng.uniform(0, total)
    for value, w in weighted:
        x -= w
        if x <= 0:
            return value
    return weighted[-1][0]


def business_time(rng, day: datetime) -> datetime:
    return day.replace(hour=rng.randint(8, 19), minute=rng.randint(0, 59), second=rng.randint(0, 59), microsecond=0)


def generate(db: Path, years: float = 5, per_day: float = 11, seed: int = 42, quiet=False) -> dict:
    rng = random.Random(seed)
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    init_db(db)
    auth.init_auth(db)
    init_v3(db)
    init_v4(db)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=int(365 * years))
    t0 = time.time()
    with connect(db) as con:
        con.execute('BEGIN')
        # Se limpian los datos de ejemplo iniciales para que la base sea solo la simulación.
        for table in ('bandeja_consultas', 'fichas_consulta', 'interacciones', 'actividades_comerciales', 'notificaciones',
                      'remitentes_gestiones', 'oportunidades'):
            con.execute(f'DELETE FROM {table}')
        for user, name in VENDEDORES:
            con.execute('''INSERT OR IGNORE INTO usuarios (usuario,nombre,password_hash,creado_en,rol)
                           VALUES (?,?,?,?,'ventas')''', (user, name, auth.password_hash(secrets.token_urlsafe(24)), now.isoformat()))
        # Clientes: unos pocos recurrentes concentran muchas consultas (como en la realidad).
        names, clients = set(), []
        while len(clients) < 2500:
            city = rng.choice(CIUDADES)
            name = f'{rng.choice(PREFIJOS)} {rng.choice(SUFIJOS)}' + (f' {city}' if city else '')
            if name in names:
                continue
            names.add(name)
            person = f'{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)}'
            slug = ''.join(ch for ch in name.lower() if ch.isalnum())[:20]
            cur = con.execute('''INSERT INTO oportunidades (cliente,contacto,email,telefono,producto,cantidad,estado,ultimo_contacto,
                                 creada_el,responsable,canal_origen,notas) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                              (name, person, f'{slug}@ejemplo.test', f'54911{rng.randint(10000000, 99999999)}',
                               rng.choice(PRODUCTOS), None, 'nueva', start.date().isoformat(), start.date().isoformat(),
                               rng.choice(VENDEDORES)[0], 'Correo', 'Demo de escala (datos ficticios)'))
            clients.append((cur.lastrowid, name, person))
        weights = [1 / math.pow(i + 1, 0.8) for i in range(len(clients))]
        cases = msgs = acts = 0
        day = start
        case_rows, msg_rows, act_rows = [], [], []
        next_case_id = (con.execute('SELECT COALESCE(MAX(id),0) FROM fichas_consulta').fetchone()[0] or 0) + 1
        next_msg_id = (con.execute('SELECT COALESCE(MAX(id),0) FROM bandeja_consultas').fetchone()[0] or 0) + 1
        last_contact = {}
        while day < now:
            factor = 0.35 if day.weekday() >= 5 else 1.15
            for _ in range(max(0, int(rng.gauss(per_day * factor, per_day * 0.3)))):
                opp_id, client, person = rng.choices(clients, weights=weights, k=1)[0]
                tipo = pick(rng, TIPOS)
                canal = pick(rng, CANALES)
                product = rng.choice(PRODUCTOS)
                qty = None
                if tipo in ('fabricacion_terceros', 'elaboracion_envasado', 'desarrollo_formula', 'exportacion'):
                    qty = int(round(rng.lognormvariate(math.log(9000), 0.7), -2)) or 1000
                elif tipo == 'mayorista':
                    qty = int(round(rng.lognormvariate(math.log(800), 0.8), -1)) or 50
                created = business_time(rng, day)
                if created > now:
                    continue
                age_days = (now - created).days
                closed = age_days > 45 or rng.random() < 0.15
                if tipo == 'no_comercial':
                    estado = 'resuelta' if closed else 'sin_atender'
                elif closed:
                    estado = 'concretada' if rng.random() < 0.33 else 'no_concretada'
                else:
                    estado = pick(rng, [('sin_atender', 30), ('calificada', 35), ('cotizada', 22), ('muestra_piloto', 13)])
                owner = '' if (estado == 'sin_atender' and rng.random() < 0.6) else rng.choice(VENDEDORES)[0]
                # Conversación: alterna cliente y vendedor; las abiertas recientes pueden esperar respuesta.
                n_msgs = rng.randint(2, 8)
                t = created
                last_in = None
                pending_end = (estado in ('sin_atender', 'calificada', 'cotizada', 'muestra_piloto') and rng.random() < 0.45)
                for k in range(n_msgs):
                    outgoing = k % 2 == 1
                    if k == n_msgs - 1 and pending_end and outgoing:
                        break
                    if k > 0:
                        t += timedelta(hours=rng.choice([0.3, 0.8, 1.5, 3, 5, 9, 20, 30]) if outgoing else rng.uniform(4, 96))
                    if t > now:
                        break
                    if outgoing:
                        text = rng.choice(RESPUESTAS)
                        user = owner or rng.choice(VENDEDORES)[0]
                    else:
                        text = (rng.choice(PEDIDOS).format(p=product.lower(), q=qty or 'algunas') if k == 0
                                else rng.choice(SEGUIMIENTOS))
                        user = ''
                        last_in = t
                    channel = canal if not outgoing or canal != 'Formulario web' else 'Correo'
                    read = outgoing or not (pending_end and t > now - timedelta(days=2))
                    msg_rows.append((next_msg_id, client, person, channel, text, t.isoformat(timespec='seconds'),
                                     'resuelta' if outgoing else 'nueva', t.isoformat(timespec='seconds') if read else None,
                                     f"{client.split()[0].lower()}@ejemplo.test" if channel == 'Correo' else '',
                                     '' if channel == 'Correo' else '5491100000000', 'Consulta comercial' if channel == 'Correo' else '',
                                     next_case_id, opp_id, 'saliente' if outgoing else 'entrante', user))
                    next_msg_id += 1
                    msgs += 1
                closed_at = (t + timedelta(days=rng.randint(1, 20))) if estado in ('concretada', 'no_concretada', 'resuelta') else None
                if closed_at and closed_at > now:
                    closed_at = now
                quoted = estado in ('cotizada', 'muestra_piloto', 'concretada') or (estado == 'no_concretada' and rng.random() < 0.6)
                currency = 'USD' if tipo == 'exportacion' or rng.random() < 0.45 else 'ARS'
                amount = None
                if quoted:
                    units = qty or 1000
                    amount = round(units * (rng.uniform(1.2, 4.5) if currency == 'USD' else rng.uniform(1300, 5200)), -2)
                case_rows.append((next_case_id, f'CON-{created.year}-{next_case_id:05d}', opp_id, f'Consulta sobre {product}', client,
                                  person, product, qty, tipo, owner, estado,
                                  closed_at.isoformat(timespec='seconds') if closed_at else None,
                                  pick(rng, MOTIVOS) if estado == 'no_concretada' else ('Consulta no comercial' if estado == 'resuelta' else ''),
                                  amount, currency if quoted else '', created.date().isoformat() if quoted else None, 30 if quoted else None,
                                  created.isoformat(timespec='seconds'), (closed_at or t).isoformat(timespec='seconds')))
                if rng.random() < 0.3:
                    due = t + timedelta(days=rng.randint(2, 10))
                    act_state = 'programada' if estado in ('sin_atender', 'calificada', 'cotizada', 'muestra_piloto') else 'realizada'
                    if act_state == 'programada' and due < now - timedelta(days=3):
                        act_state = 'realizada'
                    act_rows.append((next_case_id, opp_id, f'Seguimiento · {client}', 'seguimiento', due.isoformat(timespec='seconds'),
                                     owner or rng.choice(VENDEDORES)[0], 'Seguimiento de la propuesta', act_state,
                                     created.isoformat(timespec='seconds'), created.isoformat(timespec='seconds')))
                    acts += 1
                last_contact[opp_id] = max(last_contact.get(opp_id, ''), t.date().isoformat())
                next_case_id += 1
                cases += 1
            day += timedelta(days=1)
        con.executemany('''INSERT INTO fichas_consulta (id,codigo,oportunidad_id,titulo,cliente,contacto,producto,cantidad,tipo_consulta,
                           responsable,estado_gestion,cerrada_en,motivo_cierre,cotizacion_monto,cotizacion_moneda,cotizacion_fecha,
                           cotizacion_validez_dias,creada_en,actualizada_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', case_rows)
        con.executemany('''INSERT INTO bandeja_consultas (id,cliente,contacto,canal,texto,recibido_el,estado,leido_en,email_remitente,
                           telefono_remitente,asunto,ficha_id,oportunidad_id,direccion,usuario) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', msg_rows)
        con.executemany('''INSERT INTO actividades_comerciales (ficha_id,oportunidad_id,titulo,tipo,inicio,responsable,notas,estado,
                           creada_en,actualizada_en) VALUES (?,?,?,?,?,?,?,?,?,?)''', act_rows)
        con.executemany('UPDATE oportunidades SET ultimo_contacto=?, creada_el=? WHERE id=?',
                        [(d, d, i) for i, d in last_contact.items()])
        # Clientes que nunca consultaron: no forman parte de la demo.
        con.execute('DELETE FROM oportunidades WHERE NOT EXISTS (SELECT 1 FROM fichas_consulta f WHERE f.oportunidad_id=oportunidades.id)')
        refresh_case_stats(con)
    elapsed = time.time() - t0
    with connect(db) as con:
        con.execute('ANALYZE')
    result = {'gestiones': cases, 'mensajes': msgs, 'actividades': acts, 'clientes': len(last_contact), 'segundos': round(elapsed, 1)}
    if not quiet:
        print(f"Base generada en {db}: {cases:,} gestiones, {msgs:,} mensajes, {acts:,} actividades, "
              f"{len(last_contact):,} clientes ({elapsed:.0f} s).".replace(',', '.'))
    return result


def measure(db: Path) -> list[tuple[str, float, int]]:
    """Mide las pantallas principales como las pide el navegador."""
    import os
    os.environ.setdefault('AUTH_ENABLED', 'false')
    from fastapi.testclient import TestClient
    from app.main import create_app
    urls = [('Bandeja (50 conversaciones)', '/api/inbox/conversations?limit=50'),
            ('Bandeja por prioridad', '/api/inbox/conversations?orden=prioridad&limit=50'),
            ('Bandeja: búsqueda de texto', '/api/inbox/conversations?q=envase&limit=50'),
            ('Ficha de contactos (lista)', '/api/contacts/search?limit=50'),
            ('Tablero (gestiones abiertas)', '/api/fichas-search?estado=calificada&limit=30'),
            ('Finalizados', '/api/fichas-search?estado=cerradas&limit=50'),
            ('Reportes · este mes', '/api/reports/summary?period=mes'),
            ('Reportes · histórico', '/api/reports/summary?period=todos'),
            ('Notificaciones', '/api/notifications')]
    out = []
    with TestClient(create_app(db)) as c:
        first = c.get('/api/inbox/conversations?limit=1').json()['items'][0]['key']
        urls.insert(1, ('Abrir una conversación', f'/api/inbox/conversations/{first}'))
        for label, url in urls:
            c.get(url)  # primera llamada: calienta la caché del disco
            t = time.time()
            r = c.get(url)
            out.append((label, round((time.time() - t) * 1000), len(r.content)))
            assert r.status_code == 200, (url, r.status_code, r.text[:200])
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', default=str(BACKEND / 'data' / 'impulso_escala.sqlite3'))
    parser.add_argument('--anios', type=float, default=5)
    parser.add_argument('--por-dia', type=float, default=11)
    parser.add_argument('--semilla', type=int, default=42)
    args = parser.parse_args()
    db = Path(args.db)
    generate(db, args.anios, args.por_dia, args.semilla)
    print('\nTiempos de respuesta (servidor, sin red):')
    for label, ms, size in measure(db):
        print(f'  {label:32s} {ms:6d} ms   {size / 1024:8.1f} KB')


if __name__ == '__main__':
    main()
