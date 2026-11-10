"""V4: IA con contexto completo, fusión, métricas unificadas, pipeline y calificación Pasmanter."""
from datetime import date, datetime, timedelta, timezone
import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.ai import ConsultaExtraida
from app.business_v4 import datos_a_confirmar, filtrar_faltantes, norm_name, parse_form_text
from app.db import connect
from app.escala import refresh_case_stats
from app.main import create_app

FORM = ('Solicitud desde el formulario de Pasmanter. Producto: Máscara capilar de 300 ml. '
        'Cantidad estimada: 5000 unidades. Localidad: CABA. Solicitamos información comercial.')


def fake_ai(calls, **over):
    def run(texto):
        calls.append(texto)
        base = dict(cliente='Botánica', contacto='', producto='Máscara capilar', cantidad=None,
                    requisitos=['Envase personalizado'],
                    datos_faltantes=['Cantidad de unidades requeridas', 'Si requiere desarrollo de fórmula'],
                    resumen='Consulta por máscara capilar.', respuesta_sugerida='Hola, ¿qué cantidad necesitan?',
                    tipo_consulta='fabricacion_terceros')
        base.update(over)
        return ConsultaExtraida(**base)
    return run


def new_msg(c, **kw):
    body = {'cliente': 'Botánica Studio', 'contacto': 'Andrés', 'canal': 'Correo',
            'email_remitente': 'andres@ejemplo.test', 'texto': 'Consulta general'}
    body.update(kw)
    r = c.post('/api/inbox/new', json=body)
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------- 1.1
def test_form_parser_extracts_fields():
    assert parse_form_text(FORM) == {'producto': 'Máscara capilar de 300 ml', 'cantidad': 5000, 'localidad': 'CABA'}
    assert parse_form_text('Hola, quiero trabajar con ustedes') == {}


def test_form_fields_go_to_ficha_and_ai_receives_full_thread(tmp_path):
    app = create_app(tmp_path / 'v4.sqlite3')
    with TestClient(app) as c:
        form = new_msg(c, canal='Formulario web', texto=FORM)
        ws = new_msg(c, canal='WhatsApp', email_remitente='andres@ejemplo.test',
                     texto='Les compartimos más información. El envase sería personalizado.')
        assert ws['ficha_id'] == form['ficha_id']
        ficha = c.get(f"/api/fichas/{form['ficha_id']}").json()
        assert ficha['cantidad'] == 5000 and ficha['localidad'] == 'CABA'
        assert 'cantidad' in ficha['campos_editados']
        calls = []
        app.state.analizar_consulta = fake_ai(calls)
        r = c.post(f"/api/inbox/{ws['id']}/analysis", json={'regenerar': False})
        assert r.status_code == 200, r.text
        context = calls[0]
        assert 'Cantidad (unidades): 5000' in context
        assert 'Formulario web' in context and 'WhatsApp' in context
        assert 'MENSAJE A RESPONDER' in context
        result = r.json()['resultado']
        assert result['cantidad'] == 5000
        assert not any('cantidad' in x.lower() for x in result['datos_faltantes'])
        assert 'Si requiere desarrollo de fórmula' in result['datos_faltantes']


