"""Flujos nuevos: notificaciones persistentes y resultados de IA reutilizables."""
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import create_app
from app.ai import ConsultaExtraida, SeguimientoGenerado
from app.db import connect


def test_notifications_persist_and_do_not_duplicate(tmp_path):
    db=tmp_path/'notif.sqlite3'
    with TestClient(create_app(db)) as client:
        first=client.get('/api/notifications').json()
        second=client.get('/api/notifications').json()
        assert len(first['items'])==len(second['items'])
        assert first['sin_leer'] > 0
        new=client.post('/api/inbox',json={
            'cliente':'Cliente prueba','contacto':'Persona prueba',
            'texto':'Necesitamos fabricar un lote de 500 unidades.'})
        assert new.status_code==201
        found=[n for n in client.get('/api/notifications').json()['items']
               if n['tipo']=='mensaje' and n['referencia_id']==new.json()['id']]
        assert len(found)==1
        assert client.post(f"/api/notifications/{found[0]['id']}/read").status_code==200
        assert next(n for n in client.get('/api/notifications').json()['items'] if n['id']==found[0]['id'])['leida']==1
    with TestClient(create_app(db)) as client:
        assert next(n for n in client.get('/api/notifications').json()['items'] if n['id']==found[0]['id'])['leida']==1
        assert len([n for n in client.get('/api/notifications').json()['items'] if n['id']==found[0]['id']])==1


def test_follow_up_notification_cleared_after_new_contact(tmp_path):
    db=tmp_path/'notif.sqlite3'
    with TestClient(create_app(db)) as client:
        # Seed de la empresa ficticia: Natural Care tiene más de siete días sin contacto.
        notices=client.get('/api/notifications').json()['items']
        target=next(n for n in notices if n['tipo']=='seguimiento' and n['titulo'].endswith('Natural Care'))
        assert 'días sin contacto' in target['detalle']
        interaction=client.post('/api/opportunities/3/interactions',json={'tipo':'llamada','descripcion':'Contactamos al cliente'})
        assert interaction.status_code==201
        notices=client.get('/api/notifications').json()['items']
        assert all(n['id']!=target['id'] for n in notices)


def test_inbox_ai_result_version_and_draft_survive_restart(tmp_path):
    db=tmp_path/'ai.sqlite3'
    calls=[]
    fake=ConsultaExtraida(cliente='Aurora Cosmética',contacto='Martina',producto='Crema 250 ml',
      cantidad=3000,requisitos=['Envase personalizado'],datos_faltantes=['Plazo'],
      resumen='Consulta de producción',respuesta_sugerida='Hola Martina')
    with TestClient(create_app(db)) as client:
        app=client.app
        app.state.analizar_consulta=lambda texto:(calls.append(texto) or fake)
        a=client.post('/api/inbox/1/analysis',json={'regenerar':False})
        assert a.status_code==200
        assert a.json()['version']==1
        assert len(calls)==1
        b=client.post('/api/inbox/1/analysis',json={'regenerar':False})
        assert b.json()['version']==1 and len(calls)==1
        edited=client.post('/api/inbox/1/draft',json={'borrador':'Hola, te escribimos desde Ventas'})
        assert edited.status_code==200
        assert edited.json()['borrador']=='Hola, te escribimos desde Ventas'
        c=client.post('/api/inbox/1/analysis',json={'regenerar':True})
        assert c.json()['version']==2 and len(calls)==2
    with TestClient(create_app(db)) as client:
        saved=client.get('/api/inbox/1/analysis').json()['analisis']
        assert saved['version']==2
        assert saved['resultado']['cliente']=='Aurora Cosmética'


def test_saved_opportunity_follow_up(tmp_path):
    db=tmp_path/'follow.sqlite3'
    fake=SeguimientoGenerado(motivo='Consulta reciente',asunto='Primer contacto',
         mensaje='Estimada Martina',consideraciones=['Confirmar cantidad'])
    calls=[]
    with TestClient(create_app(db)) as client:
        client.app.state.generar_seguimiento=lambda contexto:(calls.append(contexto) or fake)
        r=client.post('/api/opportunities/1/saved-follow-up',json={'regenerar':False})
        assert r.status_code==200, r.text
        assert r.json()['version']==1
        assert client.post('/api/opportunities/1/saved-follow-up',json={'regenerar':False}).json()['version']==1
        assert len(calls)==1
        updated=client.post('/api/opportunities/1/saved-follow-up/edit',json={'asunto':'Asunto editado','mensaje':'Texto editado'})
        assert updated.status_code==200
    with TestClient(create_app(db)) as client:
        saved=client.get('/api/opportunities/1/saved-follow-up').json()['borrador']
        assert saved['asunto']=='Asunto editado' and saved['mensaje']=='Texto editado'
