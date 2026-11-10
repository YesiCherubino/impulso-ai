export type Estado = 'nueva' | 'contactada' | 'cotizada' | 'negociacion' | 'ganada' | 'perdida';
export type Tipo = 'consulta' | 'correo' | 'llamada' | 'reunion' | 'nota';
export type TipoConsulta = 'sin_clasificar'|'fabricacion_terceros'|'desarrollo_formula'|'elaboracion_envasado'|'mayorista'|'exportacion'|'no_comercial'|'otro';
export type CanalOrigen = 'Manual'|'WhatsApp'|'Correo'|'Formulario web'|'Teléfono'|'Otro';
export const tipoConsultaNombre:Record<TipoConsulta,string>={sin_clasificar:'Sin clasificar',fabricacion_terceros:'Fabricación para terceros',desarrollo_formula:'Desarrollo de fórmula',elaboracion_envasado:'Elaboración y envasado',mayorista:'Compra mayorista (marcas propias)',exportacion:'Exportación',no_comercial:'No comercial',otro:'Otra consulta'};
export const tiposConsulta=Object.entries(tipoConsultaNombre) as [TipoConsulta,string][];
export const canalesOrigen:CanalOrigen[]=['Manual','WhatsApp','Correo','Formulario web','Teléfono','Otro'];
export type Resumen = { oportunidades_activas:number; valor_potencial_usd:number; cotizaciones_pendientes:number; sin_seguimiento:number; acciones_sugeridas:number; fecha_consulta:string };
export type Oportunidad = { id:number; cliente:string; contacto:string; email?:string; telefono?:string; producto:string; cantidad:number|null; monto_estimado_usd:number|null; estado:Estado; creada_el:string; ultimo_contacto:string; dias_sin_contacto:number; seguimiento_pendiente:boolean; proxima_accion:string|null; tipo_consulta:TipoConsulta; canal_origen:CanalOrigen; presentacion:string; packaging:string; responsable:string; fecha_seguimiento:string|null; motivo_seguimiento:string };
export type Interaccion = { id:number; tipo:Tipo; descripcion:string; fecha:string };
export type Detalle = Oportunidad & { notas:string; interacciones:Interaccion[] };
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8001').replace(/\/$/, '');
export async function api<T>(path:string,options?:RequestInit):Promise<T>{
  const authEnabled=process.env.NEXT_PUBLIC_AUTH_ENABLED==='true';
  const url=authEnabled ? `/api/backend/${path.replace(/^\/api\//,'')}` : `${BASE}${path}`;
  let code='';
  if (!authEnabled && options?.method?.toUpperCase()==='POST' && process.env.NEXT_PUBLIC_DEMO_REQUIRES_CODE==='true'){
    code=sessionStorage.getItem('impulso-demo-code')||'';
    if(!code){code=window.prompt('Ingresá el código de acceso para continuar:')?.trim()||'';if(!code)throw new Error('Ingresá el código para continuar');sessionStorage.setItem('impulso-demo-code',code)}
  }
  let response:Response;
  try{response=await fetch(url,{cache:'no-store',...options,headers:{'Content-Type':'application/json',...(code?{'X-Demo-Code':code}:{}),...(options?.headers||{})}})}
  catch{throw new Error('No se pudo conectar con el servicio. Intentá nuevamente.');}
  if(response.status===401){
    if(authEnabled && typeof window!=='undefined')window.location.assign('/login');
    else if(typeof window!=='undefined')sessionStorage.removeItem('impulso-demo-code');
  }
  if(!response.ok){const body:unknown=await response.json().catch(()=>null);const detail=body&&typeof body==='object'&&'detail'in body?String((body as {detail:unknown}).detail):'';throw new Error(detail||`Error del servidor (${response.status})`)}
  return response.json() as Promise<T>;
}
export const money=(n:number|null|undefined)=> n==null ? 'Sin estimar' : `USD ${n.toLocaleString('es-AR', {maximumFractionDigits:0})}`;
export const dateAR=(s:string)=> new Date(`${s}T12:00:00`).toLocaleDateString('es-AR',{day:'2-digit',month:'short',year:'numeric'});
export const estadoNombre:Record<Estado,string>={nueva:'Nueva',contactada:'Contactada',cotizada:'Cotizada',negociacion:'En negociación',ganada:'Concretada',perdida:'No concretada'};

export type ConsultaIA = {cliente:string;contacto:string;producto:string;cantidad:number|null;requisitos:string[];datos_faltantes:string[];resumen:string;respuesta_sugerida:string;tipo_consulta?:TipoConsulta;presentacion?:string;necesita_formula?:'si'|'no'|'sin_especificar';necesita_packaging?:'si'|'no'|'sin_especificar';datos_a_confirmar?:string[]};
export type SeguimientoIA = {motivo:string;asunto:string;mensaje:string;consideraciones:string[]};

export type Rol='ventas'|'administrador'|'gerencia';
export const roleName:Record<Rol,string>={ventas:'Ventas',administrador:'Administrador',gerencia:'Gerencia'};
export type UsuarioSesion={id:number;username:string;name:string;role:Rol;theme:'claro'|'oscuro'};
export type ConsultaBandeja = {id:number;cliente:string;contacto:string;canal:string;texto:string;recibido_el:string;estado:'nueva'|'en_gestion'|'resuelta';oportunidad_id:number|null;ficha_id:number|null;leido_en:string|null;email_remitente:string;telefono_remitente:string;asunto:string;direccion?:'entrante'|'saliente';usuario?:string};