def test_ai_fills_empty_fields_but_never_overwrites_manual_edits(tmp_path):
    app = create_app(tmp_path / 'v4.sqlite3')
    with TestClient(app) as c:
        m = new_msg(c, texto='Queremos fabricar shampoo para nuestra marca.')
        fid = m['ficha_id']
        calls = []
        app.state.analizar_consulta = fake_ai(calls, producto='Shampoo', cantidad=12000, presentacion='350 ml')
        c.post(f"/api/inbox/{m['id']}/analysis", json={})
        f = c.get(f'/api/fichas/{fid}').json()
        assert (f['producto'], f['cantidad'], f['presentacion']) == ('Shampoo', 12000, '350 ml')
        assert f['tipo_consulta'] == 'fabricacion_terceros' and f['tipo_sugerido_ia'] == 1
        edit = {k: f[k] for k in ('titulo', 'cliente', 'contacto', 'producto', 'tipo_consulta', 'presentacion', 'packaging',
                                  'requisitos', 'datos_faltantes', 'resumen')}
        r = c.post(f'/api/fichas/{fid}/edit', json={**edit, 'cantidad': 15000, 'formula': 'propia'})
        assert r.status_code == 200, r.text
        assert r.json()['formula'] == 'propia'
        app.state.analizar_consulta = fake_ai(calls, producto='Shampoo sólido', cantidad=9000)
        c.post(f"/api/inbox/{m['id']}/analysis", json={'regenerar': True})
        f = c.get(f'/api/fichas/{fid}').json()
        assert f['cantidad'] == 15000          # editado a mano: protegido
        assert f['producto'] == 'Shampoo sólido'  # completado por IA: se puede regenerar
        assert f['formula'] == 'propia'


def test_filtrar_faltantes_and_datos_a_confirmar():
    ficha = {'producto': 'Crema', 'cantidad': 3000, 'presentacion': '', 'tipo_consulta': 'fabricacion_terceros',
             'formula': 'sin_especificar', 'packaging': '', 'marca_registrada': 'si', 'registro_anmat': 'sin_especificar',
             'destino': '', 'pais_destino': '', 'plazo_deseado': ''}
    assert filtrar_faltantes(['Cantidad de unidades', 'Presentación deseada', 'Marca'], ficha) == ['Presentación deseada']
    missing = datos_a_confirmar(ficha)
    assert 'Cantidad estimada' not in missing and 'Presentación (ml/g)' in missing
    assert '¿Tiene marca registrada?' not in missing and 'Registro ANMAT' in missing
    assert datos_a_confirmar({**ficha, 'tipo_consulta': 'no_comercial'}) == []


# --------------------------------------------------------------------------- 1.2
def test_merge_moves_everything_and_hides_origin(tmp_path):
    with TestClient(create_app(tmp_path / 'v4.sqlite3')) as c:
        a = new_msg(c, cliente='Nova Beauty', email_remitente='a@nova.test', texto='Consulta por shampoo de 350 ml.')
        b = new_msg(c, cliente='NOVA  beauty', email_remitente='b@nova.test', canal='WhatsApp',
                    texto='¿Pudieron revisar lo del shampoo?')
        assert a['ficha_id'] != b['ficha_id']
        dup = c.get(f"/api/fichas/{a['ficha_id']}").json()['duplicados']
        assert b['ficha_id'] in [d['id'] for d in dup]  # también detecta la Nova Beauty del seed
        c.post('/api/calendar/events', json={'titulo': 'Llamar', 'tipo': 'llamada', 'ficha_id': b['ficha_id'],
                                             'inicio': datetime.now(timezone.utc).isoformat()})
        c.post(f"/api/fichas/{b['ficha_id']}/checklists", json={'requisitos': [{'text': 'Envase 350 ml', 'done': False}], 'faltantes': []})
        r = c.post(f"/api/fichas/{b['ficha_id']}/merge", json={'destino_id': a['ficha_id']})
        assert r.status_code == 200, r.text
        dest = c.get(f"/api/fichas/{a['ficha_id']}").json()
        assert len(dest['mensajes']) == 2
        assert any(x['text'] == 'Envase 350 ml' for x in c.get(f"/api/fichas/{a['ficha_id']}/checklists").json()['requisitos'])
        assert c.get('/api/calendar/events').json()[0]['ficha_id'] == a['ficha_id']
        assert b['ficha_id'] not in [f['id'] for f in c.get('/api/fichas').json()]
        with connect(tmp_path / 'v4.sqlite3') as con:
            row = con.execute('SELECT estado_gestion,motivo_cierre FROM fichas_consulta WHERE id=?', (b['ficha_id'],)).fetchone()
        assert row['estado_gestion'] == 'fusionada' and dest['codigo'] in row['motivo_cierre']
        # Un mensaje nuevo del remitente fusionado va a la gestión de destino.
        again = new_msg(c, cliente='Nova Beauty', email_remitente='b@nova.test', canal='WhatsApp', texto='Otra pregunta más.')
        assert again['ficha_id'] == a['ficha_id']
        assert c.post(f"/api/fichas/{b['ficha_id']}/merge", json={'destino_id': a['ficha_id']}).status_code == 409


