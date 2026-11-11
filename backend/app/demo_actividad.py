"""Actividad comercial de ejemplo sobre las consultas de prueba.

Para que una demo no muestre todo "sin atender" ni reportes en cero: asigna vendedores, registra respuestas,
genera cotizaciones (vigentes, vencidas y aceptadas) y cierra algunas gestiones, con fechas creíbles de las
últimas semanas. Solo toca consultas de prueba que nadie trabajó todavía (sin responsable, sin respuestas y sin
atender), así que correrlo de nuevo no duplica nada ni pisa lo que el equipo hizo a mano.
"""
import secrets
from datetime import datetime, timedelta, timezone

# Etapa a la que llega cada consulta trabajada, en orden. Las más nuevas quedan sin atender.
PLAN = ['concretada', 'cotizada', 'calificada', 'concretada', 'no_concretada', 'vencida', 'muestra_piloto',
        'cotizada', 'concretada', 'calificada', 'no_concretada', 'cotizada', 'concretada', 'vencida',
        'muestra_piloto', 'cotizada', 'concretada', 'calificada', 'cotizada', 'no_concretada', 'concretada',
        'cotizada', 'calificada', 'concretada']
SIN_TOCAR = 8             # las consultas más recientes quedan sin atender, como llegan en un día normal
MOTIVOS = ['Precio', 'Eligió otro proveedor', 'Plazo de entrega', 'Postergó el proyecto']
RESPUESTAS = [
    'Hola {nombre}, gracias por escribirnos. Para avanzar con la cotización necesitamos la cantidad estimada, el tipo de envase y si la fórmula es propia o la desarrollamos nosotros.',
    'Buen día {nombre}. Recibimos tu consulta. ¿Nos confirmás presentación y volumen del primer lote? Con eso te pasamos una propuesta.',
    'Hola {nombre}, gracias por el contacto. Te comparto los datos que necesitamos para cotizar: producto, cantidad, envase y plazo deseado.',
]


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec='seconds')


def _vendedores(con) -> list[str]:
    rows = [r['usuario'] for r in con.execute(
        "SELECT usuario FROM usuarios WHERE activo=1 AND eliminado_en IS NULL AND rol='ventas' ORDER BY id")]
    if not rows:
        rows = [r['usuario'] for r in con.execute(
            "SELECT usuario FROM usuarios WHERE activo=1 AND eliminado_en IS NULL ORDER BY id LIMIT 2")]
    return rows or ['']


def _evento(con, ficha_id, tipo, valor, detalle, usuario, cuando):
    con.execute('INSERT INTO gestion_eventos(ficha_id,tipo,valor,detalle,usuario,creado_en) VALUES (?,?,?,?,?,?)',
                (ficha_id, tipo, valor, detalle, usuario, _iso(cuando)))


