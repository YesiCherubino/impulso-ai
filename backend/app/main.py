"""API pública local del MVP. Agregar autenticación antes de cualquier uso real."""
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
import json
import logging
import os
import secrets
from openai import OpenAIError
from . import ai
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware

from .db import connect, init_db
from .schemas import NuevaInteraccion, NuevaOportunidad, Oportunidad, OportunidadDetalle, Resumen
from pydantic import BaseModel, Field
from .services import metrics, to_opportunity

logger = logging.getLogger(__name__)

class ConsultaInput(BaseModel):
    texto: str = Field(min_length=25, max_length=5000)

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "impulso.sqlite3"


def create_app(db_path: Path = DEFAULT_DB) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(db_path)
        yield

    # Para demos públicas, la clave de acceso es obligatoria y no se expone en Next.js.
    if os.getenv('PUBLIC_DEMO', 'false').lower() == 'true' and not os.getenv('DEMO_ACCESS_CODE'):
        raise RuntimeError('PUBLIC_DEMO exige DEMO_ACCESS_CODE')

    def require_access(request: Request):
        expected = os.getenv('DEMO_ACCESS_CODE', '')
        if expected and not secrets.compare_digest(request.headers.get('x-demo-code', ''), expected):
            raise HTTPException(401, 'Código de acceso incorrecto o ausente')

    def reserve_ai_call():
        limit = max(1, int(os.getenv('AI_DAILY_LIMIT', '12')))
        today = date.today().isoformat()
        # Reserva atómica persistente: también cuenta una llamada que luego falle.
        with connect(db_path) as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('CREATE TABLE IF NOT EXISTS ai_quota (dia TEXT PRIMARY KEY, usados INTEGER NOT NULL)')
            con.execute('DELETE FROM ai_quota WHERE dia < ?', (today,))
            used = con.execute('SELECT usados FROM ai_quota WHERE dia = ?', (today,)).fetchone()
            if used is not None and used['usados'] >= limit:
                raise HTTPException(429, 'Se alcanzó el límite diario de análisis con IA para esta demo')
            con.execute('INSERT INTO ai_quota(dia, usados) VALUES (?, 1) ON CONFLICT(dia) DO UPDATE SET usados = usados + 1', (today,))

    app = FastAPI(title="Impulso — API Comercial", version="0.1.0", lifespan=lifespan,
                  description="Demo de gestión de oportunidades de venta. Todos los datos son ficticios.")
    origins = [x.strip() for x in os.getenv('CORS_ORIGINS', '').split(',') if x.strip()]
    if not origins:
        origins = ['http://localhost:3000', 'http://127.0.0.1:3000',
                   'http://localhost:3001', 'http://127.0.0.1:3001']
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Demo-Code"])

    def all_items():
        with connect(db_path) as con:
            rows = con.execute("SELECT * FROM oportunidades ORDER BY id").fetchall()
        return [to_opportunity(row, date.today()) for row in rows]

    @app.get("/api/health")
    def health():
        return {"status": "ok", "demo": True}

    @app.get("/api/dashboard", response_model=Resumen)
    def dashboard():
        return metrics(all_items(), date.today())

    @app.get('/api/management-summary')
    def management_summary():
        items = all_items()
        pending = sorted((i for i in items if i['seguimiento_pendiente']),
                         key=lambda i: i['dias_sin_contacto'], reverse=True)
        active = [i for i in items if i['estado'] not in ('ganada', 'perdida')]
        return {
            'titulo': 'Resumen comercial del día',
            'oportunidades_activas': len(active),
            'seguimientos_pendientes': len(pending),
            'prioridades': [
                {'id': i['id'], 'cliente': i['cliente'],
                 'dias_sin_contacto': i['dias_sin_contacto'],
                 'accion': i['proxima_accion'] or 'Revisar oportunidad'}
                for i in pending[:5]
            ],
            'criterio': 'Ordenado por días sin contacto. Son reglas de negocio, no predicciones de IA.',
        }

    @app.get("/api/opportunities", response_model=list[Oportunidad])
    def list_opportunities():
        return all_items()

    @app.get("/api/opportunities/{opportunity_id}", response_model=OportunidadDetalle)
    def get_opportunity(opportunity_id: int):
        with connect(db_path) as con:
            row = con.execute("SELECT * FROM oportunidades WHERE id = ?", (opportunity_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Oportunidad no encontrada")
            events = con.execute("SELECT id, tipo, descripcion, fecha FROM interacciones WHERE oportunidad_id = ? ORDER BY fecha DESC, id DESC", (opportunity_id,)).fetchall()
        return {**to_opportunity(row, date.today()), "notas": row["notas"],
                "interacciones": [dict(event) for event in events]}

    @app.post("/api/opportunities", response_model=OportunidadDetalle, status_code=201, dependencies=[Depends(require_access)])
    def create_opportunity(payload: NuevaOportunidad):
        today = date.today().isoformat()
        with connect(db_path) as con:
            cur = con.execute("""INSERT INTO oportunidades
                  (cliente, contacto, producto, cantidad, monto_estimado_usd, estado, creada_el, ultimo_contacto, notas)
                  VALUES (?, ?, ?, ?, ?, 'nueva', ?, ?, ?)""",
                (payload.cliente, payload.contacto, payload.producto, payload.cantidad,
                 payload.monto_estimado_usd, today, today, payload.notas))
            con.execute("INSERT INTO interacciones (oportunidad_id, tipo, descripcion, fecha) VALUES (?, 'consulta', ?, ?)",
                        (cur.lastrowid, "Oportunidad creada manualmente", today))
            new_id = cur.lastrowid
        return get_opportunity(new_id)

    @app.post("/api/opportunities/{opportunity_id}/interactions", response_model=OportunidadDetalle, status_code=201, dependencies=[Depends(require_access)])
    def add_interaction(opportunity_id: int, payload: NuevaInteraccion):
        interaction_date = payload.fecha or date.today()
        if interaction_date > date.today():
            raise HTTPException(422, "No se pueden registrar contactos futuros")
        with connect(db_path) as con:
            row = con.execute("SELECT id, ultimo_contacto FROM oportunidades WHERE id = ?", (opportunity_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Oportunidad no encontrada")
            con.execute("INSERT INTO interacciones (oportunidad_id, tipo, descripcion, fecha) VALUES (?, ?, ?, ?)",
                        (opportunity_id, payload.tipo, payload.descripcion, interaction_date.isoformat()))
            previous = date.fromisoformat(row["ultimo_contacto"])
            if payload.tipo in ("correo", "llamada", "reunion") and interaction_date > previous:
                con.execute("UPDATE oportunidades SET ultimo_contacto = ? WHERE id = ?",
                            (interaction_date.isoformat(), opportunity_id))
        return get_opportunity(opportunity_id)

    # El servicio se inyecta para permitir tests offline y para evitar llamadas reales en CI.
    app.state.analizar_consulta = ai.analizar_consulta
    app.state.generar_seguimiento = ai.generar_seguimiento

    @app.post('/api/ai/analyze-inquiry', response_model=ai.ConsultaExtraida, dependencies=[Depends(require_access)])
    def analyze_inquiry(payload: ConsultaInput):
        reserve_ai_call()
        try:
            return app.state.analizar_consulta(payload.texto)
        except (OpenAIError, RuntimeError, ValueError) as exc:
            logger.warning('Falló extracción con IA: %s', type(exc).__name__)
            raise HTTPException(503, 'No se pudo generar el análisis. Verificá la configuración de OpenAI e intentá nuevamente.') from exc

    @app.post('/api/ai/opportunities/{opportunity_id}/follow-up', response_model=ai.SeguimientoGenerado, dependencies=[Depends(require_access)])
    def ai_follow_up(opportunity_id: int):
        # Reutiliza el detalle y el historial real guardado en SQLite. No envía correos.
        item = get_opportunity(opportunity_id)
        contexto = json.dumps(item.model_dump(mode='json') if hasattr(item, 'model_dump') else item,
                              ensure_ascii=False, default=str)
        reserve_ai_call()
        try:
            return app.state.generar_seguimiento(contexto)
        except (OpenAIError, RuntimeError, ValueError) as exc:
            logger.warning('Falló seguimiento con IA: %s', type(exc).__name__)
            raise HTTPException(503, 'No se pudo generar el correo. Verificá OpenAI e intentá nuevamente.') from exc

    return app

app = create_app()
