import os
from fastapi.testclient import TestClient
from app.main import create_app


def test_login_and_session(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_ENABLED', 'true')
    monkeypatch.setenv('ADMIN_USERNAME', 'ventas')
    monkeypatch.setenv('ADMIN_DISPLAY_NAME', 'Operador')
    monkeypatch.setenv('ADMIN_PASSWORD', 'una-clave-de-20-caracteres-segura')
    app = create_app(tmp_path / 'db.sqlite3')
    with TestClient(app) as client:
        assert client.get('/api/dashboard').status_code == 401
        assert client.post('/api/auth/login', json={'username': 'ventas', 'password': 'incorrecto'}).status_code == 401
        login = client.post('/api/auth/login', json={'username': 'ventas', 'password': 'una-clave-de-20-caracteres-segura'})
        assert login.status_code == 200
        token = login.json()['token']
        headers = {'X-Session-Token': token}
        assert client.get('/api/auth/me', headers=headers).json()['name'] == 'Operador'
        assert client.get('/api/dashboard', headers=headers).status_code == 200
        assert client.post('/api/auth/logout', headers=headers).status_code == 200
        assert client.get('/api/dashboard', headers=headers).status_code == 401
