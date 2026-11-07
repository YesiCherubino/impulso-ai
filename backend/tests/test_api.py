from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services import metrics

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "db.sqlite3")) as api:
        yield api

def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"

def test_list_has_eight_fake_opportunities(client):
    response = client.get("/api/opportunities")
    assert response.status_code == 200
    assert len(response.json()) == 8
    assert response.json()[0]["cliente"] == "Aurora Cosmética"

def test_follow_up_threshold_and_closed_cases(client):
    items = client.get("/api/opportunities").json()
    assert items[0]["seguimiento_pendiente"] is True
    assert items[0]["dias_sin_contacto"] == 8
    assert items[1]["seguimiento_pendiente"] is False
    assert items[6]["seguimiento_pendiente"] is False
    assert items[7]["seguimiento_pendiente"] is False

def test_dashboard_consistent_with_list(client):
    items = client.get("/api/opportunities").json()
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["oportunidades_activas"] == 6
    assert dashboard["sin_seguimiento"] == 3
    assert dashboard["cotizaciones_pendientes"] == 2
    assert dashboard["valor_potencial_usd"] == sum(i["monto_estimado_usd"] or 0 for i in items if i["estado"] not in ("ganada", "perdida"))

def test_opportunity_detail_history(client):
    response = client.get("/api/opportunities/1")
    assert response.status_code == 200
    assert response.json()["interacciones"]
    assert response.json()["notas"]

def test_404(client):
    assert client.get("/api/opportunities/999").status_code == 404

def test_create_opportunity(client):
    response = client.post("/api/opportunities", json={"cliente":"Cliente de prueba", "contacto":"Ana Ruiz", "producto":"Jabón", "cantidad":500})
    assert response.status_code == 201
    assert response.json()["estado"] == "nueva"
    assert len(client.get("/api/opportunities").json()) == 9

def test_reject_invalid_opportunity(client):
    response = client.post("/api/opportunities", json={"cliente":"A", "contacto":"Ana Ruiz", "producto":"Jabón", "cantidad":-1})
    assert response.status_code == 422

def test_contact_resets_follow_up(client):
    assert client.get("/api/opportunities/1").json()["seguimiento_pendiente"] is True
    result = client.post("/api/opportunities/1/interactions", json={"tipo":"llamada", "descripcion":"Hablamos con el cliente"})
    assert result.status_code == 201
    assert result.json()["dias_sin_contacto"] == 0
    assert result.json()["seguimiento_pendiente"] is False

def test_backdated_interaction_does_not_move_last_contact_backwards(client):
    before = client.get("/api/opportunities/2").json()["ultimo_contacto"]
    old = (date.today() - timedelta(days=100)).isoformat()
    client.post("/api/opportunities/2/interactions", json={"tipo":"nota", "descripcion":"Nota antigua", "fecha":old})
    assert client.get("/api/opportunities/2").json()["ultimo_contacto"] == before

def test_reject_future_contact(client):
    future = (date.today() + timedelta(days=1)).isoformat()
    result = client.post("/api/opportunities/1/interactions", json={"tipo":"correo", "descripcion":"No se envío todavía", "fecha":future})
    assert result.status_code == 422


def test_note_does_not_count_as_contact(client):
    previous = client.get("/api/opportunities/1").json()["ultimo_contacto"]
    result = client.post("/api/opportunities/1/interactions", json={"tipo":"nota", "descripcion":"Revisar oportunidad"})
    assert result.status_code == 201
    assert result.json()["ultimo_contacto"] == previous
    assert result.json()["seguimiento_pendiente"] is True
