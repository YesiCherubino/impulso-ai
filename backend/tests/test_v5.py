"""V5: Mi día, seguimiento, importación, cotizador, plantillas, búsqueda, exportación, notas, documentos, metas e IA de texto."""
import base64
import io
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from app.ai import ConsultaExtraida
from app.db import connect
from app.escala import refresh_case_stats
from app.main import create_app


def login(c, monkeypatch=None):
    token = c.post('/api/auth/login', json={'username': 'admin', 'password': 'una-clave-larga-segura-v5'}).json()['token']
    return {'X-Session-Token': token}


def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_ENABLED', 'true')
    monkeypatch.setenv('ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('ADMIN_PASSWORD', 'una-clave-larga-segura-v5')
    monkeypatch.setenv('AI_DAILY_LIMIT', '50')
    return tmp_path / 'v5.sqlite3'


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def xlsx_bytes(rows):
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def new_case(c, h, **kw):
    body = {'cliente': 'Laboratorio Sur', 'contacto': 'Paula', 'canal': 'Correo', 'email_remitente': 'paula@sur.test',
            'texto': 'Queremos fabricar 3000 shampoo de 350 ml'}
    body.update(kw)
    r = c.post('/api/inbox/new', headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_mi_dia_and_followup_suggestion(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        msg = new_case(c, h)
        d = c.get('/api/mi-dia', headers=h).json()
        assert d['resumen']['sin_asignar_sin_responder'] >= 1
        assert any(x['ficha_id'] == msg['ficha_id'] and x['pendiente'] for x in d['sin_asignar'])
        # Tomarla (arrastrar a "Asignadas a mí") la mueve de columna.
        assert c.post(f"/api/fichas/{msg['ficha_id']}/responsable", headers=h, json={'responsable': 'admin'}).status_code == 200
        d = c.get('/api/mi-dia', headers=h).json()
        assert any(x['ficha_id'] == msg['ficha_id'] for x in d['asignadas'])
        assert not any(x['ficha_id'] == msg['ficha_id'] for x in d['sin_asignar'])
        assert d['resumen']['asignadas_sin_responder'] >= 1 and d['propio']
        # Se cotiza y se responde; luego pasan 6 días sin respuesta del cliente.
        r = c.post(f"/api/fichas/{msg['ficha_id']}/cotizaciones", headers=h, json={
            'moneda': 'USD', 'items': [{'descripcion': 'Elaboración', 'cantidad': 3000, 'precio_unitario': 0.85}]})
        assert r.status_code == 201, r.text
        assert c.post(f"/api/inbox/{msg['id']}/reply", headers=h, json={'texto': 'Te enviamos la cotización', 'canal': 'Correo'}).status_code == 201
        old = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat(timespec='seconds')
        with connect(path) as con:
            con.execute("UPDATE bandeja_consultas SET recibido_el=? WHERE ficha_id=?", (old, msg['ficha_id']))
            refresh_case_stats(con, [msg['ficha_id']])
        d = c.get('/api/mi-dia', headers=h).json()
        sug = [x for x in d['seguimientos_sugeridos'] if x['ficha_id'] == msg['ficha_id']]
        assert sug and sug[0]['dias'] >= 5 and sug[0]['cotizacion']['moneda'] == 'USD'
        assert any(x['ficha_id'] == msg['ficha_id'] and not x['pendiente'] for x in d['asignadas'])
        # El borrador de seguimiento le indica a la IA el objetivo.
        calls = []
        c.app.state.analizar_consulta = lambda t: calls.append(t) or ConsultaExtraida(
            cliente='Laboratorio Sur', contacto='Paula', producto='Shampoo', cantidad=3000, requisitos=[], datos_faltantes=[],
            resumen='r', respuesta_sugerida='Hola Paula, ¿pudiste ver la cotización?', tipo_consulta='fabricacion_terceros')
        r = c.post(f"/api/inbox/{msg['id']}/analysis", headers=h, json={'objetivo': 'seguimiento', 'regenerar': True})
        assert r.status_code == 200, r.text
        assert 'seguimiento' in calls[-1] and r.json()['borrador'].startswith('Hola Paula')


def test_import_clients_and_articles(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        with connect(path) as con:
            con.execute('''INSERT INTO oportunidades (cliente,contacto,producto,estado,ultimo_contacto,creada_el)
                           VALUES ('LABORATORIO SUR','Paula','Shampoo','nueva','2026-01-01','2026-01-01')''')
        data = xlsx_bytes([['Listado de clientes'], ['COD_CLIENT', 'RAZON_SOCI', 'CUIT', 'E_MAIL', 'LOCALIDAD'],
                           ['000501', 'Laboratorio Sur', '30-11111111-1', 'compras@sur.test', 'Rosario'],
                           ['000502', 'Perfumería Norte SA', '30-22222222-2', '', 'Salta'],
                           ['000503', '', '', '', '']])
        body = {'tipo': 'clientes', 'nombre': 'clientes.xlsx', 'contenido_base64': b64(data)}
        p = c.post('/api/import/preview', headers=h, json=body).json()
        assert p['mapeo']['codigo'] == 0 and p['mapeo']['cliente'] == 1 and p['mapeo']['cuit'] == 2
        assert p['validas'] == 2 and p['nuevos'] == 1 and p['actualizados'] == 1
        r = c.post('/api/import/aplicar', headers=h, json={**body, 'mapeo': p['mapeo']}).json()
        assert r['nuevos'] == 1 and r['actualizados'] == 1
        # Idempotente: la segunda vez solo actualiza.
        assert c.post('/api/import/aplicar', headers=h, json={**body, 'mapeo': p['mapeo']}).json()['nuevos'] == 0
        with connect(path) as con:
            sur = con.execute("SELECT * FROM oportunidades WHERE codigo_tango='000501'").fetchone()
            assert sur['cuit'] == '30-11111111-1' and sur['localidad'] == 'Rosario' and sur['es_cliente'] == 1
            norte = con.execute("SELECT id FROM oportunidades WHERE codigo_tango='000502'").fetchone()
            assert not con.execute('SELECT 1 FROM fichas_consulta WHERE oportunidad_id=?', (norte['id'],)).fetchone()
        # Un reinicio no le crea gestiones a los clientes importados.
    with TestClient(create_app(path)) as c:
        with connect(path) as con:
            assert not con.execute('SELECT 1 FROM fichas_consulta WHERE oportunidad_id=?', (norte['id'],)).fetchone()
        h = login(c)
        csv = 'Código;Descripción;Precio;Moneda\nPX-1;Crema de manos 75 ml;"1.234,50";ARS\nPX-2;Serum 30 ml;12,5;USD\n'.encode('latin-1')
        body = {'tipo': 'articulos', 'nombre': 'lista.csv', 'contenido_base64': b64(csv)}
        p = c.post('/api/import/preview', headers=h, json=body).json()
        assert p['validas'] == 2 and p['muestra'][0]['precio'] == 1234.5 and p['muestra'][1]['moneda'] == 'USD'
        c.post('/api/import/aplicar', headers=h, json=body)
        found = c.get('/api/productos?q=serum', headers=h).json()['items']
        assert found[0]['codigo'] == 'PX-2' and found[0]['precio'] == 12.5
        t = c.get('/api/import/plantilla?tipo=articulos', headers=h).json()
        assert load_workbook(io.BytesIO(base64.b64decode(t['contenido_base64']))).active['A1'].value == 'COD_ARTICU'
        assert c.post('/api/import/preview', headers=h, json={**body, 'nombre': 'x.pdf'}).status_code == 422


def test_quote_pdf_and_state(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        msg = new_case(c, h)
        prods = c.get('/api/productos?q=marca%20a', headers=h).json()['items']
        assert prods
        r = c.post(f"/api/fichas/{msg['ficha_id']}/cotizaciones", headers=h, json={
            'moneda': 'ARS', 'incluye_iva': True, 'iva_pct': 21, 'condiciones': 'Pago a 30 días & <entrega> a convenir',
            'items': [{'producto_id': prods[0]['id'], 'codigo': prods[0]['codigo'], 'descripcion': prods[0]['descripcion'],
                       'cantidad': 100, 'precio_unitario': 1000, 'descuento_pct': 10}]})
        q = r.json()
        assert q['total'] == 108900.0 and q['numero'].startswith('COT-')
        f = c.get(f"/api/fichas/{msg['ficha_id']}", headers=h).json()
        assert f['estado_gestion'] == 'cotizada' and f['cotizacion_monto'] == 108900.0 and f['cotizacion_moneda'] == 'ARS'
        pdf = c.get(f"/api/cotizaciones/{q['id']}/pdf", headers=h).json()
        assert base64.b64decode(pdf['contenido_base64'])[:4] == b'%PDF'
        assert len(c.get(f"/api/fichas/{msg['ficha_id']}/cotizaciones", headers=h).json()) == 1


def test_templates_search_exports_notes_docs_goals_ai(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        msg = new_case(c, h)
        tpl = c.get('/api/plantillas', headers=h).json()
        assert {'datos', 'anmat', 'minimo'} <= {t['atajo'] for t in tpl}
        assert c.post('/api/plantillas', headers=h, json={'atajo': 'precio', 'titulo': 'Precios', 'texto': 'Hola {contacto}'}).status_code == 200
        res = c.get('/api/buscar?q=sur', headers=h).json()
        assert res['gestiones'] and res['contactos']
        for url in ('/api/export/gestiones?estado=todas', '/api/export/contactos', '/api/export/reporte?period=anio'):
            x = c.get(url, headers=h)
            assert x.status_code == 200, (url, x.text)
            load_workbook(io.BytesIO(base64.b64decode(x.json()['contenido_base64'])))
        before = c.get(f"/api/fichas/{msg['ficha_id']}", headers=h).json()['mensajes_count']
        assert c.post(f"/api/fichas/{msg['ficha_id']}/notas", headers=h, json={'texto': 'Consultar a I+D'}).status_code == 201
        assert c.post(f"/api/fichas/{msg['ficha_id']}/derivar", headers=h, json={'area': 'Comercio exterior'}).json()['derivada_a'] == 'Comercio exterior'
        notes = c.get(f"/api/fichas/{msg['ficha_id']}/notas", headers=h).json()
        assert len(notes) == 2 and notes[1]['area'] == 'Comercio exterior'
        assert c.get(f"/api/fichas/{msg['ficha_id']}", headers=h).json()['mensajes_count'] == before
        d = c.post('/api/documentos', headers=h, json={'nombre': 'catalogo.pdf', 'mime': 'application/pdf', 'contenido_base64': b64(b'%PDF-1.4 demo')}).json()
        r = c.post(f"/api/inbox/{msg['id']}/reply", headers=h, json={'texto': 'Te adjunto el catálogo', 'canal': 'Correo', 'adjuntos': [d['id']]})
        assert r.status_code == 201, r.text
        key = c.get(f"/api/inbox/{msg['id']}/conversation", headers=h).json()['key']
        conv = c.get(f'/api/inbox/conversations/{key}', headers=h).json()
        sent = [m for m in conv['mensajes'] if m['direccion'] == 'saliente'][-1]
        assert sent['adjuntos'][0]['nombre'] == 'catalogo.pdf'
        assert base64.b64decode(c.get(f"/api/documentos/{d['id']}", headers=h).json()['contenido_base64']).startswith(b'%PDF')
        mes = datetime.now().strftime('%Y-%m')
        assert c.post('/api/metas', headers=h, json={'usuario': 'admin', 'mes': mes, 'moneda': 'USD', 'monto': 50000}).status_code == 200
        c.post(f"/api/fichas/{msg['ficha_id']}/cotizaciones", headers=h, json={
            'moneda': 'USD', 'incluye_iva': False, 'items': [{'descripcion': 'Elaboración', 'cantidad': 1000, 'precio_unitario': 1}]})
        g = c.get(f'/api/metas?mes={mes}', headers=h).json()
        assert g['pronostico']['USD'] >= 350.0 and any(x['estado'] == 'cotizada' for x in g['pronostico_detalle'])
        assert any(v['metas'].get('USD') == 50000 for v in g['vendedores'])
        c.app.state.transformar_texto = lambda accion, texto: f'{accion}:{len(texto)}'
        assert c.post('/api/ia/texto', headers=h, json={'accion': 'traducir_en', 'texto': 'Hola'}).json()['texto'] == 'traducir_en:4'
        r = c.post('/api/ia/texto', headers=h, json={'accion': 'resumir', 'conversacion': key})
        assert r.status_code == 200 and r.json()['texto'].startswith('resumir:')


def test_reply_assigns_free_case_and_team_chat(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        for u in ('lucia', 'martin'):
            r = c.post('/api/admin/users', headers=h, json={'username': u, 'name': u.title(), 'password': 'clave-de-prueba-larga', 'role': 'ventas'})
            assert r.status_code in (200, 201), r.text
        hl = {'X-Session-Token': c.post('/api/auth/login', json={'username': 'lucia', 'password': 'clave-de-prueba-larga'}).json()['token']}
        hm = {'X-Session-Token': c.post('/api/auth/login', json={'username': 'martin', 'password': 'clave-de-prueba-larga'}).json()['token']}
        msg = new_case(c, h)
        # Lucía responde una consulta libre: queda asignada a ella.
        assert c.post(f"/api/inbox/{msg['id']}/reply", headers=hl, json={'texto': 'Hola', 'canal': 'Correo'}).status_code == 201
        assert c.get(f"/api/fichas/{msg['ficha_id']}", headers=h).json()['responsable'] == 'lucia'
        # Martín responde por ella (está ausente): no cambia el responsable.
        assert c.post(f"/api/inbox/{msg['id']}/reply", headers=hm, json={'texto': 'Sigo yo', 'canal': 'Correo'}).status_code == 201
        assert c.get(f"/api/fichas/{msg['ficha_id']}", headers=h).json()['responsable'] == 'lucia'
        # Un vendedor puede pasársela a otro; el nuevo responsable recibe un mensaje directo.
        base = c.get('/api/chat/resumen', headers=hm).json()
        assert c.post(f"/api/fichas/{msg['ficha_id']}/responsable", headers=hl, json={'responsable': 'martin'}).status_code == 200
        r = c.get(f"/api/chat/resumen?desde_id={base['ultimo_id']}", headers=hm).json()
        assert r['no_leidos'] == 1 and r['nuevos'][0]['directo'] and 'CON-' in r['nuevos'][0]['texto']
        # Canal #ventas, mención y enlace a la gestión por código.
        ventas = next(x for x in r['canales'] if x['tipo'] == 'canal')
        code = c.get(f"/api/fichas/{msg['ficha_id']}", headers=h).json()['codigo']
        sent = c.post(f"/api/chat/canales/{ventas['id']}/mensajes", headers=hl, json={'texto': f'@martin mirá {code}'}).json()
        assert sent['gestion']['codigo'] == code
        r2 = c.get(f"/api/chat/resumen?desde_id={r['ultimo_id']}", headers=hm).json()
        assert r2['nuevos'][0]['mencion']
        hist = c.get(f"/api/chat/canales/{ventas['id']}/mensajes", headers=hm).json()['mensajes']
        assert hist[-1]['texto'].startswith('@martin')
        c.post(f"/api/chat/canales/{ventas['id']}/leido", headers=hm, json={'ultimo_id': hist[-1]['id']})
        # Estado y equipo.
        assert c.post('/api/chat/estado', headers=hl, json={'estado': 'ausente', 'mensaje': 'En reunión'}).status_code == 200
        equipo = {u['usuario']: u for u in c.get('/api/chat/resumen', headers=hm).json()['equipo']}
        assert equipo['lucia']['estado'] == 'ausente' and equipo['martin']['estado'] == 'activo'
        # Mensajes directos privados.
        dm = c.post('/api/chat/directo', headers=hl, json={'usuario': 'martin'}).json()['id']
        assert c.get(f'/api/chat/canales/{dm}/mensajes', headers=h).status_code == 403
        # Retención: los mensajes viejos se borran.
        with connect(path) as con:
            con.execute("UPDATE chat_mensajes SET creado_en='2020-01-01T00:00:00+00:00'")
        assert c.post('/api/chat/retencion', headers=h, json={'dias': 90}).json()['dias'] == 90
        assert c.get(f"/api/chat/canales/{ventas['id']}/mensajes", headers=hm).json()['mensajes'] == []
        # Administración ve el tablero de otro vendedor.
        d = c.get('/api/mi-dia?usuario=martin', headers=h).json()
        assert d['usuario'] == 'martin' and not d['propio'] and any(x['ficha_id'] == msg['ficha_id'] for x in d['asignadas'])
        assert c.get('/api/mi-dia?usuario=martin', headers=hl).json()['usuario'] == 'lucia'
