'use client';
import {useCallback,useEffect,useState} from 'react';
import {FileDown,Send,X,Info} from 'lucide-react';
import Link from 'next/link';
import Shell from '@/components/shell';
import ExportButton from '@/components/export-button';
import {api,qs,ReportData,ReportResponse,UsuarioSesion,Responsable,estadoGestionNombre,fechaCorta,puede,cotizacionTexto,guardarArchivo} from '@/lib/api';

/* Tres grupos de tres: qué entra, qué está en curso y cómo termina. "alerta" se marca solo si es mayor a 0. */
type Tarjeta={k:string;n:string;alerta?:'warn'|'danger'};
const GRUPOS:{titulo:string;nota:string;items:Tarjeta[]}[]=[
 {titulo:'Entrada',nota:'del período',items:[{k:'consultas_recibidas',n:'Consultas recibidas'},{k:'no_leidas',n:'No leídas',alerta:'warn'},{k:'sin_atender',n:'Sin atender',alerta:'danger'}]},
 {titulo:'Seguimiento',nota:'hoy',items:[{k:'en_gestion',n:'En gestión'},{k:'seguimientos_vencidos',n:'Seguimientos vencidos',alerta:'danger'},{k:'sin_contacto_7_dias',n:'Sin contacto +7 días',alerta:'warn'}]},
 {titulo:'Resultado',nota:'del período',items:[{k:'concretadas',n:'Concretadas'},{k:'no_concretadas',n:'No concretadas'},{k:'monto_concretado',n:'Monto concretado'}]}];
const PERIODOS=[['semana','7 días'],['mes','Este mes'],['trimestre','90 días'],['todos','Histórico']];
const CANALES=[['todos','Todos'],['WhatsApp','WhatsApp'],['Correo','Email'],['Formulario web','Web']];
const compacto=(n:number)=>n>=1e6?`${(n/1e6).toLocaleString('es-AR',{maximumFractionDigits:1})} M`:n>=1e4?`${(n/1e3).toLocaleString('es-AR',{maximumFractionDigits:0})} mil`:n.toLocaleString('es-AR',{maximumFractionDigits:0});
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
  <section className="panel v7-summary v8-summary">
   <div className="v8-filters">
    <div className="v7-seg" role="group" aria-label="Período">{PERIODOS.map(([v,l])=><button key={v} type="button" className={period===v?'is-on':''} onClick={()=>setPeriod(v)}>{l}</button>)}</div>
    <div className="v7-seg" role="group" aria-label="Canal">{CANALES.map(([v,l])=><button key={v} type="button" className={channel===v?'is-on':''} onClick={()=>setChannel(v)}>{l}</button>)}</div>
    {todos?<select aria-label="Vendedor" value={responsable} onChange={e=>setResponsable(e.target.value)}><option value="">Todos los vendedores</option>{owners.map(o=><option key={o.username} value={o.username}>{o.name}</option>)}</select>:user&&<span className="v8-tag">Tus gestiones</span>}
    {data&&<span className="v8-info" tabIndex={0} title={data.origen_datos} aria-label={data.origen_datos}><Info size={15}/></span>}
   </div>
   <div className="v8-groups">{GRUPOS.map(g=><section key={g.titulo} className="v8-group" aria-label={g.titulo}><h2>{g.titulo} <small>{g.nota}</small></h2>
    <div className="v8-stats">{g.items.map(t=>{
     const monto=t.k==='monto_concretado';const montos=Object.entries(data?.monto_concretado||{});
     const v=monto?montos.length:(data?.indicadores[t.k]??null);
     const cls=v===null?'':v===0?'is-zero':t.alerta?`is-${t.alerta}`:'';
     return <button type="button" key={t.k} className={`v8-stat ${cls}`} onClick={()=>void show([t.k,t.n])}><small>{t.n}</small>
      {monto?<strong className="v8-money">{montos.length?montos.map(([m,x])=><span key={m}><em>{m}</em> {compacto(x)}</span>):'—'}</strong>:<strong>{v??'—'}</strong>}</button>})}</div></section>)}</div>
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
