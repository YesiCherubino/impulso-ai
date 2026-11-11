'use client';
import Link from 'next/link';
import {useParams} from 'next/navigation';
import {useCallback,useEffect,useState} from 'react';
import {ArrowLeft,CalendarDays,ChevronDown,ContactRound,History,MessageCircle} from 'lucide-react';
import Shell from '@/components/shell';
import CaseDialog from '@/components/case-dialog';
import {api,Detalle,dateAR,FichaConsulta,UsuarioSesion,estadoGestionNombre,esCerrada,ESTADOS_ABIERTOS,cotizacionTexto,puede} from '@/lib/api';

export default function DetailPage(){
 const params=useParams<{id:string}>(); const id=Number(params.id);
 const [followDate,setFollowDate]=useState(''),[followReason,setFollowReason]=useState(''),[scheduleSaving,setScheduleSaving]=useState(false),[scheduleMessage,setScheduleMessage]=useState('');
 const [fichas,setFichas]=useState<FichaConsulta[]>([]),[openedFicha,setOpenedFicha]=useState<number|null>(null),[user,setUser]=useState<UsuarioSesion|null>(null);
 const [profile,setProfile]=useState({cliente:'',contacto:'',producto:'',email:'',telefono:'',notas:''}),[profileSaving,setProfileSaving]=useState(false);
 const [data,setData]=useState<Detalle|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
 const [contactOpen,setContactOpen]=useState(false),[historyOpen,setHistoryOpen]=useState(false);
 const load=useCallback(async()=>{
  setLoading(true);setError('');
  try{const item=await api<Detalle>(`/api/opportunities/${id}`);setData(item);setProfile({cliente:item.cliente,contacto:item.contacto,producto:item.producto,email:item.email||'',telefono:item.telefono||'',notas:item.notas});setFollowDate(item.fecha_seguimiento||'');setFollowReason(item.motivo_seguimiento)}
  catch(e){setError(e instanceof Error?e.message:'Error inesperado')}
  finally{setLoading(false)}
 },[id]);
 const loadCases=useCallback(async()=>{try{setFichas(await api<FichaConsulta[]>(`/api/opportunities/${id}/fichas`))}catch{/* La ficha sigue disponible aunque falle el listado */}},[id]);
 useEffect(()=>{if(Number.isInteger(id)&&id>0){void load();void loadCases()}else{setError('Identificador no válido');setLoading(false)}},[id,load,loadCases]);
 useEffect(()=>{void fetch('/api/session/me').then(r=>r.ok?r.json():null).then(setUser).catch(()=>{})},[]);
 async function scheduleFollowUp(e?:React.FormEvent,remove=false){e?.preventDefault();setScheduleSaving(true);setScheduleMessage('');try{
  const updated=await api<Detalle>(`/api/opportunities/${id}/follow-up`,{method:'POST',body:JSON.stringify({fecha_seguimiento:remove?null:followDate||null,motivo_seguimiento:remove?'':followReason})});
  setData(updated);setFollowDate(updated.fecha_seguimiento||'');setFollowReason(updated.motivo_seguimiento);setScheduleMessage(remove?'Seguimiento eliminado':'Seguimiento guardado')
 }catch(e){setScheduleMessage(e instanceof Error?e.message:'No se pudo programar el seguimiento')}finally{setScheduleSaving(false)}}
 async function saveProfile(e:React.FormEvent){e.preventDefault();setProfileSaving(true);setError('');try{await api(`/api/opportunities/${id}/profile`,{method:'POST',body:JSON.stringify(profile)});await load()}
 catch(e){setError(e instanceof Error?e.message:'No se pudo actualizar la ficha')}finally{setProfileSaving(false)}}
 const readonly=!puede(user,'contactos');
 const activeCases=fichas.filter(f=>!esCerrada(f.estado_gestion));
 // El estado comercial vive en cada gestión; acá se muestra el de la gestión abierta más avanzada.
 const leadState=activeCases.map(f=>f.estado_gestion||'sin_atender').sort((a,b)=>ESTADOS_ABIERTOS.indexOf(b as never)-ESTADOS_ABIERTOS.indexOf(a as never))[0]||fichas[0]?.estado_gestion||'';
 const completedCases=fichas.length-activeCases.length;
 return <Shell>
  <div className="v4-contact-page">
   <Link href={fichas.length&&!activeCases.length?'/finalizados':'/contactos'} className="v4-back-link"><ArrowLeft size={16}/> Volver a fichas</Link>
   {loading&&<div className="panel empty">Cargando ficha...</div>}{error&&<p className="alert error" role="alert">{error}</p>}
   {data&&<>
    <header className="v4-contact-header">
     <div className="v4-contact-intro"><span className="v4-contact-avatar" aria-hidden="true">{data.cliente.charAt(0).toUpperCase()}</span><div><h1>{data.cliente}</h1><p>{[data.contacto,data.email||data.telefono].filter(Boolean).join(' · ')}</p></div></div>
     <div className="v4-contact-status"><label>Estado comercial</label>{leadState?<span className={`v4-case-status is-${leadState}`}>{estadoGestionNombre[leadState]}</span>:<span className="muted">Sin gestión</span>}<small>Se actualiza desde cada gestión</small></div>
    </header>
    <section className="v4-contact-section v4-contact-cases" aria-label="Gestiones comerciales">
     <div className="v4-contact-section-title"><div><h2>Gestiones comerciales</h2><small>{activeCases.length} activa{activeCases.length===1?'':'s'}{completedCases>0?` · ${completedCases} finalizada${completedCases===1?'':'s'}`:''}</small></div></div>
     {fichas.length>0?<div className="v4-contact-case-list">{fichas.map(f=><button key={f.id} type="button" className="v4-contact-case" onClick={()=>setOpenedFicha(f.id)}><span className="v4-contact-case-icon"><MessageCircle size={17}/></span><span className="v4-contact-case-copy"><strong>{f.titulo||f.producto||'Gestión comercial'}</strong><small>{f.codigo}{f.mensajes_count!=null?` · ${f.mensajes_count} mensaje${f.mensajes_count===1?'':'s'}`:''}</small></span>{f.cotizacion_monto!=null&&<small className="v5-chip is-money">{cotizacionTexto(f.cotizacion_monto,f.cotizacion_moneda)}</small>}<span className={`v4-case-status is-${f.estado_gestion||'sin_atender'}`}>{estadoGestionNombre[f.estado_gestion||'sin_atender']}</span><ChevronDown size={16} className="v4-case-chevron"/></button>)}</div>:<p className="v4-contact-empty">Todavía no hay gestiones asociadas.</p>}
    </section>
    <div className="v4-contact-secondary">
     <section className="v4-light-disclosure"><button type="button" className="v4-light-summary" aria-expanded={contactOpen} onClick={()=>setContactOpen(v=>!v)}><ContactRound size={17}/><span>Datos del contacto</span><ChevronDown size={17} className={contactOpen?'is-open':''}/></button>
      {contactOpen&&<div className="v4-light-body"><form className="fields" onSubmit={e=>void saveProfile(e)}><div className="v3-fields"><label>Empresa<input value={profile.cliente} onChange={e=>setProfile({...profile,cliente:e.target.value})} disabled={readonly}/></label><label>Persona de contacto<input value={profile.contacto} onChange={e=>setProfile({...profile,contacto:e.target.value})} disabled={readonly}/></label><label>Email<input type="email" value={profile.email} onChange={e=>setProfile({...profile,email:e.target.value})} disabled={readonly}/></label><label>Teléfono<input value={profile.telefono} onChange={e=>setProfile({...profile,telefono:e.target.value})} disabled={readonly}/></label><label className="wide">Notas comerciales<textarea value={profile.notas} onChange={e=>setProfile({...profile,notas:e.target.value})} rows={3} disabled={readonly}/></label></div>{!readonly&&<button type="submit" className="btn btn-outline" disabled={profileSaving}>{profileSaving?'Guardando…':'Guardar cambios'}</button>}</form></div>}
     </section>
     <section className="v4-light-disclosure"><button type="button" className="v4-light-summary" aria-expanded={historyOpen} onClick={()=>setHistoryOpen(v=>!v)}><History size={17}/><span>Actividad y seguimientos</span>{data.fecha_seguimiento&&<small>Próximo: {dateAR(data.fecha_seguimiento)}</small>}<ChevronDown size={17} className={historyOpen?'is-open':''}/></button>
      {historyOpen&&<div className="v4-light-body v4-activity-panel"><div className="v4-follow-heading"><h3>Próximo seguimiento</h3><Link href="/agenda"><CalendarDays size={15}/> Abrir agenda</Link></div><form className="fields" onSubmit={e=>void scheduleFollowUp(e)}><div className="v3-fields"><label>Fecha<input type="date" value={followDate} onChange={e=>setFollowDate(e.target.value)} disabled={readonly}/></label><label>Próxima acción<input maxLength={300} value={followReason} onChange={e=>setFollowReason(e.target.value)} disabled={readonly}/></label></div>{!readonly&&<div className="v4-follow-actions"><button type="submit" className="btn btn-outline" disabled={scheduleSaving}>{scheduleSaving?'Guardando…':'Guardar seguimiento'}</button>{data.fecha_seguimiento&&<button className="btn btn-ghost" type="button" onClick={()=>void scheduleFollowUp(undefined,true)}>Quitar fecha</button>}</div>}{scheduleMessage&&<small role="status">{scheduleMessage}</small>}</form><div className="v4-activity-list"><h3>Historial de actividad</h3>{data.interacciones.map(x=><article key={x.id}><small>{dateAR(x.fecha)} · {x.tipo}</small><p>{x.descripcion}</p></article>)}{!data.interacciones.length&&<p className="muted">Sin actividad registrada.</p>}</div></div>}
     </section>
    </div>
   </>}
   {openedFicha!==null&&<CaseDialog fichaId={openedFicha} readOnly={readonly} allowMove onClose={()=>{setOpenedFicha(null);void loadCases()}}/>}
  </div>
 </Shell>
}
