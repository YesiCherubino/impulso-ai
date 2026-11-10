'use client';
import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {Check,ChevronDown,ChevronRight,ClipboardCopy,FileText,Mail,MessageCircle,Plus,Search,X,CalendarDays,MoreHorizontal,CheckCheck,FolderOpen,Send,AlertTriangle,UserCheck,Archive,RotateCcw,Sparkles,Clock3,EyeOff} from 'lucide-react';
import Link from 'next/link';
import Shell from '@/components/shell';
import CaseDialog from '@/components/case-dialog';
import CaseStatusSelect from '@/components/case-status';
import {api,ConsultaBandeja,ConsultaIA,FichaConsulta,GestionHilo,Respuesta,Responsable,UsuarioSesion,estadoGestionNombre,tipoConsultaNombre,tiposConsulta,tiempoSinRespuesta,unidades,esCerrada} from '@/lib/api';

type Thread={key:string;cliente:string;contacto:string;mensajes:ConsultaBandeja[];ultimo:string;no_leidos:number;gestion:GestionHilo|null;cerrada:boolean;mensaje_tras_cierre:boolean;respuesta:Respuesta};
const newBlank={cliente:'',contacto:'',canal:'WhatsApp',texto:'',email_remitente:'',telefono_remitente:'',asunto:''};
const dt=(s:string)=>new Date(s).toLocaleString('es-AR',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const filters=[['todos','Todos'],['WhatsApp','WhatsApp'],['Correo','Email'],['Formulario web','Formulario web']];
const isOut=(m:ConsultaBandeja)=>m.direccion==='saliente';
const lowPriority=(t:Thread)=>!!t.gestion&&(t.gestion.bajo_minimo||t.gestion.tipo_consulta==='no_comercial');
export default function BandejaConsultas(){
 const [threads,setThreads]=useState<Thread[]>([]),[cases,setCases]=useState<FichaConsulta[]>([]),[user,setUser]=useState<UsuarioSesion|null>(null),[owners,setOwners]=useState<Responsable[]>([]),[selected,setSelected]=useState<string|null>(null),[messageId,setMessageId]=useState<number|null>(null);
 const [search,setSearch]=useState(''),[channel,setChannel]=useState('todos'),[filter,setFilter]=useState('abiertas'),[ownerFilter,setOwnerFilter]=useState('todos'),[typeFilter,setTypeFilter]=useState('todos'),[order,setOrder]=useState<'reciente'|'prioridad'>('reciente');
 const [openNew,setOpenNew]=useState(false),[newForm,setNewForm]=useState(newBlank),[formCase,setFormCase]=useState<number|null>(null);
 const [analysis,setAnalysis]=useState<ConsultaIA|null>(null),[draft,setDraft]=useState(''),[draftSaved,setDraftSaved]=useState(''),[showReport,setShowReport]=useState(false),[showDraft,setShowDraft]=useState(false),[sendChannel,setSendChannel]=useState<'WhatsApp'|'Correo'>('WhatsApp'),[loteMinimo,setLoteMinimo]=useState(false);
 const [busy,setBusy]=useState(false),[generating,setGenerating]=useState<''|'report'|'draft'>(''),[error,setError]=useState(''),[notice,setNotice]=useState(''),[lastSync,setLastSync]=useState<Date|null>(null),[activeCase,setActiveCase]=useState<number|null>(null);
 const [caseMenu,setCaseMenu]=useState(false),[moreMenu,setMoreMenu]=useState(false);
 const selectedThread=threads.find(t=>t.key===selected)||null;
 const caseMessages=(selectedThread?.mensajes||[]).filter(m=>activeCase===null||m.ficha_id===activeCase);
 const incomingMessages=caseMessages.filter(m=>!isOut(m));
 const activeMessage=incomingMessages.find(m=>m.id===messageId)||incomingMessages.at(-1)||caseMessages.at(-1)||null;
 const readonly=user?.role==='gerencia';
 const detailsRef=useRef<HTMLDivElement|null>(null),reportRef=useRef<HTMLElement|null>(null),draftRef=useRef<HTMLDivElement|null>(null);
 const activeMessageIdRef=useRef<number|null>(null);
 activeMessageIdRef.current=activeMessage?.id??null;
 const load=useCallback(async()=>{try{const [t,f]=await Promise.all([api<Thread[]>('/api/inbox/threads'),api<FichaConsulta[]>('/api/fichas')]);setThreads(t);setCases(f);setLastSync(new Date());setError('')}catch(e){setError(e instanceof Error?e.message:'No se pudo sincronizar la bandeja')}},[]);
 useEffect(()=>{void load();void fetch('/api/session/me').then(r=>r.ok?r.json():null).then((u:UsuarioSesion|null)=>{setUser(u);if(u?.role==='ventas')setOwnerFilter('mias_y_libres')}).catch(()=>{});void api<Responsable[]>('/api/users/responsables').then(setOwners).catch(()=>{});const timer=setInterval(()=>{if(document.visibilityState==='visible')void load()},30000);const focused=()=>{if(document.visibilityState==='visible')void load()};document.addEventListener('visibilitychange',focused);return()=>{clearInterval(timer);document.removeEventListener('visibilitychange',focused)}},[load]);
 useEffect(()=>{
  if(!threads.length||selected)return;
  const params=new URLSearchParams(window.location.search);
  const queued=window.sessionStorage.getItem('impulso:pending-consulta');
  const id=Number(queued||params.get('consulta'));
  if(!id)return;
  window.sessionStorage.removeItem('impulso:pending-consulta');
  if(params.has('consulta')){params.delete('consulta');window.history.replaceState(window.history.state,'',window.location.pathname+(params.toString()?'?'+params.toString():''));}
  const found=threads.find(t=>t.mensajes.some(m=>m.id===id));
  if(found)void openThread(found,id);
 },[threads,selected]);
 useEffect(()=>{
  const onOpen=(event:Event)=>{const id=Number((event as CustomEvent<number>).detail);const found=threads.find(t=>t.mensajes.some(m=>m.id===id));if(found){window.sessionStorage.removeItem('impulso:pending-consulta');void openThread(found,id)}};
  window.addEventListener('impulso:open-consulta',onOpen);
  return()=>window.removeEventListener('impulso:open-consulta',onOpen);
 },[threads]);
 useEffect(()=>{
  if(!selected)return;
  const onKey=(event:KeyboardEvent)=>{if(event.key!=='Escape')return;if(caseMenu||moreMenu){setCaseMenu(false);setMoreMenu(false)}else closeThread()};
  window.addEventListener('keydown',onKey);
  return()=>window.removeEventListener('keydown',onKey);
 },[selected,caseMenu,moreMenu]);
 useEffect(()=>{
  if(!activeMessage){setAnalysis(null);setDraft('');setDraftSaved('');return;}
  let valid=true;const id=activeMessage.id;
  setAnalysis(null);setDraft('');setDraftSaved('');
  void api<{analisis:{resultado:ConsultaIA|null;borrador:string}|null}>(`/api/inbox/${id}/analysis`).then(r=>{if(valid){setAnalysis(r.analisis?.resultado||null);setDraft(r.analisis?.borrador||'');setDraftSaved(r.analisis?.borrador||'')}}).catch(()=>{});
  return()=>{valid=false};
 },[activeMessage?.id]);
 useEffect(()=>{if(showReport)reportRef.current?.scrollIntoView({behavior:'smooth',block:'nearest'})},[showReport]);
 useEffect(()=>{if(showDraft)draftRef.current?.scrollIntoView({behavior:'smooth',block:'nearest'})},[showDraft]);
 const shown=useMemo(()=>{
  const term=search.toLowerCase();
  const list=threads.filter(t=>{
   const matchChannel=channel==='todos'||t.mensajes.some(m=>!isOut(m)&&(m.canal===channel||(channel==='WhatsApp'&&m.canal.startsWith('WhatsApp'))));
   const open=!t.cerrada||t.mensaje_tras_cierre;
   const matchState=filter==='todas'||(filter==='abiertas'&&open)||(filter==='sin_leer'&&t.no_leidos>0)||(filter==='sin_atender'&&open&&t.gestion?.estado_gestion==='sin_atender')||(filter==='sin_responder'&&t.respuesta.pendiente)||(filter==='cerradas'&&t.cerrada);
   const owner=t.gestion?.responsable||'';
   const matchOwner=ownerFilter==='todos'||(ownerFilter==='mias'&&owner===user?.username)||(ownerFilter==='mias_y_libres'&&(owner===user?.username||!owner))||(ownerFilter==='sin_asignar'&&!owner)||(ownerFilter.startsWith('u:')&&owner===ownerFilter.slice(2));
   const matchType=typeFilter==='todos'||t.gestion?.tipo_consulta===typeFilter;
   return matchChannel&&matchState&&matchOwner&&matchType&&[t.cliente,t.contacto,t.gestion?.codigo,...t.mensajes.flatMap(m=>[m.texto,m.asunto,m.email_remitente])].some(s=>(s||'').toLowerCase().includes(term));
  });
  if(order==='prioridad')return [...list].sort((a,b)=>Number(lowPriority(a))-Number(lowPriority(b))||Number(b.respuesta.pendiente)-Number(a.respuesta.pendiente)||b.respuesta.horas-a.respuesta.horas||(b.gestion?.cantidad||0)-(a.gestion?.cantidad||0)||b.ultimo.localeCompare(a.ultimo));
  return list;
 },[threads,search,channel,filter,ownerFilter,typeFilter,order,user]);
 async function openThread(t:Thread,focusId?:number){setSelected(t.key);setCaseMenu(false);setMoreMenu(false);const id=focusId||t.mensajes.filter(m=>!isOut(m)).at(-1)?.id||t.mensajes.at(-1)?.id||null;setMessageId(id);setActiveCase(t.mensajes.find(m=>m.id===id)?.ficha_id||t.gestion?.id||null);setShowReport(false);setShowDraft(false);setAnalysis(null);setNotice('');setLoteMinimo(false);const last=t.mensajes.find(m=>m.id===id);setSendChannel(last?.canal==='Correo'?'Correo':'WhatsApp');const unseen=t.mensajes.filter(m=>!m.leido_en&&!isOut(m));if(unseen.length&&!readonly){await Promise.all(unseen.map(m=>api(`/api/inbox/${m.id}/read`,{method:'POST',body:JSON.stringify({read:true})}).catch(()=>{})));await load()}}
 function pick(m:ConsultaBandeja){if(isOut(m))return;setCaseMenu(false);setMoreMenu(false);setMessageId(m.id);setAnalysis(null);setShowReport(false);setShowDraft(false);setSendChannel(m.canal==='Correo'?'Correo':'WhatsApp')}
 async function markUnread(){if(!activeMessage||readonly)return;setBusy(true);try{await api(`/api/inbox/${activeMessage.id}/read`,{method:'POST',body:JSON.stringify({read:false})});setSelected(null);await load()}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function createNew(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');try{await api('/api/inbox/new',{method:'POST',body:JSON.stringify(newForm)});setNewForm(newBlank);setOpenNew(false);await load()}catch(e){setError(String(e))}finally{setBusy(false)}}
 function changeCase(id:number|null){setCaseMenu(false);setMoreMenu(false);setActiveCase(id);setMessageId((selectedThread?.mensajes||[]).filter(m=>!isOut(m)&&(id===null||m.ficha_id===id)).at(-1)?.id||null);setShowReport(false);setAnalysis(null);setShowDraft(false);setNotice('')}
 async function act(action:()=>Promise<unknown>,ok:string){setBusy(true);setError('');try{await action();await load();setNotice(ok)}catch(e){setError(e instanceof Error?e.message:'No se pudo completar la acción')}finally{setBusy(false)}}
 async function generate(kind:'report'|'draft',regenerate=false,lote=loteMinimo){if(!activeMessage)return;const target=activeMessage.id;setBusy(true);setGenerating(kind);setError('');try{const r=await api<{resultado:ConsultaIA;borrador:string}>(`/api/inbox/${target}/analysis`,{method:'POST',body:JSON.stringify({regenerar:regenerate,informar_lote_minimo:lote})});if(activeMessageIdRef.current!==target)return;setAnalysis(r.resultado);setDraft(r.borrador);setDraftSaved(r.borrador);await load();if(kind==='report')setShowReport(true);else setShowDraft(true)}catch(e){if(activeMessageIdRef.current===target)setError(e instanceof Error?e.message:'No se pudo generar')}finally{setBusy(false);setGenerating('')}}
 async function saveAnalysis(){const c=cases.find(f=>f.id===activeCase);if(!analysis||!c)return;setBusy(true);try{await api(`/api/fichas/${c.id}/edit`,{method:'POST',body:JSON.stringify({titulo:c.titulo,cliente:c.cliente,contacto:c.contacto,producto:c.producto||analysis.producto,cantidad:c.cantidad??analysis.cantidad,tipo_consulta:c.tipo_consulta!=='sin_clasificar'?c.tipo_consulta:(analysis.tipo_consulta||'sin_clasificar'),presentacion:c.presentacion||analysis.presentacion||'',packaging:c.packaging,requisitos:analysis.requisitos,datos_faltantes:analysis.datos_faltantes,resumen:analysis.resumen,origen:'ia'})});await load();setNotice('Información guardada en la gestión')}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function saveDraft(){if(!activeMessage)return;const target=activeMessage.id;const snapshot=draft;setBusy(true);try{await api(`/api/inbox/${target}/draft`,{method:'POST',body:JSON.stringify({borrador:snapshot})});if(activeMessageIdRef.current===target){setDraftSaved(snapshot);setNotice('Borrador guardado')}}catch(e){if(activeMessageIdRef.current===target)setError(String(e))}finally{setBusy(false)}}
 async function copyAndRegister(){if(!activeMessage||!draft.trim())return;try{await navigator.clipboard.writeText(draft)}catch{/* Si el navegador no permite copiar, igual se registra la respuesta. */}
  await act(()=>api(`/api/inbox/${activeMessage.id}/reply`,{method:'POST',body:JSON.stringify({texto:draft,canal:sendChannel})}),`Respuesta copiada y registrada como enviada por ${sendChannel==='Correo'?'email':'WhatsApp'}`);setShowDraft(false)}
 async function newCaseForLatest(){const t=selectedThread;if(!t?.gestion)return;const closedAt=t.gestion.cerrada_en?new Date(t.gestion.cerrada_en).getTime():0;const after=t.mensajes.filter(m=>!isOut(m)&&m.ficha_id===t.gestion?.id&&new Date(m.recibido_el).getTime()>closedAt);const first=after[0]||t.mensajes.filter(m=>!isOut(m)).at(-1);if(!first)return;
  await act(async()=>{const c=await api<{id:number}>(`/api/inbox/${first.id}/new-case`,{method:'POST',body:JSON.stringify({titulo:`Nueva consulta de ${t.cliente}`})});for(const m of after)await api(`/api/inbox/${m.id}/move`,{method:'POST',body:JSON.stringify({ficha_id:c.id})});setActiveCase(c.id)},'Nueva gestión creada con los mensajes posteriores al cierre')}
 const related=cases.filter(c=>c.cliente===selectedThread?.cliente||(selectedThread?.mensajes||[]).some(m=>m.ficha_id===c.id)||c.oportunidad_id!=null&&c.oportunidad_id===cases.find(f=>f.id===activeMessage?.ficha_id)?.oportunidad_id);
 const currentCase=cases.find(c=>c.id===activeCase);
 const sortedMessages=[...caseMessages].sort((a,b)=>new Date(a.recibido_el).getTime()-new Date(b.recibido_el).getTime());
 const messageDay=(m:ConsultaBandeja)=>new Date(m.recibido_el).toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'short'});
 const closeThread=()=>{setSelected(null);setCaseMenu(false);setMoreMenu(false);setShowDraft(false);setShowReport(false);const params=new URLSearchParams(window.location.search);if(params.has('consulta')){params.delete('consulta');window.history.replaceState(window.history.state,'',window.location.pathname+(params.toString()?'?'+params.toString():''))}};
 const ownerName=(u?:string)=>owners.find(o=>o.username===u)?.name||u||'';
 const pendientes=currentCase?.datos_a_confirmar||analysis?.datos_a_confirmar||[];
 const extrasIA=(analysis?.datos_faltantes||[]).filter(x=>!pendientes.some(p=>p.toLowerCase()===x.toLowerCase()));
 return <Shell><div className="v2-page-head"><div><h1>Bandeja de consultas</h1></div><div className="v2-head-right"><span className="v2-sync">{lastSync?'Sincronizado':'Conectando'}</span>{!readonly&&<button className="btn btn-primary" onClick={()=>setOpenNew(true)}><Plus size={17}/> Nueva consulta</button>}</div></div>
 {error&&<p className="alert error" role="alert">{error}</p>}
 <section className="panel v2-inbox"><div className="v3-inbox-filters"><label className="search"><Search size={17}/><input placeholder="Buscar en conversaciones" value={search} onChange={e=>setSearch(e.target.value)}/></label><div className="v3-switch">{filters.map(([val,label])=><button key={val} className={channel===val?'selected':''} onClick={()=>setChannel(val)}>{label}</button>)}</div>
  <div className="v5-filter-row">
   <select aria-label="Filtro por estado" value={filter} onChange={e=>setFilter(e.target.value)}><option value="abiertas">Abiertas</option><option value="sin_leer">No leídas</option><option value="sin_atender">Sin atender</option><option value="sin_responder">Sin responder</option><option value="cerradas">Cerradas</option><option value="todas">Todas</option></select>
   <select aria-label="Filtro por responsable" value={ownerFilter} onChange={e=>setOwnerFilter(e.target.value)}><option value="todos">Todos los responsables</option>{user&&<option value="mias">Mis consultas</option>}{user&&<option value="mias_y_libres">Mis consultas y sin asignar</option>}<option value="sin_asignar">Sin asignar</option>{owners.filter(o=>o.username!==user?.username).map(o=><option key={o.username} value={`u:${o.username}`}>{o.name}</option>)}</select>
   <select aria-label="Filtro por tipo de servicio" value={typeFilter} onChange={e=>setTypeFilter(e.target.value)}><option value="todos">Todos los servicios</option>{tiposConsulta.map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>
   <select aria-label="Orden" value={order} onChange={e=>setOrder(e.target.value as 'reciente'|'prioridad')}><option value="reciente">Más reciente</option><option value="prioridad">Prioridad</option></select>
  </div></div>
 <div className="v3-conversations">{shown.map(t=>{const g=t.gestion;const last=t.mensajes.at(-1);return <button key={t.key} className={`v3-conversation ${t.no_leidos?'is-unread':''} ${lowPriority(t)?'is-low':''}`} onClick={()=>void openThread(t)}><span className="v3-conversation-icon"><MessageCircle size={20}/></span><span className="v3-conversation-body"><span className="v3-conversation-top"><strong>{t.cliente}</strong><small>{dt(t.ultimo)}</small></span><small>{t.contacto} · {t.mensajes.length} mensaje{t.mensajes.length===1?'':'s'}{g?` · ${g.codigo}`:''}</small>
   {g&&<span className="v5-chips"><span className={`v5-chip is-state is-${g.estado_gestion}`}>{estadoGestionNombre[g.estado_gestion]||g.estado_gestion}</span>{g.tipo_consulta!=='sin_clasificar'&&<span className="v5-chip">{tipoConsultaNombre[g.tipo_consulta]}{g.tipo_sugerido_ia?' · IA':''}</span>}{g.cantidad!=null&&<span className="v5-chip">{unidades(g.cantidad)}</span>}<span className="v5-chip">{g.responsable?ownerName(g.responsable):'Sin asignar'}</span>{g.bajo_minimo&&<span className="v5-chip is-warning">Bajo mínimo</span>}{t.respuesta.pendiente&&<span className={`v5-chip ${t.respuesta.horas>=24?'is-danger':'is-attention'}`}><Clock3 size={11}/> Sin responder {tiempoSinRespuesta(t.respuesta.horas)}</span>}{t.mensaje_tras_cierre&&<span className="v5-chip is-attention">Nuevo mensaje en gestión cerrada</span>}</span>}
   <span>{last&&isOut(last)?'Vos: ':''}{last?.texto}</span></span>{t.no_leidos>0&&<b className="v3-unread-count">{t.no_leidos}</b>}<ChevronRight size={17}/></button>})}{!shown.length&&<div className="v3-empty">No hay conversaciones para estos filtros.</div>}</div></section>
 {openNew&&<div className="modal-backdrop v2-overlay" onMouseDown={()=>setOpenNew(false)}><div className="modal v2-modal" role="dialog" aria-modal="true" aria-label="Nueva consulta" onMouseDown={e=>e.stopPropagation()}><div className="modal-head"><h2>Nueva consulta</h2><button aria-label="Cerrar" className="icon-button" onClick={()=>setOpenNew(false)}><X/></button></div><form className="fields" onSubmit={createNew}><div className="form-row"><label>Empresa<input required value={newForm.cliente} onChange={e=>setNewForm({...newForm,cliente:e.target.value})}/></label><label>Nombre de contacto<input required value={newForm.contacto} onChange={e=>setNewForm({...newForm,contacto:e.target.value})}/></label></div><label>Origen<select value={newForm.canal} onChange={e=>setNewForm({...newForm,canal:e.target.value})}><option>WhatsApp</option><option value="Correo">Email</option><option>Formulario web</option><option>Manual</option></select></label><div className="form-row"><label>Email<input type="email" value={newForm.email_remitente} onChange={e=>setNewForm({...newForm,email_remitente:e.target.value})}/></label><label>Teléfono<input value={newForm.telefono_remitente} onChange={e=>setNewForm({...newForm,telefono_remitente:e.target.value})}/></label></div><label>Asunto (si corresponde)<input value={newForm.asunto} onChange={e=>setNewForm({...newForm,asunto:e.target.value})}/></label><label>Mensaje<textarea required minLength={5} rows={5} value={newForm.texto} onChange={e=>setNewForm({...newForm,texto:e.target.value})}/></label><button className="btn btn-primary" disabled={busy}>Guardar mensaje</button></form></div></div>}
 {selectedThread&&<div className="modal-backdrop v2-overlay" onMouseDown={closeThread}>
  <div className="v3-thread-modal v4-chat-modal" role="dialog" aria-modal="true" aria-label={`Conversación con ${selectedThread.cliente}`} onMouseDown={e=>e.stopPropagation()} ref={detailsRef}>
   <header className="v4-chat-header">
    <span className="v4-chat-avatar" aria-hidden="true">{selectedThread.cliente.charAt(0).toUpperCase()}</span>
    <div className="v4-chat-person"><h2>{selectedThread.cliente}</h2><small>{selectedThread.contacto} · {selectedThread.mensajes.length} mensaje{selectedThread.mensajes.length!==1?'s':''}</small></div>
    <button className="v4-icon-action" type="button" aria-label="Cerrar conversación" onClick={closeThread}><X size={19}/></button>
   </header>

   <div className="v4-chat-context">
    <div className="v4-case-selector-wrap">
     <button className="v4-case-trigger" type="button" aria-expanded={caseMenu} onClick={()=>{setCaseMenu(v=>!v);setMoreMenu(false)}}>
      <FolderOpen size={15} aria-hidden="true"/><span>{activeCase===null?'Todos los mensajes':currentCase?`${currentCase.codigo} · ${currentCase.titulo||currentCase.producto}`:'Sin gestión asociada'}</span><ChevronDown size={15}/>
     </button>
      {caseMenu&&<div className="v4-case-popover" role="menu" aria-label="Ver mensajes por gestión">
       <button type="button" role="menuitem" className={`v4-menu-item ${activeCase===null?'is-current':''}`} onClick={()=>changeCase(null)}><span className="v4-menu-copy"><strong>Todos los mensajes</strong></span>{activeCase===null&&<Check size={15}/>}</button>
       {related.map(c=><button type="button" role="menuitem" className={`v4-menu-item ${activeCase===c.id?'is-current':''}`} key={c.id} onClick={()=>changeCase(c.id)}><span className="v4-menu-copy"><strong>{c.codigo}</strong><small>{c.titulo||c.producto} · {estadoGestionNombre[c.estado_gestion||'sin_atender']}</small></span>{activeCase===c.id&&<Check size={15}/>}</button>)}
      </div>}
    </div>
    {currentCase&&<div className="v5-context-tools">
     {readonly?<span className="v4-case-state">{estadoGestionNombre[currentCase.estado_gestion||'sin_atender']}</span>:<CaseStatusSelect compact fichaId={currentCase.id} value={currentCase.estado_gestion||'sin_atender'} quote={{monto:currentCase.cotizacion_monto,moneda:currentCase.cotizacion_moneda}} onChanged={async()=>{await load();setNotice('Estado actualizado')}} onError={setError}/>}
     {currentCase.responsable?<span className="v5-chip"><UserCheck size={12}/> {ownerName(currentCase.responsable)}</span>:!readonly&&user?<button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={()=>void act(()=>api(`/api/fichas/${currentCase.id}/responsable`,{method:'POST',body:JSON.stringify({responsable:user.username})}),'Gestión asignada a vos')}><UserCheck size={14}/> Asignarme</button>:<span className="v5-chip">Sin asignar</span>}
     {currentCase.tipo_consulta!=='sin_clasificar'&&<span className="v5-chip">{tipoConsultaNombre[currentCase.tipo_consulta]}{currentCase.tipo_sugerido_ia?<> · <Sparkles size={11}/> IA</>:null}</span>}
     {currentCase.bajo_minimo&&<span className="v5-chip is-warning"><AlertTriangle size={11}/> Bajo mínimo</span>}
    </div>}
   </div>
   {selectedThread.mensaje_tras_cierre&&!readonly&&selectedThread.gestion&&<div className="v5-banner is-attention v5-chat-banner"><AlertTriangle size={16}/><span>Nuevo mensaje en una gestión cerrada ({selectedThread.gestion.codigo} · {estadoGestionNombre[selectedThread.gestion.estado_gestion]}).</span><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={()=>void act(()=>api(`/api/fichas/${selectedThread.gestion!.id}/estado`,{method:'POST',body:JSON.stringify({estado:'calificada'})}),'Gestión reabierta')}><RotateCcw size={14}/> Reabrir</button><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={()=>void newCaseForLatest()}><Plus size={14}/> Nueva gestión</button></div>}

   <div className="v4-chat-transcript" aria-label="Mensajes de la conversación">
    {sortedMessages.map((m,i)=><div className={`v4-chat-message-block ${isOut(m)?'is-outgoing':''}`} key={m.id}>
     {(i===0||messageDay(sortedMessages[i-1])!==messageDay(m))&&<div className="v4-chat-day">{messageDay(m)}</div>}
     <button type="button" aria-label={isOut(m)?'Respuesta registrada':`Seleccionar mensaje de ${m.canal}`} className={`v4-message-bubble ${isOut(m)?'is-outgoing':''} ${activeMessage?.id===m.id?'is-selected':''}`} onClick={()=>pick(m)}>
      <span className="v4-message-meta">{isOut(m)?<Send size={13}/>:m.canal==='Correo'?<Mail size={13}/>:<MessageCircle size={13}/>} {isOut(m)?`Respuesta registrada${m.usuario?` · ${ownerName(m.usuario)}`:''} · `:''}{m.canal==='Correo'?'Email':m.canal.replace(' (simulado)','')} · {new Date(m.recibido_el).toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit'})}</span>
      {m.asunto&&<strong className="v4-message-subject">{m.asunto}</strong>}
      <span className="v4-message-text">{m.texto}</span>
     </button>
    </div>)}
    {showDraft&&activeMessage&&<div className="v4-chat-draft" ref={draftRef}><span className="v4-draft-label"><CheckCheck size={14}/> Borrador · No enviado</span><textarea aria-label="Editar borrador de respuesta" rows={Math.max(4,Math.min(7,draft.split('\n').length+3))} value={draft} onChange={e=>setDraft(e.target.value)} onBlur={()=>{if(draft!==draftSaved&&!readonly)void saveDraft()}} disabled={readonly} placeholder="Escribí tu respuesta o usá IA para prepararla"/>
     {currentCase?.bajo_minimo&&!readonly&&<label className="v5-check"><input type="checkbox" checked={loteMinimo} disabled={busy} onChange={e=>{setLoteMinimo(e.target.checked);void generate('draft',true,e.target.checked)}}/> Informar lote mínimo ({unidades(currentCase.lote_minimo)}) en la respuesta</label>}
     <div className="v4-draft-actions"><small title="La respuesta actual está guardada. Podés editarla para guardar otra versión.">{generating==='draft'?'Preparando borrador…':draft===draftSaved?'Borrador guardado':'Cambios sin guardar'}</small><button type="button" className="btn btn-outline" onClick={()=>void navigator.clipboard.writeText(draft)} disabled={!draft}><ClipboardCopy size={15}/> Copiar</button>{!readonly&&draft!==draftSaved&&<button type="button" className="btn btn-outline" onClick={()=>void saveDraft()} disabled={busy}>Guardar</button>}{!readonly&&<button type="button" className="btn btn-outline" onClick={()=>void generate('draft',true)} disabled={busy}><Sparkles size={14}/> Regenerar</button>}</div>
     <div className="v4-send-footer"><div className="v3-switch" role="group" aria-label="Canal de envío"><button className={sendChannel==='WhatsApp'?'selected':''} type="button" onClick={()=>setSendChannel('WhatsApp')}>WhatsApp</button><button className={sendChannel==='Correo'?'selected':''} type="button" onClick={()=>setSendChannel('Correo')}>Email</button></div>{!readonly&&<button className="btn btn-primary" type="button" disabled={busy||!draft.trim()} onClick={()=>void copyAndRegister()}><Send size={14}/> Copiar y marcar como respondida</button>}<small>El envío directo todavía no está integrado: copiá la respuesta, enviala por {sendChannel==='Correo'?'email':'WhatsApp'} y queda registrada en el hilo.</small></div></div>}
   </div>

   {(showReport||generating==='report')&&<section className="v4-chat-report" aria-label="Informe de la consulta" ref={reportRef}>
    <div className="v3-section-line"><h3>Información de la consulta</h3><button type="button" className="v4-icon-action" onClick={()=>setShowReport(false)} aria-label="Cerrar informe"><X size={16}/></button></div>
    {generating==='report'&&!analysis?<p className="v5-loading" role="status">Generando informe con toda la conversación…</p>:analysis?<><div className="v4-report-fields"><div><small>Producto</small><strong>{currentCase?.producto||analysis.producto||'Sin definir'}</strong></div><div><small>Cantidad</small><strong>{unidades(currentCase?.cantidad??analysis.cantidad)||'Sin definir'}</strong></div>{currentCase&&<div><small>Tipo de servicio</small><strong>{tipoConsultaNombre[currentCase.tipo_consulta]}</strong></div>}</div>{analysis.resumen&&<p>{analysis.resumen}</p>}
     {!!analysis.requisitos?.length&&<div><h4>Requisitos</h4><ul>{analysis.requisitos.map((v,i)=><li key={i}>{v}</li>)}</ul></div>}
     {!!pendientes.length&&<div><h4>Datos a confirmar</h4><ul>{pendientes.map((v,i)=><li key={i}>{v}</li>)}</ul></div>}
     {!!extrasIA.length&&<div><h4>Otros puntos sugeridos por IA</h4><ul>{extrasIA.map((v,i)=><li key={i}>{v}</li>)}</ul></div>}
     <div className="v4-report-actions">{!readonly&&<button className="btn btn-outline" type="button" onClick={()=>void saveAnalysis()} disabled={busy||!activeCase}>Guardar en gestión</button>}{activeCase&&<button type="button" className="btn btn-outline" onClick={()=>setFormCase(activeCase)}>Editar detalles</button>}{!readonly&&<button type="button" className="btn btn-outline" onClick={()=>void generate('report',true)} disabled={busy}><Sparkles size={14}/> Regenerar</button>}</div></>:<p>Generá el informe para ver la información.</p>}
   </section>}

   {activeMessage&&<footer className="v4-chat-footer">
    <div className="v4-chat-primary-actions">
     <button type="button" className="btn btn-outline" aria-busy={generating==='report'} onClick={()=>{if(analysis)setShowReport(v=>!v);else void generate('report')}} disabled={busy}><FileText size={16}/> {generating==='report'?'Generando informe…':showReport?'Ocultar informe':'Informe'}</button>
     <button type="button" className="btn btn-primary" aria-busy={generating==='draft'} onClick={()=>{if(draft)setShowDraft(v=>!v);else void generate('draft')}} disabled={busy}><MessageCircle size={16}/> {generating==='draft'?'Preparando…':showDraft?'Ocultar borrador':'Preparar respuesta'}</button>
    </div>
    <div className="v4-more-wrap">
     <button className="v4-icon-action" type="button" aria-label="Más acciones de la conversación" aria-expanded={moreMenu} onClick={()=>{setMoreMenu(v=>!v);setCaseMenu(false)}}><MoreHorizontal size={21}/></button>
     {moreMenu&&<div className="v4-more-popover">
      <div className="v4-menu-heading">Conversación</div>
      {!readonly&&<button type="button" className="v4-menu-item" onClick={()=>{setMoreMenu(false);void markUnread()}} disabled={busy}><EyeOff size={16}/> Marcar como no leído</button>}
      <Link className="v4-menu-item" href={`/agenda?ficha=${activeCase||''}`}><CalendarDays size={16}/> Agendar actividad</Link>
      {activeCase&&<button type="button" className="v4-menu-item" onClick={()=>{setMoreMenu(false);setFormCase(activeCase)}}><FolderOpen size={16}/> Abrir gestión</button>}
      {activeCase&&!readonly&&currentCase?.tipo_consulta!=='no_comercial'&&!esCerrada(currentCase?.estado_gestion)&&<button type="button" className="v4-menu-item" onClick={()=>{setMoreMenu(false);if(window.confirm('¿Archivar como consulta no comercial? Queda resuelta y no cuenta en los indicadores de ventas.'))void act(()=>api(`/api/fichas/${activeCase}/no-comercial`,{method:'POST'}),'Archivada como no comercial')}}><Archive size={16}/> Archivar como no comercial</button>}
     </div>}
    </div>
   </footer>}
   {notice&&<div className="v4-toast" role="status"><Check size={15}/>{notice}<button type="button" onClick={()=>setNotice('')} aria-label="Cerrar aviso"><X size={13}/></button></div>}
  </div>
 </div>}
 {formCase&&<CaseDialog fichaId={formCase} onClose={()=>{setFormCase(null);void load()}} readOnly={readonly}/>}
 </Shell>;
}
