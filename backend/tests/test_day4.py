from fastapi.testclient import TestClient
from app.main import create_app
from app.ai import ConsultaExtraida


def test_demo_code_protects_writes(monkeypatch, tmp_path):
    monkeypatch.setenv('DEMO_ACCESS_CODE', 'test-secret')
    app = create_app(tmp_path / 'security.sqlite3')
    with TestClient(app) as c:
        body = {'cliente':'Prueba','contacto':'Ana','producto':'Crema','cantidad':500}
        assert c.get('/api/dashboard').status_code == 200
        assert c.post('/api/opportunities', json=body).status_code == 401
        assert c.post('/api/opportunities', json=body, headers={'X-Demo-Code':'incorrecta'}).status_code == 401
        assert c.post('/api/opportunities', json=body, headers={'X-Demo-Code':'test-secret'}).status_code == 201


def test_ai_daily_limit_persists(monkeypatch, tmp_path):
    monkeypatch.setenv('DEMO_ACCESS_CODE', 'test-secret')
    monkeypatch.setenv('AI_DAILY_LIMIT', '1')
    path = tmp_path / 'quota.sqlite3'
    app = create_app(path)
    app.state.analizar_consulta = lambda text: ConsultaExtraida(cliente='Prueba', contacto='', producto='Crema', cantidad=500, requisitos=[], datos_faltantes=[], resumen='Resumen', respuesta_sugerida='Hola')
    with TestClient(app) as c:
        hdr={'X-Demo-Code':'test-secret'}
        payload={'texto':'Quiero comprar 500 unidades de crema para mi marca.'}
        assert c.post('/api/ai/analyze-inquiry',json=payload).status_code == 401
        assert c.post('/api/ai/analyze-inquiry',json=payload,headers=hdr).status_code == 200
        assert c.post('/api/ai/analyze-inquiry',json=payload,headers=hdr).status_code == 429
    app2=create_app(path)
    app2.state.analizar_consulta=app.state.analizar_consulta
    with TestClient(app2) as c:
        assert c.post('/api/ai/analyze-inquiry',json=payload,headers=hdr).status_code == 429


def test_management_summary(monkeypatch,tmp_path):
    monkeypatch.delenv('DEMO_ACCESS_CODE',raising=False)
    with TestClient(create_app(tmp_path / 'management.sqlite3')) as c:
        data=c.get('/api/management-summary').json()
        assert data['oportunidades_activas']==6
        assert data['seguimientos_pendientes']==3
        assert data['prioridades'][0]['dias_sin_contacto']>=data['prioridades'][-1]['dias_sin_contacto']


def test_public_demo_requires_secret(monkeypatch,tmp_path):
    monkeypatch.setenv('PUBLIC_DEMO','true')
    monkeypatch.delenv('DEMO_ACCESS_CODE',raising=False)
    import pytest
    with pytest.raises(RuntimeError): create_app(tmp_path / 'public.sqlite3')
