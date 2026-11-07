from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Estado = Literal["nueva", "contactada", "cotizada", "negociacion", "ganada", "perdida"]
TipoInteraccion = Literal["consulta", "correo", "llamada", "reunion", "nota"]

class NuevaOportunidad(BaseModel):
    cliente: str = Field(min_length=2, max_length=120)
    contacto: str = Field(min_length=2, max_length=120)
    producto: str = Field(min_length=2, max_length=150)
    cantidad: int | None = Field(default=None, ge=1)
    monto_estimado_usd: float | None = Field(default=None, ge=0)
    notas: str = Field(default="", max_length=3000)

class NuevaInteraccion(BaseModel):
    tipo: TipoInteraccion
    descripcion: str = Field(min_length=3, max_length=2000)
    fecha: date | None = None

class Interaccion(BaseModel):
    id: int
    tipo: TipoInteraccion
    descripcion: str
    fecha: date

class Oportunidad(BaseModel):
    id: int
    cliente: str
    contacto: str
    producto: str
    cantidad: int | None
    monto_estimado_usd: float | None
    estado: Estado
    creada_el: date
    ultimo_contacto: date
    dias_sin_contacto: int
    seguimiento_pendiente: bool
    proxima_accion: str | None

class OportunidadDetalle(Oportunidad):
    notas: str
    interacciones: list[Interaccion]

class Resumen(BaseModel):
    oportunidades_activas: int
    valor_potencial_usd: float
    cotizaciones_pendientes: int
    sin_seguimiento: int
    acciones_sugeridas: int
    fecha_consulta: date
