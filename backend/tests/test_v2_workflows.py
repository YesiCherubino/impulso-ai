"""Pruebas de la nueva organización sin consumir OpenAI ni modificar Railway."""
from fastapi.testclient import TestClient
from app.main import create_app


def test_sender_fichas_and_read_state(tmp_path):
    with TestClient(create_app(tmp_path/'db.sqlite3')) as c:
        payload={'cliente':'Fábrica A','contacto':'Carla','canal':'Correo',
                 'email_remitente':'Carla@EJEMPLO.com','texto':'Necesitamos desarrollar 3000 cremas corporales.'}
        first=c.post('/api/inbox/new',json=payload)
        assert first.status_code==201, first.text
        a=first.json()
        assert a['leido_en'] is None and a['estado']=='nueva'
        second=c.post('/api/inbox/new',json={**payload,'texto':'También queremos conocer las presentaciones.'})
        assert second.status_code==201 and second.json()['ficha_id']==a['ficha_id']
        read=c.post(f'/api/inbox/{a["id"]}/read',json={'read':True})
        assert read.status_code==200 and read.json()['leido_en']
        assert read.json()['estado']=='nueva', 'Leer no equivale a cambiar etapa comercial'
        ficha=c.get(f'/api/fichas/{a["ficha_id"]}').json()
        assert ficha['codigo'].startswith('CON-') and len(ficha['mensajes'])==2
        moved=c.post(f'/api/inbox/{second.json()["id"]}/move',json={'ficha_id':None})
        assert moved.status_code==200 and moved.json()['ficha_id']!=a['ficha_id']
        assert len(c.get(f'/api/fichas/{a["ficha_id"]}').json()['mensajes'])==1


def test_save_contact_no_duplicate_and_edit_ficha(tmp_path):
    with TestClient(create_app(tmp_path/'db.sqlite3')) as c:
        m=c.post('/api/inbox/new',json={'cliente':'Delta','contacto':'Mara','canal':'WhatsApp',
                                        'telefono_remitente':'+54 11 4444 2222','texto':'Solicito presupuesto de jabón líquido.'}).json()
        id_=m['ficha_id']
        payload={'titulo':'Jabón líquido','cliente':'Delta','contacto':'Mara',
                 'producto':'Jabón líquido','cantidad':2000,'tipo_consulta':'fabricacion_terceros',
                 'presentacion':'500 ml','packaging':'Botella','requisitos':['Envase'],
                 'datos_faltantes':['Plazo'],'resumen':'Consulta inicial','contacto_telefono':'541144442222'}
        saved=c.post(f'/api/fichas/{id_}/save-contact',json=payload)
        assert saved.status_code==200, saved.text
        opp=saved.json()['opportunity_id']
        again=c.post(f'/api/fichas/{id_}/save-contact',json={**payload,'producto':'Jabón líquido modificado'})
        assert again.status_code==200 and again.json()['opportunity_id']==opp
        detail=c.get(f'/api/opportunities/{opp}').json()
        assert detail['producto']=='Jabón líquido modificado'
        assert len(c.get(f'/api/opportunities/{opp}/fichas').json())==1


def test_auth_roles_theme_and_pdf(tmp_path,monkeypatch):
    monkeypatch.setenv('AUTH_ENABLED','true')
    monkeypatch.setenv('ADMIN_USERNAME','admin')
    monkeypatch.setenv('ADMIN_DISPLAY_NAME','Administración')
    monkeypatch.setenv('ADMIN_PASSWORD','una-clave-larga-super-segura')
    with TestClient(create_app(tmp_path/'db.sqlite3')) as c:
        resp=c.post('/api/auth/login',json={'username':'admin','password':'una-clave-larga-super-segura'})
        assert resp.status_code==200,resp.text
        token=resp.json()['token']; headers={'X-Session-Token':token}
        assert c.post('/api/auth/me/theme',headers=headers,json={'theme':'oscuro'}).json()['theme']=='oscuro'
        assert c.get('/api/auth/me',headers=headers).json()['theme']=='oscuro'
        created=c.post('/api/admin/users',headers=headers,json={'username':'reporte','name':'Gerencia',
                              'role':'gerencia','password':'otra-clave-muy-segura'})
        assert created.status_code==201,created.text
        gerencia=c.post('/api/auth/login',json={'username':'reporte','password':'otra-clave-muy-segura'}).json()
        gh={'X-Session-Token':gerencia['token']}
        assert c.post('/api/inbox/new',headers=gh,json={'cliente':'Empresa A','contacto':'Persona',
                       'texto':'Probando mensaje entrante','canal':'Manual'}).status_code==403
        assert c.get('/api/reports/summary',headers=gh).status_code==200
        report=c.post('/api/reports/pdf',headers=gh,json={'title':'Informe comercial',
                       'question':'¿Cuántas consultas?', 'report':'Resumen ejecutivo de operaciones.',
                       'data':{'periodo':'mes','canal':'todos'}})
        assert report.status_code==200,report.text
        assert report.json()['pdf_base64'].startswith('JVBER')
        assert c.get('/api/admin/users',headers=gh).status_code==403
