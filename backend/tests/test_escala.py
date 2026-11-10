"""Escalabilidad: endpoints paginados, datos resumidos por gestión y tiempos con volumen."""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import connect
from app.escala import refresh_case_stats
from app.main import create_app

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from generar_volumen import generate  # noqa: E402


def msg(c, **kw):
    body = {'cliente': 'Luna Natural', 'contacto': 'Flor', 'canal': 'WhatsApp', 'telefono_remitente': '5491100000001',
            'texto': 'Hola, consulta por crema facial.'}
    body.update(kw)
    r = c.post('/api/inbox/new', json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_case_stats_follow_every_change(tmp_path):
    db = tmp_path / 'e.sqlite3'
    with TestClient(create_app(db)) as c:
        m = msg(c)
        f = c.get(f"/api/fichas/{m['ficha_id']}").json()
        assert f['mensajes_count'] == 1 and f['no_leidos_count'] == 1 and f['pendiente_desde']
        assert f['canal_origen'] == 'WhatsApp' and f['tiene_whatsapp'] == 1
        conv = c.get(f"/api/inbox/{m['id']}/conversation").json()['key']
        c.post(f'/api/inbox/conversations/{conv}/read')
        assert c.get(f"/api/fichas/{m['ficha_id']}").json()['no_leidos_count'] == 0
        c.post(f"/api/inbox/{m['id']}/reply", json={'texto': 'Gracias, ¿qué cantidad necesitan?', 'canal': 'WhatsApp'})
        f = c.get(f"/api/fichas/{m['ficha_id']}").json()
        assert f['mensajes_count'] == 2 and f['pendiente_desde'] is None and f['primera_respuesta_en']
        time.sleep(1.1)  # las horas se guardan con precisión de segundos
        m2 = msg(c, texto='Unas 3000 unidades.')
        f = c.get(f"/api/fichas/{m['ficha_id']}").json()
        assert m2['ficha_id'] == m['ficha_id'] and f['pendiente_desde'] == m2['recibido_el']
        # Mover el mensaje a otra gestión refresca origen y destino.
        c.post(f"/api/inbox/{m2['id']}/move", json={'ficha_id': None})
        assert c.get(f"/api/fichas/{m['ficha_id']}").json()['mensajes_count'] == 2


def test_conversations_paginate_and_filter(tmp_path):
    db = tmp_path / 'e.sqlite3'
    with TestClient(create_app(db)) as c:
        for i in range(7):
            msg(c, cliente=f'Cliente {i}', telefono_remitente=f'549110000{i:04d}', canal='Correo' if i % 2 else 'WhatsApp',
                email_remitente=f'c{i}@x.test', texto=f'Consulta número {i} por envase especial')
        first = c.get('/api/inbox/conversations?limit=3').json()
        second = c.get('/api/inbox/conversations?limit=3&offset=3').json()
        assert len(first['items']) == 3 and first['total'] == second['total'] >= 7
        assert not {i['key'] for i in first['items']} & {i['key'] for i in second['items']}
        assert all('mensajes' not in i for i in first['items'])  # el listado no trae los mensajes
        wa = c.get('/api/inbox/conversations?canal=WhatsApp&limit=50').json()
        assert all(i['gestion'] for i in wa['items']) and wa['total'] < first['total']
        found = c.get('/api/inbox/conversations?q=número 3').json()
        assert [i['cliente'] for i in found['items']] == ['Cliente 3']
        key = found['items'][0]['key']
        detail = c.get(f'/api/inbox/conversations/{key}').json()
        assert detail['mensajes'][0]['texto'].startswith('Consulta número 3') and detail['fichas'][0]['codigo']
        # Cerrar la gestión la saca de "abiertas" y la pasa a "cerradas".
        c.post(f"/api/fichas/{detail['fichas'][0]['id']}/estado", json={'estado': 'concretada'})
        assert key not in [i['key'] for i in c.get('/api/inbox/conversations?limit=200').json()['items']]
        assert key in [i['key'] for i in c.get('/api/inbox/conversations?estado=cerradas&limit=200').json()['items']]


def test_fichas_and_contacts_search(tmp_path):
    with TestClient(create_app(tmp_path / 'e.sqlite3')) as c:
        m = msg(c, cliente='Pampa Cosmética', texto='Consulta por emulsión corporal')
        c.post(f"/api/fichas/{m['ficha_id']}/estado", json={'estado': 'no_concretada', 'motivo': 'Plazo'})
        closed = c.get('/api/fichas-search?estado=cerradas&limit=2').json()
        assert closed['total'] >= 1 and len(closed['items']) <= 2
        assert closed['conteos'].get('no_concretada', 0) >= 1
        assert c.get('/api/fichas-search?estado=cerradas&q=pampa').json()['items'][0]['motivo_cierre'] == 'Plazo'
        contacts = c.get('/api/contacts/search?limit=5').json()
        assert contacts['total'] >= 1 and all(i['estado_gestion_actual'] for i in contacts['items'])


def test_calendar_range_and_notifications_are_bounded(tmp_path):
    db = tmp_path / 'e.sqlite3'
    with TestClient(create_app(db)) as c:
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=400)).isoformat()
        c.post('/api/calendar/events', json={'titulo': 'Viejo', 'tipo': 'reunion', 'inicio': old})
        c.post('/api/calendar/events', json={'titulo': 'Vencido', 'tipo': 'seguimiento', 'inicio': (now - timedelta(days=40)).isoformat()})
        c.post('/api/calendar/events', json={'titulo': 'Hoy', 'tipo': 'llamada', 'inicio': now.isoformat()})
        desde, hasta = (now - timedelta(days=7)).isoformat(), (now + timedelta(days=7)).isoformat()
        titles = [e['titulo'] for e in c.get(f'/api/calendar/events?desde={desde}&hasta={hasta}').json()]
        assert titles == ['Hoy']
        titles = [e['titulo'] for e in c.get(f'/api/calendar/events?desde={desde}&hasta={hasta}&vencidos=true').json()]
        assert set(titles) == {'Vencido', 'Hoy'}
        # Mensajes viejos no generan avisos nuevos.
        with connect(db) as con:
            con.execute('''INSERT INTO bandeja_consultas(cliente,contacto,canal,texto,recibido_el,estado)
                           VALUES ('Viejo SA','X','Correo','Mensaje de hace un año', ?, 'nueva')''', (old,))
        items = c.get('/api/notifications').json()['items']
        assert not any(n['detalle'] == 'Mensaje de hace un año' for n in items)


