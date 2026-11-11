"""V9: editar y eliminar usuarios, tema automático y ejemplos sin el nombre ni las marcas del cliente."""
from fastapi.testclient import TestClient

from app.db import connect
from app.main import create_app
from tests.test_v5 import setup, login, new_case
from tests.test_v6 import users


def test_editar_y_eliminar_usuario(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        hl, hg = users(c, h)
        lista = c.get('/api/admin/users', headers=h).json()
        lucia = next(u for u in lista if u['username'] == 'lucia')
        admin = next(u for u in lista if u['role'] == 'administrador')
        assert lucia['theme'] == 'auto'
        # Editar nombre.
        assert c.post(f"/api/admin/users/{lucia['id']}", headers=h, json={'name': 'Lucía Paredes', 'role': 'ventas', 'active': True}).status_code == 200
        assert any(u['name'] == 'Lucía Paredes' for u in c.get('/api/admin/users', headers=h).json())
        # Una gestión abierta suya queda sin asignar al eliminarla, y el historial conserva su nombre.
        fid = new_case(c, h)['ficha_id']
        c.post(f'/api/fichas/{fid}/responsable', headers=h, json={'responsable': 'lucia'})
        r = c.post(f"/api/admin/users/{lucia['id']}/eliminar", headers=h).json()
        assert r['fichas'] == [fid]
        assert c.get(f'/api/fichas/{fid}', headers=h).json()['responsable'] == ''
        assert not any(u['username'] == 'lucia' for u in c.get('/api/admin/users', headers=h).json())
        assert not any(u['username'] == 'lucia' for u in c.get('/api/users/responsables', headers=h).json())
        assert c.get('/api/auth/me', headers=hl).status_code == 401
        assert c.post('/api/auth/login', json={'username': 'lucia', 'password': 'clave-de-prueba-larga'}).status_code == 401
        ev = c.get(f'/api/fichas/{fid}/historial', headers=h).json()['eventos']
        asign = next(e for e in ev if e['tipo'] == 'responsable' and e['valor'] == 'lucia')
        assert asign['valor_nombre'] == 'Lucía Paredes'
        # El nombre de usuario no se puede reutilizar.
        assert 'eliminado' in c.post('/api/admin/users', headers=h, json={'username': 'lucia', 'name': 'Otra', 'password': 'clave-de-prueba-larga', 'role': 'ventas'}).json()['detail']
        # Deshacer: vuelve y recupera la gestión.
        assert c.post(f"/api/admin/users/{lucia['id']}/restaurar", headers=h, json={'fichas': r['fichas'], 'activo': True}).json()['reasignadas'] == 1
        assert c.get(f'/api/fichas/{fid}', headers=h).json()['responsable'] == 'lucia'
        assert c.post('/api/auth/login', json={'username': 'lucia', 'password': 'clave-de-prueba-larga'}).status_code == 200
        # No se puede eliminar a uno mismo ni al último administrador; ventas no puede eliminar.
        assert c.post(f"/api/admin/users/{admin['id']}/eliminar", headers=h).status_code == 400
        assert c.post(f"/api/admin/users/{admin['id']}/eliminar", headers=hg).status_code == 403


def test_tema_automatico(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        assert c.get('/api/auth/me', headers=h).json()['theme'] == 'auto'
        for t in ('oscuro', 'auto', 'claro'):
            assert c.post('/api/auth/me/theme', headers=h, json={'theme': t}).status_code == 200
        assert c.get('/api/auth/me', headers=h).json()['theme'] == 'claro'
        assert c.post('/api/auth/me/theme', headers=h, json={'theme': 'azul'}).status_code == 422


def test_ejemplos_sin_marca_del_cliente(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    with TestClient(create_app(path)) as c:
        h = login(c)
        emp = c.get('/api/empresa', headers=h).json()
        assert emp['razon_social'] == 'Empresa S.A.' and 'pasmanter' not in emp['email']
        assert c.get('/api/productos?q=marca%20b', headers=h).json()['items']
    # Una base vieja, con los datos anteriores, se limpia una sola vez al arrancar.
    with connect(path) as con:
        con.execute("UPDATE empresa_config SET razon_social='Roberto Pasmanter S.A.', web='www.pasmanter.com.ar' WHERE id=1")
        con.execute("UPDATE productos SET codigo='DG-CC250', descripcion='Dermogreen Crema corporal 250 ml' WHERE codigo='MA-CC250'")
        con.execute("UPDATE plantillas SET texto='Saludos – Roberto Pasmanter S.A.' WHERE atajo='gracias'")
        con.execute("DELETE FROM migraciones WHERE clave='sin_marca_cliente'")
    with TestClient(create_app(path)) as c:
        h = login(c)
        emp = c.get('/api/empresa', headers=h).json()
        assert emp['razon_social'] == 'Empresa S.A.' and emp['web'] == 'www.empresa.com.ar'
        with connect(path) as con:
            assert not con.execute("SELECT 1 FROM productos WHERE codigo LIKE 'DG-%'").fetchone()
            assert con.execute("SELECT texto FROM plantillas WHERE atajo='gracias'").fetchone()['texto'] == 'Saludos – Empresa S.A.'
            for t, col in (('bandeja_consultas', 'texto'), ('fichas_consulta', 'titulo'), ('productos', 'descripcion')):
                assert not con.execute(f"SELECT 1 FROM {t} WHERE {col} LIKE '%Pasmanter%' OR {col} LIKE '%Dermogreen%'").fetchone()
