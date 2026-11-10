'use client';
import {useCallback,useEffect,useState} from 'react';
import {Upload,FileSpreadsheet,Check,Loader2,Trash2,Plus,FileText,Download} from 'lucide-react';
import {api,ArchivoB64,guardarArchivo,abrirArchivo,leerArchivo,tamanoTexto,Documento,Plantilla,Empresa} from '@/lib/api';

type Msg={ok:(m:string)=>void;fail:(m:string)=>void};
/* Vercel limita el cuerpo de cada pedido a 4,5 MB; en base64 un archivo crece un 33 %. */
const MAX_SUBIDA=3*1024*1024;
const errText=(e:unknown,f:string)=>e instanceof Error?e.message:f;
const nombresCampo:Record<string,string>={codigo:'Código',cliente:'Razón social',cuit:'CUIT',email:'Email',telefono:'Teléfono',contacto:'Contacto',localidad:'Localidad',provincia:'Provincia',vendedor:'Vendedor',lista_precios:'Lista de precios',descripcion:'Descripción',precio:'Precio',moneda:'Moneda',unidad:'Unidad',linea:'Línea / rubro'};

/* ---------------------------------------------------------------- Importar desde Tango (Excel o CSV) */
type Preview={columnas:string[];campos:string[];obligatorios:string[];mapeo:Record<string,number>;total_filas:number;validas:number;errores:string[];muestra:Record<string,string|number|null>[];nuevos:number;actualizados:number};
export function ImportPanel({ok,fail}:Msg){
 const [tipo,setTipo]=useState<'clientes'|'articulos'>('clientes'),[file,setFile]=useState<{nombre:string;b64:string}|null>(null),[prev,setPrev]=useState<Preview|null>(null),[map,setMap]=useState<Record<string,number|null>>({}),[busy,setBusy]=useState(false);
 async function preview(f=file,m?:Record<string,number|null>){if(!f)return;setBusy(true);try{const p=await api<Preview>('/api/import/preview',{method:'POST',body:JSON.stringify({tipo,nombre:f.nombre,contenido_base64:f.b64,mapeo:m})});setPrev(p);setMap(p.mapeo)}catch(e){fail(errText(e,'No se pudo leer el archivo'));setPrev(null)}finally{setBusy(false)}}
 async function pick(e:React.ChangeEvent<HTMLInputElement>){const f=e.target.files?.[0];e.target.value='';if(!f)return;if(f.size>MAX_SUBIDA){fail('El archivo supera los 3 MB. Exportá solo las columnas necesarias o dividilo en partes.');return}const next={nombre:f.name,b64:await leerArchivo(f)};setFile(next);await preview(next)}
 async function apply(){if(!file||!prev)return;if(!window.confirm(`¿Importar ${prev.validas} ${tipo}? Se crean ${prev.nuevos} y se actualizan ${prev.actualizados}. No se borra nada.`))return;setBusy(true);try{const r=await api<{nuevos:number;actualizados:number;omitidas:number}>('/api/import/aplicar',{method:'POST',body:JSON.stringify({tipo,nombre:file.nombre,contenido_base64:file.b64,mapeo:map})});ok(`${r.nuevos} nuevos, ${r.actualizados} actualizados${r.omitidas?`, ${r.omitidas} omitidos`:''}`);setFile(null);setPrev(null)}catch(e){fail(errText(e,'No se pudo importar'))}finally{setBusy(false)}}
 async function template(){try{guardarArchivo(await api<ArchivoB64>(`/api/import/plantilla?tipo=${tipo}`))}catch(e){fail(errText(e,'No se pudo descargar'))}}
 async function examples(){setBusy(true);try{const r=await api<{agregados:number}>('/api/productos/ejemplo',{method:'POST'});ok(r.agregados?`${r.agregados} productos agregados`:'Ya estaba cargada')}catch(e){fail(errText(e,'No se pudo cargar'))}finally{setBusy(false)}}
 const missing=prev?prev.obligatorios.filter(c=>map[c]==null):[];
 return <section className="panel v2-admin-list"><div className="v3-section-line"><h3><FileSpreadsheet size={18}/> Importar desde Tango o Excel</h3></div>
  <p className="muted">Listado de clientes o de artículos exportado de Tango (.xlsx o .csv). Nada cambia hasta confirmar.</p>
  <div className="v5-inline"><div className="v3-switch" role="group" aria-label="Qué importar">{(['clientes','articulos'] as const).map(t=><button type="button" key={t} className={tipo===t?'selected':''} onClick={()=>{setTipo(t);setFile(null);setPrev(null)}}>{t==='clientes'?'Clientes':'Artículos y precios'}</button>)}</div>
   <label className="btn btn-primary v6-file"><Upload size={16}/> Elegir archivo<input type="file" accept=".xlsx,.xlsm,.csv,.txt" onChange={e=>void pick(e)} hidden/></label>
   <button type="button" className="btn btn-outline" onClick={()=>void template()}><Download size={16}/> Descargar planilla modelo</button>
   {tipo==='articulos'&&<button type="button" className="btn btn-outline" disabled={busy} onClick={()=>void examples()}>Cargar lista de ejemplo</button>}</div>
  {busy&&<p className="v5-loading"><Loader2 size={14} className="v5-spin"/> Procesando…</p>}
  {prev&&file&&<div className="v6-import">
   <p><b>{file.nombre}</b>: {prev.total_filas} filas · {prev.validas} válidas · <span className="v5-chip is-money">{prev.nuevos} nuevos</span> <span className="v5-chip">{prev.actualizados} a actualizar</span></p>
   <h4>Columnas</h4><div className="v6-map">{prev.campos.map(c=><label key={c}>{nombresCampo[c]||c}{prev.obligatorios.includes(c)?' *':''}<select value={map[c]??''} onChange={e=>{const m={...map,[c]:e.target.value===''?null:Number(e.target.value)};setMap(m);void preview(file,m)}}><option value="">— No importar —</option>{prev.columnas.map((col,i)=><option key={i} value={i}>{col}</option>)}</select></label>)}</div>
   {!!prev.muestra.length&&<><h4>Vista previa</h4><div className="v5-table-wrap"><table className="v5-mini-table"><thead><tr>{prev.campos.filter(c=>map[c]!=null).map(c=><th key={c}>{nombresCampo[c]||c}</th>)}</tr></thead><tbody>{prev.muestra.map((r,i)=><tr key={i}>{prev.campos.filter(c=>map[c]!=null).map(c=><td key={c}>{r[c]==null?'':String(r[c])}</td>)}</tr>)}</tbody></table></div></>}
   {!!prev.errores.length&&<details><summary>{prev.errores.length} filas con problemas (se omiten)</summary><ul>{prev.errores.map(e=><li key={e}>{e}</li>)}</ul></details>}
   {missing.length>0&&<p className="v5-banner is-warning">Falta elegir la columna de: {missing.map(c=>nombresCampo[c]||c).join(', ')}</p>}
   <button type="button" className="btn btn-primary" disabled={busy||!prev.validas||missing.length>0} onClick={()=>void apply()}><Check size={16}/> Importar {prev.validas} {tipo==='clientes'?'clientes':'artículos'}</button>
  </div>}
 </section>;
}

