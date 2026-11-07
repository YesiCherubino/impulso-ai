"""SQLite local de demostración. No contiene información real de clientes."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS oportunidades (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 cliente TEXT NOT NULL,
 contacto TEXT NOT NULL,
 producto TEXT NOT NULL,
 cantidad INTEGER,
 monto_estimado_usd REAL,
 estado TEXT NOT NULL,
 creada_el TEXT NOT NULL,
 ultimo_contacto TEXT NOT NULL,
 notas TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS interacciones (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 oportunidad_id INTEGER NOT NULL REFERENCES oportunidades(id),
 tipo TEXT NOT NULL,
 descripcion TEXT NOT NULL,
 fecha TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interacciones_oportunidad ON interacciones(oportunidad_id);
"""

# Los nombres, contactos y montos son completamente ficticios.
SEED = [
 ("Aurora Cosmética", "Lucía Torres", "Crema corporal 250 ml", 3000, 12000, "cotizada", 12, 8, "Cotización enviada; consultar confirmación de envase."),
 ("Nova Beauty", "Martín Álvarez", "Shampoo 350 ml", 5000, 18500, "negociacion", 15, 2, "Pidió revisar especificaciones de empaque."),
 ("Natural Care", "Valentina Ríos", "Jabón líquido 500 ml", 2000, 7400, "contactada", 20, 12, "Pendiente confirmar fecha tentativa."),
 ("Esencia Sur", "Carolina Ponce", "Perfume 100 ml", 1500, 15800, "nueva", 5, 5, "Consulta inicial por elaboración de marca propia."),
 ("Botánica Studio", "Andrés Molina", "Máscara capilar 300 ml", 4000, 11200, "cotizada", 18, 9, "Aguardando respuesta a presupuesto."),
 ("Luna Natural", "Florencia Vega", "Crema facial 50 ml", 1000, 6100, "contactada", 8, 1, "Enviamos ficha técnica de referencia."),
 ("Oliva Labs", "Federico Paz", "Gel de ducha 400 ml", 6000, 16700, "ganada", 30, 4, "Pedido confirmado; caso cerrado en esta demo."),
 ("Vita Belle", "Sofía Acosta", "Acondicionador 250 ml", 2500, 9200, "perdida", 40, 25, "Cliente postergó proyecto; caso cerrado en esta demo."),
]

def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as con:
        con.executescript(SCHEMA)
        if con.execute("SELECT COUNT(*) FROM oportunidades").fetchone()[0]:
            return
        today = date.today()
        for cliente, contacto, producto, cantidad, monto, estado, dias_creado, dias_contacto, notas in SEED:
            creada = today - timedelta(days=dias_creado)
            ultimo = today - timedelta(days=dias_contacto)
            cur = con.execute("""INSERT INTO oportunidades
              (cliente, contacto, producto, cantidad, monto_estimado_usd, estado, creada_el, ultimo_contacto, notas)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (cliente, contacto, producto, cantidad, monto, estado, creada.isoformat(), ultimo.isoformat(), notas))
            con.execute("""INSERT INTO interacciones (oportunidad_id, tipo, descripcion, fecha)
              VALUES (?, ?, ?, ?)""", (cur.lastrowid, "consulta", "Consulta comercial recibida (dato ficticio).", creada.isoformat()))
            if ultimo > creada:
                tipo = "correo" if estado in ("cotizada", "contactada", "negociacion") else "nota"
                con.execute("""INSERT INTO interacciones (oportunidad_id, tipo, descripcion, fecha)
                  VALUES (?, ?, ?, ?)""", (cur.lastrowid, tipo, notas, ultimo.isoformat()))
