'use client';
import {useCallback,useEffect,useState} from 'react';
import {FileDown,Send,X} from 'lucide-react';
import Link from 'next/link';
import Shell from '@/components/shell';
import ExportButton from '@/components/export-button';
import {api,qs,ReportData,ReportResponse,UsuarioSesion,Responsable,estadoGestionNombre,fechaCorta,puede,cotizacionTexto,guardarArchivo} from '@/lib/api';

const TARJETAS:[string,string][]=[['consultas_recibidas','Consultas recibidas'],['sin_atender','Sin atender'],['en_gestion','En gestión'],['concretadas','Concretadas'],['no_concretadas','No concretadas'],['no_leidas','No leídas'],['contactos_activos','Contactos activos'],['seguimientos_vencidos','Seguimientos vencidos'],['sin_contacto_7_dias','Sin contacto +7 días']];
type Detalle={total:number;items:{ficha_id:number|null;oportunidad_id?:number;codigo:string;cliente:string;titulo:string;estado_gestion:string;responsable:string;fecha:string|null;conversacion:string;monto?:number|null;moneda?:string}[]};
const examples=['Resumen del mes para gerencia','¿Qué productos se consultaron más?','¿Cómo vienen las cotizaciones?','¿Qué canal trae más consultas?'];

/* Reportes: resumen comercial con el detalle de cada número y, debajo, reportes con IA. */
export default function Reportes(){
 const [data,setData]=useState<ReportData|null>(null),[period,setPeriod]=useState('mes'),[channel,setChannel]=useState('todos'),[responsable,setResponsable]=useState('');
 const [user,setUser]=useState<UsuarioSesion|null>(null),[owners,setOwners]=useState<Responsable[]>([]),[error,setError]=useState('');
 const [open,setOpen]=useState<[string,string]|null>(null),[detalle,setDetalle]=useState<Detalle|null>(null);
 const [prompt,setPrompt]=useState(''),[history,setHistory]=useState<ReportResponse[]>([]),[busy,setBusy]=useState(false);
 const todos=puede(user,'reportes_todos');
 const ownerName=(u:string)=>owners.find(o=>o.username===u)?.name||u||'Sin asignar';
 useEffect(()=>{void fetch('/api/session/me').then(r=>r.ok?r.json():null).then(setUser).catch(()=>{});void api<Responsable[]>('/api/users/responsables').then(setOwners).catch(()=>{})},[]);
 const params={period,channel,responsable:todos?responsable:''};
 const load=useCallback(async()=>{try{setData(await api<ReportData>(`/api/reports/summary?${qs({period,channel,responsable:todos?responsable:''})}`));setError('')}catch(e){setError(e instanceof Error?e.message:'No se pudo cargar')}},[period,channel,responsable,todos]);
 useEffect(()=>{void load()},[load]);
 async function show(t:[string,string]){setOpen(t);setDetalle(null);try{setDetalle(await api<Detalle>(`/api/reports/detalle?${qs({indicador:t[0],...params})}`))}catch(e){setError(String(e));setOpen(null)}}
 useEffect(()=>{if(!open)return;const k=(e:KeyboardEvent)=>{if(e.key==='Escape')setOpen(null)};window.addEventListener('keydown',k);return()=>window.removeEventListener('keydown',k)},[open]);
 async function ask(e?:React.FormEvent){e?.preventDefault();if(!prompt.trim())return;setBusy(true);setError('');try{const r=await api<ReportResponse>('/api/reports/chat',{method:'POST',body:JSON.stringify({question:prompt,...params})});setHistory(v=>[r,...v]);setPrompt('')}catch(x){setError(x instanceof Error?x.message:'No se pudo generar el reporte')}finally{setBusy(false)}}
 async function pdf(r:ReportResponse){setBusy(true);try{const f=await api<{pdf_base64:string;filename:string}>('/api/reports/pdf',{method:'POST',body:JSON.stringify({title:r.title,question:r.question,report:r.report,data:r.data})});guardarArchivo({filename:f.filename,mime:'application/pdf',contenido_base64:f.pdf_base64})}catch(x){setError(String(x))}finally{setBusy(false)}}
 const href=(i:Detalle['items'][number])=>i.ficha_id?`/consultas?conversacion=${i.conversacion}&ficha=${i.ficha_id}`:i.oportunidad_id?`/oportunidades/${i.oportunidad_id}`:'/agenda';
 return <Shell>
  <div className="v2-page-head"><h1>Reportes</h1>{puede(user,'exportar')&&<ExportButton path={`/api/export/reporte?${qs({period,canal:channel,responsable:todos?responsable:''})}`} onError={setError}/>}</div>
  {error&&<p className="alert error" role="alert">{error}</p>}
  <section className="panel v7-summary">
   <div className="v7-filters">
    <label>Período<select value={period} onChange={e=>setPeriod(e.target.value)}><option value="semana">Últimos 7 días</option><option value="mes">Este mes</option><option value="trimestre">Últimos 90 días</option><option value="todos">Histórico</option></select></label>
    <label>Canal<select value={channel} onChange={e=>setChannel(e.target.value)}><option value="todos">Todos</option><option value="WhatsApp">WhatsApp</option><option value="Correo">Email</option><option value="Formulario web">Formulario web</option></select></label>
    {todos?<label>Vendedor<select value={responsable} onChange={e=>setResponsable(e.target.value)}><option value="">Todos</option>{owners.map(o=><option key={o.username} value={o.username}>{o.name}</option>)}</select></label>:user&&<span className="v7-scope">Tus gestiones</span>}
   </div>
   <div className="v7-cards">{TARJETAS.map(t=><button type="button" key={t[0]} className="v7-stat" onClick={()=>void show(t)}><small>{t[1]}</small><strong>{data?.indicadores[t[0]]??'—'}</strong></button>)}</div>
   {data&&<p className="v7-note">{data.origen_datos}</p>}
  </section>
  {puede(user,'reporte_ia')&&<section className="panel v7-ai-report"><h2>Reportes con IA</h2>
   <form className="v7-ask" onSubmit={e=>void ask(e)}><input aria-label="Pedí un reporte" placeholder={todos?'Pedí un reporte: “resumen del mes por vendedor”':'Pedí un reporte sobre tus gestiones'} value={prompt} onChange={e=>setPrompt(e.target.value)} maxLength={1000}/><button type="submit" className="btn btn-primary" disabled={busy||!prompt.trim()}><Send size={15}/> {busy?'Generando…':'Generar'}</button></form>
   {!history.length&&<div className="v7-chips">{examples.map(q=><button key={q} type="button" onClick={()=>setPrompt(q)}>{q}</button>)}</div>}
   {history.map((r,i)=><article key={`${r.generated_at}-${i}`} className="v7-report"><header><strong>{r.question}</strong><button className="btn btn-outline btn-sm" disabled={busy} onClick={()=>void pdf(r)}><FileDown size={14}/> PDF</button></header><p>{r.report}</p></article>)}
  </section>}
  {open&&<div className="modal-backdrop v2-overlay" onMouseDown={()=>setOpen(null)}><div className="modal v7-detail" role="dialog" aria-modal="true" aria-label={open[1]} onMouseDown={e=>e.stopPropagation()}>
   <div className="modal-head"><h2>{open[1]}{detalle?<small> · {detalle.total}</small>:null}</h2><button className="icon-button" aria-label="Cerrar" onClick={()=>setOpen(null)}><X size={18}/></button></div>
   {!detalle?<p className="muted">Cargando…</p>:detalle.items.length?<ul className="v7-detail-list">{detalle.items.map((i,n)=><li key={n}><Link href={href(i)}><span className="v7-what"><strong>{i.cliente}</strong><small>{[i.codigo,i.titulo].filter(Boolean).join(' · ')}</small></span><span className="v7-detail-meta">{i.estado_gestion&&<span>{estadoGestionNombre[i.estado_gestion]||i.estado_gestion}</span>}{i.monto!=null&&i.moneda&&<span>{cotizacionTexto(i.monto,i.moneda)}</span>}<span>{ownerName(i.responsable)}</span><span>{fechaCorta(i.fecha)}</span></span></Link></li>)}</ul>:<p className="muted">Sin gestiones.</p>}
   {detalle&&detalle.total>detalle.items.length&&<p className="v7-note">Se muestran {detalle.items.length} de {detalle.total}.</p>}
  </div></div>}
 </Shell>;
}
