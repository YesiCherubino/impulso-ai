"""V3: flujos de demo, gestiones y calendario, sin llamadas externas."""
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import create_app
from app.db import connect


def test_demo_seed_idempotent_with_web_and_threads(tmp_path,monkeypatch):
    monkeypatch.setenv('AUTH_ENABLED','true')
    monkeypatch.setenv('ADMIN_USERNAME','admin')
    monkeypatch.setenv('ADMIN_DISPLAY_NAME','Administración')
    monkeypatch.setenv('ADMIN_PASSWORD','una-clave-larga-segura-v3')
    path=tmp_path/'v3.sqlite3'
    with TestClient(create_app(path)) as c:
        token=c.post('/api/auth/login',json={'username':'admin','password':'una-clave-larga-segura-v3'}).json()['token']
        hdr={'X-Session-Token':token}
        first=c.post('/api/demo/seed',headers=hdr,json={'incluir_web':True})
        assert first.status_code==200,first.text
        assert first.json()['added']==40  # 35 de V3 + 5 casos del rubro (V4)
        second=c.post('/api/demo/seed',headers=hdr,json={'incluir_web':True})
        assert second.status_code==200 and second.json()['added']==0
        threads=c.get('/api/inbox/threads',headers=hdr)
        assert threads.status_code==200,threads.text
        actual=threads.json()
        with connect(path) as con:
            assert con.execute("SELECT COUNT(*) FROM fixtures_v3").fetchone()[0]==40
            assert con.execute("SELECT COUNT(DISTINCT cliente) FROM bandeja_consultas WHERE id IN (SELECT mensaje_id FROM fixtures_v3)").fetchone()[0]==25
            web=con.execute("SELECT COUNT(*) FROM bandeja_consultas WHERE canal='Formulario web'").fetchone()[0]
            assert web==6  # 5 de V3 + 1 CV por formulario (V4)
            assert con.execute("SELECT COUNT(*) FROM oportunidades WHERE notas='Ejemplo ficticio de Impulso V3'").fetchone()[0]==25
        assert any(len(t['mensajes'])>=3 for t in actual)
        assert any(m['canal']=='Correo' for t in actual for m in t['mensajes'])
        assert any(m['canal']=='WhatsApp' for t in actual for m in t['mensajes'])
        assert c.get('/api/reports/summary?channel=Formulario%20web',headers=hdr).status_code==200


def test_new_case_keeps_conversation_and_history(tmp_path):
    with TestClient(create_app(tmp_path/'v3.sqlite3')) as c:
        msg={'cliente':'Empresa Verde','contacto':'Sol','canal':'Correo','email_remitente':'sol@ejemplo.test',
             'texto':'Queremos fabricar una línea de cremas corporales.'}
        old=c.post('/api/inbox/new',json=msg).json()
        result=c.post(f'/api/inbox/{old["id"]}/new-case',json={'titulo':'Nueva línea de perfumes'})
        assert result.status_code==200,result.text
        assert result.json()['id']!=old['ficha_id']
        again=c.post('/api/inbox/new',json={**msg,'texto':'Ahora queremos analizar otro producto.'})
        assert again.status_code==201,again.text
        assert again.json()['ficha_id']==result.json()['id']
        threads=c.get('/api/inbox/threads').json()
        related=[t for t in threads if any(m['id']==old['id'] for m in t['mensajes'])]
        assert len(related)==1
        assert len(related[0]['mensajes'])==2


def test_calendar_and_case_status(tmp_path):
    with TestClient(create_app(tmp_path/'v3.sqlite3')) as c:
        m=c.post('/api/inbox/new',json={'cliente':'Empresa X','contacto':'Rosa','canal':'Manual',
            'texto':'Quiero consultar sobre fabricación para terceros.'}).json()
        moment=datetime(2026,11,12,10,tzinfo=timezone.utc)
        event={'titulo':'Llamar a Rosa','tipo':'llamada','inicio':moment.isoformat(),
               'ficha_id':m['ficha_id'],'estado':'programada'}
        created=c.post('/api/calendar/events',json=event)
        assert created.status_code==201,created.text
        eid=created.json()['id']
        edit=c.post(f'/api/calendar/events/{eid}',json={**event,'inicio':(moment+timedelta(days=2)).isoformat()})
        assert edit.status_code==200,edit.text
        assert len(c.get('/api/calendar/events').json())==1
        closed=c.post(f'/api/fichas/{m["ficha_id"]}/estado',json={'estado':'concretada'})
        assert closed.status_code==200 and closed.json()['estado']=='concretada'


def test_case_status_preserved_after_restart(tmp_path):
    path=tmp_path/'restart.sqlite3'
    with TestClient(create_app(path)) as c:
        m=c.post('/api/inbox/new',json={'cliente':'Contacto R','contacto':'Ana','canal':'Correo',
            'email_remitente':'ana@ejemplo.test','texto':'Necesito un proyecto de fabricación particular.'}).json()
        fid=m['ficha_id']
        r=c.post(f'/api/fichas/{fid}/estado',json={'estado':'sin_atender'})
        assert r.status_code==200
    with TestClient(create_app(path)) as c:
        assert c.get(f'/api/fichas/{fid}').json()['estado_gestion']=='sin_atender'
