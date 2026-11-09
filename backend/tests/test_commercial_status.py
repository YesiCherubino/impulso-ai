"""Etapas administradas por el vendedor; finalizados se identifican por ganada/perdida."""
from datetime import date
from fastapi.testclient import TestClient
from app.main import create_app
from app.db import connect


def test_status_change_preserves_history_and_excludes_closed_from_dashboard(tmp_path):
    db=tmp_path/'estado.sqlite3'
    with TestClient(create_app(db)) as client:
        old=client.get('/api/opportunities/1').json()
        old_date=old['ultimo_contacto']
        before_count=client.get('/api/dashboard').json()['oportunidades_activas']
        r=client.post('/api/opportunities/1/status',json={'estado':'ganada'})
        assert r.status_code==200,r.text
        assert r.json()['estado']=='ganada'
        assert r.json()['ultimo_contacto']==old_date
        assert client.get('/api/dashboard').json()['oportunidades_activas']==before_count-1
        assert any('Estado comercial actualizado:' in i['descripcion'] for i in r.json()['interacciones'])
        # No se generan nuevas notas si el vendedor guarda el mismo estado.
        repeated=client.post('/api/opportunities/1/status',json={'estado':'ganada'})
        assert len(repeated.json()['interacciones'])==len(r.json()['interacciones'])
    with TestClient(create_app(db)) as client:
        assert client.get('/api/opportunities/1').json()['estado']=='ganada'
        reopened=client.post('/api/opportunities/1/status',json={'estado':'contactada'})
        assert reopened.status_code==200
        assert client.get('/api/dashboard').json()['oportunidades_activas']==before_count


def test_status_rejects_invalid_and_unknown_contact(tmp_path):
    with TestClient(create_app(tmp_path/'estado.sqlite3')) as client:
        assert client.post('/api/opportunities/1/status',json={'estado':'sin_clasificar'}).status_code==422
        assert client.post('/api/opportunities/987654/status',json={'estado':'perdida'}).status_code==404


def test_status_endpoint_requires_access_code_when_configured(tmp_path,monkeypatch):
    monkeypatch.setenv('DEMO_ACCESS_CODE','clave-secreta-para-pruebas')
    with TestClient(create_app(tmp_path/'estado.sqlite3')) as client:
        assert client.post('/api/opportunities/1/status',json={'estado':'perdida'}).status_code==401
        assert client.post('/api/opportunities/1/status',json={'estado':'perdida'},headers={'X-Demo-Code':'clave-secreta-para-pruebas'}).status_code==200
