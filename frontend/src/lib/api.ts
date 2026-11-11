export type Estado = 'nueva' | 'contactada' | 'cotizada' | 'negociacion' | 'ganada' | 'perdida';
export type Tipo = 'consulta' | 'correo' | 'llamada' | 'reunion' | 'nota';
export type TipoConsulta = 'sin_clasificar'|'fabricacion_terceros'|'produccion_terceros'|'otros_servicios'|'desarrollo_formula'|'elaboracion_envasado'|'mayorista'|'exportacion'|'no_comercial'|'otro';
export type CanalOrigen = 'Manual'|'WhatsApp'|'Correo'|'Formulario web'|'Teléfono'|'Otro';
export const tipoConsultaNombre:Record<TipoConsulta,string>={sin_clasificar:'Sin clasificar',fabricacion_terceros:'Full Service',produccion_terceros:'Producción a terceros',elaboracion_envasado:'Elaboración y envasado',desarrollo_formula:'Desarrollo de fórmulas',otros_servicios:'Otros servicios',exportacion:'Exportación',mayorista:'Compra mayorista',no_comercial:'No comercial',otro:'Otra consulta'};
export const RUBROS=['Cuidado facial','Cuidado corporal','Protección solar','Bebés','Dermocosmética','Higiene','Perfumería','Capilar','Otro'];
export const ENVASES=['Frasco','Doypack','Pomo','Aerosol','Roll-on','Sachet','A definir'];
export const TIPOS_CLIENTE=['Cadena o supermercado','Farmacia','Marca propia o emprendimiento','Distribuidor','Exportador'];
export const ETAPAS_FULL=['Fórmula','Diseño de packaging','Abastecimiento','Elaboración','Envasado','Codificado','Estuchado','Celofanado','Entrega'];
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
export type Permiso='ver_todas'|'responder'|'gestionar'|'asignar'|'contactos'|'reportes_todos'|'reporte_ia'|'exportar'|'chat'|'tablero_otros';
export type UsuarioSesion={id:number;username:string;name:string;role:Rol;theme:'claro'|'oscuro'|'auto';permisos?:Partial<Record<Permiso,boolean>>;rol_real?:Rol;viendo_como?:Rol};
/* Sin inicio de sesión (demo local) todo está permitido. */
export const puede=(u:UsuarioSesion|null|undefined,p:Permiso)=>!u||!u.permisos||!!u.permisos[p];
export type ConsultaBandeja = {id:number;cliente:string;contacto:string;canal:string;texto:string;recibido_el:string;estado:'nueva'|'en_gestion'|'resuelta';oportunidad_id:number|null;ficha_id:number|null;leido_en:string|null;email_remitente:string;telefono_remitente:string;asunto:string;direccion?:'entrante'|'saliente';usuario?:string;adjuntos?:Adjunto[]};

/* Pipeline único de la gestión comercial (V4). */
export type EstadoGestion='sin_atender'|'calificada'|'cotizada'|'muestra_piloto'|'concretada'|'no_concretada'|'resuelta';
export const estadoGestionNombre:Record<string,string>={sin_atender:'Sin atender',calificada:'Calificada',cotizada:'Cotizada',muestra_piloto:'Muestra / piloto',concretada:'Concretada',no_concretada:'No concretada',resuelta:'Resuelta',fusionada:'Fusionada',en_gestion:'Calificada'};
export const ESTADOS_ABIERTOS:EstadoGestion[]=['sin_atender','calificada','cotizada','muestra_piloto'];
export const ESTADOS_GESTION:EstadoGestion[]=[...ESTADOS_ABIERTOS,'concretada','no_concretada','resuelta'];
export const esCerrada=(estado?:string)=>!ESTADOS_ABIERTOS.includes((estado||'sin_atender') as EstadoGestion);
export const MOTIVOS_NO_CONCRETADA=['Precio','Volumen bajo el mínimo','Plazo','Sin respuesta del cliente','Eligió otro proveedor','Otro'];
export type Respuesta={pendiente:boolean;horas:number;desde:string|null};
export type FichaConsulta = {id:number;codigo:string;oportunidad_id:number|null;titulo:string;cliente:string;contacto:string;producto:string;cantidad:number|null;tipo_consulta:TipoConsulta;presentacion:string;packaging:string;requisitos:string[];datos_faltantes:string[];resumen:string;creada_en:string;actualizada_en:string;mensajes?:ConsultaBandeja[];mensajes_count?:number;estado_gestion?:string;cerrada_en?:string|null;motivo_cierre?:string;
 formula?:'propia'|'desarrollo_empresa'|'sin_especificar';marca_registrada?:'si'|'no'|'sin_especificar';registro_anmat?:'si'|'no'|'en_tramite'|'sin_especificar';destino?:''|'local'|'exportacion';pais_destino?:string;plazo_deseado?:string;localidad?:string;responsable?:string;
 cotizacion_monto?:number|null;cotizacion_moneda?:''|'ARS'|'USD';cotizacion_fecha?:string|null;cotizacion_validez_dias?:number|null;tipo_sugerido_ia?:number;
 bajo_minimo?:boolean;lote_minimo?:number;rubro?:string;envase?:string;tipo_cliente?:string;etapas?:string[];datos_a_confirmar?:string[];campos_editados?:string[];canal_origen?:string;respuesta?:Respuesta;duplicados?:Duplicado[];derivada_a?:string};
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
export type ReportData={periodo:string;desde:string;hasta:string;canal:string;responsable:string;indicadores:Record<string,number>;monto_concretado?:Record<string,number>;canales:Record<string,number>;productos_consultados:[string,number][];origen_datos:string;
 embudo?:{estado:string;cantidad:number;montos:Record<string,number>}[];conversion_por_tipo?:ReportBreakdown;conversion_por_canal?:ReportBreakdown;motivos_no_concretadas?:Record<string,number>;
 tiempo_primera_respuesta?:{promedio_horas:number|null;respondidas:number;sin_respuesta_registrada:number;por_canal:Record<string,{promedio_horas:number|null;gestiones:number}>;por_vendedor:Record<string,{promedio_horas:number|null;gestiones:number}>};
 alertas_sin_respuesta?:{ficha_id:number;codigo:string;cliente:string;horas:number;responsable:string;conversacion:string}[];seguimientos_vencidos_detalle?:{id:number;titulo:string;inicio:string;cliente:string;ficha_codigo:string|null;conversacion:string}[]};