/* ---------------------------------------------------------------- Datos de la empresa, cotizaciones y pronóstico */
export function EmpresaPanel({ok,fail}:Msg){
 const [e,setE]=useState<Empresa|null>(null),[busy,setBusy]=useState(false);
 useEffect(()=>{void api<Empresa>('/api/empresa').then(setE).catch(x=>fail(errText(x,'No se pudo cargar')))},[fail]);
 if(!e)return <section className="panel v2-admin-list"><p className="muted">Cargando…</p></section>;
 const set=(k:keyof Empresa,v:string|number)=>setE({...e,[k]:v});
 async function save(ev:React.FormEvent){ev.preventDefault();if(!e)return;setBusy(true);try{const saved=await api<Empresa>('/api/empresa',{method:'POST',body:JSON.stringify(e)});setE({...e,...saved});
  if(saved.color_acento){document.documentElement.style.setProperty('--brand',saved.color_acento);try{localStorage.setItem('impulso-brand',saved.color_acento)}catch{/* sin almacenamiento */}}ok('Guardado')}catch(x){fail(errText(x,'No se pudo guardar'))}finally{setBusy(false)}}
 return <section className="panel v2-admin-list"><div className="v3-section-line"><h3>Empresa y apariencia</h3></div>
  <form className="fields" onSubmit={ev=>void save(ev)}><p className="muted">Encabezan el PDF de las cotizaciones. Lo vacío no se imprime.</p>
   <div className="v3-fields"><label>Razón social<input required value={e.razon_social} onChange={x=>set('razon_social',x.target.value)}/></label><label>CUIT<input value={e.cuit} onChange={x=>set('cuit',x.target.value)}/></label>
    <label>Domicilio<input value={e.domicilio} onChange={x=>set('domicilio',x.target.value)}/></label><label>Teléfono<input value={e.telefono} onChange={x=>set('telefono',x.target.value)}/></label>
    <label>Email<input value={e.email} onChange={x=>set('email',x.target.value)}/></label><label>Web<input value={e.web} onChange={x=>set('web',x.target.value)}/></label>
    <label>IVA (%)<input type="number" min="0" max="50" step="0.5" value={e.iva_pct} onChange={x=>set('iva_pct',Number(x.target.value))}/></label>
    <label>Color de acento<span className="v5-inline"><input type="color" aria-label="Color de acento" value={e.color_acento||'#2e6a57'} onChange={x=>{set('color_acento',x.target.value);document.documentElement.style.setProperty('--brand',x.target.value)}} style={{width:48,padding:2}}/><code>{e.color_acento||'#2e6a57'}</code></span></label>
    <label className="wide">Condiciones por defecto de la cotización<textarea rows={2} value={e.condiciones} onChange={x=>set('condiciones',x.target.value)}/></label></div>
   <button type="submit" className="btn btn-primary" disabled={busy}><Check size={16}/> Guardar</button></form></section>;
}