def _items(con, ficha, k):
    """Líneas de cotización: servicios en dólares, o productos de marca en pesos para compras mayoristas."""
    precios = {r['codigo']: r for r in con.execute('SELECT * FROM productos WHERE activo=1')} if _tiene(con, 'productos', 'activo') \
        else {r['codigo']: r for r in con.execute('SELECT * FROM productos')}
    cant = int(ficha['cantidad'] or (2000 + (k % 5) * 1500))
    if ficha['tipo_consulta'] == 'compra_mayorista' and 'MA-CC250' in precios:
        lineas = [('MA-CC250', max(cant // 4, 300)), ('MA-SH350', max(cant // 4, 300))]
    else:
        lineas = [('SV-ELAB', cant), ('SV-ETIQ', 1)] + ([('SV-PILOTO', 1)] if k % 2 == 0 else [])
    out = []
    for cod, q in lineas:
        p = precios.get(cod)
        if p:
            out.append((p['id'], cod, p['descripcion'], p['unidad'], q, p['precio'], p['moneda']))
    return out


def _tiene(con, tabla, col):
    return col in {r[1] for r in con.execute(f'PRAGMA table_info({tabla})')}


def seed_actividad(con) -> int:
    """Devuelve cuántas gestiones de prueba se trabajaron."""
    fichas = con.execute('''SELECT DISTINCT f.* FROM fichas_consulta f
        JOIN bandeja_consultas b ON b.ficha_id=f.id JOIN fixtures_v3 fx ON fx.mensaje_id=b.id
        WHERE f.estado_gestion='sin_atender' AND COALESCE(f.responsable,'')=''
          AND NOT EXISTS (SELECT 1 FROM bandeja_consultas s WHERE s.ficha_id=f.id AND s.direccion='saliente')
          AND NOT EXISTS (SELECT 1 FROM cotizaciones q WHERE q.ficha_id=f.id)
        ORDER BY f.id''').fetchall()
    trabajables = fichas[:-SIN_TOCAR] if len(fichas) > SIN_TOCAR else []
    if not trabajables:
        return 0
    vendedores = _vendedores(con)
    now = datetime.now(timezone.utc)
    hechas = 0
    for k, f in enumerate(trabajables[:len(PLAN)]):
        etapa = PLAN[k]
        quien = vendedores[k % len(vendedores)]
        # Cuándo entró: las cerradas, hace 6 a 10 días (cierran dentro del mes); el resto, hace 2 a 20 días.
        dias = 6 + k % 5 if etapa in ('concretada', 'no_concretada') else (22 + k % 4 if etapa == 'vencida' else 2 + (k * 3) % 15)
        entro = now - timedelta(days=dias, hours=(k * 5) % 9)
        respondio = entro + timedelta(hours=1, minutes=10 + (k * 7) % 40)
        con.execute("UPDATE bandeja_consultas SET recibido_el=?, leido_en=?, estado='en_gestion' WHERE ficha_id=? AND direccion='entrante'",
                    (_iso(entro), _iso(entro + timedelta(minutes=30)), f['id']))
        msg = con.execute("SELECT * FROM bandeja_consultas WHERE ficha_id=? ORDER BY id LIMIT 1", (f['id'],)).fetchone()
        nombre = (f['contacto'] or '').split(' ')[0] or 'cómo estás'
        con.execute('''INSERT INTO bandeja_consultas (cliente,contacto,canal,texto,recibido_el,estado,leido_en,email_remitente,
                       telefono_remitente,asunto,ficha_id,oportunidad_id,direccion,usuario)
                       VALUES (?,?,?,?,?,'resuelta',?,?,?,?,?,?,'saliente',?)''',
                    (f['cliente'], f['contacto'], msg['canal'], RESPUESTAS[k % len(RESPUESTAS)].format(nombre=nombre),
                     _iso(respondio), _iso(respondio), msg['email_remitente'], msg['telefono_remitente'],
                     msg['asunto'] and f"Re: {msg['asunto']}", f['id'], f['oportunidad_id'], quien))
        con.execute('UPDATE fichas_consulta SET responsable=?, creada_en=?, actualizada_en=? WHERE id=?',
                    (quien, _iso(entro), _iso(respondio), f['id']))
        _evento(con, f['id'], 'responsable', quien, '', quien, respondio)
        _evento(con, f['id'], 'estado', 'calificada', '', quien, respondio + timedelta(hours=2))
        estado, cerrada, motivo, monto, moneda, qfecha = 'calificada', None, '', None, None, None
        if etapa != 'calificada':
            items = _items(con, f, k)
            if items:
                moneda = items[0][6]
                cotizo = entro + timedelta(days=1, hours=3) if etapa != 'vencida' else now - timedelta(days=20 + k % 3)
                validez = 15
                subtotal = round(sum(q * p for _, _, _, _, q, p, _ in items))
                iva = round(subtotal * 0.21)
                monto = float(subtotal + iva)
                numero = f"{f['codigo'].replace('CON-', 'COT-')}-1"
                aceptada = cotizo + timedelta(days=2 + k % 3) if etapa == 'concretada' else None
                cur = con.execute('''INSERT INTO cotizaciones(ficha_id,numero,fecha,validez_dias,moneda,incluye_iva,iva_pct,condiciones,notas,
                                     subtotal,iva,total,creada_por,creada_en,token,aceptada_en,aceptada_por)
                                     VALUES (?,?,?,?,?,1,21,'','',?,?,?,?,?,?,?,?)''',
                                  (f['id'], numero, cotizo.date().isoformat(), validez, moneda, subtotal, iva, monto, quien,
                                   _iso(cotizo), secrets.token_urlsafe(18), _iso(aceptada) if aceptada else None,
                                   (f['contacto'] or f['cliente']) if aceptada else ''))
                for pid, cod, desc, uni, q, p, _ in items:
                    con.execute('''INSERT INTO cotizacion_items(cotizacion_id,producto_id,codigo,descripcion,unidad,cantidad,precio_unitario,
                                   descuento_pct,importe) VALUES (?,?,?,?,?,?,?,0,?)''', (cur.lastrowid, pid, cod, desc, uni, q, p, round(q * p, 2)))
                qfecha = cotizo.date().isoformat()
                _evento(con, f['id'], 'cotizacion', numero, f'{moneda} {monto:,.0f}'.replace(',', '.'), quien, cotizo)
                _evento(con, f['id'], 'estado', 'cotizada', '', quien, cotizo)
                estado = 'cotizada'
                if etapa == 'muestra_piloto':
                    estado = 'muestra_piloto'
                    _evento(con, f['id'], 'estado', 'muestra_piloto', '', quien, cotizo + timedelta(days=2))
                elif etapa == 'concretada':
                    estado, cerrada = 'concretada', aceptada
                    _evento(con, f['id'], 'aceptacion', numero, f'{f["contacto"]} aceptó la cotización por el enlace', '', aceptada)
                    _evento(con, f['id'], 'estado', 'concretada', '', '', aceptada)
                elif etapa == 'no_concretada':
                    estado, cerrada, motivo = 'no_concretada', cotizo + timedelta(days=4), MOTIVOS[k % len(MOTIVOS)]
                    _evento(con, f['id'], 'estado', 'no_concretada', motivo, quien, cerrada)
        con.execute('''UPDATE fichas_consulta SET estado_gestion=?, cerrada_en=?, motivo_cierre=?, cotizacion_monto=?, cotizacion_moneda=?,
                       cotizacion_fecha=?, cotizacion_validez_dias=?, actualizada_en=? WHERE id=?''',
                    (estado, _iso(cerrada) if cerrada else None, motivo, monto, moneda or '', qfecha, 15 if qfecha else None,
                     _iso(cerrada or respondio), f['id']))
        # Seguimientos agendados para hoy en algunas cotizaciones abiertas.
        if etapa == 'cotizada' and k % 3 == 1:
            hora = now.replace(hour=13 + k % 6, minute=0, second=0, microsecond=0)
            con.execute('''INSERT INTO actividades_comerciales(ficha_id,oportunidad_id,titulo,tipo,inicio,fin,responsable,notas,estado,creada_en,actualizada_en)
                           VALUES (?,?,?,?,?,?,?,?,'programada',?,?)''',
                        (f['id'], f['oportunidad_id'], f'Llamar a {f["contacto"] or f["cliente"]} por la cotización', 'llamada',
                         _iso(hora), _iso(hora + timedelta(minutes=30)), quien, '', _iso(now), _iso(now)))
        hechas += 1
    from .escala import refresh_case_stats
    refresh_case_stats(con)
    return hechas