export type ReportResponse={title:string;question:string;report:string;data:ReportData;generated_at:string};

/* V5: archivos que el backend devuelve en base64 (el proxy solo reenvía texto). */
export type ArchivoB64={filename:string;mime:string;contenido_base64:string};
export function guardarArchivo(f:ArchivoB64){const bin=atob(f.contenido_base64);const bytes=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);const url=URL.createObjectURL(new Blob([bytes],{type:f.mime}));const a=document.createElement('a');a.href=url;a.download=f.filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),4000)}
export function abrirArchivo(f:ArchivoB64){if(f.mime!=='application/pdf'){guardarArchivo(f);return}const bin=atob(f.contenido_base64);const bytes=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);const url=URL.createObjectURL(new Blob([bytes],{type:f.mime}));const w=window.open(url,'_blank');if(!w)guardarArchivo(f);setTimeout(()=>URL.revokeObjectURL(url),60000)}
export const leerArchivo=(file:File)=>new Promise<string>((ok,fail)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',').pop()||'');r.onerror=()=>fail(new Error('No se pudo leer el archivo'));r.readAsDataURL(file)});
export const tamanoTexto=(b:number)=>b<1024?`${b} B`:b<1048576?`${Math.round(b/1024)} KB`:`${(b/1048576).toFixed(1)} MB`;
export type Adjunto={id:number;nombre:string;mime:string;tamano:number};
export type Documento=Adjunto&{descripcion:string;subido_por:string;creado_en:string};
export type Plantilla={id:number;atajo:string;titulo:string;texto:string;activa:number};
export type Producto={id:number;codigo:string;descripcion:string;unidad:string;linea:string;precio:number|null;moneda:'ARS'|'USD';origen:string};
export type NotaInterna={id:number;ficha_id:number;usuario:string;texto:string;area:string;creada_en:string};
export type Empresa={razon_social:string;domicilio:string;telefono:string;email:string;web:string;cuit:string;condiciones:string;iva_pct:number;dias_seguimiento:number;probabilidades:Record<string,number>;areas?:string[];color_acento?:string};
export type ItemMiDia={ficha_id:number;codigo:string;cliente:string;titulo?:string;conversacion:string};
export type ActividadMiDia={id:number;titulo:string;tipo:string;inicio:string;fin:string|null;cliente:string;ficha_id:number|null;oportunidad_id:number|null;responsable:string;notas:string;ficha_codigo:string|null;conversacion:string};
export type TarjetaMiDia={ficha_id:number;codigo:string;cliente:string;contacto:string;titulo:string;estado_gestion:string;tipo_consulta:TipoConsulta;cantidad:number|null;responsable:string;pendiente:boolean;horas:number;ultimo_mensaje_en:string|null;canal:string;bajo_minimo:boolean;conversacion:string};
export type MiDia={usuario:string;propio:boolean;fecha:string;dias_seguimiento:number;usuarios:{usuario:string;nombre:string}[];
 resumen:{asignadas:number;asignadas_sin_responder:number;sin_asignar:number;sin_asignar_sin_responder:number;actividades_hoy:number;vencidas:number};
 asignadas:TarjetaMiDia[];sin_asignar:TarjetaMiDia[];actividades_hoy:ActividadMiDia[];actividades_vencidas:ActividadMiDia[];
 seguimientos_sugeridos:(ItemMiDia&{dias:number;cotizacion:{monto:number|null;moneda:string};mensaje_id:number|null})[]};
/* Variables de las respuestas rápidas. */
export function completarPlantilla(texto:string,v:Record<string,string>){return texto.replace(/\{(\w+)\}/g,(m,k)=>v[k]!==undefined&&v[k]!==''?v[k]:m)}

/* Fechas con un solo formato en todo el sistema: "hoy 14:30", "ayer 09:10", "8 nov" o "8 nov 2025". */
export function fechaCorta(s?:string|null,conHora=true){if(!s)return '';const d=new Date(s.length===10?`${s}T12:00:00`:s);if(isNaN(d.getTime()))return '';const t=new Date();const h=d.toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit',hour12:false});
 const y=new Date(t);y.setDate(t.getDate()-1);if(d.toDateString()===t.toDateString())return conHora&&s.length>10?`hoy ${h}`:'hoy';if(d.toDateString()===y.toDateString())return conHora&&s.length>10?`ayer ${h}`:'ayer';
 const base=d.toLocaleDateString('es-AR',{day:'numeric',month:'short'}).replace('.','');return d.getFullYear()===t.getFullYear()?base:`${base} ${d.getFullYear()}`}
/* "Ver como": el administrador elige un perfil y el sistema se muestra con sus permisos. */
export const verComoActual=()=>{if(typeof document==='undefined')return '';const m=document.cookie.match(/(?:^|; )impulso_ver_como=([^;]+)/);return m?decodeURIComponent(m[1]):''};
export function setVerComo(rol:''|'ventas'|'gerencia'){document.cookie=rol?`impulso_ver_como=${rol}; path=/; SameSite=Lax`:'impulso_ver_como=; path=/; max-age=0; SameSite=Lax';window.location.reload()}