/* ---------------------------------------------------------------- Reglas comerciales */
export function ReglasPanel({ok,fail}:Msg){
 const [e,setE]=useState<Empresa|null>(null),[lote,setLote]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{void Promise.all([api<Empresa>('/api/empresa'),api<{lote_minimo:number}>('/api/commercial/settings')]).then(([x,c])=>{setE(x);setLote(String(c.lote_minimo))}).catch(x=>fail(errText(x,'No se pudo cargar')))},[fail]);
 if(!e)return <section className="panel v2-admin-list"><p className="muted">Cargando…</p></section>;
 async function save(ev:React.FormEvent){ev.preventDefault();if(!e)return;setBusy(true);try{await api('/api/commercial/settings',{method:'POST',body:JSON.stringify({lote_minimo:Number(lote)})});await api('/api/empresa',{method:'POST',body:JSON.stringify(e)});ok('Guardado')}catch(x){fail(errText(x,'No se pudo guardar'))}finally{setBusy(false)}}
 return <section className="panel v2-admin-list"><div className="v3-section-line"><h3>Reglas comerciales</h3></div>
  <form className="fields" onSubmit={ev=>void save(ev)}><div className="v3-fields">
   <label>Lote mínimo (unidades)<input type="number" min="1" required value={lote} onChange={x=>setLote(x.target.value)}/></label>
   <label>Sugerir seguimiento tras (días sin respuesta)<input type="number" min="1" max="60" value={e.dias_seguimiento} onChange={x=>setE({...e,dias_seguimiento:Number(x.target.value)})}/></label></div>
   <p className="muted">Por debajo del lote mínimo, Full Service, producción a terceros y elaboración se marcan como Bajo mínimo.</p>
   <button type="submit" className="btn btn-primary" disabled={busy}><Check size={16}/> Guardar</button></form></section>;
}

/* ---------------------------------------------------------------- Chat del equipo */
export function ChatPanel({ok,fail}:Msg){
 const [dias,setDias]=useState('90'),[busy,setBusy]=useState(false);
 useEffect(()=>{void api<{dias:number}>('/api/chat/retencion').then(r=>setDias(String(r.dias))).catch(x=>fail(errText(x,'No se pudo cargar')))},[fail]);
 async function save(){setBusy(true);try{await api('/api/chat/retencion',{method:'POST',body:JSON.stringify({dias:Number(dias)||0})});ok('Guardado')}catch(x){fail(errText(x,'No se pudo guardar'))}finally{setBusy(false)}}
 return <section className="panel v2-admin-list"><div className="v3-section-line"><h3>Chat del equipo</h3></div>
  <div className="fields"><label>Borrar los mensajes<select value={dias} onChange={x=>setDias(x.target.value)}><option value="30">A los 30 días</option><option value="90">A los 90 días</option><option value="180">A los 180 días</option><option value="365">Al año</option><option value="0">Nunca</option></select></label>
  <button type="button" className="btn btn-primary" disabled={busy} onClick={()=>void save()}><Check size={16}/> Guardar</button></div></section>;
}

