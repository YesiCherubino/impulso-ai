export type Estado = 'nueva' | 'contactada' | 'cotizada' | 'negociacion' | 'ganada' | 'perdida';
export type Tipo = 'consulta' | 'correo' | 'llamada' | 'reunion' | 'nota';
export type TipoConsulta = 'sin_clasificar'|'fabricacion_terceros'|'desarrollo_formula'|'elaboracion_envasado'|'mayorista'|'otro';
export type CanalOrigen = 'Manual'|'WhatsApp'|'Correo'|'Formulario web'|'Teléfono'|'Otro';
export const tipoConsultaNombre:Record<TipoConsulta,string>={sin_clasificar:'Sin clasificar',fabricacion_terceros:'Fabricación para terceros',desarrollo_formula:'Desarrollo de fórmula',elaboracion_envasado:'Elaboración y envasado',mayorista:'Compra mayorista',otro:'Otra consulta'};
export const tiposConsulta=Object.entries(tipoConsultaNombre) as [TipoConsulta,string][];
export const canalesOrigen:CanalOrigen[]=['Manual','WhatsApp','Correo','Formulario web','Teléfono','Otro'];
export type Resumen = { oportunidades_activas:number; valor_potencial_usd:number; cotizaciones_pendientes:number; sin_seguimiento:number; acciones_sugeridas:number; fecha_consulta:string };
export type Oportunidad = { id:number; cliente:string; contacto:string; producto:string; cantidad:number|null; monto_estimado_usd:number|null; estado:Estado; creada_el:string; ultimo_contacto:string; dias_sin_contacto:number; seguimiento_pendiente:boolean; proxima_accion:string|null; tipo_consulta:TipoConsulta; canal_origen:CanalOrigen; presentacion:string; packaging:string; responsable:string; fecha_seguimiento:string|null; motivo_seguimiento:string };
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
export const estadoNombre:Record<Estado,string>={nueva:'Nueva',contactada:'Contactada',cotizada:'Cotizada',negociacion:'En negociación',ganada:'Ganada',perdida:'Perdida'};

export type ConsultaIA = {cliente:string;contacto:string;producto:string;cantidad:number|null;requisitos:string[];datos_faltantes:string[];resumen:string;respuesta_sugerida:string;tipo_consulta?:TipoConsulta;presentacion?:string;necesita_formula?:'si'|'no'|'sin_especificar';necesita_packaging?:'si'|'no'|'sin_especificar'};
export type SeguimientoIA = {motivo:string;asunto:string;mensaje:string;consideraciones:string[]};

export type ConsultaBandeja = {id:number;cliente:string;contacto:string;canal:string;texto:string;recibido_el:string;estado:'nueva'|'en_gestion'|'resuelta';oportunidad_id:number|null};
