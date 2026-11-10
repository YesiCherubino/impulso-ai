'use client';
import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {Check,ChevronDown,ChevronRight,ClipboardCopy,FileText,Mail,MessageCircle,Plus,Search,Send,X,CalendarDays,MoreHorizontal,CheckCheck,FolderOpen} from 'lucide-react';
import Link from 'next/link';
import Shell from '@/components/shell';
import CaseDialog from '@/components/case-dialog';
import {api,ConsultaBandeja,ConsultaIA,FichaConsulta,UsuarioSesion} from '@/lib/api';

type Thread={key:string;cliente:string;contacto:string;mensajes:ConsultaBandeja[];ultimo:string;no_leidos:number};
const newBlank={cliente:'',contacto:'',canal:'WhatsApp',texto:'',email_remitente:'',telefono_remitente:'',asunto:''};
const dt=(s:string)=>new Date(s).toLocaleString('es-AR',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const filters=[['todos','Todos'],['WhatsApp','WhatsApp'],['Correo','Email'],['Formulario web','Formulario web']];
export default function BandejaConsultas(){
 const [threads,setThreads]=useState<Thread[]>([]),[cases,setCases]=useState<FichaConsulta[]>([]),[user,setUser]=useState<UsuarioSesion|null>(null),[selected,setSelected]=useState<string|null>(null),[messageId,setMessageId]=useState<number|null>(null);
 const [search,setSearch]=useState(''),[channel,setChannel]=useState('todos'),[filter,setFilter]=useState('todos'),[openNew,setOpenNew]=useState(false),[newForm,setNewForm]=useState(newBlank),[formCase,setFormCase]=useState<number|null>(null);
 const [analysis,setAnalysis]=useState<ConsultaIA|null>(null),[draft,setDraft]=useState(''),[draftSaved,setDraftSaved]=useState(''),[showReport,setShowReport]=useState(false),[showDraft,setShowDraft]=useState(false),[sendChannel,setSendChannel]=useState('WhatsApp');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[lastSync,setLastSync]=useState<Date|null>(null),[activeCase,setActiveCase]=useState<number|null>(null);
 const [caseMenu,setCaseMenu]=useState(false),[moreMenu,setMoreMenu]=useState(false),[creatingCase,setCreatingCase]=useState(false),[caseTitle,setCaseTitle]=useState('');
 const selectedThread=threads.find(t=>t.key===selected)||null;
 const activeMessage=selectedThread?.mensajes.find(m=>m.id===messageId)||selectedThread?.mensajes.at(-1)||null;
 const readonly=user?.role==='gerencia';
 const detailsRef=useRef<HTMLDivElement|null>(null);
 const load=useCallback(async()=>{try{const [t,f]=await Promise.all([api<Thread[]>('/api/inbox/threads'),api<FichaConsulta[]>('/api/fichas')]);setThreads(t);setCases(f);setLastSync(new Date());setError('')}catch(e){setError(e instanceof Error?e.message:'No se pudo sincronizar la bandeja')}},[]);
 useEffect(()=>{void load();void fetch('/api/session/me').then(r=>r.ok?r.json():null).then(setUser).catch(()=>{});const timer=setInterval(()=>{if(document.visibilityState==='visible')void load()},30000);const focused=()=>{if(document.visibilityState==='visible')void load()};document.addEventListener('visibilitychange',focused);return()=>{clearInterval(timer);document.removeEventListener('visibilitychange',focused)}},[load]);
 useEffect(()=>{if(!threads.length||selected)return;const id=Number(new URLSearchParams(window.location.search).get('consulta'));if(!id)return;const found=threads.find(t=>t.mensajes.some(m=>m.id===id));if(found)void openThread(found,id)},[threads,selected]);
 useEffect(()=>{if(!messageId)return;let valid=true;void api<{analisis:{resultado:ConsultaIA;borrador:string}|null}>(`/api/inbox/${messageId}/analysis`).then(r=>{if(valid){setAnalysis(r.analisis?.resultado||null);setDraft(r.analisis?.borrador||'');setDraftSaved(r.analisis?.borrador||'')}}).catch(()=>{});return()=>{valid=false}},[messageId]);
 const shown=useMemo(()=>threads.filter(t=>{const matchChannel=channel==='todos'||t.mensajes.some(m=>m.canal===channel||(channel==='WhatsApp'&&m.canal.startsWith('WhatsApp')));
   const matchState=filter==='todos'||(filter==='sin_leer'&&t.no_leidos>0)||(filter==='nueva'&&t.mensajes.some(m=>m.leido_en&&m.estado==='nueva'))||(filter==='en_gestion'&&t.mensajes.some(m=>m.estado==='en_gestion'));
   const term=search.toLowerCase();return matchChannel&&matchState&&[t.cliente,t.contacto,...t.mensajes.flatMap(m=>[m.texto,m.asunto,m.email_remitente])].some(s=>(s||'').toLowerCase().includes(term))}),[threads,search,channel,filter]);
 async function openThread(t:Thread,focusId?:number){setSelected(t.key);setCaseMenu(false);setMoreMenu(false);setCreatingCase(false);const id=focusId||t.mensajes.at(-1)?.id||null;setMessageId(id);setActiveCase(t.mensajes.find(m=>m.id===id)?.ficha_id||null);setShowReport(false);setShowDraft(false);setAnalysis(null);setNotice('');const unseen=t.mensajes.filter(m=>!m.leido_en);if(unseen.length&&!readonly){await Promise.all(unseen.map(m=>api(`/api/inbox/${m.id}/read`,{method:'POST',body:JSON.stringify({read:true})}).catch(()=>{})));await load()}}
 function pick(m:ConsultaBandeja){setCaseMenu(false);setMoreMenu(false);setMessageId(m.id);setActiveCase(m.ficha_id);setAnalysis(null);setShowReport(false);setShowDraft(false);setSendChannel(m.canal==='Correo'?'Correo':'WhatsApp')}
 async function state(value:string){if(!activeMessage||readonly)return;setBusy(true);try{if(value==='no_leido'){await api(`/api/inbox/${activeMessage.id}/read`,{method:'POST',body:JSON.stringify({read:false})});setSelected(null)}else{if(!activeMessage.leido_en)await api(`/api/inbox/${activeMessage.id}/read`,{method:'POST',body:JSON.stringify({read:true})});await api(`/api/inbox/${activeMessage.id}/status`,{method:'POST',body:JSON.stringify({estado:value})})}await load()}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function createNew(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');try{await api('/api/inbox/new',{method:'POST',body:JSON.stringify(newForm)});setNewForm(newBlank);setOpenNew(false);await load()}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function changeCase(id:number){if(!activeMessage)return;setBusy(true);try{await api(`/api/inbox/${activeMessage.id}/move`,{method:'POST',body:JSON.stringify({ficha_id:id})});setActiveCase(id);await load();setNotice('Gestión actualizada')}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function updateCaseStatus(value:string){if(!activeCase)return;setBusy(true);try{await api(`/api/fichas/${activeCase}/estado`,{method:'POST',body:JSON.stringify({estado:value})});await load();setNotice('Estado actualizado')}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function startNewCase(){if(!activeMessage||!caseTitle.trim())return;setBusy(true);try{const r=await api<{id:number;codigo:string}>(`/api/inbox/${activeMessage.id}/new-case`,{method:'POST',body:JSON.stringify({titulo:caseTitle.trim()})});await load();setActiveCase(r.id);setCreatingCase(false);setCaseTitle('');setCaseMenu(false);setNotice(`Gestión ${r.codigo} creada`)}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function generate(kind:'report'|'draft',regenerate=false){if(!activeMessage)return;setBusy(true);setError('');try{const r=await api<{resultado:ConsultaIA;borrador:string}>(`/api/inbox/${activeMessage.id}/analysis`,{method:'POST',body:JSON.stringify({regenerar:regenerate})});setAnalysis(r.resultado);setDraft(r.borrador);setDraftSaved(r.borrador);if(kind==='report')setShowReport(true);else setShowDraft(true)}catch(e){setError(e instanceof Error?e.message:'No se pudo generar')}finally{setBusy(false)}}
 async function saveAnalysis(){const c=cases.find(f=>f.id===activeCase);if(!analysis||!c)return;setBusy(true);try{await api(`/api/fichas/${c.id}/edit`,{method:'POST',body:JSON.stringify({titulo:c.titulo,cliente:c.cliente,contacto:c.contacto,producto:analysis.producto,cantidad:analysis.cantidad,tipo_consulta:analysis.tipo_consulta||'sin_clasificar',presentacion:analysis.presentacion||'',packaging:c.packaging,requisitos:analysis.requisitos,datos_faltantes:analysis.datos_faltantes,resumen:analysis.resumen})});await load();setNotice('Información guardada en la gestión')}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function saveDraft(){if(!activeMessage)return;setBusy(true);try{await api(`/api/inbox/${activeMessage.id}/draft`,{method:'POST',body:JSON.stringify({borrador:draft})});setDraftSaved(draft);setNotice('Borrador guardado')}catch(e){setError(String(e))}finally{setBusy(false)}}
 const related=cases.filter(c=>c.cliente===selectedThread?.cliente||c.oportunidad_id!=null&&c.oportunidad_id===cases.find(f=>f.id===activeMessage?.ficha_id)?.oportunidad_id);
 const currentCase=cases.find(c=>c.id===activeCase);
 const sortedMessages=[...(selectedThread?.mensajes||[])].sort((a,b)=>new Date(a.recibido_el).getTime()-new Date(b.recibido_el).getTime());
 const messageDay=(m:ConsultaBandeja)=>new Date(m.recibido_el).toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'short'});
 const closeThread=()=>{setSelected(null);setCaseMenu(false);setMoreMenu(false);setShowDraft(false);setShowReport(false)};
 return <Shell><div className="v2-page-head"><div><h1>Bandeja de consultas</h1></div><div className="v2-head-right"><span className="v2-sync">{lastSync?'Sincronizado':'Conectando'}</span>{!readonly&&<button className="btn btn-primary" onClick={()=>setOpenNew(true)}><Plus size={17}/> Nueva consulta</button>}</div></div>
 {error&&<p className="alert error" role="alert">{error}</p>}
 <section className="panel v2-inbox"><div className="v3-inbox-filters"><label className="search"><Search size={17}/><input placeholder="Buscar en conversaciones" value={search} onChange={e=>setSearch(e.target.value)}/></label><div className="v3-switch">{filters.map(([val,label])=><button key={val} className={channel===val?'selected':''} onClick={()=>setChannel(val)}>{label}</button>)}</div><select aria-label="Filtro de mensajes" value={filter} onChange={e=>setFilter(e.target.value)}><option value="todos">Todos los estados</option><option value="sin_leer">No leídos</option><option value="nueva">Sin atender</option><option value="en_gestion">En gestión</option></select></div>
 <div className="v3-conversations">{shown.map(t=><button key={t.key} className={`v3-conversation ${t.no_leidos?'is-unread':''}`} onClick={()=>void openThread(t)}><span className="v3-conversation-icon"><MessageCircle size={20}/></span><span className="v3-conversation-body"><span className="v3-conversation-top"><strong>{t.cliente}</strong><small>{dt(t.ultimo)}</small></span><small>{t.contacto} · {t.mensajes.length} mensaje{t.mensajes.length===1?'':'s'}</small><span>{t.mensajes.at(-1)?.texto}</span></span>{t.no_leidos>0&&<b className="v3-unread-count">{t.no_leidos}</b>}<ChevronRight size={17}/></button>)}{!shown.length&&<div className="v3-empty">No hay conversaciones para estos filtros.</div>}</div></section>
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
      <FolderOpen size={15} aria-hidden="true"/><span>{currentCase?`${currentCase.codigo} · ${currentCase.titulo||currentCase.producto}`:'Sin gestión asociada'}</span><ChevronDown size={15}/>
     </button>
     {caseMenu&&<div className="v4-case-popover">
      <div className="v4-menu-heading">Gestiones comerciales</div>
      {related.map(c=><button type="button" className={`v4-menu-item ${activeCase===c.id?'is-current':''}`} key={c.id} onClick={()=>{setCaseMenu(false);if(activeCase!==c.id)void changeCase(c.id)}} disabled={busy||readonly}>
       <span className="v4-menu-copy"><strong>{c.codigo}</strong><small>{c.titulo||c.producto}</small></span>{activeCase===c.id&&<Check size={15}/>}
      </button>)}
      {!readonly&&<>
       <div className="v4-menu-separator"/>
       {!creatingCase?<button type="button" className="v4-menu-item" onClick={()=>{setCreatingCase(true);setCaseTitle('')}}><Plus size={16}/> Nueva gestión</button>:<form className="v4-create-case" onSubmit={e=>{e.preventDefault();void startNewCase()}}><label htmlFor="v4-new-case">Nombre de la gestión</label><input id="v4-new-case" value={caseTitle} onChange={e=>setCaseTitle(e.target.value)} placeholder="Ej. Crema corporal" autoFocus required/><div className="v4-create-actions"><button type="button" className="btn btn-outline" onClick={()=>setCreatingCase(false)}>Cancelar</button><button type="submit" className="btn btn-primary" disabled={busy||!caseTitle.trim()}>Crear</button></div></form>}
      </>}
      {activeCase&&<button type="button" className="v4-menu-item" onClick={()=>{setCaseMenu(false);setFormCase(activeCase)}}><FileText size={16}/> Ver detalles de la gestión</button>}
     </div>}
    </div>
    {currentCase&&<span className="v4-case-state">{({sin_atender:'Sin atender',en_gestion:'En gestión',concretada:'Concretada',no_concretada:'No concretada',resuelta:'Resuelta'} as Record<string,string>)[currentCase.estado_gestion||'sin_atender']||'En gestión'}</span>}
   </div>

   <div className="v4-chat-transcript" aria-label="Mensajes de la conversación">
    {sortedMessages.map((m,i)=><div className="v4-chat-message-block" key={m.id}>
     {(i===0||messageDay(sortedMessages[i-1])!==messageDay(m))&&<div className="v4-chat-day">{messageDay(m)}</div>}
     <button type="button" aria-label={`Seleccionar mensaje de ${m.canal}`} className={`v4-message-bubble ${activeMessage?.id===m.id?'is-selected':''}`} onClick={()=>pick(m)}>
      <span className="v4-message-meta">{m.canal==='Correo'?<Mail size={13}/>:<MessageCircle size={13}/>} {m.canal==='Correo'?'Email':m.canal.replace(' (simulado)','')} · {new Date(m.recibido_el).toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit'})}</span>
      {m.asunto&&<strong className="v4-message-subject">{m.asunto}</strong>}
      <span className="v4-message-text">{m.texto}</span>
     </button>
    </div>)}
    {showDraft&&<div className="v4-chat-draft"><span className="v4-draft-label"><CheckCheck size={14}/> Borrador · No enviado</span><textarea aria-label="Editar borrador de respuesta" rows={Math.max(4,Math.min(7,draft.split('\n').length+3))} value={draft} onChange={e=>setDraft(e.target.value)} onBlur={()=>{if(draft!==draftSaved&&!readonly)void saveDraft()}} disabled={readonly} placeholder="Escribí o generá una respuesta"/><div className="v4-draft-actions"><small title="La respuesta actual está guardada. Podés editarla para guardar otra versión.">{draft===draftSaved?'Borrador guardado':'Cambios sin guardar'}</small><button type="button" className="btn btn-outline" onClick={()=>void navigator.clipboard.writeText(draft)} disabled={!draft}><ClipboardCopy size={15}/> Copiar</button>{!readonly&&draft!==draftSaved&&<button type="button" className="btn btn-outline" onClick={()=>void saveDraft()} disabled={busy}>Guardar</button>}</div><div className="v4-send-footer"><div className="v3-switch" role="group" aria-label="Canal de envío"><button className={sendChannel==='WhatsApp'?'selected':''} type="button" onClick={()=>setSendChannel('WhatsApp')}>WhatsApp</button><button className={sendChannel==='Correo'?'selected':''} type="button" onClick={()=>setSendChannel('Correo')}>Email</button></div><button className="btn btn-outline" type="button" disabled title="Integración pendiente"><Send size={14}/> Enviar</button><small>Envío pendiente de integración</small></div></div>}
   </div>

   {showReport&&<section className="v4-chat-report" aria-label="Informe de la consulta">
    <div className="v3-section-line"><h3>Información de la consulta</h3><button type="button" className="v4-icon-action" onClick={()=>setShowReport(false)} aria-label="Cerrar informe"><X size={16}/></button></div>
    {analysis?<><div className="v4-report-fields"><div><small>Producto</small><strong>{analysis.producto||'Sin definir'}</strong></div><div><small>Cantidad</small><strong>{analysis.cantidad??'Sin definir'}</strong></div></div>{analysis.resumen&&<p>{analysis.resumen}</p>}
     {!!analysis.requisitos?.length&&<div><h4>Requisitos</h4><ul>{analysis.requisitos.map((v,i)=><li key={i}>{v}</li>)}</ul></div>}
     {!!analysis.datos_faltantes?.length&&<div><h4>Datos a confirmar</h4><ul>{analysis.datos_faltantes.map((v,i)=><li key={i}>{v}</li>)}</ul></div>}
     <div className="v4-report-actions">{!readonly&&<button className="btn btn-outline" type="button" onClick={()=>void saveAnalysis()} disabled={busy||!activeCase}>Guardar en gestión</button>}{activeCase&&<button type="button" className="btn btn-outline" onClick={()=>setFormCase(activeCase)}>Editar detalles</button>}</div></>:<p>Generá el informe para ver la información.</p>}
   </section>}

   {activeMessage&&<footer className="v4-chat-footer">
    <div className="v4-chat-primary-actions">
     <button type="button" className="btn btn-outline" onClick={()=>{if(analysis)setShowReport(v=>!v);else void generate('report')}} disabled={busy}><FileText size={16}/> {showReport?'Ocultar informe':'Informe'}</button>
     <button type="button" className="btn btn-primary" onClick={()=>{if(draft)setShowDraft(v=>!v);else void generate('draft')}} disabled={busy}><MessageCircle size={16}/> {showDraft?'Ocultar borrador':'Preparar respuesta'}</button>
    </div>
    <div className="v4-more-wrap">
     <button className="v4-icon-action" type="button" aria-label="Más acciones de la conversación" aria-expanded={moreMenu} onClick={()=>{setMoreMenu(v=>!v);setCaseMenu(false)}}><MoreHorizontal size={21}/></button>
     {moreMenu&&<div className="v4-more-popover">
      <div className="v4-menu-heading">Mensaje seleccionado</div>
      {!readonly&&<label className="v4-menu-select">Estado del mensaje<select value={!activeMessage.leido_en?'no_leido':activeMessage.estado} onChange={e=>{setMoreMenu(false);void state(e.target.value)}} disabled={busy}><option value="no_leido">No leído</option><option value="nueva">Sin atender</option><option value="en_gestion">En gestión</option><option value="resuelta">Resuelta</option></select></label>}
      {currentCase&&!readonly&&<label className="v4-menu-select">Estado de la gestión<select value={currentCase.estado_gestion||'sin_atender'} onChange={e=>{setMoreMenu(false);void updateCaseStatus(e.target.value)}} disabled={busy}><option value="sin_atender">Sin atender</option><option value="en_gestion">En gestión</option><option value="concretada">Concretada</option><option value="no_concretada">No concretada</option><option value="resuelta">Resuelta</option></select></label>}
      <Link className="v4-menu-item" href={`/agenda?ficha=${activeCase||''}`}><CalendarDays size={16}/> Agendar actividad</Link>
      {activeCase&&<button type="button" className="v4-menu-item" onClick={()=>{setMoreMenu(false);setFormCase(activeCase)}}><FolderOpen size={16}/> Abrir gestión</button>}
     </div>}
    </div>
   </footer>}
   {notice&&<div className="v4-toast" role="status"><Check size={15}/>{notice}<button type="button" onClick={()=>setNotice('')} aria-label="Cerrar aviso"><X size={13}/></button></div>}
  </div>
 </div>}
 {formCase&&<CaseDialog fichaId={formCase} onClose={()=>{setFormCase(null);void load()}} readOnly={readonly}/>}
 </Shell>;
}
