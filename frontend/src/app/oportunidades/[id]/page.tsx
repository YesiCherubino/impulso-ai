'use client';
import Link from 'next/link';
import {useParams} from 'next/navigation';
import {useCallback,useEffect,useState} from 'react';
import {ArrowLeft,CalendarClock} from 'lucide-react';
import Shell from '@/components/shell';
import CaseDialog from '@/components/case-dialog';
import {api,Detalle,Estado,dateAR,estadoNombre,FichaConsulta,UsuarioSesion} from '@/lib/api';
export default function DetailPage(){const params=useParams<{id:string}>();const id=Number(params.id);const [selectedEstado,setSelectedEstado]=useState<Estado>('nueva'),[estadoSaving,setEstadoSaving]=useState(false),[estadoError,setEstadoError]=useState(''),[estadoSuccess,setEstadoSuccess]=useState('');const [followDate,setFollowDate]=useState(''),[followReason,setFollowReason]=useState(''),[scheduleSaving,setScheduleSaving]=useState(false),[scheduleMessage,setScheduleMessage]=useState('');const [fichas,setFichas]=useState<FichaConsulta[]>([]),[openedFicha,setOpenedFicha]=useState<number|null>(null),[user,setUser]=useState<UsuarioSesion|null>(null),[profile,setProfile]=useState({cliente:'',contacto:'',producto:'',email:'',telefono:'',notas:''}),[profileSaving,setProfileSaving]=useState(false),[data,setData]=useState<Detalle|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
 const load=useCallback(async()=>{setLoading(true);setError('');try{const item=await api<Detalle>(`/api/opportunities/${id}`);setData(item);setProfile({cliente:item.cliente,contacto:item.contacto,producto:item.producto,email:item.email||'',telefono:item.telefono||'',notas:item.notas});setSelectedEstado(item.estado);setFollowDate(item.fecha_seguimiento||'');setFollowReason(item.motivo_seguimiento)}catch(e){setError(e instanceof Error?e.message:'Error inesperado')}finally{setLoading(false)}},[id]);useEffect(()=>{if(Number.isInteger(id)&&id>0)void load();else{setError('Identificador no válido');setLoading(false)}},[id,load]);
 useEffect(()=>{void fetch('/api/session/me').then(r=>r.ok?r.json():null).then(setUser).catch(()=>{})},[]);
 useEffect(()=>{if(Number.isInteger(id)&&id>0)void api<FichaConsulta[]>(`/api/opportunities/${id}/fichas`).then(setFichas).catch(()=>{})},[id]);
 async function saveStatus(next:Estado){
  if(!data || next===data.estado)return;
  setEstadoError('');setEstadoSuccess('');setEstadoSaving(true);
  try{
   const updated=await api<Detalle>(`/api/opportunities/${id}/status`,{
    method:'POST',body:JSON.stringify({estado:next})
   });
   setData(updated);setSelectedEstado(updated.estado);setEstadoSuccess('Guardado');
  }catch(e){setSelectedEstado(data.estado);setEstadoError(e instanceof Error?e.message:'No se pudo actualizar el estado')}
  finally{setEstadoSaving(false)}
 }
 async function scheduleFollowUp(e?:React.FormEvent,remove=false){e?.preventDefault();setScheduleSaving(true);setScheduleMessage('');try{
  const updated=await api<Detalle>(`/api/opportunities/${id}/follow-up`,{method:'POST',body:JSON.stringify({fecha_seguimiento:remove?null:followDate||null,motivo_seguimiento:remove?'':followReason})});
  setData(updated);setFollowDate(updated.fecha_seguimiento||'');setFollowReason(updated.motivo_seguimiento);setScheduleMessage(remove?'Seguimiento eliminado.':'Seguimiento guardado.');
 }catch(e){setScheduleMessage(e instanceof Error?e.message:'No se pudo programar el seguimiento')}finally{setScheduleSaving(false)}}
 async function saveProfile(e:React.FormEvent){e.preventDefault();setProfileSaving(true);setError('');try{await api(`/api/opportunities/${id}/profile`,{method:'POST',body:JSON.stringify(profile)});await load();}catch(e){setError(e instanceof Error?e.message:'No se pudo actualizar la ficha')}finally{setProfileSaving(false)}}
 return <Shell><div className="page-head v3-contact-heading"><div><Link href={data && ['ganada','perdida'].includes(data.estado)?'/finalizados':'/'} className="back-link"><ArrowLeft size={16}/> Volver a fichas</Link><div className="eyebrow">DETALLE DE CONTACTO COMERCIAL <span className="eyebrow-line"/></div><h1>{data?.cliente ?? 'Contacto comercial'}</h1><p>{data?.producto ?? 'Información comercial'}</p></div>
 {data&&<div className="v3-contact-status" aria-label="Estado comercial"><label htmlFor="estado-contacto">Estado comercial</label>{user?.role==='gerencia'?<span className={`status status-${data.estado}`}>{estadoNombre[data.estado]}</span>:<select id="estado-contacto" value={selectedEstado} onChange={e=>{const next=e.target.value as Estado;setSelectedEstado(next);void saveStatus(next)}} disabled={estadoSaving} aria-busy={estadoSaving}>{(Object.keys(estadoNombre) as Estado[]).map(st=><option key={st} value={st}>{estadoNombre[st]}</option>)}</select>}{estadoSaving&&<small role="status">Guardando…</small>}{estadoSuccess&&!estadoSaving&&<small role="status">{estadoSuccess}</small>}{estadoError&&<small role="alert" className="v3-form-error">{estadoError}</small>}</div>}
 </div>
 {loading&&<div className="panel empty">Cargando contacto comercial...</div>}{error&&<div className="alert error">{error}</div>}
 {data&&<>
 <details className="panel v3-accordion"><summary>Datos del contacto</summary><div className="v3-accordion-body"><form className="fields" onSubmit={e=>void saveProfile(e)}><div className="v3-fields"><label>Empresa<input value={profile.cliente} onChange={e=>setProfile({...profile,cliente:e.target.value})} disabled={user?.role==='gerencia'}/></label><label>Persona de contacto<input value={profile.contacto} onChange={e=>setProfile({...profile,contacto:e.target.value})} disabled={user?.role==='gerencia'}/></label><label>Email<input type="email" value={profile.email} onChange={e=>setProfile({...profile,email:e.target.value})} disabled={user?.role==='gerencia'}/></label><label>Teléfono<input value={profile.telefono} onChange={e=>setProfile({...profile,telefono:e.target.value})} disabled={user?.role==='gerencia'}/></label><label className="wide">Notas comerciales<textarea value={profile.notas} onChange={e=>setProfile({...profile,notas:e.target.value})} rows={3} disabled={user?.role==='gerencia'}/></label></div>{user?.role!=='gerencia'&&<button type="submit" className="btn btn-outline" disabled={profileSaving}>{profileSaving?'Guardando…':'Guardar cambios'}</button>}</form></div></details>
 <details className="panel v3-accordion"><summary>Consultas del contacto <small>{fichas.length}</small></summary><div className="v3-accordion-body v3-case-links">{fichas.map(f=><button key={f.id} className="v3-case-link" onClick={()=>setOpenedFicha(f.id)}><strong>{f.codigo}</strong><span>{f.titulo||f.producto}</span><span>Ver detalle ›</span></button>)}{!fichas.length&&<p className="muted">Sin consultas asociadas.</p>}</div></details>
 <details className="panel v3-accordion"><summary>Seguimiento comercial</summary><div className="v3-accordion-body"><form className="fields" onSubmit={e=>void scheduleFollowUp(e)}><label>Próximo seguimiento<input type="date" value={followDate} onChange={e=>setFollowDate(e.target.value)}/></label><label>Motivo o próxima acción<input maxLength={300} value={followReason} onChange={e=>setFollowReason(e.target.value)}/></label><div className="v3-thread-tools"><button type="submit" className="btn btn-primary" disabled={user?.role==='gerencia'||scheduleSaving}>{scheduleSaving?'Guardando…':'Programar seguimiento'}</button>{data.fecha_seguimiento&&<button className="btn btn-outline" type="button" onClick={()=>void scheduleFollowUp(undefined,true)}>Quitar fecha</button>}<Link className="btn btn-outline" href="/agenda"><CalendarClock size={17}/> Abrir agenda</Link></div>{scheduleMessage&&<small role="status">{scheduleMessage}</small>}</form></div></details>
 <details className="panel v3-accordion"><summary>Historial de actividad <small>{data.interacciones.length}</small></summary><div className="v3-accordion-body v3-history">{data.interacciones.map(x=><article key={x.id}><small>{dateAR(x.fecha)} · {x.tipo}</small><p>{x.descripcion}</p></article>)}{!data.interacciones.length&&<p className="muted">Sin actividad registrada.</p>}</div></details>
 </>}
 {openedFicha!==null&&<CaseDialog fichaId={openedFicha} readOnly={user?.role==='gerencia'} allowMove onClose={()=>setOpenedFicha(null)}/>}
 </Shell>
}
