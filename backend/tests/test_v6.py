"""V6: permisos por perfil, Ver como, detalle de reportes, historial, cotización online, cierres en #ventas y Mi día."""
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_v5 import setup, login, new_case


def users(c, h):
    for u, role in (('lucia', 'ventas'), ('gero', 'gerencia')):
        assert c.post('/api/admin/users', headers=h, json={'username': u, 'name': u.title(), 'password': 'clave-de-prueba-larga', 'role': role}).status_code in (200, 201)
    tok = lambda u: {'X-Session-Token': c.post('/api/auth/login', json={'username': u, 'password': 'clave-de-prueba-larga'}).json()['token']}
    return tok('lucia'), tok('gero')


def test_permissions_and_view_as(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        hl, hg = users(c, h)
        msg = new_case(c, h)
        # Gerencia no responde por defecto; con el permiso habilitado, sí.
        assert c.post(f"/api/inbox/{msg['id']}/reply", headers=hg, json={'texto': 'Hola', 'canal': 'Correo'}).status_code == 403
        matrix = c.get('/api/permisos', headers=h).json()
        assert matrix['perfiles']['gerencia']['responder'] is False and len(matrix['permisos']) == 10
        assert c.post('/api/permisos', headers=h, json={'rol': 'gerencia', 'permiso': 'responder', 'permitido': True}).status_code == 200
        assert c.post(f"/api/inbox/{msg['id']}/reply", headers=hg, json={'texto': 'Hola', 'canal': 'Correo'}).status_code == 201
        # Ventas sin "exportar" no descarga Excel.
        c.post('/api/permisos', headers=h, json={'rol': 'ventas', 'permiso': 'exportar', 'permitido': False})
        assert c.get('/api/export/contactos', headers=hl).status_code == 403
        assert c.get('/api/auth/me', headers=hl).json()['permisos']['exportar'] is False
        # Ver como: el administrador pasa a tener los permisos del perfil elegido.
        me = c.get('/api/auth/me', headers={**h, 'X-Ver-Como': 'ventas'}).json()
        assert me['role'] == 'ventas' and me['viendo_como'] == 'ventas' and me['permisos']['exportar'] is False
        assert c.get('/api/admin/users', headers={**h, 'X-Ver-Como': 'ventas'}).status_code == 403
        assert c.get('/api/admin/users', headers=h).status_code == 200
        # Un vendedor no puede usar "Ver como".
        assert c.get('/api/auth/me', headers={**hl, 'X-Ver-Como': 'gerencia'}).json()['role'] == 'ventas'


def test_report_detail_history_public_quote(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        hl, hg = users(c, h)
        msg = new_case(c, h)
        fid = msg['ficha_id']
        d = c.get('/api/reports/detalle?indicador=sin_atender&period=todos', headers=h).json()
        assert any(x['ficha_id'] == fid for x in d['items']) and d['total'] >= 1
        assert c.get('/api/reports/detalle?indicador=otro', headers=h).status_code == 422
        # Ventas solo ve lo propio en el detalle.
        assert not any(x['ficha_id'] == fid for x in c.get('/api/reports/detalle?indicador=sin_atender&period=todos', headers=hl).json()['items'])
        c.post(f'/api/fichas/{fid}/responsable', headers=h, json={'responsable': 'lucia'})
        assert any(x['ficha_id'] == fid for x in c.get('/api/reports/detalle?indicador=sin_atender&period=todos', headers=hl).json()['items'])
        # Cotización: historial y enlace público.
        q = c.post(f'/api/fichas/{fid}/cotizaciones', headers=hl, json={'moneda': 'USD', 'incluye_iva': False,
                   'items': [{'descripcion': 'Elaboración', 'cantidad': 1000, 'precio_unitario': 2}]}).json()
        hist = c.get(f'/api/fichas/{fid}/historial', headers=h).json()
        assert [t['estado'] for t in hist['tramos']] == ['sin_atender', 'cotizada'] and hist['eventos'][0]['tipo'] in ('estado', 'cotizacion')
        pub = c.get(f"/api/publico/cotizaciones/{q['token']}").json()
        assert pub['estado'] == 'pendiente' and pub['total'] == 2000 and 'token' not in pub
        assert c.get('/api/publico/cotizaciones/inexistente-1234567890').status_code == 404
        before = c.get('/api/chat/resumen', headers=hl).json()['ultimo_id']
        acc = c.post(f"/api/publico/cotizaciones/{q['token']}/aceptar", json={'nombre': 'Paula'}).json()
        assert acc['estado'] == 'aceptada'
        f = c.get(f'/api/fichas/{fid}', headers=h).json()
        assert f['estado_gestion'] == 'concretada' and f['cotizacion_monto'] == 2000
        chat = c.get(f'/api/chat/resumen?desde_id={before}', headers=hg).json()
        ventas = next(x for x in chat['canales'] if x['tipo'] == 'canal')
        assert 'aceptó la cotización' in ventas['ultimo']['texto']
        # Cierre manual en #ventas.
        m2 = new_case(c, h, cliente='Otra Empresa', email_remitente='x@otra.test')
        c.post(f"/api/fichas/{m2['ficha_id']}/estado", headers=hl, json={'estado': 'concretada'})
        ventas = next(x for x in c.get('/api/chat/resumen', headers=hg).json()['canales'] if x['tipo'] == 'canal')
        assert ventas['ultimo']['texto'].startswith('Cerré Otra Empresa')
        # Deshacer "no comercial".
        m3 = new_case(c, h, cliente='Tercera', email_remitente='y@tercera.test')
        c.post(f"/api/fichas/{m3['ficha_id']}/no-comercial", headers=h)
        c.post(f"/api/fichas/{m3['ficha_id']}/no-comercial/deshacer", headers=h, json={'tipo_consulta': 'sin_clasificar', 'estado_gestion': 'sin_atender'})
        assert c.get(f"/api/fichas/{m3['ficha_id']}", headers=h).json()['estado_gestion'] == 'sin_atender'
        # Mi día sin pulso y calificación del rubro.
        assert 'pulso' not in c.get('/api/mi-dia', headers=h).json()
        f = c.get(f"/api/fichas/{m3['ficha_id']}", headers=h).json()
        body = {k: f[k] for k in ('titulo', 'cliente', 'contacto', 'producto', 'cantidad', 'presentacion', 'packaging', 'resumen')}
        r = c.post(f"/api/fichas/{m3['ficha_id']}/edit", headers=h, json={**body, 'tipo_consulta': 'produccion_terceros', 'rubro': 'Higiene',
                   'envase': 'Doypack', 'tipo_cliente': 'Cadena o supermercado', 'etapas': ['Elaboración', 'Envasado'], 'requisitos': [], 'datos_faltantes': []})
        assert r.status_code == 200, r.text
        assert r.json()['etapas'] == ['Elaboración', 'Envasado'] and r.json()['envase'] == 'Doypack'
        assert {'fullservice', 'marcapropia', 'etiqueta'} <= {t['atajo'] for t in c.get('/api/plantillas', headers=h).json()}