def test_admin_unify_duplicates(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_ENABLED', 'true')
    monkeypatch.setenv('ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('ADMIN_PASSWORD', 'una-clave-larga-segura-v5')
    with TestClient(create_app(tmp_path / 'e.sqlite3')) as c:
        h = {'X-Session-Token': c.post('/api/auth/login', json={'username': 'admin', 'password': 'una-clave-larga-segura-v5'}).json()['token']}
        c.post('/api/demo/seed', headers=h, json={'incluir_web': True})
        preview = c.get('/api/admin/duplicados', headers=h).json()
        assert preview['gestiones'] and any(g['cliente'] == 'Botánica Studio' for g in preview['gestiones'])
        result = c.post('/api/admin/duplicados/unificar', headers=h).json()
        assert result['gestiones_fusionadas'] == len(preview['gestiones'])
        again = c.get('/api/admin/duplicados', headers=h).json()
        assert again == {'gestiones': [], 'contactos': []}
        clients = [i['cliente'] for i in c.get('/api/inbox/conversations?limit=200', headers=h).json()['items']]
        assert clients.count('Botánica Studio') == 1


@pytest.mark.parametrize('years', [1])
def test_volume_stays_fast(tmp_path, years):
    """1 año de datos en CI; con IMPULSO_PRUEBA_ESCALA_COMPLETA=1 se prueban 5 años (~90.000 mensajes)."""
    if os.getenv('IMPULSO_PRUEBA_ESCALA_COMPLETA') == '1':
        years = 5
    db = tmp_path / 'vol.sqlite3'
    info = generate(db, years=years, per_day=11, quiet=True)
    assert info['mensajes'] > 15000 * years
    with TestClient(create_app(db)) as c:
        checks = [('/api/inbox/conversations?limit=50', 0.5), ('/api/inbox/conversations?orden=prioridad&limit=50', 0.5),
                  ('/api/fichas-search?estado=cerradas&limit=50', 0.3), ('/api/contacts/search?limit=50', 0.3),
                  ('/api/reports/summary?period=todos', 1.0), ('/api/notifications', 0.5)]
        for url, budget in checks:
            c.get(url)
            t = time.time()
            r = c.get(url)
            elapsed = time.time() - t
            assert r.status_code == 200, url
            assert elapsed < budget, f'{url} tardó {elapsed:.2f} s (máximo {budget} s)'
            assert len(r.content) < 400_000, f'{url} devolvió {len(r.content)} bytes'
        key = c.get('/api/inbox/conversations?limit=1').json()['items'][0]['key']
        detail = c.get(f'/api/inbox/conversations/{key}').json()
        assert len(detail['mensajes']) <= 200
        # Los datos resumidos coinciden con los mensajes reales.
        with connect(db) as con:
            bad = con.execute('''SELECT COUNT(*) FROM fichas_consulta f WHERE f.mensajes_count <>
                                 (SELECT COUNT(*) FROM bandeja_consultas b WHERE b.ficha_id=f.id)''').fetchone()[0]
        assert bad == 0
