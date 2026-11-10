'use client';
import {useCallback,useEffect,useState} from 'react';
import Link from 'next/link';
import {Clock3,CalendarDays,Receipt,Send,AlertTriangle,Check,ArrowUpRight,Inbox,Sparkles,Target,UserPlus,UserCheck,Search,Briefcase} from 'lucide-react';
import Shell from '@/components/shell';
import {api,MiDia,ActividadMiDia,PendienteMiDia,UsuarioSesion,tiempoSinRespuesta,cotizacionTexto} from '@/lib/api';

type Metas={vendedores:{usuario:string;nombre:string;metas:Record<string,number>;real:Record<string,number>;concretadas:number}[]};
const hora=(s:string)=>new Date(s).toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit'});
const dia=(s:string)=>new Date(s).toLocaleDateString('es-AR',{day:'numeric',month:'short'});
const saludo=()=>{const h=new Date().getHours();return h<12?'Buen día':h<20?'Buenas tardes':'Buenas noches'};
const tipoNombre:Record<string,string>={llamada:'Llamada',reunion:'Reunión',seguimiento:'Seguimiento',pendiente:'Pendiente'};

/* Pantalla de inicio del vendedor: todo lo que tiene que hacer hoy, en orden de urgencia. */
export default function MiDiaPage(){
 const [data,setData]=useState<MiDia|null>(null),[user,setUser]=useState<UsuarioSesion|null>(null),[metas,setMetas]=useState<Metas|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState<number|null>(null);
 const load=useCallback(async()=>{try{setData(await api<MiDia>('/api/mi-dia'));setError('')}catch(e){setError(e instanceof Error?e.message:'No se pudo cargar tu día')}},[]);
 useEffect(()=>{void load();void fetch('/api/session/me').then(r=>r.ok?r.json():null).then(setUser).catch(()=>{});void api<Metas>('/api/metas').then(setMetas).catch(()=>{})},[load]);
 useEffect(()=>{const t=setInterval(()=>{if(document.visibilityState==='visible')void load()},60000);return()=>clearInterval(t)},[load]);
  const readonly=user?.role==='gerencia';
 async function assign(x:PendienteMiDia){if(!user)return;setBusy(x.ficha_id);try{await api(`/api/fichas/${x.ficha_id}/responsable`,{method:'POST',body:JSON.stringify({responsable:user.username})});await load()}catch(e){setError(e instanceof Error?e.message:'No se pudo asignar')}finally{setBusy(null)}}
 async function done(a:ActividadMiDia){setBusy(a.id);try{await api(`/api/calendar/events/${a.id}`,{method:'POST',body:JSON.stringify({titulo:a.titulo,tipo:a.tipo,inicio:a.inicio,fin:a.fin,ficha_id:a.ficha_id,oportunidad_id:a.oportunidad_id,responsable:a.responsable,notas:a.notas,estado:'realizada'})});await load()}catch(e){setError(e instanceof Error?e.message:'No se pudo actualizar')}finally{setBusy(null)}}
 const r=data?.resumen;
 const mine=metas?.vendedores.find(v=>v.usuario===user?.username);
 const fecha=new Date().toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'long'});
 const nothing=data&&!data.mias_sin_responder.length&&!data.sin_asignar_sin_responder.length&&!data.seguimientos_sugeridos.length&&!data.actividades_hoy.length&&!data.actividades_vencidas.length&&!data.cotizaciones_por_vencer.length;
 const Pending=({x,free}:{x:PendienteMiDia;free?:boolean})=><li className={x.horas>=24?'is-late':''}><span className={`v5-chip ${x.horas>=24?'is-danger':'is-attention'}`}><Clock3 size={11}/> {tiempoSinRespuesta(x.horas)}</span><span className="v6-line-body"><strong>{x.cliente}</strong><small>{x.titulo} · {x.codigo}{x.bajo_minimo?' · Bajo mínimo':''}</small></span>{free&&!readonly&&<button type="button" className="btn btn-outline btn-sm" disabled={busy===x.ficha_id} onClick={()=>void assign(x)}><UserCheck size={13}/> Asignarme</button>}<Link className="btn btn-primary btn-sm" href={`/consultas?conversacion=${x.conversacion}&ficha=${x.ficha_id}`}>Responder <ArrowUpRight size={13}/></Link></li>;
 const Activity=({a,late}:{a:ActividadMiDia;late?:boolean})=><li className={late?'is-late':''}><span className="v6-time">{late?dia(a.inicio):hora(a.inicio)}</span><span className="v6-line-body"><strong>{a.titulo}</strong><small>{tipoNombre[a.tipo]||a.tipo}{a.cliente?` · ${a.cliente}`:''}{a.ficha_codigo?` · ${a.ficha_codigo}`:''}</small></span>{a.conversacion&&<Link className="btn btn-outline btn-sm" href={`/consultas?conversacion=${a.conversacion}`}>Abrir</Link>}{!readonly&&<button type="button" className="btn btn-outline btn-sm" disabled={busy===a.id} onClick={()=>void done(a)}><Check size={14}/> Hecho</button>}</li>;
 return <Shell>
  <div className="v2-page-head"><div><div className="eyebrow">{fecha.toUpperCase()}</div><h1>{saludo()}{user?.name?`, ${user.name.split(' ')[0]}`:''}</h1><p className="muted">Lo que tenés pendiente hoy, de lo más urgente a lo menos urgente.</p></div>
   <div className="v2-head-right"><button type="button" className="btn btn-outline" onClick={()=>window.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true}))}><Search size={16}/> Buscar</button><Link className="btn btn-primary" href="/consultas"><Inbox size={16}/> Ir a la bandeja</Link></div></div>
  {error&&<p className="alert error" role="alert">{error}</p>}
  <section className="v6-kpis" aria-label="Resumen del día">
   <Link href="/consultas?responsable=mias" className="v6-kpi"><Briefcase size={18}/><strong>{r?.asignadas??'—'}</strong><small>Asignadas a mí</small></Link>
   <Link href="/consultas?responsable=mias&estado=sin_responder" className={`v6-kpi ${r&&r.mias_sin_responder?'is-alert':''}`}><Clock3 size={18}/><strong>{r?.mias_sin_responder??'—'}</strong><small>Mías sin responder</small></Link>
   <Link href="/consultas?responsable=sin_asignar&estado=sin_responder" className={`v6-kpi ${r&&r.sin_asignar_sin_responder?'is-warn':''}`}><UserPlus size={18}/><strong>{r?.sin_asignar_sin_responder??'—'}</strong><small>Sin asignar sin responder</small></Link>
   <a href="#seguimientos" className="v6-kpi" title={`Cotizaciones o muestras enviadas sin respuesta del cliente hace ${data?.dias_seguimiento??5} días o más`}><Send size={18}/><strong>{data?.seguimientos_sugeridos.length??'—'}</strong><small>Seguimientos sugeridos</small><small className="v6-kpi-hint">Cotizaste y el cliente no respondió hace {data?.dias_seguimiento??5}+ días</small></a>
   <Link href="/agenda" className={`v6-kpi ${r&&r.vencidas?'is-alert':''}`}><CalendarDays size={18}/><strong>{r?`${r.actividades_hoy}${r.vencidas?` + ${r.vencidas}`:''}`:'—'}</strong><small>Actividades hoy{r?.vencidas?' + vencidas':''}</small></Link>
   <a href="#cotizaciones" className="v6-kpi"><Receipt size={18}/><strong>{r?.cotizaciones_por_vencer??'—'}</strong><small>Cotizaciones por vencer</small></a>
   {mine&&Object.keys(mine.metas).length>0&&<Link href="/resumen-gerencial#metas" className="v6-kpi is-goal"><Target size={18}/>{Object.entries(mine.metas).map(([m,meta])=>{const real=mine.real[m]||0;const pct=meta?Math.min(100,Math.round(100*real/meta)):0;return <span key={m} className="v6-goal"><strong>{pct}%</strong><small>Meta del mes {m}: {cotizacionTexto(real,m)} de {cotizacionTexto(meta,m)}</small><span className="v6-bar"><span style={{width:`${pct}%`}}/></span></span>})}</Link>}
  </section>
  {nothing&&<section className="panel v6-empty"><Check size={22}/><h2>Estás al día</h2><p className="muted">No hay consultas sin responder, seguimientos ni actividades para hoy.</p></section>}
  <div className="v6-day-grid">
   {data&&<section className="panel v6-day-block"><div className="v3-section-line"><h3><UserCheck size={17}/> Mías sin responder</h3>{r!.mias_sin_responder>0&&<Link className="v3-text-action" href="/consultas?responsable=mias&estado=sin_responder">Ver todas ({r!.mias_sin_responder})</Link>}</div>
    {data.mias_sin_responder.length?<ul className="v6-lines">{data.mias_sin_responder.map(x=><Pending key={x.ficha_id} x={x}/>)}</ul>:<p className="muted v6-help">No tenés consultas asignadas esperando respuesta.</p>}</section>}
   {data&&<section className="panel v6-day-block"><div className="v3-section-line"><h3><UserPlus size={17}/> Sin asignar sin responder</h3>{r!.sin_asignar_sin_responder>0&&<Link className="v3-text-action" href="/consultas?responsable=sin_asignar&estado=sin_responder">Ver todas ({r!.sin_asignar_sin_responder})</Link>}</div>
    {data.sin_asignar_sin_responder.length?<ul className="v6-lines">{data.sin_asignar_sin_responder.map(x=><Pending key={x.ficha_id} x={x} free/>)}</ul>:<p className="muted v6-help">No hay consultas libres esperando respuesta.</p>}</section>}
   {!!r?.otros_sin_responder&&<p className="muted v6-others is-wide">Además hay {r.otros_sin_responder} consulta{r.otros_sin_responder===1?'':'s'} sin responder asignada{r.otros_sin_responder===1?'':'s'} a otros vendedores. <Link href="/consultas?estado=sin_responder">Ver en la bandeja</Link></p>}
   {!!data?.seguimientos_sugeridos.length&&<section className="panel v6-day-block" id="seguimientos"><div className="v3-section-line"><h3><Send size={17}/> Seguimientos sugeridos</h3></div><p className="muted v6-help">Cotizaciones o muestras enviadas sin respuesta del cliente hace {data.dias_seguimiento} días o más.</p>
    <ul className="v6-lines">{data.seguimientos_sugeridos.map(x=><li key={x.ficha_id}><span className="v5-chip is-attention">{x.dias} días</span><span className="v6-line-body"><strong>{x.cliente}</strong><small>{x.codigo}{x.cotizacion.monto!=null?` · ${cotizacionTexto(x.cotizacion.monto,x.cotizacion.moneda)}`:''}</small></span><Link className="btn btn-outline btn-sm" href={`/consultas?conversacion=${x.conversacion}&ficha=${x.ficha_id}&seguimiento=1`}><Sparkles size={13}/> Preparar seguimiento</Link></li>)}</ul></section>}
   {!!(data?.actividades_hoy.length||data?.actividades_vencidas.length)&&<section className="panel v6-day-block"><div className="v3-section-line"><h3><CalendarDays size={17}/> Agenda</h3><Link className="v3-text-action" href="/agenda">Abrir agenda</Link></div>
    {!!data.actividades_vencidas.length&&<><h4 className="v6-sub is-late"><AlertTriangle size={14}/> Vencidas</h4><ul className="v6-lines">{data.actividades_vencidas.map(a=><Activity key={a.id} a={a} late/>)}</ul></>}
    {!!data.actividades_hoy.length&&<><h4 className="v6-sub">Hoy</h4><ul className="v6-lines">{data.actividades_hoy.map(a=><Activity key={a.id} a={a}/>)}</ul></>}</section>}
   {!!data?.cotizaciones_por_vencer.length&&<section className="panel v6-day-block" id="cotizaciones"><div className="v3-section-line"><h3><Receipt size={17}/> Cotizaciones por vencer</h3></div>
    <ul className="v6-lines">{data.cotizaciones_por_vencer.map(x=><li key={x.ficha_id} className={x.vencida?'is-late':''}><span className={`v5-chip ${x.vencida?'is-danger':'is-attention'}`}>{x.vencida?'Vencida':'Vence'} {dia(`${x.vence}T12:00:00`)}</span><span className="v6-line-body"><strong>{x.cliente}</strong><small>{x.codigo} · {cotizacionTexto(x.monto,x.moneda)}</small></span><Link className="btn btn-outline btn-sm" href={`/consultas?conversacion=${x.conversacion}&ficha=${x.ficha_id}`}>Abrir</Link></li>)}</ul></section>}
  </div>
  {!data&&!error&&<p className="muted">Cargando…</p>}
 </Shell>;
}
