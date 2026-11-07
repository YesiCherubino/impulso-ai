from fastapi.testclient import TestClient
from app.main import create_app
from app.ai import ConsultaExtraida, SeguimientoGenerado


def test_analisis_estructura_sin_api_key(tmp_path):
    app = create_app(tmp_path / 'ai.sqlite3')
    app.state.analizar_consulta = lambda text: ConsultaExtraida(
        cliente='Aurora', contacto='', producto='Crema corporal', cantidad=3000,
        requisitos=['250 ml'], datos_faltantes=['Fecha requerida'],
        resumen='Solicitan crema corporal.', respuesta_sugerida='Gracias por escribirnos.')
    with TestClient(app) as client:
        response = client.post('/api/ai/analyze-inquiry', json={'texto':'Necesitamos 3000 unidades de crema corporal de 250 ml.'})
        assert response.status_code == 200
        assert response.json()['cantidad'] == 3000
        assert response.json()['datos_faltantes'] == ['Fecha requerida']


def test_input_insuficiente(tmp_path):
    with TestClient(create_app(tmp_path / 'ai.sqlite3')) as client:
        assert client.post('/api/ai/analyze-inquiry', json={'texto':'hola'}).status_code == 422


def test_seguimiento_toma_historial_guardado(tmp_path):
    app = create_app(tmp_path / 'ai.sqlite3')
    received=[]
    def fake(contexto):
        received.append(contexto)
        return SeguimientoGenerado(motivo='8 días', asunto='Seguimiento de propuesta',
                                   mensaje='Hola, ¿pudieron revisar la propuesta?', consideraciones=[])
    app.state.generar_seguimiento=fake
    with TestClient(app) as client:
        response=client.post('/api/ai/opportunities/1/follow-up')
        assert response.status_code == 200
        assert 'Aurora Cosmética' in received[0]
        assert 'interacciones' in received[0]
        assert response.json()['asunto'] == 'Seguimiento de propuesta'


def test_ia_no_encuentra_oportunidad(tmp_path):
    with TestClient(create_app(tmp_path / 'ai.sqlite3')) as client:
        assert client.post('/api/ai/opportunities/999/follow-up').status_code == 404
