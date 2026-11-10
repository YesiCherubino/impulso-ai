"""Regresiones V3: notificaciones y borradores manuales sin LLM."""
from fastapi.testclient import TestClient
from app.main import create_app
from app.ai import ConsultaExtraida


def test_mark_all_notifications_read_persists_and_new_messages_remain_unread(tmp_path):
    path = tmp_path / 'notificaciones.sqlite3'
    with TestClient(create_app(path)) as client:
        before = client.get('/api/notifications').json()
        assert before['sin_leer'] > 0
        assert client.post('/api/notifications/read-all').status_code == 200
        after = client.get('/api/notifications').json()
        assert after['sin_leer'] == 0
        assert all(n['leida'] == 1 for n in after['items'])
        assert client.post('/api/notifications/read-all').status_code == 200
        new = client.post('/api/inbox/new',json={
            'cliente':'Ejemplo Test','contacto':'Persona Test','canal':'Correo',
            'texto':'Quería pedir información para fabricar una línea de cosméticos.'})
        assert new.status_code == 201, new.text
        unseen = client.get('/api/notifications').json()
        assert any(n['referencia_id']==new.json()['id'] and n['leida']==0 for n in unseen['items'])
    with TestClient(create_app(path)) as client:
        notices = client.get('/api/notifications').json()
        assert sum(not n['leida'] for n in notices['items']) == 1


def test_manual_draft_before_ai_then_ai_generation(tmp_path):
    path = tmp_path / 'borrador.sqlite3'
    with TestClient(create_app(path)) as client:
        msg=client.post('/api/inbox/new',json={
            'cliente':'Empresa Manual','contacto':'Elena','canal':'WhatsApp',
            'texto':'Quisiera recibir más información sobre fabricación de productos de cosmética.'})
        assert msg.status_code==201,msg.text
        mid=msg.json()['id']
        manual=client.post(f'/api/inbox/{mid}/draft',json={'borrador':'Hola Elena, gracias por escribirnos.'})
        assert manual.status_code==200,manual.text
        assert manual.json()['version']==1
        assert manual.json()['resultado'] is None
        assert client.get(f'/api/inbox/{mid}/analysis').json()['analisis']['borrador']=='Hola Elena, gracias por escribirnos.'
        generated=ConsultaExtraida(cliente='Empresa Manual',contacto='Elena',producto='Cosméticos',cantidad=None,
            requisitos=[],datos_faltantes=['Cantidad'],resumen='Consulta comercial',respuesta_sugerida='Hola Elena, nos gustaría saber más.')
        calls=[]
        client.app.state.analizar_consulta=lambda texto:(calls.append(texto) or generated)
        ai=client.post(f'/api/inbox/{mid}/analysis',json={'regenerar':False})
        assert ai.status_code==200,ai.text
        assert ai.json()['version']==2
        assert ai.json()['borrador']=='Hola Elena, nos gustaría saber más.'
        assert len(calls)==1
        assert client.post(f'/api/inbox/{mid}/draft',json={'borrador':'Versión corregida'}).status_code==200
    with TestClient(create_app(path)) as client:
        r=client.get(f'/api/inbox/{mid}/analysis').json()['analisis']
        assert r['borrador']=='Versión corregida'
        assert r['version']==2


def test_manual_draft_missing_message(tmp_path):
    with TestClient(create_app(tmp_path/'empty.sqlite3')) as client:
        assert client.post('/api/inbox/999999/draft',json={'borrador':'Texto'}).status_code==404
