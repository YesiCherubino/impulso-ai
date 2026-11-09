from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Estado = Literal["nueva", "contactada", "cotizada", "negociacion", "ganada", "perdida"]
TipoInteraccion = Literal["consulta", "correo", "llamada", "reunion", "nota"]
TipoConsulta = Literal["sin_clasificar", "fabricacion_terceros", "desarrollo_formula", "elaboracion_envasado", "mayorista", "otro"]
CanalOrigen = Literal["Manual", "WhatsApp", "Correo", "Formulario web", "Teléfono", "Otro"]

class NuevaOportunidad(BaseModel):
    cliente: str = Field(min_length=2, max_length=120)
    contacto: str = Field(min_length=2, max_length=120)
    producto: str = Field(min_length=2, max_length=150)
    cantidad: int | None = Field(default=None, ge=1)
    monto_estimado_usd: float | None = Field(default=None, ge=0)
    notas: str = Field(default="", max_length=3000)
    tipo_consulta: TipoConsulta = 'sin_clasificar'
    canal_origen: CanalOrigen = 'Manual'
    presentacion: str = Field(default='', max_length=120)
    packaging: str = Field(default='', max_length=200)
    responsable: str = Field(default='', max_length=120)

class EditarDatosComerciales(BaseModel):
    tipo_consulta: TipoConsulta
    canal_origen: CanalOrigen
    presentacion: str = Field(max_length=120)
    packaging: str = Field(max_length=200)
    responsable: str = Field(max_length=120)

class ProgramarSeguimiento(BaseModel):
    fecha_seguimiento: date | None = None
    motivo_seguimiento: str = Field(default='', max_length=300)

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
    tipo_consulta: TipoConsulta
    canal_origen: CanalOrigen
    presentacion: str
    packaging: str
    responsable: str
    fecha_seguimiento: date | None
    motivo_seguimiento: str

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
