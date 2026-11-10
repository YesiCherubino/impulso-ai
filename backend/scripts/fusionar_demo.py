"""Fusiona gestiones y contactos duplicados de la base (pensado para los datos demo).

Uso (desde la carpeta backend):

    python scripts/fusionar_demo.py                 # muestra qué haría, sin cambiar nada
    python scripts/fusionar_demo.py --aplicar       # hace un backup y aplica la fusión
    python scripts/fusionar_demo.py --db ruta.sqlite3 --aplicar

Criterio: se agrupan por nombre de empresa normalizado (sin acentos ni mayúsculas).
- Gestiones ABIERTAS de la misma empresa: quedan en una sola (la que tiene contacto y más mensajes).
- Contactos de la misma empresa: quedan en uno solo (el que tiene más gestiones).
No se borra nada: lo fusionado queda marcado y sus mensajes pasan al destino.
Es idempotente: correrlo dos veces no cambia nada la segunda vez.
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.db import connect, init_db  # noqa: E402
from app.business_v3 import init_v3  # noqa: E402
from app.business_v4 import ESTADOS_ABIERTOS, init_v4, merge_contacts, merge_fichas, norm_name  # noqa: E402


def plan(con):
    marks = ','.join('?' * len(ESTADOS_ABIERTOS))
    fichas = con.execute(f'''SELECT f.id,f.codigo,f.cliente,f.oportunidad_id,
                (SELECT COUNT(*) FROM bandeja_consultas b WHERE b.ficha_id=f.id) AS mensajes
                FROM fichas_consulta f WHERE f.estado_gestion IN ({marks}) ORDER BY f.id''', ESTADOS_ABIERTOS).fetchall()
    groups = {}
    for f in fichas:
        groups.setdefault(norm_name(f['cliente']), []).append(dict(f))
    case_merges = []
    for items in groups.values():
        if len(items) < 2:
            continue
        items.sort(key=lambda f: (f['oportunidad_id'] is None, -f['mensajes'], f['id']))
        destino = items[0]
        case_merges += [(f, destino) for f in items[1:]]
    return case_merges


def contact_plan(con):
    rows = con.execute('''SELECT o.id,o.cliente,(SELECT COUNT(*) FROM fichas_consulta f WHERE f.oportunidad_id=o.id) AS gestiones
                          FROM oportunidades o WHERE o.fusionada_con IS NULL ORDER BY o.id''').fetchall()
    groups = {}
    for r in rows:
        groups.setdefault(norm_name(r['cliente']), []).append(dict(r))
    merges = []
    for items in groups.values():
        if len(items) < 2:
            continue
        items.sort(key=lambda r: (-r['gestiones'], r['id']))
        merges += [(r, items[0]) for r in items[1:]]
    return merges


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', default=str(BACKEND / 'data' / 'impulso.sqlite3'))
    parser.add_argument('--aplicar', action='store_true', help='aplica los cambios (por defecto solo muestra el plan)')
    args = parser.parse_args()
    db = Path(args.db)
    if not db.exists():
        sys.exit(f'No existe la base {db}')
    if args.aplicar:
        backups = BACKEND.parent / 'backups'
        backups.mkdir(exist_ok=True)
        target = backups / f'impulso_pre_fusion_{datetime.now():%Y%m%d_%H%M%S}.sqlite3'
        shutil.copy2(db, target)
        print(f'Backup: {target}')
    # Asegura el esquema V4 (migraciones aditivas).
    init_db(db)
    init_v3(db)
    init_v4(db)
    with connect(db) as con:
        cases = plan(con)
        print(f'Gestiones a fusionar: {len(cases)}')
        for src, dst in cases:
            print(f"  {src['codigo']} ({src['cliente']}, {src['mensajes']} msj) → {dst['codigo']}")
        if args.aplicar:
            con.execute('BEGIN IMMEDIATE')
            for src, dst in cases:
                merge_fichas(con, src['id'], dst['id'])
        contacts = contact_plan(con)
        print(f'Contactos a unificar: {len(contacts)}')
        for src, dst in contacts:
            print(f"  #{src['id']} {src['cliente']} → #{dst['id']}")
        if args.aplicar:
            for src, dst in contacts:
                merge_contacts(con, src['id'], dst['id'])
    print('Listo.' if args.aplicar else 'Simulación: no se cambió nada. Usá --aplicar para ejecutar.')


if __name__ == '__main__':
    main()
