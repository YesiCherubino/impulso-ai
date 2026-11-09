"""Reglas de negocio de Impulso (sin IA)."""
from datetime import date
from sqlite3 import Row

CERRADAS = {"ganada", "perdida"}
DIAS_SEGUIMIENTO = 7

def to_opportunity(row: Row, today: date) -> dict:
    last = date.fromisoformat(row["ultimo_contacto"])
    days = max(0, (today - last).days)
    active = row["estado"] not in CERRADAS
    due = date.fromisoformat(row['fecha_seguimiento']) if row['fecha_seguimiento'] else None
    # La fecha programada tiene prioridad sobre el aviso automático de 7 días.
    pending = active and (due <= today if due is not None else days >= DIAS_SEGUIMIENTO)
    if pending and due is not None:
        action = row['motivo_seguimiento'] or 'Realizar seguimiento programado'
    elif pending and row["estado"] == "cotizada":
        action = "Retomar contacto por cotización sin respuesta"
    elif pending:
        action = "Contactar al cliente para actualizar la oportunidad"
    elif active and row["estado"] == "nueva":
        action = "Revisar la consulta y preparar primera respuesta"
    else:
        action = None
    return {
        "id": row["id"], "cliente": row["cliente"], "contacto": row["contacto"],
        "producto": row["producto"], "cantidad": row["cantidad"],
        "monto_estimado_usd": row["monto_estimado_usd"], "estado": row["estado"],
        "creada_el": row["creada_el"], "ultimo_contacto": row["ultimo_contacto"],
        "dias_sin_contacto": days, "seguimiento_pendiente": pending, "proxima_accion": action,
        "tipo_consulta": row['tipo_consulta'], "canal_origen": row['canal_origen'],
        "presentacion": row['presentacion'], "packaging": row['packaging'],
        "responsable": row['responsable'],
        "fecha_seguimiento": row['fecha_seguimiento'], "motivo_seguimiento": row['motivo_seguimiento'],
    }

def metrics(items: list[dict], today: date) -> dict:
    active = [item for item in items if item["estado"] not in CERRADAS]
    pending = [item for item in active if item["seguimiento_pendiente"]]
    return {
        "oportunidades_activas": len(active),
        "valor_potencial_usd": round(sum(item["monto_estimado_usd"] or 0 for item in active), 2),
        "cotizaciones_pendientes": sum(item["estado"] == "cotizada" for item in active),
        "sin_seguimiento": len(pending),
        "acciones_sugeridas": sum(item["proxima_accion"] is not None for item in active),
        "fecha_consulta": today,
    }