/* ---------------------------------------------------------------- Integraciones (hoja de ruta) */
const INTEGRACIONES:[string,string,'Disponible'|'Próximamente'|'A pedido'][]=[
 ['Excel / CSV de Tango','Importar clientes y artículos con precios.','Disponible'],
 ['Exportación a Excel','Gestiones, contactos y reportes.','Disponible'],
 ['WhatsApp Business','Recibir y responder consultas desde Impulso, sin copiar y pegar.','Próximamente'],
 ['Correo (Gmail u Outlook)','Las consultas por mail entran solas a la bandeja y las respuestas salen desde Impulso.','Próximamente'],
 ['Envío de cotizaciones por mail','La cotización y su enlace de aceptación salen directo al cliente.','Próximamente'],
 ['Formulario web','Las consultas del sitio entran con producto, cantidad y localidad.','Próximamente'],
 ['Google Calendar u Outlook','La agenda comercial se sincroniza con el calendario de cada vendedor.','A pedido'],
 ['Tango Gestión en línea','Clientes, artículos, precios y pedidos sincronizados sin importar archivos.','A pedido'],
];
export function IntegracionesPanel(){
 return <section className="panel v2-admin-list"><div className="v3-section-line"><h3>Integraciones</h3></div>
  <ul className="v7-integrations">{INTEGRACIONES.map(([n,d,e])=><li key={n}><div><strong>{n}</strong><small>{d}</small></div><span className={`v7-status is-${e==='Disponible'?'ok':e==='Próximamente'?'soon':'ask'}`}>{e}</span></li>)}</ul></section>;
}

