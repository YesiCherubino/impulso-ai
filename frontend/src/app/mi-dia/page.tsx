'use client';
import {useCallback,useEffect,useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {Check,ArrowRight,ArrowLeft} from 'lucide-react';
import Shell from '@/components/shell';
import {api,MiDia,ActividadMiDia,TarjetaMiDia,UsuarioSesion,tiempoSinRespuesta,cotizacionTexto,estadoGestionNombre,unidades,puede} from '@/lib/api';

const hora=(s:string)=>new Date(s).toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit'});
const dia=(s:string)=>new Date(s).toLocaleDateString('es-AR',{day:'numeric',month:'short'});
const tipoNombre:Record<string,string>={llamada:'Llamada',reunion:'Reunión',seguimiento:'Seguimiento',pendiente:'Tarea'};
type Col='asignadas'|'sin_asignar';

/* Tablero personal: lo asignado y lo libre, con arrastrar y soltar para tomar o liberar consultas. */
export default function MiDiaPage(){
 const router=useRouter();
 const [data,setData]=useState<MiDia|null>(null),[user,setUser]=useState<UsuarioSesion|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState<number|null>(null);
 const [ver,setVer]=useState(''),[soloPend,setSoloPend]=useState(false),[over,setOver]=useState<Col|null>(null),[dragging,setDragging]=useState<number|null>(null);
 const load=useCallback(async()=>{try{setData(await api<MiDia>(`/api/mi-dia${ver?`?usuario=${encodeURIComponent(ver)}`:''}`));setError('')}catch(e){setError(e instanceof Error?e.message:'No se pudo cargar')}},[ver]);
 useEffect(()=>{void load()},[load]);
 useEffect(()=>{void fetch('/api/session/me').then(r=>r.ok?r.json():null).then(setUser).catch(()=>{})},[]);
 useEffect(()=>{const t=setInterval(()=>{if(document.visibilityState==='visible'&&dragging===null)void load()},30000);return()=>clearInterval(t)},[load,dragging]);
 const readonly=!puede(user,'asignar');
 const owner=data?.usuario||user?.username||'';

 // Mover una tarjeta: se actualiza la pantalla al instante y después se guarda.
 async function move(card:TarjetaMiDia,to:Col){if(!data||readonly)return;const from:Col=data.asignadas.some(c=>c.ficha_id===card.ficha_id)?'asignadas':'sin_asignar';if(from===to)return;
  const moved={...card,responsable:to==='asignadas'?owner:''};
  setData({...data,[from]:data[from].filter(c=>c.ficha_id!==card.ficha_id),[to]:[moved,...data[to]],
   resumen:{...data.resumen,asignadas:data.resumen.asignadas+(to==='asignadas'?1:-1),sin_asignar:data.resumen.sin_asignar+(to==='sin_asignar'?1:-1),
    asignadas_sin_responder:data.resumen.asignadas_sin_responder+(card.pendiente?(to==='asignadas'?1:-1):0),sin_asignar_sin_responder:data.resumen.sin_asignar_sin_responder+(card.pendiente?(to==='sin_asignar'?1:-1):0)}});
  setBusy(card.ficha_id);
  try{await api(`/api/fichas/${card.ficha_id}/responsable`,{method:'POST',body:JSON.stringify({responsable:moved.responsable})})}
  catch(e){setError(e instanceof Error?e.message:'No se pudo asignar');void load()}finally{setBusy(null)}}
 async function done(a:ActividadMiDia){setBusy(a.id);try{await api(`/api/calendar/events/${a.id}`,{method:'POST',body:JSON.stringify({titulo:a.titulo,tipo:a.tipo,inicio:a.inicio,fin:a.fin,ficha_id:a.ficha_id,oportunidad_id:a.oportunidad_id,responsable:a.responsable,notas:a.notas,estado:'realizada'})});await load()}catch(e){setError(e instanceof Error?e.message:'No se pudo actualizar')}finally{setBusy(null)}}

 function onDrop(e:React.DragEvent,to:Col){e.preventDefault();setOver(null);const id=Number(e.dataTransfer.getData('text/plain'));const card=[...(data?.asignadas||[]),...(data?.sin_asignar||[])].find(c=>c.ficha_id===id);setDragging(null);if(card)void move(card,to)}
 const href=(c:TarjetaMiDia)=>`/consultas?conversacion=${c.conversacion}&ficha=${c.ficha_id}`;
 const Card=({c,col}:{c:TarjetaMiDia;col:Col})=><div className={`v7-card ${c.pendiente?(c.horas>=24?'is-late':'is-pending'):''} ${dragging===c.ficha_id?'is-dragging':''}`} draggable={!readonly}
   onDragStart={e=>{e.dataTransfer.setData('text/plain',String(c.ficha_id));e.dataTransfer.effectAllowed='move';setDragging(c.ficha_id)}} onDragEnd={()=>{setDragging(null);setOver(null)}}
   role="link" tabIndex={0} onClick={()=>router.push(href(c))} onKeyDown={e=>{if(e.key==='Enter')router.push(href(c))}} title="Abrir la conversación">
   <strong>{c.cliente}</strong>
   <span className="v7-sub">{c.titulo}</span>
   <span className="v7-meta"><span>{c.codigo}</span><span>{estadoGestionNombre[c.estado_gestion]||c.estado_gestion}</span>{c.cantidad!=null&&<span>{unidades(c.cantidad)}</span>}{c.bajo_minimo&&<span className="is-pending">Bajo mínimo</span>}{c.pendiente&&<span className={c.horas>=24?'is-late':'is-pending'}>Sin responder {tiempoSinRespuesta(c.horas)}</span>}</span>
   <span className="v7-actions">
    {!readonly&&<button type="button" className="btn btn-outline v7-move" disabled={busy===c.ficha_id} onClick={e=>{e.stopPropagation();void move(c,col==='asignadas'?'sin_asignar':'asignadas')}}>{col==='asignadas'?<><ArrowRight size={12}/> Liberar</>:<><ArrowLeft size={12}/> Asignarme</>}</button>}</span>
  </div>;
 const column=(col:Col,title:string,cards:TarjetaMiDia[],total:number,pend:number)=>{
  const list=col==='asignadas'&&soloPend?cards.filter(c=>c.pendiente):cards;
  return <section className={`v7-col ${over===col?'is-over':''}`} aria-label={title} onDragOver={e=>{if(readonly)return;e.preventDefault();e.dataTransfer.dropEffect='move';if(over!==col)setOver(col)}} onDragLeave={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node))setOver(null)}} onDrop={e=>onDrop(e,col)}>
   <div className="v7-col-head"><h2>{title}</h2><span className="v7-count">{total}{pend?` · ${pend} sin responder`:''}</span>
    {col==='asignadas'&&<div className="v7-seg" role="group" aria-label="Filtrar"><button type="button" className={!soloPend?'is-on':''} onClick={()=>setSoloPend(false)}>Todas</button><button type="button" className={soloPend?'is-on':''} onClick={()=>setSoloPend(true)}>Sin responder</button></div>}</div>
   <div className="v7-list">{list.map(c=><Card key={c.ficha_id} c={c} col={col}/>)}
    {!list.length&&<p className="v7-empty">{col==='asignadas'?(soloPend?'Nada sin responder.':data?.propio?'No tenés consultas asignadas. Arrastrá una desde Sin asignar.':'Sin consultas asignadas.'):'Nada sin asignar.'}</p>}
    {cards.length<total&&<Link className="v3-text-action v7-empty" href={`/consultas?responsable=${col==='asignadas'?(data?.propio?'mias':`u:${owner}`):'sin_asignar'}`}>Ver las {total} en la bandeja</Link>}</div>
  </section>};
 const fecha=new Date().toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'long'});
 const acts=[...(data?.actividades_vencidas||[]).map(a=>({a,late:true})),...(data?.actividades_hoy||[]).map(a=>({a,late:false}))];
 return <Shell>
  <div className="v7-day-head"><div><div className="v7-date">{fecha}</div><h1>Mi día</h1></div>
   <div className="v7-day-actions"><Link className="btn btn-primary" href="/consultas?foco=1" title="La consulta más urgente, una tras otra (F)">Siguiente consulta</Link>
   {!!data?.usuarios.length&&<select aria-label="Ver el tablero de" value={ver||user?.username||''} onChange={e=>setVer(e.target.value===user?.username?'':e.target.value)}>{data.usuarios.map(u=><option key={u.usuario} value={u.usuario}>{u.usuario===user?.username?`${u.nombre} (yo)`:u.nombre}</option>)}{user&&!data.usuarios.some(u=>u.usuario===user.username)&&<option value={user.username}>{user.name} (yo)</option>}</select>}</div></div>
  {error&&<p className="alert error" role="alert">{error}</p>}
  {!data?<p className="muted">Cargando…</p>:<>
   <div className="v7-board">
    {column('asignadas',data.propio?'Asignadas a mí':`Asignadas a ${data.usuarios.find(u=>u.usuario===data.usuario)?.nombre||data.usuario}`,data.asignadas,data.resumen.asignadas,data.resumen.asignadas_sin_responder)}
    {column('sin_asignar','Sin asignar',data.sin_asignar,data.resumen.sin_asignar,data.resumen.sin_asignar_sin_responder)}
   </div>
   <div className="v7-lower">
    <section className="v7-block" id="seguimientos"><h3>Seguimientos sugeridos <small>cotizaciones sin respuesta hace {data.dias_seguimiento}+ días</small></h3>
     {data.seguimientos_sugeridos.length?<ul className="v7-rows">{data.seguimientos_sugeridos.map(x=><li key={x.ficha_id}><span className="v7-when">{x.dias} d</span><span className="v7-what"><strong>{x.cliente}</strong><small>{x.codigo}{x.cotizacion.monto!=null?` · ${cotizacionTexto(x.cotizacion.monto,x.cotizacion.moneda)}`:''}</small></span><Link className="btn btn-outline" href={`/consultas?conversacion=${x.conversacion}&ficha=${x.ficha_id}&seguimiento=1`}>Preparar seguimiento</Link></li>)}</ul>:<p className="v7-note">Ninguno por ahora.</p>}</section>
    <section className="v7-block"><h3>Actividades de hoy {!!data.resumen.vencidas&&<small>{data.resumen.vencidas} vencida{data.resumen.vencidas===1?'':'s'}</small>}</h3>
     {acts.length?<ul className="v7-rows">{acts.map(({a,late})=><li key={a.id}><span className={`v7-when ${late?'is-late':''}`}>{late?dia(a.inicio):hora(a.inicio)}</span><span className="v7-what"><strong>{a.titulo}</strong><small>{tipoNombre[a.tipo]||a.tipo}{a.cliente?` · ${a.cliente}`:''}</small></span>{a.conversacion&&<Link className="btn btn-outline" href={`/consultas?conversacion=${a.conversacion}${a.ficha_id?`&ficha=${a.ficha_id}`:''}`}>Abrir</Link>}{!readonly&&<button type="button" className="btn btn-outline" disabled={busy===a.id} onClick={()=>void done(a)}><Check size={12}/> Hecho</button>}</li>)}</ul>:<p className="v7-note">Nada agendado. <Link href="/agenda" className="v3-text-action">Ir a la agenda</Link></p>}</section>
   </div></>}
 </Shell>;
}
