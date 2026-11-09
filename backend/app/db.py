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
 notas TEXT NOT NULL DEFAULT '',
 tipo_consulta TEXT NOT NULL DEFAULT 'sin_clasificar',
 canal_origen TEXT NOT NULL DEFAULT 'Manual',
 presentacion TEXT NOT NULL DEFAULT '',
 packaging TEXT NOT NULL DEFAULT '',
 responsable TEXT NOT NULL DEFAULT '',
 fecha_seguimiento TEXT,
 motivo_seguimiento TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS interacciones (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 oportunidad_id INTEGER NOT NULL REFERENCES oportunidades(id),
 tipo TEXT NOT NULL,
 descripcion TEXT NOT NULL,
 fecha TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interacciones_oportunidad ON interacciones(oportunidad_id);
CREATE TABLE IF NOT EXISTS bandeja_consultas (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 cliente TEXT NOT NULL,
 contacto TEXT NOT NULL,
 canal TEXT NOT NULL DEFAULT 'WhatsApp (simulado)',
 texto TEXT NOT NULL,
 recibido_el TEXT NOT NULL,
 estado TEXT NOT NULL DEFAULT 'nueva' CHECK (estado IN ('nueva','en_gestion','resuelta')),
 oportunidad_id INTEGER REFERENCES oportunidades(id)
);
CREATE INDEX IF NOT EXISTS idx_bandeja_estado ON bandeja_consultas(estado);
CREATE TABLE IF NOT EXISTS notificaciones (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 clave TEXT NOT NULL UNIQUE,
 tipo TEXT NOT NULL CHECK(tipo IN ('mensaje', 'seguimiento')),
 referencia_id INTEGER NOT NULL,
 titulo TEXT NOT NULL,
 detalle TEXT NOT NULL,
 creada_en TEXT NOT NULL,
 activa INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_notificaciones_activas ON notificaciones(activa,creada_en);
CREATE TABLE IF NOT EXISTS notificaciones_lecturas (
 notificacion_id INTEGER NOT NULL REFERENCES notificaciones(id) ON DELETE CASCADE,
 usuario_id INTEGER NOT NULL,
 leida_en TEXT NOT NULL,
 PRIMARY KEY(notificacion_id,usuario_id)
);
CREATE TABLE IF NOT EXISTS consultas_analisis (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 consulta_id INTEGER NOT NULL REFERENCES bandeja_consultas(id),
 version INTEGER NOT NULL,
 resultado_json TEXT NOT NULL,
 borrador TEXT NOT NULL,
 generado_en TEXT NOT NULL,
 actualizado_en TEXT NOT NULL,
 UNIQUE(consulta_id, version)
);
CREATE INDEX IF NOT EXISTS idx_consultas_analisis ON consultas_analisis(consulta_id,version);
CREATE TABLE IF NOT EXISTS seguimientos_ia (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 oportunidad_id INTEGER NOT NULL REFERENCES oportunidades(id),
 version INTEGER NOT NULL,
 resultado_json TEXT NOT NULL,
 asunto TEXT NOT NULL,
 mensaje TEXT NOT NULL,
 generado_en TEXT NOT NULL,
 actualizado_en TEXT NOT NULL,
 UNIQUE(oportunidad_id, version)
);
CREATE INDEX IF NOT EXISTS idx_seguimientos_ia ON seguimientos_ia(oportunidad_id,version);



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

# Bandeja demostrativa: no está conectada a WhatsApp, Gmail ni otros canales reales.
INBOX_SEED = [
 ("Aurora Cosmética", "Martina", "Hola, somos Aurora Cosmética. Queremos desarrollar una crema corporal de 250 ml y producir 3.000 unidades con envase personalizado. ¿Podrían orientarnos sobre las opciones?", 1),
 ("Natural Care", "Valentina", "Hola, nos gustaría consultar por producción de 2.000 unidades de jabón líquido de 500 ml. ¿Qué información necesitan para preparar una cotización?", 2),
 ("Botánica Studio", "Andrés", "Buen día, enviamos las especificaciones del envase de la máscara capilar. ¿Nos confirman si necesitan algún dato adicional para avanzar?", 3),
 ("Nova Beauty", "Martín", "Hola, quería saber si pudieron revisar nuestra consulta sobre el shampoo de 350 ml. Necesitaríamos definir el packaging para avanzar con la propuesta.", 4),
 ("Estudio Luma", "Julia", "Buenas tardes, tenemos una marca nueva y buscamos fabricar 5.000 unidades de crema facial. Queremos consultar por fórmula, presentación y requisitos iniciales.", 5),
 ("Esencia Sur", "Carolina", "¿Trabajan con elaboración de perfumes para marca propia? Estamos evaluando un primer lote y queremos conocer las opciones de presentación.", 6),
 ("Oliva Labs", "Federico", "Hola, gracias por la información enviada. Ya tenemos todo lo necesario y confirmamos que vamos a continuar por el canal comercial habitual.", 7),
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
        # Migración aditiva para bases existentes: no elimina ningún dato.
        columns = {row['name'] for row in con.execute('PRAGMA table_info(oportunidades)')}
        additions = {
            'tipo_consulta': "TEXT NOT NULL DEFAULT 'sin_clasificar'",
            'canal_origen': "TEXT NOT NULL DEFAULT 'Manual'",
            'presentacion': "TEXT NOT NULL DEFAULT ''",
            'packaging': "TEXT NOT NULL DEFAULT ''",
            'responsable': "TEXT NOT NULL DEFAULT ''",
            'fecha_seguimiento': 'TEXT',
            'motivo_seguimiento': "TEXT NOT NULL DEFAULT ''",
        }
        for column, definition in additions.items():
            if column not in columns:
                con.execute(f'ALTER TABLE oportunidades ADD COLUMN {column} {definition}')
        # V2: migraciones aditivas. Los mensajes y contactos históricos no se eliminan.
        inbox_columns = {r['name'] for r in con.execute('PRAGMA table_info(bandeja_consultas)')}
        inbox_additions = {
            'leido_en': 'TEXT', 'email_remitente': "TEXT NOT NULL DEFAULT ''",
            'telefono_remitente': "TEXT NOT NULL DEFAULT ''", 'asunto': "TEXT NOT NULL DEFAULT ''",
            'ficha_id': 'INTEGER REFERENCES fichas_consulta(id)',
        }
        for column, definition in inbox_additions.items():
            if column not in inbox_columns:
                con.execute(f'ALTER TABLE bandeja_consultas ADD COLUMN {column} {definition}')
        for column, definition in {
            'email': "TEXT NOT NULL DEFAULT ''", 'telefono': "TEXT NOT NULL DEFAULT ''",
            'fecha_cierre': 'TEXT',
        }.items():
            if column not in columns:
                con.execute(f'ALTER TABLE oportunidades ADD COLUMN {column} {definition}')
        con.executescript("""
        CREATE TABLE IF NOT EXISTS fichas_consulta (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          codigo TEXT NOT NULL UNIQUE,
          oportunidad_id INTEGER REFERENCES oportunidades(id),
          titulo TEXT NOT NULL DEFAULT '',
          cliente TEXT NOT NULL DEFAULT '', contacto TEXT NOT NULL DEFAULT '',
          producto TEXT NOT NULL DEFAULT '', cantidad INTEGER,
          tipo_consulta TEXT NOT NULL DEFAULT 'sin_clasificar',
          presentacion TEXT NOT NULL DEFAULT '', packaging TEXT NOT NULL DEFAULT '',
          requisitos_json TEXT NOT NULL DEFAULT '[]', datos_faltantes_json TEXT NOT NULL DEFAULT '[]',
          resumen TEXT NOT NULL DEFAULT '',
          creada_en TEXT NOT NULL, actualizada_en TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_fichas_oportunidad ON fichas_consulta(oportunidad_id);
        CREATE INDEX IF NOT EXISTS idx_inbox_ficha ON bandeja_consultas(ficha_id);
        CREATE INDEX IF NOT EXISTS idx_inbox_email ON bandeja_consultas(email_remitente);
        CREATE INDEX IF NOT EXISTS idx_inbox_telefono ON bandeja_consultas(telefono_remitente);
        """)
        # No convertimos fichas existentes en datos nuevos inventados. Se generan
        # las fichas numeradas para los mensajes históricos con id estable.
        for row in con.execute('SELECT * FROM bandeja_consultas WHERE ficha_id IS NULL ORDER BY id').fetchall():
            stamp = row['recibido_el']
            cur = con.execute("""INSERT INTO fichas_consulta
                (codigo,oportunidad_id,titulo,cliente,contacto,creada_en,actualizada_en)
                VALUES ('PENDIENTE',?,?,?,?,?,?)""",
                (row['oportunidad_id'],f"Consulta de {row['cliente']}",row['cliente'],row['contacto'],stamp,stamp))
            ficha = cur.lastrowid
            con.execute('UPDATE fichas_consulta SET codigo=? WHERE id=?',
                        (f"CON-{stamp[:4]}-{ficha:05d}",ficha))
            con.execute('UPDATE bandeja_consultas SET ficha_id=? WHERE id=?',(ficha,row['id']))
        # Se agregan mensajes ficticios también a bases SQLite existentes.
        if not con.execute("SELECT COUNT(*) FROM bandeja_consultas").fetchone()[0]:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            for cliente, contacto, texto, horas in INBOX_SEED:
                estado = 'resuelta' if horas == 7 else ('en_gestion' if horas in (3, 4) else 'nueva')
                received = (now - timedelta(hours=horas)).isoformat(timespec='seconds')
                con.execute("""INSERT INTO bandeja_consultas(cliente, contacto, texto, recibido_el, estado)
                       VALUES (?, ?, ?, ?, ?)""", (cliente, contacto, texto, received, estado))
        for row in con.execute('SELECT * FROM bandeja_consultas WHERE ficha_id IS NULL ORDER BY id').fetchall():
            stamp = row['recibido_el']
            cur = con.execute("""INSERT INTO fichas_consulta
                (codigo,titulo,cliente,contacto,creada_en,actualizada_en)
                VALUES ('PENDIENTE',?,?,?,?,?)""",
                (f"Consulta de {row['cliente']}",row['cliente'],row['contacto'],stamp,stamp))
            ficha = cur.lastrowid
            con.execute('UPDATE fichas_consulta SET codigo=? WHERE id=?',
                        (f"CON-{stamp[:4]}-{ficha:05d}",ficha))
            con.execute('UPDATE bandeja_consultas SET ficha_id=? WHERE id=?',(ficha,row['id']))
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
