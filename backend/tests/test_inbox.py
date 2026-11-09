from fastapi.testclient import TestClient
from app.main import create_app


def test_inbox_seed_and_status_persist(tmp_path):
    path = tmp_path / 'bandeja.sqlite3'
    with TestClient(create_app(path)) as client:
        response = client.get('/api/inbox')
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 7
        assert all('simulado' in m['canal'].lower() for m in messages)
        message_id = messages[0]['id']
        updated = client.post(f'/api/inbox/{message_id}/status', json={'estado': 'resuelta'})
        assert updated.status_code == 200
        assert updated.json()['estado'] == 'resuelta'
    with TestClient(create_app(path)) as client:
        assert len(client.get('/api/inbox').json()) == 7
        assert next(x for x in client.get('/api/inbox').json() if x['id'] == message_id)['estado'] == 'resuelta'


def test_inbox_status_validation_and_not_found(tmp_path):
    with TestClient(create_app(tmp_path / 'test.sqlite3')) as client:
        assert client.post('/api/inbox/1/status', json={'estado':'cualquier_estado'}).status_code == 422
        assert client.post('/api/inbox/999/status', json={'estado':'resuelta'}).status_code == 404


def test_inbox_changes_protected(monkeypatch,tmp_path):
    monkeypatch.setenv('DEMO_ACCESS_CODE','secret')
    with TestClient(create_app(tmp_path / 'protected.sqlite3')) as client:
        assert client.get('/api/inbox').status_code == 200
        assert client.post('/api/inbox/1/status', json={'estado':'resuelta'}).status_code == 401
        assert client.post('/api/inbox/1/status',json={'estado':'resuelta'},headers={'X-Demo-Code':'secret'}).status_code == 200


def test_link_inbox_to_opportunity(tmp_path):
    path = tmp_path / 'linked.sqlite3'
    with TestClient(create_app(path)) as client:
        reply = client.post('/api/inbox/1/link-opportunity', json={'opportunity_id': 1})
        assert reply.status_code == 200
        assert reply.json()['oportunidad_id'] == 1
        assert reply.json()['estado'] == 'en_gestion'
        assert client.post('/api/inbox/1/link-opportunity', json={'opportunity_id': 9876}).status_code == 404
    with TestClient(create_app(path)) as client:
        assert next(x for x in client.get('/api/inbox').json() if x['id']==1)['oportunidad_id'] == 1