def test_merge_script_unifies_demo_duplicates(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_ENABLED', 'true')
    monkeypatch.setenv('ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('ADMIN_PASSWORD', 'una-clave-larga-segura-v4')
    db = tmp_path / 'demo.sqlite3'
    with TestClient(create_app(db)) as c:
        token = c.post('/api/auth/login', json={'username': 'admin', 'password': 'una-clave-larga-segura-v4'}).json()['token']
        assert c.post('/api/demo/seed', headers={'X-Session-Token': token}, json={'incluir_web': True}).status_code == 200
    with connect(db) as con:
        before = con.execute("SELECT COUNT(*) FROM fichas_consulta WHERE cliente='Botánica Studio' AND estado_gestion<>'fusionada'").fetchone()[0]
    assert before >= 2  # V3 demo + mensaje histórico (+ contacto histórico con su gestión)
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'fusionar_demo.py'
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    out = subprocess.run([sys.executable, str(script), '--db', str(db), '--aplicar'], capture_output=True, text=True,
                         encoding='utf-8', env=env)
    assert out.returncode == 0, out.stderr
    with connect(db) as con:
        names = [norm_name(r['cliente']) for r in con.execute(
            "SELECT cliente FROM fichas_consulta WHERE estado_gestion IN ('sin_atender','calificada','cotizada','muestra_piloto')")]
        assert len(names) == len(set(names))
        contacts = [norm_name(r['cliente']) for r in con.execute('SELECT cliente FROM oportunidades WHERE fusionada_con IS NULL')]
        assert len(contacts) == len(set(contacts))
        botanica = con.execute("SELECT id FROM fichas_consulta WHERE cliente='Botánica Studio' AND estado_gestion<>'fusionada'").fetchall()
        assert len(botanica) == 1
        assert con.execute('SELECT COUNT(*) FROM bandeja_consultas WHERE ficha_id=?', (botanica[0]['id'],)).fetchone()[0] == 4
    second = subprocess.run([sys.executable, str(script), '--db', str(db), '--aplicar'], capture_output=True, text=True,
                            encoding='utf-8', env=env)
    assert 'Gestiones a fusionar: 0' in second.stdout and 'Contactos a unificar (antes de fusionar gestiones): 0' in second.stdout


# --------------------------------------------------------------------------- 1.3
def test_reports_match_finalizados_and_agenda(tmp_path):
    with TestClient(create_app(tmp_path / 'v4.sqlite3')) as c:
        m1 = new_msg(c, cliente='Uno', email_remitente='uno@x.test', texto='Consulta uno de prueba')
        m2 = new_msg(c, cliente='Dos', email_remitente='dos@x.test', texto='Consulta dos de prueba')
        assert c.post(f"/api/fichas/{m1['ficha_id']}/estado", json={'estado': 'concretada'}).status_code == 200
        assert c.post(f"/api/fichas/{m2['ficha_id']}/estado", json={'estado': 'no_concretada'}).status_code == 422
        assert c.post(f"/api/fichas/{m2['ficha_id']}/estado", json={'estado': 'no_concretada', 'motivo': 'Precio'}).status_code == 200
        report = c.get('/api/reports/summary?period=todos').json()
        fichas = c.get('/api/fichas').json()
        # Incluye la ficha legacy creada por la migración para la oportunidad ganada del seed.
        assert report['indicadores']['concretadas'] == sum(1 for f in fichas if f['estado_gestion'] == 'concretada')
        assert report['indicadores']['no_concretadas'] == sum(1 for f in fichas if f['estado_gestion'] == 'no_concretada')
        assert report['motivos_no_concretadas'].get('Precio') == 1
        # Seguimiento vencido: aparece en Reportes y en la Agenda (misma fuente).
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        ev = c.post('/api/calendar/events', json={'titulo': 'Llamar a Dos', 'tipo': 'seguimiento', 'inicio': yesterday,
                                                  'ficha_id': m1['ficha_id']}).json()
        report = c.get('/api/reports/summary?period=todos').json()
        assert report['indicadores']['seguimientos_vencidos'] == 1
        assert ev['id'] in [e['id'] for e in c.get('/api/calendar/events').json()]
        assert report['seguimientos_vencidos_detalle'][0]['id'] == ev['id']


def test_contact_followup_creates_agenda_activity(tmp_path):
    with TestClient(create_app(tmp_path / 'v4.sqlite3')) as c:
        due = (date.today() - timedelta(days=1)).isoformat()
        assert c.post('/api/opportunities/2/follow-up', json={'fecha_seguimiento': due, 'motivo_seguimiento': 'Llamar'}).status_code == 200
        events = [e for e in c.get('/api/calendar/events').json() if e['oportunidad_id'] == 2]
        assert len(events) == 1 and events[0]['estado'] == 'programada' and events[0]['inicio'].startswith(due)
        assert c.get('/api/reports/summary?period=todos').json()['indicadores']['seguimientos_vencidos'] >= 1
        c.post('/api/opportunities/2/interactions', json={'tipo': 'llamada', 'descripcion': 'Llamada hecha'})
        events = [e for e in c.get('/api/calendar/events').json() if e['oportunidad_id'] == 2]
        assert events[0]['estado'] == 'realizada'


def test_closed_case_leaves_inbox_until_new_message(tmp_path):
    db = tmp_path / 'v4.sqlite3'
    with TestClient(create_app(db)) as c:
        m = new_msg(c, cliente='Aurora', email_remitente='aurora@x.test', texto='Queremos crema corporal.')
        c.post(f"/api/fichas/{m['ficha_id']}/estado", json={'estado': 'concretada'})
        thread = next(t for t in c.get('/api/inbox/threads').json() if any(x['id'] == m['id'] for x in t['mensajes']))
        assert thread['cerrada'] is True and thread['mensaje_tras_cierre'] is False
        # Mensaje posterior en la misma gestión cerrada (por ejemplo, movido a mano).
        later = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec='seconds')
        with connect(db) as con:
            con.execute('''INSERT INTO bandeja_consultas(cliente,contacto,canal,texto,recibido_el,estado,ficha_id)
                           VALUES ('Aurora','Martina','WhatsApp','Hola, ¿siguen?',?, 'nueva', ?)''', (later, m['ficha_id']))
        thread = next(t for t in c.get('/api/inbox/threads').json() if any(x['id'] == m['id'] for x in t['mensajes']))
        assert thread['mensaje_tras_cierre'] is True


# --------------------------------------------------------------------------- 1.4 / 2.x
def test_pipeline_states_and_legacy_mapping(tmp_path):
    db = tmp_path / 'v4.sqlite3'
    with TestClient(create_app(db)) as c:
        m = new_msg(c, texto='Consulta para cotizar crema')
        fid = m['ficha_id']
        assert c.post(f'/api/fichas/{fid}/estado', json={'estado': 'en_gestion'}).json()['estado'] == 'calificada'
        assert c.post(f'/api/fichas/{fid}/estado', json={'estado': 'cotizada'}).status_code == 422
        r = c.post(f'/api/fichas/{fid}/estado', json={'estado': 'cotizada', 'cotizacion_monto': 1500000,
                                                     'cotizacion_moneda': 'ARS', 'cotizacion_validez_dias': 15})
        assert r.status_code == 200, r.text
        f = c.get(f'/api/fichas/{fid}').json()
        assert (f['cotizacion_monto'], f['cotizacion_moneda'], f['cotizacion_validez_dias']) == (1500000, 'ARS', 15)
        assert f['cotizacion_fecha'] == date.today().isoformat()
        assert c.post(f'/api/fichas/{fid}/estado', json={'estado': 'muestra_piloto'}).status_code == 200
        embudo = {e['estado']: e for e in c.get('/api/reports/summary?period=todos').json()['embudo']}
        assert embudo['muestra_piloto']['montos'] == {'ARS': 1500000}
    with connect(db) as con:
        con.execute("UPDATE fichas_consulta SET estado_gestion='en_gestion' WHERE id=?", (fid,))
    with TestClient(create_app(db)) as c:
        assert c.get(f'/api/fichas/{fid}').json()['estado_gestion'] == 'calificada'
        # La oportunidad perdida del seed tiene su gestión cerrada (migración de históricos).
        lost = [f for f in c.get('/api/fichas').json() if f['cliente'] == 'Vita Belle']
        assert lost and lost[0]['estado_gestion'] == 'no_concretada'


def test_bajo_minimo_and_settings(tmp_path):
    app = create_app(tmp_path / 'v4.sqlite3')
    with TestClient(app) as c:
        m = new_msg(c, texto='Queremos 2000 unidades de sérum con nuestra fórmula.')
        fid = m['ficha_id']
        f = c.get(f'/api/fichas/{fid}').json()
        edit = {k: f[k] for k in ('titulo', 'cliente', 'contacto', 'producto', 'presentacion', 'packaging',
                                  'requisitos', 'datos_faltantes', 'resumen')}
        f = c.post(f'/api/fichas/{fid}/edit', json={**edit, 'cantidad': 2000, 'tipo_consulta': 'fabricacion_terceros'}).json()
        assert f['bajo_minimo'] is True and f['lote_minimo'] == 10000
        f = c.post(f'/api/fichas/{fid}/edit', json={**edit, 'cantidad': 2000, 'tipo_consulta': 'mayorista'}).json()
        assert f['bajo_minimo'] is False
        f = c.post(f'/api/fichas/{fid}/edit', json={**edit, 'cantidad': 2000, 'tipo_consulta': 'elaboracion_envasado'}).json()
        thread = next(t for t in c.get('/api/inbox/threads').json() if t['gestion'] and t['gestion']['id'] == fid)
        assert thread['gestion']['bajo_minimo'] is True
        calls = []
        app.state.analizar_consulta = fake_ai(calls)
        c.post(f"/api/inbox/{m['id']}/analysis", json={'informar_lote_minimo': True})
        assert 'lote mínimo de producción es de 10.000 unidades' in calls[-1]
        c.post(f"/api/inbox/{m['id']}/analysis", json={'regenerar': True})
        assert 'INDICACIÓN DEL VENDEDOR' not in calls[-1]


def test_reply_registers_outgoing_and_response_time(tmp_path):
    db = tmp_path / 'v4.sqlite3'
    with TestClient(create_app(db)) as c:
        m = new_msg(c, cliente='Luna', email_remitente='luna@x.test', texto='Hola, consulta por crema facial.')
        old = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(timespec='seconds')
        with connect(db) as con:
            con.execute('UPDATE bandeja_consultas SET recibido_el=? WHERE id=?', (old, m['id']))
            refresh_case_stats(con, [m['ficha_id']])  # escritura directa en la base: se refrescan los resúmenes
        report = c.get('/api/reports/summary?period=todos').json()
        assert any(a['ficha_id'] == m['ficha_id'] for a in report['alertas_sin_respuesta'])
        thread = next(t for t in c.get('/api/inbox/threads').json() if t['gestion'] and t['gestion']['id'] == m['ficha_id'])
        assert thread['respuesta']['pendiente'] is True and thread['respuesta']['horas'] >= 29
        r = c.post(f"/api/inbox/{m['id']}/reply", json={'texto': 'Gracias por escribirnos.', 'canal': 'Correo'})
        assert r.status_code == 201, r.text
        assert r.json()['direccion'] == 'saliente'
        thread = next(t for t in c.get('/api/inbox/threads').json() if t['gestion'] and t['gestion']['id'] == m['ficha_id'])
        assert thread['respuesta']['pendiente'] is False and thread['no_leidos'] == 0
        report = c.get('/api/reports/summary?period=todos').json()
        assert not any(a['ficha_id'] == m['ficha_id'] for a in report['alertas_sin_respuesta'])
        assert report['tiempo_primera_respuesta']['por_canal']['Correo']['promedio_horas'] >= 29
        notices = c.get('/api/notifications').json()['items']
        assert not any(n['referencia_id'] == r.json()['id'] and n['tipo'] == 'mensaje' for n in notices)


def test_owner_and_non_commercial(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_ENABLED', 'true')
    monkeypatch.setenv('ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('ADMIN_PASSWORD', 'una-clave-larga-segura-v4')
    with TestClient(create_app(tmp_path / 'v4.sqlite3')) as c:
        admin = {'X-Session-Token': c.post('/api/auth/login', json={'username': 'admin', 'password': 'una-clave-larga-segura-v4'}).json()['token']}
        c.post('/api/admin/users', headers=admin, json={'username': 'flor', 'name': 'Florencia', 'password': 'clave-de-ventas-segura', 'role': 'ventas'})
        flor = {'X-Session-Token': c.post('/api/auth/login', json={'username': 'flor', 'password': 'clave-de-ventas-segura'}).json()['token']}
        m = c.post('/api/inbox/new', headers=admin, json={'cliente': 'Envases SA', 'contacto': 'Diego', 'canal': 'Correo',
                   'email_remitente': 'd@envases.test', 'texto': 'Somos proveedores de envases y queremos presentarnos.'}).json()
        fid = m['ficha_id']
        # Un vendedor puede pasarle la gestión a un compañero (V5) pero no a un usuario inexistente.
        assert c.post(f'/api/fichas/{fid}/responsable', headers=flor, json={'responsable': 'admin'}).status_code == 200
        assert c.post(f'/api/fichas/{fid}/responsable', headers=flor, json={'responsable': 'nadie'}).status_code == 422
        assert c.post(f'/api/fichas/{fid}/responsable', headers=flor, json={'responsable': 'flor'}).json()['responsable'] == 'flor'
        assert {u['username'] for u in c.get('/api/users/responsables', headers=flor).json()} == {'admin', 'flor'}
        report = c.get('/api/reports/summary?period=todos', headers=flor).json()
        assert report['indicadores']['sin_atender'] == 1
        assert c.post(f'/api/fichas/{fid}/no-comercial', headers=flor).status_code == 200
        f = c.get(f'/api/fichas/{fid}', headers=flor).json()
        assert f['tipo_consulta'] == 'no_comercial' and f['estado_gestion'] == 'resuelta'
        report = c.get('/api/reports/summary?period=todos', headers=flor).json()
        assert report['indicadores']['sin_atender'] == 0 and report['indicadores']['consultas_recibidas'] == 0
        settings = c.post('/api/commercial/settings', headers=admin, json={'lote_minimo': 5000})
        assert settings.status_code == 200
        assert c.post('/api/commercial/settings', headers=flor, json={'lote_minimo': 1}).status_code == 403
        assert c.get('/api/commercial/settings', headers=flor).json()['lote_minimo'] == 5000


def test_new_contact_gets_a_case(tmp_path):
    with TestClient(create_app(tmp_path / 'v4.sqlite3')) as c:
        r = c.post('/api/opportunities', json={'cliente': 'Nueva SA', 'contacto': 'Ana', 'producto': 'Crema', 'cantidad': 12000})
        cases = c.get(f"/api/opportunities/{r.json()['id']}/fichas").json()
        assert len(cases) == 1 and cases[0]['estado_gestion'] == 'sin_atender' and cases[0]['cantidad'] == 12000