/* ---------------------------------------------------------------- Respuestas rápidas */
const blankTpl={atajo:'',titulo:'',texto:'',activa:true};
export function PlantillasPanel({ok,fail}:Msg){
 const [list,setList]=useState<Plantilla[]>([]),[edit,setEdit]=useState<typeof blankTpl|null>(null),[busy,setBusy]=useState(false);
 const load=useCallback(async()=>{try{setList(await api<Plantilla[]>('/api/plantillas?todas=true'))}catch(e){fail(errText(e,'No se pudo cargar'))}},[fail]);
 useEffect(()=>{void load()},[load]);
 async function save(ev:React.FormEvent){ev.preventDefault();if(!edit)return;setBusy(true);try{await api('/api/plantillas',{method:'POST',body:JSON.stringify({...edit,atajo:edit.atajo.toLowerCase().replace(/^\//,'')})});setEdit(null);ok('Respuesta rápida guardada');await load()}catch(e){fail(errText(e,'No se pudo guardar'))}finally{setBusy(false)}}
 async function remove(t:Plantilla){if(!window.confirm(`¿Eliminar /${t.atajo}?`))return;try{await api(`/api/plantillas/${t.id}/borrar`,{method:'POST'});await load()}catch(e){fail(errText(e,'No se pudo eliminar'))}}
 return <section className="panel v2-admin-list"><div className="v3-section-line"><h3>Respuestas rápidas</h3><button type="button" className="btn btn-outline btn-sm" onClick={()=>setEdit(blankTpl)}><Plus size={14}/> Nueva</button></div>
  <p className="muted">Se insertan escribiendo / en el chat. Variables: <code>{'{cliente}'}</code> <code>{'{contacto}'}</code> <code>{'{producto}'}</code> <code>{'{cantidad}'}</code> <code>{'{vendedor}'}</code> <code>{'{lote_minimo}'}</code></p>
  {edit&&<form className="fields v6-tpl-form" onSubmit={ev=>void save(ev)}><div className="form-row"><label>Atajo<input required pattern="[a-z0-9_\-]{2,30}" title="Minúsculas, números, guiones" value={edit.atajo} onChange={e=>setEdit({...edit,atajo:e.target.value})} placeholder="precios"/></label><label>Título<input required minLength={2} value={edit.titulo} onChange={e=>setEdit({...edit,titulo:e.target.value})}/></label></div><label>Texto<textarea required rows={4} value={edit.texto} onChange={e=>setEdit({...edit,texto:e.target.value})}/></label><label className="v3-config-check"><input type="checkbox" checked={edit.activa} onChange={e=>setEdit({...edit,activa:e.target.checked})}/> Activa</label><div className="v5-inline"><button className="btn btn-primary" disabled={busy}><Check size={16}/> Guardar</button><button type="button" className="btn btn-outline" onClick={()=>setEdit(null)}>Cancelar</button></div></form>}
  <div className="v6-tpl-list">{list.map(t=><div key={t.id} className={`v6-tpl ${t.activa?'':'is-off'}`}><div><strong>/{t.atajo}</strong> · {t.titulo}{!t.activa&&' (inactiva)'}<p>{t.texto}</p></div><div className="v5-inline"><button type="button" className="btn btn-outline btn-sm" onClick={()=>setEdit({atajo:t.atajo,titulo:t.titulo,texto:t.texto,activa:!!t.activa})}>Editar</button><button type="button" className="v4-icon-action" aria-label={`Eliminar /${t.atajo}`} onClick={()=>void remove(t)}><Trash2 size={15}/></button></div></div>)}</div>
 </section>;
}

/* ---------------------------------------------------------------- Documentos para adjuntar */
export function DocumentosPanel({ok,fail}:Msg){
 const [list,setList]=useState<Documento[]>([]),[desc,setDesc]=useState(''),[busy,setBusy]=useState(false);
 const load=useCallback(async()=>{try{setList(await api<Documento[]>('/api/documentos'))}catch(e){fail(errText(e,'No se pudo cargar'))}},[fail]);
 useEffect(()=>{void load()},[load]);
 async function upload(e:React.ChangeEvent<HTMLInputElement>){const f=e.target.files?.[0];e.target.value='';if(!f)return;if(f.size>MAX_SUBIDA){fail('El archivo supera los 3 MB (límite del hosting de la demo).');return}setBusy(true);try{await api('/api/documentos',{method:'POST',body:JSON.stringify({nombre:f.name,descripcion:desc,mime:f.type||'application/octet-stream',contenido_base64:await leerArchivo(f)})});setDesc('');ok(`${f.name} subido`);await load()}catch(x){fail(errText(x,'No se pudo subir'))}finally{setBusy(false)}}
 async function remove(d:Documento){if(!window.confirm(`¿Eliminar ${d.nombre}? Los mensajes donde ya se adjuntó conservan el nombre.`))return;try{await api(`/api/documentos/${d.id}/borrar`,{method:'POST'});await load()}catch(e){fail(errText(e,'No se pudo eliminar'))}}
 async function open(d:Documento){try{abrirArchivo(await api<ArchivoB64>(`/api/documentos/${d.id}`))}catch(e){fail(errText(e,'No se pudo abrir'))}}
 return <section className="panel v2-admin-list"><div className="v3-section-line"><h3><FileText size={18}/> Documentos para adjuntar</h3></div>
  <p className="muted">Catálogos y fichas técnicas para adjuntar desde el chat. Hasta 3 MB.</p>
  <div className="v5-inline"><input aria-label="Descripción del documento" placeholder="Descripción (opcional), ej. Catálogo 2026" value={desc} onChange={e=>setDesc(e.target.value)}/><label className="btn btn-primary v6-file">{busy?<Loader2 size={16} className="v5-spin"/>:<Upload size={16}/>} Subir documento<input type="file" onChange={e=>void upload(e)} hidden/></label></div>
  <div className="v3-user-list">{list.map(d=><div key={d.id} className="v3-user-row"><FileText size={18}/><div className="v3-user-data"><strong>{d.nombre}</strong><small>{[d.descripcion,tamanoTexto(d.tamano),new Date(d.creado_en).toLocaleDateString('es-AR')].filter(Boolean).join(' · ')}</small></div><button type="button" className="btn btn-outline btn-sm" onClick={()=>void open(d)}>Abrir</button><button type="button" className="v4-icon-action" aria-label={`Eliminar ${d.nombre}`} onClick={()=>void remove(d)}><Trash2 size={15}/></button></div>)}{!list.length&&<p className="muted">Todavía no hay documentos.</p>}</div>
 </section>;
}
