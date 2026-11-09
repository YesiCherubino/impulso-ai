'use client';
import Link from 'next/link';
import {useCallback,useEffect,useMemo,useState} from 'react';
import {ArrowUpRight,Plus,RefreshCw,Search,X} from 'lucide-react';
import Shell from '@/components/shell';
import {api,Resumen,Oportunidad,estadoNombre,money,dateAR,TipoConsulta,CanalOrigen,tipoConsultaNombre,tiposConsulta,canalesOrigen} from '@/lib/api';

type Form={cliente:string;contacto:string;producto:string;cantidad:string;monto_estimado_usd:string;notas:string;tipo_consulta:TipoConsulta;canal_origen:CanalOrigen;presentacion:string;packaging:string;responsable:string};
const empty:Form={cliente:'',contacto:'',producto:'',cantidad:'',monto_estimado_usd:'',notas:'',tipo_consulta:'sin_clasificar',canal_origen:'Manual',presentacion:'',packaging:'',responsable:''};
type ResumenFiltro='todos'|'activos'|'cotizaciones'|'seguimiento'|'valor';
type Orden='ultimo'|'prioridad'|'cliente_asc'|'cliente_desc'|'valor_desc'|'valor_asc';
const activos=(o:Oportunidad)=>!['ganada','perdida'].includes(o.estado);
export default function ContactosComerciales(){
 const [summary,setSummary]=useState<Resumen|null>(null);
 const [items,setItems]=useState<Oportunidad[]>([]);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState('');
 const [search,setSearch]=useState('');
 const [estado,setEstado]=useState('todas');
 const [tipoFiltro,setTipoFiltro]=useState<TipoConsulta|'todos'>('todos');
 const [resumenFiltro,setResumenFiltro]=useState<ResumenFiltro>('todos');
 const [orden,setOrden]=useState<Orden>('ultimo');
 const [dialog,setDialog]=useState(false);
 const [form,setForm]=useState<Form>(empty);
 const [saving,setSaving]=useState(false);
 const [saveError,setSaveError]=useState('');
 const load=useCallback(async()=>{setLoading(true);setError('');try{
  const [s,o]=await Promise.all([api<Resumen>('/api/dashboard'),api<Oportunidad[]>('/api/opportunities')]);
  setSummary(s);setItems(o);
 }catch(err){setError(err instanceof Error?err.message:'No se pudieron cargar los contactos');}finally{setLoading(false)}},[]);
 useEffect(()=>{void load()},[load]);
 const shown=useMemo(()=>items.filter(o=>activos(o)).filter(o=>{
   const term=search.trim().toLocaleLowerCase('es');
   const searchMatch=[o.cliente,o.contacto,o.producto].some(x=>x.toLocaleLowerCase('es').includes(term));
   const stateMatch=estado==='todas'||o.estado===estado;
   const typeMatch=tipoFiltro==='todos'||o.tipo_consulta===tipoFiltro;
   const metricMatch=resumenFiltro==='todos'||
      (resumenFiltro==='activos'&&activos(o))||
      (resumenFiltro==='cotizaciones'&&o.estado==='cotizada')||
      (resumenFiltro==='seguimiento'&&o.seguimiento_pendiente)||
      (resumenFiltro==='valor'&&activos(o)&&o.monto_estimado_usd!=null);
   return searchMatch&&stateMatch&&typeMatch&&metricMatch;
 }).sort((a,b)=>{
  if(orden==='ultimo')return b.ultimo_contacto.localeCompare(a.ultimo_contacto)||b.id-a.id;
  if(orden==='prioridad'){const pa=(a.seguimiento_pendiente?3:activos(a)?a.estado==='cotizada'?2:1:0),pb=(b.seguimiento_pendiente?3:activos(b)?b.estado==='cotizada'?2:1:0);return pb-pa||b.dias_sin_contacto-a.dias_sin_contacto||b.ultimo_contacto.localeCompare(a.ultimo_contacto)}
  if(orden==='cliente_asc'||orden==='cliente_desc')return a.cliente.localeCompare(b.cliente,'es')*(orden==='cliente_asc'?1:-1);
  const va=a.monto_estimado_usd??-1,vb=b.monto_estimado_usd??-1;
  return orden==='valor_desc'?vb-va:va-vb;
 }),[items,search,estado,tipoFiltro,resumenFiltro,orden]);
 function selectMetric(value:ResumenFiltro){setResumenFiltro(current=>current===value?'todos':value);setEstado('todas');setTimeout(()=>document.querySelector('#contactos')?.scrollIntoView({behavior:'smooth',block:'start'}),0)}
 async function submit(e:React.FormEvent){e.preventDefault();setSaving(true);setSaveError('');try{
  await api('/api/opportunities',{method:'POST',body:JSON.stringify({cliente:form.cliente.trim(),contacto:form.contacto.trim(),producto:form.producto.trim(),cantidad:form.cantidad?Number(form.cantidad):null,monto_estimado_usd:form.monto_estimado_usd?Number(form.monto_estimado_usd):null,notas:form.notas})});
  setDialog(false);setForm(empty);await load();
 }catch(err){setSaveError(err instanceof Error?err.message:'No se pudo guardar')}finally{setSaving(false)}}
 const metrics:[ResumenFiltro,string,string][]=[
  ['activos','Contactos comerciales activos',summary?String(summary.oportunidades_activas):'—'],
  ['cotizaciones','Cotizaciones pendientes',summary?String(summary.cotizaciones_pendientes):'—'],
  ['seguimiento','Seguimientos pendientes',summary?String(summary.sin_seguimiento):'—'],
  ['valor','Valor potencial estimado',summary?money(summary.valor_potencial_usd):'—']
 ];
 return <Shell>
  <div className="page-head simple-head"><h1>Contactos comerciales</h1><button className="btn btn-outline" onClick={()=>void load()}><RefreshCw size={16}/> Actualizar</button></div>
  {error&&<div className="alert error" role="alert">{error}<button onClick={()=>void load()}>Reintentar</button></div>}
  <section className="panel resume-table" aria-labelledby="sales-title"><div className="resume-heading"><h2 id="sales-title">Resumen de ventas</h2><small>Actualizado hoy</small></div>
   <div className="resume-rows">{metrics.map(([key,label,value])=><button type="button" key={key} className={`resume-row ${resumenFiltro===key?'is-active':''}`} onClick={()=>selectMetric(key)} aria-pressed={resumenFiltro===key} title={`Filtrar por ${label.toLowerCase()}`}><span>{label}</span><strong>{value}</strong></button>)}</div>
  </section>
  <section className="panel table-panel compact-contact-table" id="contactos"><div className="section-head table-head"><h2>Contactos comerciales</h2><button className="btn btn-primary" onClick={()=>setDialog(true)}><Plus size={16}/> Nuevo contacto</button></div>
   <div className="table-toolbar compact-toolbar"><label className="search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar cliente, producto o contacto" aria-label="Buscar contactos"/></label>
    <select value={estado} aria-label="Filtrar por estado" onChange={e=>setEstado(e.target.value)}><option value="todas">Todos los estados</option>{Object.entries(estadoNombre).filter(([key])=>!['ganada','perdida'].includes(key)).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select>
    <select value={tipoFiltro} aria-label="Filtrar por tipo de consulta" onChange={e=>setTipoFiltro(e.target.value as TipoConsulta|'todos')}><option value="todos">Todos los servicios</option>{tiposConsulta.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select>
    <select value={orden} aria-label="Ordenar contactos" onChange={e=>setOrden(e.target.value as Orden)}><option value="ultimo">Último contacto (más reciente)</option><option value="prioridad">Prioridad de seguimiento</option><option value="cliente_asc">Cliente (A–Z)</option><option value="cliente_desc">Cliente (Z–A)</option><option value="valor_desc">Valor (mayor a menor)</option><option value="valor_asc">Valor (menor a mayor)</option></select>
    {(resumenFiltro!=='todos'||tipoFiltro!=='todos')&&<button type="button" className="btn btn-outline clear-filter" onClick={()=>{setResumenFiltro('todos');setTipoFiltro('todos')}}><X size={14}/> Quitar filtros</button>}
   </div>
   <div className="table-scroll"><table><thead><tr><th>CLIENTE</th><th>PRODUCTO</th><th>ESTADO</th><th>VALOR ESTIMADO</th><th>ÚLTIMO CONTACTO</th><th></th></tr></thead><tbody>{shown.map(o=><tr key={o.id}><td data-label="Cliente"><Link className="table-client" href={`/oportunidades/${o.id}`}><span><strong>{o.cliente}</strong><small>{o.contacto}</small></span></Link></td><td data-label="Producto">{o.producto}<small className="commercial-subtype">{tipoConsultaNombre[o.tipo_consulta]}</small></td><td data-label="Estado"><span className={`status status-${o.estado}`}>{estadoNombre[o.estado]}</span></td><td data-label="Valor estimado" className="value">{money(o.monto_estimado_usd)}</td><td data-label="Último contacto">{dateAR(o.ultimo_contacto)}{o.fecha_seguimiento&&<small className={`commercial-subtype ${o.seguimiento_pendiente?'is-overdue':''}`}>Próximo: {dateAR(o.fecha_seguimiento)}</small>}</td><td><Link href={`/oportunidades/${o.id}`} className="row-link" aria-label={`Abrir ${o.cliente}`}><ArrowUpRight size={16}/></Link></td></tr>)}</tbody></table>
   {!shown.length&&<p className="empty muted">{loading?'Cargando datos...':'No hay contactos con los filtros seleccionados.'}</p>}</div>
   <div className="table-foot">{shown.length} de {items.filter(activos).length} contactos activos</div>
  </section>
  {dialog&&<div className="modal-backdrop" role="presentation" onMouseDown={()=>setDialog(false)}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="dialog-title" onMouseDown={e=>e.stopPropagation()}><div className="modal-head"><h2 id="dialog-title">Nuevo contacto comercial</h2><button className="icon-button" onClick={()=>setDialog(false)} aria-label="Cerrar"><X size={20}/></button></div><form className="fields" onSubmit={e=>void submit(e)}><label>Cliente<input required minLength={2} maxLength={120} value={form.cliente} onChange={e=>setForm({...form,cliente:e.target.value})}/></label><label>Persona de contacto<input required minLength={2} maxLength={120} value={form.contacto} onChange={e=>setForm({...form,contacto:e.target.value})}/></label><label>Producto o servicio<input required minLength={2} maxLength={150} value={form.producto} onChange={e=>setForm({...form,producto:e.target.value})}/></label><div className="form-row"><label>Cantidad<input type="number" min="1" value={form.cantidad} onChange={e=>setForm({...form,cantidad:e.target.value})}/></label><label>Valor estimado USD<input type="number" min="0" step="0.01" value={form.monto_estimado_usd} onChange={e=>setForm({...form,monto_estimado_usd:e.target.value})}/></label></div><div className="form-row"><label>Tipo de consulta<select value={form.tipo_consulta} onChange={e=>setForm({...form,tipo_consulta:e.target.value as TipoConsulta})}>{tiposConsulta.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label><label>Canal de origen<select value={form.canal_origen} onChange={e=>setForm({...form,canal_origen:e.target.value as CanalOrigen})}>{canalesOrigen.map(c=><option key={c} value={c}>{c}</option>)}</select></label></div><div className="form-row"><label>Presentación (opcional)<input maxLength={120} placeholder="Ej. 250 ml" value={form.presentacion} onChange={e=>setForm({...form,presentacion:e.target.value})}/></label><label>Envase o packaging (opcional)<input maxLength={200} placeholder="Ej. Etiqueta personalizada" value={form.packaging} onChange={e=>setForm({...form,packaging:e.target.value})}/></label></div><label>Responsable (opcional)<input maxLength={120} placeholder="Nombre del vendedor" value={form.responsable} onChange={e=>setForm({...form,responsable:e.target.value})}/></label><label>Notas<textarea rows={3} maxLength={3000} value={form.notas} onChange={e=>setForm({...form,notas:e.target.value})}/></label>{saveError&&<div className="alert error" role="alert">{saveError}</div>}<button className="btn btn-primary full" disabled={saving}>{saving?'Guardando...':'Guardar contacto'}</button></form></div></div>}
 </Shell>;
}
