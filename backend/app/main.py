"""API del backoffice Impulso con autenticación opcional de sesiones."""
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
import json
import logging
import os
import secrets
from openai import OpenAIError
from . import ai, auth
from .business_v2 import register_business_v2
from .business_v3 import init_v3, register_business_v3
from .business_v4 import (init_v4, register_business_v4, build_case_context, apply_analysis,
                          sync_contact_followup, complete_contact_followup, create_case_for_contact)
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware

from .db import connect, init_db
from .schemas import (Estado, NuevaInteraccion, NuevaOportunidad, EditarDatosComerciales,
                      ProgramarSeguimiento, CanalOrigen, Oportunidad, OportunidadDetalle, Resumen)
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
        auth.init_auth(db_path)
        init_v3(db_path)
        init_v4(db_path)
        yield

    # Para demos públicas, la clave de acceso es obligatoria y no se expone en Next.js.
    if os.getenv('AUTH_ENABLED', 'false').lower() != 'true' and os.getenv('PUBLIC_DEMO', 'false').lower() == 'true' and not os.getenv('DEMO_ACCESS_CODE'):
        raise RuntimeError('PUBLIC_DEMO exige DEMO_ACCESS_CODE')

    def require_access(request: Request):
        if os.getenv('AUTH_ENABLED', 'false').lower() == 'true':
            if not auth.get_user(db_path, request.headers.get('x-session-token', '')):
                raise HTTPException(401, 'Sesión no válida o vencida')
            return
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
                       allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Demo-Code", "X-Session-Token"])

    class LoginInput(BaseModel):
        username: str = Field(min_length=1, max_length=120)
        password: str = Field(min_length=1, max_length=200)

    @app.middleware('http')
    async def protect_private_api(request: Request, call_next):
        if (os.getenv('AUTH_ENABLED', 'false').lower() == 'true'
                and request.url.path.startswith('/api/')
                and request.url.path not in ('/api/health', '/api/auth/login', '/api/auth/logout')):
            if not auth.get_user(db_path, request.headers.get('x-session-token', '')):
                from fastapi.responses import JSONResponse
                return JSONResponse({'detail': 'Sesión no válida o vencida'}, status_code=401)
        if os.getenv('AUTH_ENABLED', 'false').lower() == 'true' and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            path = request.url.path
            user = auth.get_user(db_path, request.headers.get('x-session-token', ''))
            if user and user.get('role') == 'gerencia' and ((path.startswith('/api/inbox') and not path.endswith('/read')) or path.startswith('/api/opportunities') or path.startswith('/api/ai/')):
                from fastapi.responses import JSONResponse
                return JSONResponse({'detail':'Gerencia tiene acceso de consulta, no puede modificar registros.'},status_code=403)
        return await call_next(request)

    @app.post('/api/auth/login')
    def login(payload: LoginInput):
        if os.getenv('AUTH_ENABLED', 'false').lower() != 'true':
            raise HTTPException(404, 'Inicio de sesión no habilitado')
        session = auth.authenticate(db_path, payload.username, payload.password)
        if not session:
            raise HTTPException(401, 'Usuario o contraseña incorrectos, o cuenta temporalmente bloqueada')
        return session

    @app.get('/api/auth/me')
    def me(request: Request):
        user = auth.get_user(db_path, request.headers.get('x-session-token', ''))
        if not user:
            raise HTTPException(401, 'Sesión no válida o vencida')
        return user

    @app.post('/api/auth/logout')
    def logout(request: Request):
        auth.logout(db_path, request.headers.get('x-session-token', ''))
        return {'ok': True}

    def all_items():
        with connect(db_path) as con:
            rows = con.execute("SELECT * FROM oportunidades WHERE fusionada_con IS NULL ORDER BY id").fetchall()
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
                         key=lambda i: (i['fecha_seguimiento'] is None,
                                        i['fecha_seguimiento'] or '',
                                        -i['dias_sin_contacto']))
        active = [i for i in items if i['estado'] not in ('ganada', 'perdida')]
        return {
            'titulo': 'Resumen comercial del día',
            'oportunidades_activas': len(active),
            'seguimientos_pendientes': len(pending),
            'prioridades': [
                {'id': i['id'], 'cliente': i['cliente'],
                 'dias_sin_contacto': i['dias_sin_contacto'],
                 'fecha_seguimiento': i['fecha_seguimiento'],
                 'accion': i['proxima_accion'] or 'Revisar oportunidad'}
                for i in pending[:5]
            ],
            'criterio': 'Primero seguimientos programados vencidos, luego días sin contacto. Son reglas de negocio, no predicciones de IA.',
        }

    def current_user_id(request: Request) -> int:
        if os.getenv('AUTH_ENABLED', 'false').lower() == 'true':
            user = auth.get_user(db_path, request.headers.get('x-session-token', ''))
            if not user:
                raise HTTPException(401, 'Sesión no válida o vencida')
            return int(user['id'])
        return 0

    def sync_notifications():
        """UNIQUE identifica cada aviso; actualizar no duplica notificaciones."""
        stamp = datetime.now(timezone.utc).isoformat()
        with connect(db_path) as con:
            for row in con.execute("SELECT id,cliente,texto,recibido_el FROM bandeja_consultas WHERE direccion<>'saliente'").fetchall():
                con.execute('''INSERT OR IGNORE INTO notificaciones
                    (clave,tipo,referencia_id,titulo,detalle,creada_en)
                    VALUES (?,?,?,?,?,?)''',
                    (f"mensaje:{row['id']}", 'mensaje', row['id'],
                     f"Nueva consulta · {row['cliente']}", row['texto'][:160], row['recibido_el']))
            con.execute("UPDATE notificaciones SET activa=0 WHERE tipo='seguimiento'")
            for row in con.execute('''SELECT id, cliente, ultimo_contacto, fecha_seguimiento, motivo_seguimiento FROM oportunidades
                 WHERE estado NOT IN ('ganada','perdida') AND fusionada_con IS NULL''').fetchall():
                try:
                    days = (date.today() - date.fromisoformat(row['ultimo_contacto'])).days
                    due = date.fromisoformat(row['fecha_seguimiento']) if row['fecha_seguimiento'] else None
                except ValueError:
                    continue
                if due is not None:
                    if due > date.today():
                        continue
                    detalle = f"Programado para {due.strftime('%d/%m/%Y')}"
                    if row['motivo_seguimiento']:
                        detalle += f" · {row['motivo_seguimiento']}"
                    key = f"seguimiento:{row['id']}:{due.isoformat()}"
                else:
                    if days < 7:
                        continue
                    detalle = f'{days} días sin contacto'
                    key = f"seguimiento:{row['id']}:{row['ultimo_contacto']}"
                con.execute('''INSERT OR IGNORE INTO notificaciones
                     (clave,tipo,referencia_id,titulo,detalle,creada_en,activa)
                     VALUES (?,?,?,?,?,?,1)''',
                     (key, 'seguimiento', row['id'], f"Seguimiento · {row['cliente']}",
                      detalle, stamp))
                con.execute('UPDATE notificaciones SET activa=1, detalle=? WHERE clave=?',
                            (detalle, key))
            # Actividades de seguimiento vencidas cargadas en la Agenda (misma fuente que Reportes).
            from .metrics import list_seguimientos_vencidos
            for act in list_seguimientos_vencidos(con):
                if act['origen'] == 'seguimiento_contacto':
                    continue  # ya avisado arriba por el seguimiento programado del contacto
                ref = act['oportunidad_id'] or 0
                if not ref and act['ficha_id']:
                    f = con.execute('SELECT oportunidad_id FROM fichas_consulta WHERE id=?', (act['ficha_id'],)).fetchone()
                    ref = (f['oportunidad_id'] if f else 0) or 0
                key = f"actividad:{act['id']}:{act['inicio']}"
                detalle = f"Vencido · {act['titulo']}"
                con.execute('''INSERT OR IGNORE INTO notificaciones (clave,tipo,referencia_id,titulo,detalle,creada_en,activa)
                     VALUES (?,?,?,?,?,?,1)''', (key, 'seguimiento', ref, f"Seguimiento · {act['cliente'] or act['titulo']}", detalle, stamp))
                con.execute('UPDATE notificaciones SET activa=1 WHERE clave=?', (key,))

    @app.get('/api/notifications')
    def notifications(request: Request):
        user_id = current_user_id(request)
        sync_notifications()
        with connect(db_path) as con:
            rows = con.execute('''SELECT n.id,n.tipo,n.referencia_id,n.titulo,n.detalle,
                 n.creada_en,CASE WHEN l.notificacion_id IS NULL THEN 0 ELSE 1 END AS leida
                 FROM notificaciones n LEFT JOIN notificaciones_lecturas l
                 ON l.notificacion_id=n.id AND l.usuario_id=?
                 WHERE n.activa=1 ORDER BY n.creada_en DESC,n.id DESC LIMIT 80''',(user_id,)).fetchall()
        items = [dict(row) for row in rows]
        return {'items':items, 'sin_leer':sum(1 for r in items if not r['leida'])}

    @app.post('/api/notifications/{notification_id}/read', dependencies=[Depends(require_access)])
    def read_notification(notification_id: int, request: Request):
        user_id = current_user_id(request)
        with connect(db_path) as con:
            if not con.execute('SELECT id FROM notificaciones WHERE id=? AND activa=1', (notification_id,)).fetchone():
                raise HTTPException(404, 'Notificación no encontrada')
            con.execute('''INSERT OR IGNORE INTO notificaciones_lecturas
                (notificacion_id,usuario_id,leida_en) VALUES (?,?,?)''',
                (notification_id, user_id, datetime.now(timezone.utc).isoformat()))
        return {'ok': True}

    @app.post('/api/notifications/read-all', dependencies=[Depends(require_access)])
    def read_all_notifications(request: Request):
        user_id = current_user_id(request)
        sync_notifications()
        with connect(db_path) as con:
            con.execute('''INSERT OR IGNORE INTO notificaciones_lecturas
                (notificacion_id, usuario_id, leida_en)
                SELECT id, ?, ? FROM notificaciones WHERE activa=1''',
                (user_id, datetime.now(timezone.utc).isoformat()))
        return {'ok': True}

    class NuevaConsulta(BaseModel):
        cliente: str = Field(min_length=2, max_length=120)
        contacto: str = Field(min_length=2, max_length=120)
        texto: str = Field(min_length=5, max_length=5000)
        canal: CanalOrigen = 'Manual'

    @app.post('/api/inbox', status_code=201, dependencies=[Depends(require_access)])
    def add_inbox_message(payload: NuevaConsulta):
        received = datetime.now(timezone.utc).isoformat()
        with connect(db_path) as con:
            cur = con.execute('''INSERT INTO bandeja_consultas
              (cliente,contacto,canal,texto,recibido_el,estado) VALUES (?,?,?,?,?,'nueva')''',
              (payload.cliente.strip(),payload.contacto.strip(),payload.canal,payload.texto.strip(),received))
            row = con.execute('SELECT * FROM bandeja_consultas WHERE id=?',(cur.lastrowid,)).fetchone()
        sync_notifications()
        return dict(row)

    class AnalizarBandejaInput(BaseModel):
        regenerar: bool = False
        informar_lote_minimo: bool = False

    class GuardarBorradorInput(BaseModel):
        borrador: str = Field(max_length=7000)

    def last_analysis(con, message_id: int):
        row = con.execute('''SELECT id,version,resultado_json,borrador,generado_en,actualizado_en
                 FROM consultas_analisis WHERE consulta_id=? ORDER BY version DESC LIMIT 1''',
                 (message_id,)).fetchone()
        return None if row is None else {
            'id': row['id'], 'version': row['version'], 'resultado': json.loads(row['resultado_json']),
            'borrador': row['borrador'], 'generado_en': row['generado_en'],
            'actualizado_en': row['actualizado_en']
        }

    @app.get('/api/inbox/{message_id}/analysis')
    def get_saved_analysis(message_id: int):
        with connect(db_path) as con:
            if not con.execute('SELECT id FROM bandeja_consultas WHERE id=?',(message_id,)).fetchone():
                raise HTTPException(404,'Consulta no encontrada')
            return {'analisis':last_analysis(con,message_id)}

    @app.post('/api/inbox/{message_id}/analysis',dependencies=[Depends(require_access)])
    def analyze_saved_inbox(message_id: int,payload: AnalizarBandejaInput):
        with connect(db_path) as con:
            msg = con.execute('SELECT texto,ficha_id FROM bandeja_consultas WHERE id=?',(message_id,)).fetchone()
            if msg is None:
                raise HTTPException(404,'Consulta no encontrada')
            existing = last_analysis(con,message_id)
            # La IA recibe la gestión completa: datos de la ficha + todos los mensajes, de todos los canales.
            texto = (build_case_context(con, msg['ficha_id'], message_id, payload.informar_lote_minimo)
                     if msg['ficha_id'] else msg['texto'])
        if existing and existing['resultado'] is not None and not payload.regenerar:
            return existing
        reserve_ai_call()
        try:
            result = app.state.analizar_consulta(texto)
        except (OpenAIError,RuntimeError,ValueError) as exc:
            logger.warning('Falló análisis de bandeja: %s',type(exc).__name__)
            raise HTTPException(503,'No se pudo preparar la respuesta') from exc
        payload_data = result.model_dump() if hasattr(result,'model_dump') else dict(result)
        draft = payload_data.get('respuesta_sugerida','')
        stamp = datetime.now(timezone.utc).isoformat()
        with connect(db_path) as con:
            if msg['ficha_id']:
                # La ficha es la fuente de verdad: se completan vacíos y se corrige lo ya informado.
                payload_data = apply_analysis(con, msg['ficha_id'], payload_data, payload.regenerar)
            con.execute('''INSERT INTO consultas_analisis
              (consulta_id,version,resultado_json,borrador,generado_en,actualizado_en)
              VALUES (?,?,?,?,?,?)''',
              (message_id,(existing['version'] if existing else 0)+1,
               json.dumps(payload_data,ensure_ascii=False),draft,stamp,stamp))
            return last_analysis(con,message_id)

    @app.post('/api/inbox/{message_id}/draft',dependencies=[Depends(require_access)])
    def save_saved_draft(message_id: int,payload: GuardarBorradorInput):
        with connect(db_path) as con:
            if not con.execute('SELECT id FROM bandeja_consultas WHERE id=?',(message_id,)).fetchone():
                raise HTTPException(404,'Mensaje no encontrado')
            row = last_analysis(con,message_id)
            stamp = datetime.now(timezone.utc).isoformat()
            if row is None:
                # A human-written draft must not require or consume an AI call.
                con.execute('''INSERT INTO consultas_analisis
                    (consulta_id,version,resultado_json,borrador,generado_en,actualizado_en)
                    VALUES (?,?,?, ?,?,?)''', (message_id,1,'null',payload.borrador,stamp,stamp))
            else:
                con.execute('UPDATE consultas_analisis SET borrador=?,actualizado_en=? WHERE id=?',
                            (payload.borrador,stamp,row['id']))
            return last_analysis(con,message_id)

    class CambiarEstadoConsulta(BaseModel):
        estado: str = Field(pattern='^(nueva|en_gestion|resuelta)$')

    @app.get('/api/inbox')
    def inbox():
        # Solo datos ficticios: se simula una bandeja de mensajes, no una integración externa.
        with connect(db_path) as con:
            rows = con.execute('SELECT * FROM bandeja_consultas ORDER BY recibido_el DESC, id DESC').fetchall()
        return [dict(row) for row in rows]

    @app.post('/api/inbox/{message_id}/status', dependencies=[Depends(require_access)])
    def change_inbox_status(message_id: int, payload: CambiarEstadoConsulta):
        with connect(db_path) as con:
            updated = con.execute('UPDATE bandeja_consultas SET estado = ? WHERE id = ?',
                                  (payload.estado, message_id))
            if updated.rowcount == 0:
                raise HTTPException(404, 'Consulta no encontrada')
            row = con.execute('SELECT * FROM bandeja_consultas WHERE id = ?', (message_id,)).fetchone()
        return dict(row)

    @app.post('/api/inbox/{message_id}/link-opportunity', dependencies=[Depends(require_access)])
    def link_inbox_opportunity(message_id: int, payload: dict[str, int]):
        opportunity_id = payload.get('opportunity_id')
        if not isinstance(opportunity_id, int) or isinstance(opportunity_id, bool):
            raise HTTPException(422, 'ID de oportunidad inválido')
        with connect(db_path) as con:
            if not con.execute('SELECT id FROM oportunidades WHERE id=?', (opportunity_id,)).fetchone():
                raise HTTPException(404, 'Oportunidad no encontrada')
            updated = con.execute('UPDATE bandeja_consultas SET oportunidad_id=?, estado=? WHERE id=?',
                                  (opportunity_id, 'en_gestion', message_id))
            if not updated.rowcount:
                raise HTTPException(404, 'Consulta no encontrada')
            row = con.execute('SELECT * FROM bandeja_consultas WHERE id=?', (message_id,)).fetchone()
        return dict(row)

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
                  (cliente, contacto, producto, cantidad, monto_estimado_usd, estado, creada_el, ultimo_contacto, notas,
                   tipo_consulta, canal_origen, presentacion, packaging, responsable)
                  VALUES (?, ?, ?, ?, ?, 'nueva', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload.cliente, payload.contacto, payload.producto, payload.cantidad,
                 payload.monto_estimado_usd, today, today, payload.notas, payload.tipo_consulta,
                 payload.canal_origen, payload.presentacion, payload.packaging, payload.responsable))
            con.execute("INSERT INTO interacciones (oportunidad_id, tipo, descripcion, fecha) VALUES (?, 'consulta', ?, ?)",
                        (cur.lastrowid, "Oportunidad creada manualmente", today))
            new_id = cur.lastrowid
            # El estado comercial vive en la gestión: cada contacto nuevo nace con una gestión.
            create_case_for_contact(con, con.execute('SELECT * FROM oportunidades WHERE id=?', (new_id,)).fetchone())
        return get_opportunity(new_id)

    @app.post('/api/opportunities/{opportunity_id}/commercial-details', response_model=OportunidadDetalle,
              dependencies=[Depends(require_access)])
    def edit_commercial_details(opportunity_id: int, payload: EditarDatosComerciales):
        get_opportunity(opportunity_id)
        with connect(db_path) as con:
            con.execute('''UPDATE oportunidades SET tipo_consulta=?, canal_origen=?, presentacion=?,
                packaging=?, responsable=? WHERE id=?''',
                (payload.tipo_consulta, payload.canal_origen, payload.presentacion.strip(),
                 payload.packaging.strip(), payload.responsable.strip(), opportunity_id))
        return get_opportunity(opportunity_id)

    @app.post('/api/opportunities/{opportunity_id}/follow-up', response_model=OportunidadDetalle,
              dependencies=[Depends(require_access)])
    def schedule_follow_up(opportunity_id: int, payload: ProgramarSeguimiento):
        get_opportunity(opportunity_id)
        due = payload.fecha_seguimiento.isoformat() if payload.fecha_seguimiento else None
        reason = payload.motivo_seguimiento.strip() if due else ''
        with connect(db_path) as con:
            previous = con.execute('''SELECT fecha_seguimiento, motivo_seguimiento FROM oportunidades WHERE id=?''',
                                   (opportunity_id,)).fetchone()
            if previous['fecha_seguimiento'] != due or previous['motivo_seguimiento'] != reason:
                con.execute('''UPDATE oportunidades SET fecha_seguimiento=?, motivo_seguimiento=? WHERE id=?''',
                            (due, reason, opportunity_id))
                description = (f'Seguimiento programado para {due}: {reason or "Sin motivo indicado"}'
                               if due else 'Se eliminó la fecha de seguimiento programada')
                con.execute('''INSERT INTO interacciones (oportunidad_id,tipo,descripcion,fecha)
                    VALUES (?,'nota',?,?)''', (opportunity_id, description, date.today().isoformat()))
            # El seguimiento programado se refleja en la Agenda (una sola fuente para vencidos).
            cliente = con.execute('SELECT cliente FROM oportunidades WHERE id=?', (opportunity_id,)).fetchone()['cliente']
            sync_contact_followup(con, opportunity_id, due, reason, cliente)
        return get_opportunity(opportunity_id)

    class CambiarEstadoComercial(BaseModel):
        estado: Estado

    @app.post("/api/opportunities/{opportunity_id}/status", response_model=OportunidadDetalle,
              dependencies=[Depends(require_access)])
    def cambiar_estado_comercial(opportunity_id: int, payload: CambiarEstadoComercial):
        """El vendedor decide la etapa comercial; no se infiere automáticamente por IA.

        Conservar el historial permite recuperar un contacto ganado/perdido e incluso reabrirlo.
        El cambio de etapa no cuenta como un nuevo contacto con el cliente.
        """
        nombres = {
            'nueva': 'Nueva', 'contactada': 'Contactada', 'cotizada': 'Cotizada',
            'negociacion': 'En negociación', 'ganada': 'Ganada', 'perdida': 'Perdida',
        }
        with connect(db_path) as con:
            row = con.execute("SELECT estado FROM oportunidades WHERE id = ?", (opportunity_id,)).fetchone()
            if row is None:
                raise HTTPException(404, 'Contacto comercial no encontrado')
            if row['estado'] != payload.estado:
                con.execute("UPDATE oportunidades SET estado = ?, fecha_cierre = ? WHERE id = ?", (payload.estado, date.today().isoformat() if payload.estado in ('ganada','perdida') else None, opportunity_id))
                con.execute("""INSERT INTO interacciones (oportunidad_id, tipo, descripcion, fecha)
                    VALUES (?, 'nota', ?, ?)""", (
                    opportunity_id,
                    f"Estado comercial actualizado: {nombres[row['estado']]} → {nombres[payload.estado]}",
                    date.today().isoformat(),
                ))
        return get_opportunity(opportunity_id)

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
            if payload.tipo in ("correo", "llamada", "reunion"):
                if interaction_date > previous:
                    con.execute("UPDATE oportunidades SET ultimo_contacto = ? WHERE id = ?",
                                (interaction_date.isoformat(), opportunity_id))
                # Un contacto realizado en la fecha acordada cumple el recordatorio.
                planned = con.execute('SELECT fecha_seguimiento FROM oportunidades WHERE id=?', (opportunity_id,)).fetchone()
                if planned['fecha_seguimiento'] and interaction_date >= date.fromisoformat(planned['fecha_seguimiento']):
                    con.execute("UPDATE oportunidades SET fecha_seguimiento=NULL, motivo_seguimiento='' WHERE id=?",
                                (opportunity_id,))
                    complete_contact_followup(con, opportunity_id)
        return get_opportunity(opportunity_id)

    # El servicio se inyecta para permitir tests offline y para evitar llamadas reales en CI.
    def get_ai_profile():
        with connect(db_path) as con:
            try:
                row=con.execute('SELECT * FROM ia_configuracion WHERE id=1').fetchone()
                return dict(row) if row else {}
            except Exception:
                return {}
    app.state.analizar_consulta = lambda texto: ai.analizar_consulta(texto, get_ai_profile())
    app.state.generar_seguimiento = lambda contexto: ai.generar_seguimiento(contexto, get_ai_profile())

    @app.post('/api/ai/analyze-inquiry', response_model=ai.ConsultaExtraida, dependencies=[Depends(require_access)])
    def analyze_inquiry(payload: ConsultaInput):
        reserve_ai_call()
        try:
            return app.state.analizar_consulta(payload.texto)
        except (OpenAIError, RuntimeError, ValueError) as exc:
            logger.warning('Falló extracción con IA: %s', type(exc).__name__)
            raise HTTPException(503, 'No se pudo generar el análisis. Verificá la configuración de OpenAI e intentá nuevamente.') from exc

    def saved_follow_up(con,opportunity_id:int):
        row=con.execute('''SELECT id,version,resultado_json,asunto,mensaje,generado_en,actualizado_en
            FROM seguimientos_ia WHERE oportunidad_id=? ORDER BY version DESC LIMIT 1''',
            (opportunity_id,)).fetchone()
        if row is None:return None
        return {'id':row['id'],'version':row['version'],
                'resultado':json.loads(row['resultado_json']),
                'asunto':row['asunto'],'mensaje':row['mensaje'],
                'generado_en':row['generado_en'],'actualizado_en':row['actualizado_en']}

    @app.get('/api/opportunities/{opportunity_id}/saved-follow-up')
    def get_saved_follow_up(opportunity_id:int):
        get_opportunity(opportunity_id)
        with connect(db_path) as con:
            return {'borrador':saved_follow_up(con,opportunity_id)}

    class GenerarSeguimientoInput(BaseModel):
        regenerar:bool=False

    @app.post('/api/opportunities/{opportunity_id}/saved-follow-up',dependencies=[Depends(require_access)])
    def generate_saved_follow_up(opportunity_id:int,payload:GenerarSeguimientoInput):
        item=get_opportunity(opportunity_id)
        with connect(db_path) as con:
            existing=saved_follow_up(con,opportunity_id)
        if existing and not payload.regenerar:return existing
        reserve_ai_call()
        try:
            contexto=json.dumps(item,ensure_ascii=False,default=str)
            generated=app.state.generar_seguimiento(contexto)
        except (OpenAIError,RuntimeError,ValueError) as exc:
            logger.warning('Falló seguimiento con IA: %s',type(exc).__name__)
            raise HTTPException(503,'No se pudo preparar el seguimiento') from exc
        result=generated.model_dump() if hasattr(generated,'model_dump') else dict(generated)
        stamp=datetime.now(timezone.utc).isoformat()
        with connect(db_path) as con:
            con.execute('''INSERT INTO seguimientos_ia
              (oportunidad_id,version,resultado_json,asunto,mensaje,generado_en,actualizado_en)
              VALUES (?,?,?,?,?,?,?)''',(opportunity_id,(existing['version'] if existing else 0)+1,
              json.dumps(result,ensure_ascii=False),result.get('asunto',''),result.get('mensaje',''),stamp,stamp))
            return saved_follow_up(con,opportunity_id)

    class EditarSeguimientoInput(BaseModel):
        asunto:str=Field(max_length=250)
        mensaje:str=Field(max_length=7000)

    @app.post('/api/opportunities/{opportunity_id}/saved-follow-up/edit',dependencies=[Depends(require_access)])
    def edit_saved_follow_up(opportunity_id:int,payload:EditarSeguimientoInput):
        with connect(db_path) as con:
            existing=saved_follow_up(con,opportunity_id)
            if not existing:raise HTTPException(404,'No hay borrador guardado')
            stamp=datetime.now(timezone.utc).isoformat()
            con.execute('UPDATE seguimientos_ia SET asunto=?,mensaje=?,actualizado_en=? WHERE id=?',
                        (payload.asunto,payload.mensaje,stamp,existing['id']))
            return saved_follow_up(con,opportunity_id)

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

    register_business_v2(app, db_path, reserve_ai_call)
    register_business_v3(app, db_path)
    register_business_v4(app, db_path)
    return app

app = create_app()