/* Pipeline único de la gestión comercial (V4). */
export type EstadoGestion='sin_atender'|'calificada'|'cotizada'|'muestra_piloto'|'concretada'|'no_concretada'|'resuelta';
export const estadoGestionNombre:Record<string,string>={sin_atender:'Sin atender',calificada:'Calificada',cotizada:'Cotizada',muestra_piloto:'Muestra / piloto',concretada:'Concretada',no_concretada:'No concretada',resuelta:'Resuelta',fusionada:'Fusionada',en_gestion:'Calificada'};
export const ESTADOS_ABIERTOS:EstadoGestion[]=['sin_atender','calificada','cotizada','muestra_piloto'];
export const ESTADOS_GESTION:EstadoGestion[]=[...ESTADOS_ABIERTOS,'concretada','no_concretada','resuelta'];
export const esCerrada=(estado?:string)=>!ESTADOS_ABIERTOS.includes((estado||'sin_atender') as EstadoGestion);
export const MOTIVOS_NO_CONCRETADA=['Precio','Volumen bajo el mínimo','Plazo','Sin respuesta del cliente','Eligió otro proveedor','Otro'];
export type Respuesta={pendiente:boolean;horas:number;desde:string|null};
export type FichaConsulta = {id:number;codigo:string;oportunidad_id:number|null;titulo:string;cliente:string;contacto:string;producto:string;cantidad:number|null;tipo_consulta:TipoConsulta;presentacion:string;packaging:string;requisitos:string[];datos_faltantes:string[];resumen:string;creada_en:string;actualizada_en:string;mensajes?:ConsultaBandeja[];mensajes_count?:number;estado_gestion?:string;cerrada_en?:string|null;motivo_cierre?:string;
 formula?:'propia'|'desarrollo_pasmanter'|'sin_especificar';marca_registrada?:'si'|'no'|'sin_especificar';registro_anmat?:'si'|'no'|'en_tramite'|'sin_especificar';destino?:''|'local'|'exportacion';pais_destino?:string;plazo_deseado?:string;localidad?:string;responsable?:string;
 cotizacion_monto?:number|null;cotizacion_moneda?:''|'ARS'|'USD';cotizacion_fecha?:string|null;cotizacion_validez_dias?:number|null;tipo_sugerido_ia?:number;
 bajo_minimo?:boolean;lote_minimo?:number;datos_a_confirmar?:string[];campos_editados?:string[];canal_origen?:string;respuesta?:Respuesta;duplicados?:Duplicado[]};
export type Duplicado={id:number;codigo:string;titulo:string;cliente:string;producto:string;estado_gestion:string;oportunidad_id:number|null;mensajes:number};
export type GestionHilo={id:number;codigo:string;titulo:string;estado_gestion:string;tipo_consulta:TipoConsulta;tipo_sugerido_ia:number;cantidad:number|null;producto:string;responsable:string;cerrada_en:string|null;cotizacion_monto:number|null;cotizacion_moneda:string;bajo_minimo:boolean};
export type Responsable={username:string;name:string;role:Rol};
/* Escalabilidad: listados paginados desde el servidor. */
export type Pagina<T>={items:T[];total:number;limit:number;offset:number;conteos?:Record<string,number>};
export type Conversacion={key:string;cliente:string;contacto:string;ultimo:string;mensajes_count:number;no_leidos:number;cerrada:boolean;mensaje_tras_cierre:boolean;respuesta:Respuesta;ultimo_texto:string;ultimo_saliente:boolean;gestion:GestionHilo|null};
export type ConversacionDetalle=Conversacion&{mensajes:ConsultaBandeja[];hay_anteriores:boolean;fichas:FichaConsulta[]};
export type ContactoResumen={id:number;cliente:string;contacto:string;email:string;telefono:string;producto:string;cantidad:number|null;tipo_consulta:TipoConsulta;responsable:string;ultimo_contacto:string;fecha_seguimiento:string|null;canal_origen:string;estado_gestion_actual:string;gestiones_abiertas:number;gestiones:number};
export const qs=(params:Record<string,string|number|boolean|null|undefined>)=>{const u=new URLSearchParams();Object.entries(params).forEach(([k,v])=>{if(v!==undefined&&v!==null&&v!=='')u.set(k,String(v))});return u.toString()};
export const cotizacionTexto=(monto?:number|null,moneda?:string|null)=>monto==null||!moneda?'':`${moneda} ${monto.toLocaleString('es-AR',{maximumFractionDigits:2})}`;
export const unidades=(n?:number|null)=>n==null?'':`${n.toLocaleString('es-AR')} u.`;
export function tiempoSinRespuesta(horas:number){if(horas<1)return 'hace menos de 1 h';if(horas<48)return `hace ${horas} h`;return `hace ${Math.floor(horas/24)} días`}
export type ReportBreakdown=Record<string,{concretadas:number;no_concretadas:number;tasa:number|null}>;
export type ReportData={periodo:string;desde:string;hasta:string;canal:string;responsable:string;indicadores:Record<string,number>;canales:Record<string,number>;productos_consultados:[string,number][];origen_datos:string;
 embudo?:{estado:string;cantidad:number;montos:Record<string,number>}[];conversion_por_tipo?:ReportBreakdown;conversion_por_canal?:ReportBreakdown;motivos_no_concretadas?:Record<string,number>;
 tiempo_primera_respuesta?:{promedio_horas:number|null;respondidas:number;sin_respuesta_registrada:number;por_canal:Record<string,{promedio_horas:number|null;gestiones:number}>;por_vendedor:Record<string,{promedio_horas:number|null;gestiones:number}>};
 alertas_sin_respuesta?:{ficha_id:number;codigo:string;cliente:string;horas:number;responsable:string;conversacion:string}[];seguimientos_vencidos_detalle?:{id:number;titulo:string;inicio:string;cliente:string;ficha_codigo:string|null;conversacion:string}[]};
export type ReportResponse={title:string;question:string;report:string;data:ReportData;generated_at:string};
