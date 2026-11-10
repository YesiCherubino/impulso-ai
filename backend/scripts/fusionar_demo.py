"""Fusiona gestiones y contactos duplicados de la base (pensado para los datos demo).

Uso (desde la carpeta backend):

    python scripts/fusionar_demo.py                 # muestra qué haría, sin cambiar nada
    python scripts/fusionar_demo.py --aplicar       # hace un backup y aplica la fusión
    python scripts/fusionar_demo.py --db ruta.sqlite3 --aplicar

Criterio: se agrupan por nombre de empresa normalizado (sin acentos ni mayúsculas).
- Gestiones ABIERTAS de la misma empresa: quedan en una sola (la que tiene contacto y más mensajes).
- Contactos de la misma empresa: quedan en uno solo (el que tiene más gestiones).
No se borra nada: lo fusionado queda marcado y sus mensajes pasan al destino.
Lo mismo se puede hacer desde Administración → Datos de prueba → Unificar duplicados.
Es idempotente: correrlo dos veces no cambia nada la segunda vez.
"""
import argparse
import shutil
import sys
from datetime import datetime
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

from app.db import connect, init_db  # noqa: E402
from app.business_v3 import init_v3  # noqa: E402
from app.business_v4 import init_v4, plan_case_merges, plan_contact_merges, apply_merge_plan  # noqa: E402
from app.escala import refresh_case_stats  # noqa: E402


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
        cases = plan_case_merges(con)
        print(f'Gestiones a fusionar: {len(cases)}')
        for src, dst in cases:
            print(f"  {src['codigo']} ({src['cliente']}, {src['mensajes']} msj) → {dst['codigo']}")
        contacts = plan_contact_merges(con)
        print(f'Contactos a unificar (antes de fusionar gestiones): {len(contacts)}')
        for src, dst in contacts:
            print(f"  #{src['id']} {src['cliente']} → #{dst['id']}")
        if args.aplicar:
            con.execute('BEGIN IMMEDIATE')
            result = apply_merge_plan(con)
            refresh_case_stats(con)
            print(f"Aplicado: {result['gestiones_fusionadas']} gestiones fusionadas, {result['contactos_unificados']} contactos unificados.")
    print('Listo.' if args.aplicar else 'Simulación: no se cambió nada. Usá --aplicar para ejecutar.')


if __name__ == '__main__':
    main()
