"""Regresión de las mejoras: datos comerciales, fechas, canales y migraciones."""
from datetime import date, timedelta
import sqlite3
from fastapi.testclient import TestClient
from app.db import connect, init_db
from app.main import create_app


def test_create_with_specific_commercial_fields(tmp_path):
    with TestClient(create_app(tmp_path / 'data.sqlite3')) as client:
        response = client.post('/api/opportunities', json={
            'cliente': 'Cliente de prueba', 'contacto': 'Ana Ruiz',
            'producto': 'Crema corporal', 'cantidad': 20000,
            'tipo_consulta': 'fabricacion_terceros', 'canal_origen': 'Formulario web',
            'presentacion': '250 ml', 'packaging': 'Etiqueta personalizada',
            'responsable': 'Ventas',
        })
        assert response.status_code == 201, response.text
        obj = response.json()
        assert obj['tipo_consulta'] == 'fabricacion_terceros'
        assert obj['canal_origen'] == 'Formulario web'
        assert obj['packaging'] == 'Etiqueta personalizada'
        assert obj['responsable'] == 'Ventas'
        assert client.get('/api/opportunities').json()[-1]['tipo_consulta'] == 'fabricacion_terceros'


def test_update_fields_followup_and_reset(tmp_path):
    with TestClient(create_app(tmp_path / 'data.sqlite3')) as client:
        updated = client.post('/api/opportunities/1/commercial-details', json={
            'tipo_consulta': 'desarrollo_formula', 'canal_origen': 'WhatsApp',
            'presentacion': '250 ml', 'packaging': 'Envase a definir', 'responsable': 'Florencia',
        })
        assert updated.status_code == 200, updated.text
        assert updated.json()['tipo_consulta'] == 'desarrollo_formula'
        due = (date.today() + timedelta(days=2)).isoformat()
        follow = client.post('/api/opportunities/1/follow-up', json={
            'fecha_seguimiento': due, 'motivo_seguimiento': 'Consultar cotización',
        })
        assert follow.status_code == 200, follow.text
        assert follow.json()['fecha_seguimiento'] == due
        assert follow.json()['seguimiento_pendiente'] is False
        assert client.get('/api/dashboard').json()['sin_seguimiento'] == 2
        notices = client.get('/api/notifications').json()['items']
        assert not any(n['tipo'] == 'seguimiento' and n['referencia_id'] == 1 for n in notices)
        reset = client.post('/api/opportunities/1/follow-up', json={'fecha_seguimiento': None})
        assert reset.status_code == 200
        assert reset.json()['seguimiento_pendiente'] is True
        assert reset.json()['motivo_seguimiento'] == ''


def test_scheduled_due_today_triggers_notification(tmp_path):
    with TestClient(create_app(tmp_path / 'data.sqlite3')) as client:
        day = date.today().isoformat()
        res = client.post('/api/opportunities/2/follow-up', json={
            'fecha_seguimiento': day, 'motivo_seguimiento': 'Contactar cliente',
        })
        assert res.status_code == 200
        assert res.json()['seguimiento_pendiente'] is True
        notices = client.get('/api/notifications').json()['items']
        assert any(n['referencia_id'] == 2 and n['tipo'] == 'seguimiento' and
                   'Contactar cliente' in n['detalle'] for n in notices)
        done = client.post('/api/opportunities/2/interactions', json={
            'tipo': 'llamada', 'descripcion': 'Seguimiento realizado',
        })
        assert done.status_code == 201
        assert done.json()['fecha_seguimiento'] is None
        assert done.json()['seguimiento_pendiente'] is False


def test_manual_consultation_has_channel(tmp_path):
    with TestClient(create_app(tmp_path / 'data.sqlite3')) as client:
        r = client.post('/api/inbox', json={
            'cliente': 'Empresa Demo', 'contacto': 'Martina',
            'texto': 'Quiero consultar por elaboración para terceros.', 'canal': 'Correo',
        })
        assert r.status_code == 201
        assert r.json()['canal'] == 'Correo'
        assert client.post('/api/inbox', json={
            'cliente': 'Empresa Demo', 'contacto': 'Martina',
            'texto': 'Consulta de prueba.', 'canal': 'Canal inventado',
        }).status_code == 422


def test_existing_sqlite_database_migrates_without_deleting(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(path) as con:
        con.execute('''CREATE TABLE oportunidades (id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL, contacto TEXT NOT NULL, producto TEXT NOT NULL,
            cantidad INTEGER, monto_estimado_usd REAL, estado TEXT NOT NULL,
            creada_el TEXT NOT NULL, ultimo_contacto TEXT NOT NULL,
            notas TEXT NOT NULL DEFAULT '')''')
        con.execute('''INSERT INTO oportunidades(cliente,contacto,producto,cantidad,
            monto_estimado_usd,estado,creada_el,ultimo_contacto,notas)
            VALUES ('Cliente previo','Ana','Crema',500,1000,'contactada',?,?, 'Preservar')''',
                    (date.today().isoformat(),date.today().isoformat()))
    init_db(path)
    with connect(path) as con:
        row = con.execute('SELECT * FROM oportunidades WHERE id=1').fetchone()
        assert row['cliente'] == 'Cliente previo'
        assert row['notas'] == 'Preservar'
        assert row['fecha_seguimiento'] is None
        assert row['tipo_consulta'] == 'sin_clasificar'
    init_db(path)
    with connect(path) as con:
        assert con.execute('SELECT COUNT(*) FROM oportunidades').fetchone()[0] == 1
