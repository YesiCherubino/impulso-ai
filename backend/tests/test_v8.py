"""V8: crear contacto desde una gestión, monto concretado, preferencias personales de IA y listado de cotizaciones."""
from fastapi.testclient import TestClient

from app.ai import ConsultaExtraida
from app.main import create_app
from tests.test_v5 import setup, login, new_case
from tests.test_v6 import users


def quote(c, h, fid, monto=2, moneda='USD', **kw):
    r = c.post(f'/api/fichas/{fid}/cotizaciones', headers=h, json={'moneda': moneda, 'incluye_iva': False, **kw,
               'items': [{'descripcion': 'Elaboración', 'cantidad': 1000, 'precio_unitario': monto}]})
    assert r.status_code == 201, r.text
    return r.json()


def test_crear_contacto_y_monto(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        m = new_case(c, h, cliente='Cosmética Norte', email_remitente='ana@norte.test')
        fid = m['ficha_id']
        assert c.get(f'/api/fichas/{fid}', headers=h).json()['oportunidad_id'] is None
        r = c.post(f'/api/fichas/{fid}/crear-contacto', headers=h).json()
        assert r['creado'] is True
        opp = c.get(f"/api/opportunities/{r['oportunidad_id']}", headers=h).json()
        assert opp['cliente'] == 'Cosmética Norte'
        assert c.get(f'/api/fichas/{fid}', headers=h).json()['oportunidad_id'] == r['oportunidad_id']
        # Una segunda vez no duplica; otra gestión del mismo correo se vincula al mismo contacto.
        assert c.post(f'/api/fichas/{fid}/crear-contacto', headers=h).json() == {'oportunidad_id': r['oportunidad_id'], 'creado': False}
        hist = c.get(f'/api/fichas/{fid}/historial', headers=h).json()
        assert hist['eventos'][0]['tipo'] == 'contacto'
        # Monto concretado del período, por moneda.
        quote(c, h, fid, monto=3)
        c.post(f'/api/fichas/{fid}/estado', headers=h, json={'estado': 'concretada'})
        rep = c.get('/api/reports/summary?period=mes', headers=h).json()
        assert rep['monto_concretado'] == {'USD': 3000}
        det = c.get('/api/reports/detalle?indicador=monto_concretado&period=mes', headers=h).json()
        assert det['total'] == 1 and det['items'][0]['monto'] == 3000


def test_preferencias_ia_personales(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        hl, hg = users(c, h)
        perfiles = []
        c.app.state.analizar_consulta = None
        from app import ai
        monkeypatch.setattr(ai, 'analizar_consulta', lambda texto, profile=None: perfiles.append(profile) or ConsultaExtraida(
            cliente='X', contacto='', producto='Crema', cantidad=500, requisitos=[], datos_faltantes=[], resumen='r', respuesta_sugerida='Hola'))
        c.app.state.analizar_consulta = lambda texto: ai.analizar_consulta(texto, __import__('app.ia_personal', fromlist=['perfil']).perfil(path))
        # La base de la empresa la edita solo el administrador; cada uno edita la suya.
        assert c.get('/api/ai/settings', headers=hl).status_code == 403
        mine = c.get('/api/ai/mis-preferencias', headers=hl).json()
        assert mine['propias']['tono'] is None and mine['base']['tratamiento'] == 'vos'
        assert c.post('/api/ai/mis-preferencias', headers=hl, json={'tono': 'cercano', 'extension': None, 'signos_apertura': False,
                      'firma': 'Lucía · Ventas'}).json()['ok']
        mine = c.get('/api/ai/mis-preferencias', headers=hl).json()['propias']
        assert mine == {'tono': 'cercano', 'extension': None, 'signos_apertura': False, 'firma': 'Lucía · Ventas'}
        # La sugerencia usa las preferencias de quien la pide, sobre la base.
        m = new_case(c, h)
        c.post(f"/api/inbox/{m['id']}/analysis", headers=hl, json={'regenerar': True})
        c.post(f"/api/inbox/{m['id']}/analysis", headers=h, json={'regenerar': True})
        lucia, admin = perfiles[-2], perfiles[-1]
        assert lucia['tono'] == 'cercano' and lucia['signos_apertura'] == 0 and lucia['firma'] == 'Lucía · Ventas'
        assert lucia['extension'] == admin['extension'] and admin['firma'] == '' and admin['tono'] == 'profesional'
        assert 'Lucía · Ventas' in ai.personalized_instructions(lucia)


def test_listado_cotizaciones(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        hl, hg = users(c, h)
        a = new_case(c, h, cliente='Alfa', email_remitente='a@alfa.test')['ficha_id']
        b = new_case(c, h, cliente='Beta', email_remitente='b@beta.test')['ficha_id']
        d = new_case(c, h, cliente='Delta', email_remitente='d@delta.test')['ficha_id']
        c.post(f'/api/fichas/{a}/responsable', headers=h, json={'responsable': 'lucia'})
        quote(c, hl, a, monto=1)
        q2 = quote(c, hl, a, monto=2)                       # reemplaza a la primera
        qb = quote(c, h, b, monto=5, moneda='ARS', validez_dias=1)
        quote(c, h, d, monto=4)
        c.post(f'/api/fichas/{d}/estado', headers=h, json={'estado': 'no_concretada', 'motivo': 'Precio'})
        c.post(f"/api/publico/cotizaciones/{q2['token']}/aceptar", json={'nombre': 'Ana'})
        with __import__('app.db', fromlist=['connect']).connect(path) as con:
            con.execute("UPDATE cotizaciones SET fecha=date('now','-5 days') WHERE id=?", (qb['id'],))
        todo = c.get('/api/cotizaciones', headers=h).json()
        est = {i['numero']: i['estado'] for i in todo['items']}
        assert sorted(est.values()) == ['aceptada', 'no_concretada', 'reemplazada', 'vencida']
        r = todo['resumen']
        assert r['cantidad'] == 3 and r['aceptadas'] == 1 and r['aceptado'] == {'USD': 2000} and r['tasa'] == 33
        assert c.get('/api/cotizaciones?estado=vencida', headers=h).json()['total'] == 1
        assert c.get('/api/cotizaciones?q=beta', headers=h).json()['items'][0]['cliente'] == 'Beta'
        # Sin "ver todas", ventas ve solo lo suyo (lo que cotizó o lo que tiene asignado).
        c.post('/api/permisos', headers=h, json={'rol': 'ventas', 'permiso': 'ver_todas', 'permitido': False})
        mias = c.get('/api/cotizaciones', headers=hl).json()
        assert {i['cliente'] for i in mias['items']} == {'Alfa'}
        assert c.get('/api/cotizaciones?vendedor=lucia', headers=hg).json()['total'] == 2
        assert c.get('/api/export/cotizaciones', headers=h).json()['filename'].startswith('impulso_cotizaciones_')
