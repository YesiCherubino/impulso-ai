export type Estado = 'nueva' | 'contactada' | 'cotizada' | 'negociacion' | 'ganada' | 'perdida';
export type Tipo = 'consulta' | 'correo' | 'llamada' | 'reunion' | 'nota';
export type Resumen = { oportunidades_activas:number; valor_potencial_usd:number; cotizaciones_pendientes:number; sin_seguimiento:number; acciones_sugeridas:number; fecha_consulta:string };
export type Oportunidad = { id:number; cliente:string; contacto:string; producto:string; cantidad:number|null; monto_estimado_usd:number|null; estado:Estado; creada_el:string; ultimo_contacto:string; dias_sin_contacto:number; seguimiento_pendiente:boolean; proxima_accion:string|null };
export type Interaccion = { id:number; tipo:Tipo; descripcion:string; fecha:string };
export type Detalle = Oportunidad & { notas:string; interacciones:Interaccion[] };
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8001').replace(/\/$/, '');
export async function api<T>(path:string, options?:RequestInit):Promise<T>{
  let response:Response;
  let demoCode = '';
  if (options?.method?.toUpperCase() === 'POST' && process.env.NEXT_PUBLIC_DEMO_REQUIRES_CODE === 'true') {
    demoCode = sessionStorage.getItem('impulso-demo-code') || '';
    if (!demoCode) {
      demoCode = window.prompt('Ingresá el código de acceso de la demo para continuar:')?.trim() || '';
      if (!demoCode) throw new Error('Ingresá el código de acceso para continuar');
      sessionStorage.setItem('impulso-demo-code', demoCode);
    }
  }
  try {response = await fetch(`${BASE}${path}`, {cache:'no-store', ...options,headers:{'Content-Type':'application/json',...(demoCode ? {'X-Demo-Code': demoCode} : {}),...(options?.headers || {})}})}
  catch { throw new Error('No pudimos conectar con FastAPI. Verificá que esté ejecutándose en el puerto 8001.'); }
  if(response.status === 401 && typeof window !== 'undefined') sessionStorage.removeItem('impulso-demo-code');
  if(!response.ok){ const body:unknown = await response.json().catch(()=>null); const detail = body && typeof body==='object' && 'detail' in body ? String((body as {detail:unknown}).detail) : ''; throw new Error(detail || `Error del servidor (${response.status})`); }
  return response.json() as Promise<T>;
}
export const money=(n:number|null|undefined)=> n==null ? 'Sin estimar' : `USD ${n.toLocaleString('es-AR', {maximumFractionDigits:0})}`;
export const dateAR=(s:string)=> new Date(`${s}T12:00:00`).toLocaleDateString('es-AR',{day:'2-digit',month:'short',year:'numeric'});
export const estadoNombre:Record<Estado,string>={nueva:'Nueva',contactada:'Contactada',cotizada:'Cotizada',negociacion:'En negociación',ganada:'Ganada',perdida:'Perdida'};

export type ConsultaIA = {cliente:string;contacto:string;producto:string;cantidad:number|null;requisitos:string[];datos_faltantes:string[];resumen:string;respuesta_sugerida:string};
export type SeguimientoIA = {motivo:string;asunto:string;mensaje:string;consideraciones:string[]};
