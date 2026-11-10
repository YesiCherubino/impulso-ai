'use client';
import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {Check,ChevronDown,ChevronRight,FileText,Mail,MessageCircle,Plus,Search,X,CalendarDays,MoreHorizontal,FolderOpen,Send,AlertTriangle,UserCheck,Archive,RotateCcw,Sparkles,Clock3,EyeOff,History,Loader2} from 'lucide-react';
import Link from 'next/link';
import Shell from '@/components/shell';
import CaseDialog from '@/components/case-dialog';
import CaseStatusSelect from '@/components/case-status';
import {api,qs,ConsultaBandeja,ConsultaIA,Conversacion,ConversacionDetalle,Pagina,Responsable,UsuarioSesion,estadoGestionNombre,tipoConsultaNombre,tiposConsulta,tiempoSinRespuesta,unidades,esCerrada} from '@/lib/api';

const PAGE=50;
const newBlank={cliente:'',contacto:'',canal:'WhatsApp',texto:'',email_remitente:'',telefono_remitente:'',asunto:''};
const dt=(s:string)=>new Date(s).toLocaleString('es-AR',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const filters=[['todos','Todos'],['WhatsApp','WhatsApp'],['Correo','Email'],['Formulario web','Formulario web']];
const isOut=(m:ConsultaBandeja)=>m.direccion==='saliente';
const lowPriority=(t:Conversacion)=>!!t.gestion&&(t.gestion.bajo_minimo||t.gestion.tipo_consulta==='no_comercial');
export default function BandejaConsultas(){
 const [items,setItems]=useState<Conversacion[]>([]),[total,setTotal]=useState(0),[listLoading,setListLoading]=useState(true),[moreLoading,setMoreLoading]=useState(false);
 const [user,setUser]=useState<UsuarioSesion|null>(null),[owners,setOwners]=useState<Responsable[]>([]),[ready,setReady]=useState(false);
 const [selected,setSelected]=useState<string|null>(null),[detail,setDetail]=useState<ConversacionDetalle|null>(null),[messageId,setMessageId]=useState<number|null>(null),[olderLoading,setOlderLoading]=useState(false);
 const [search,setSearch]=useState(''),[query,setQuery]=useState(''),[channel,setChannel]=useState('todos'),[filter,setFilter]=useState('abiertas'),[ownerFilter,setOwnerFilter]=useState('todos'),[typeFilter,setTypeFilter]=useState('todos'),[order,setOrder]=useState<'reciente'|'prioridad'>('reciente');
 const [openNew,setOpenNew]=useState(false),[newForm,setNewForm]=useState(newBlank),[formCase,setFormCase]=useState<number|null>(null);
 const [analysis,setAnalysis]=useState<ConsultaIA|null>(null),[draft,setDraft]=useState(''),[draftSaved,setDraftSaved]=useState(''),[showReport,setShowReport]=useState(false),[sendChannel,setSendChannel]=useState<'WhatsApp'|'Correo'>('WhatsApp'),[loteMinimo,setLoteMinimo]=useState(false),[aiMenu,setAiMenu]=useState(false);
 const [busy,setBusy]=useState(false),[generating,setGenerating]=useState<''|'report'|'draft'>(''),[error,setError]=useState(''),[notice,setNotice]=useState(''),[lastSync,setLastSync]=useState<Date|null>(null),[activeCase,setActiveCase]=useState<number|null>(null);
 const [caseMenu,setCaseMenu]=useState(false),[moreMenu,setMoreMenu]=useState(false);
 const readonly=user?.role==='gerencia';
 const reportRef=useRef<HTMLElement|null>(null),transcriptRef=useRef<HTMLDivElement|null>(null),composerRef=useRef<HTMLTextAreaElement|null>(null);
 const activeMessageIdRef=useRef<number|null>(null),loadedRef=useRef(PAGE),selectedRef=useRef<string|null>(null);
 selectedRef.current=selected;
 const caseMessages=(detail?.mensajes||[]).filter(m=>activeCase===null||m.ficha_id===activeCase);
 const incomingMessages=caseMessages.filter(m=>!isOut(m));
 const activeMessage=incomingMessages.find(m=>m.id===messageId)||incomingMessages.at(-1)||null;
 activeMessageIdRef.current=activeMessage?.id??null;
 const cases=detail?.fichas||[];
 const currentCase=cases.find(c=>c.id===activeCase);
 const params=useMemo(()=>({estado:filter,canal:channel,responsable:ownerFilter,tipo:typeFilter,q:query,orden:order}),[filter,channel,ownerFilter,typeFilter,query,order]);

 // Listado paginado: el servidor filtra y ordena; el navegador solo recibe la página visible.
 const loadList=useCallback(async(mode:'reset'|'refresh'='reset')=>{
  const limit=mode==='refresh'?Math.min(200,Math.max(PAGE,loadedRef.current)):PAGE;
  if(mode==='reset')setListLoading(true);
  try{const page=await api<Pagina<Conversacion>>(`/api/inbox/conversations?${qs({...params,limit,offset:0})}`);setItems(page.items);setTotal(page.total);if(mode==='reset')loadedRef.current=PAGE;setLastSync(new Date());setError('')}
  catch(e){setError(e instanceof Error?e.message:'No se pudo sincronizar la bandeja')}finally{setListLoading(false)}
 },[params]);
 async function loadMore(){setMoreLoading(true);try{const page=await api<Pagina<Conversacion>>(`/api/inbox/conversations?${qs({...params,limit:PAGE,offset:items.length})}`);setItems(old=>[...old,...page.items.filter(n=>!old.some(o=>o.key===n.key))]);setTotal(page.total);loadedRef.current=items.length+page.items.length}catch(e){setError(String(e))}finally{setMoreLoading(false)}}
 const loadDetail=useCallback(async(key:string)=>{const d=await api<ConversacionDetalle>(`/api/inbox/conversations/${key}`);if(selectedRef.current===key)setDetail(d);return d},[]);
 const refreshAll=useCallback(async()=>{await loadList('refresh');if(selectedRef.current)await loadDetail(selectedRef.current).catch(()=>{})},[loadList,loadDetail]);

 useEffect(()=>{void fetch('/api/session/me').then(r=>r.ok?r.json():null).then((u:UsuarioSesion|null)=>{setUser(u);if(u?.role==='ventas')setOwnerFilter('mias_y_libres')}).catch(()=>{}).finally(()=>setReady(true));void api<Responsable[]>('/api/users/responsables').then(setOwners).catch(()=>{})},[]);
 useEffect(()=>{const t=setTimeout(()=>setQuery(search.trim()),300);return()=>clearTimeout(t)},[search]);
 useEffect(()=>{if(ready)void loadList('reset')},[ready,loadList]);
 useEffect(()=>{const timer=setInterval(()=>{if(document.visibilityState==='visible')void loadList('refresh')},30000);const focused=()=>{if(document.visibilityState==='visible')void loadList('refresh')};document.addEventListener('visibilitychange',focused);return()=>{clearInterval(timer);document.removeEventListener('visibilitychange',focused)}},[loadList]);
 // Abrir desde notificaciones, alertas de Reportes o enlaces (?consulta=ID de mensaje o ?conversacion=clave).
 useEffect(()=>{
  const p=new URLSearchParams(window.location.search);
  const queued=window.sessionStorage.getItem('impulso:pending-consulta');
  const messageParam=Number(queued||p.get('consulta'));const convParam=p.get('conversacion');
  if(!messageParam&&!convParam)return;
  window.sessionStorage.removeItem('impulso:pending-consulta');
  p.delete('consulta');p.delete('conversacion');window.history.replaceState(window.history.state,'',window.location.pathname+(p.toString()?'?'+p.toString():''));
  if(convParam)void openConversation(convParam);
  else void api<{key:string}>(`/api/inbox/${messageParam}/conversation`).then(r=>openConversation(r.key,messageParam)).catch(()=>setError('No se encontró la conversación'));
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[]);
 useEffect(()=>{const onOpen=(event:Event)=>{const id=Number((event as CustomEvent<number>).detail);window.sessionStorage.removeItem('impulso:pending-consulta');void api<{key:string}>(`/api/inbox/${id}/conversation`).then(r=>openConversation(r.key,id)).catch(()=>{})};window.addEventListener('impulso:open-consulta',onOpen);return()=>window.removeEventListener('impulso:open-consulta',onOpen)
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[]);
 useEffect(()=>{if(!selected)return;const onKey=(event:KeyboardEvent)=>{if(event.key!=='Escape')return;if(caseMenu||moreMenu||aiMenu){setCaseMenu(false);setMoreMenu(false);setAiMenu(false)}else closeThread()};window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey)
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[selected,caseMenu,moreMenu,aiMenu]);
 // Borrador e informe guardados del mensaje que se está respondiendo.
 useEffect(()=>{
  if(!activeMessage){setAnalysis(null);setDraft('');setDraftSaved('');return;}
  let valid=true;const id=activeMessage.id;
  setAnalysis(null);setDraft('');setDraftSaved('');
  void api<{analisis:{resultado:ConsultaIA|null;borrador:string}|null}>(`/api/inbox/${id}/analysis`).then(r=>{if(valid){setAnalysis(r.analisis?.resultado||null);setDraft(r.analisis?.borrador||'');setDraftSaved(r.analisis?.borrador||'')}}).catch(()=>{});
  return()=>{valid=false};
 },[activeMessage?.id]);
 // Guardado automático del borrador mientras se escribe.
 useEffect(()=>{if(!activeMessage||readonly||draft===draftSaved)return;const t=setTimeout(()=>void saveDraft(true),1200);return()=>clearTimeout(t)
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[draft]);
 useEffect(()=>{const el=composerRef.current;if(!el)return;el.style.height='auto';el.style.height=`${Math.min(220,Math.max(44,el.scrollHeight))}px`},[draft,selected]);
 useEffect(()=>{if(showReport)reportRef.current?.scrollIntoView({behavior:'smooth',block:'nearest'})},[showReport]);
 useEffect(()=>{if(detail&&!olderLoading)transcriptRef.current?.scrollTo({top:transcriptRef.current.scrollHeight})
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[detail?.key,detail?.mensajes.length,activeCase]);

 async function openConversation(key:string,focusId?:number){
  setSelected(key);selectedRef.current=key;setDetail(null);setCaseMenu(false);setMoreMenu(false);setAiMenu(false);setShowReport(false);setAnalysis(null);setNotice('');setLoteMinimo(false);
  try{
   const d=await loadDetail(key);
   const incoming=d.mensajes.filter(m=>!isOut(m));
   const id=focusId&&d.mensajes.some(m=>m.id===focusId)?focusId:incoming.at(-1)?.id||null;
   setMessageId(id);
   const focus=d.mensajes.find(m=>m.id===id);
   setActiveCase(focus?.ficha_id||d.gestion?.id||null);
   setSendChannel(focus?.canal==='Correo'?'Correo':'WhatsApp');
   if(d.no_leidos>0&&!readonly){await api(`/api/inbox/conversations/${key}/read`,{method:'POST'});setItems(old=>old.map(i=>i.key===key?{...i,no_leidos:0}:i))}
  }catch(e){setError(e instanceof Error?e.message:'No se pudo abrir la conversación')}
 }
 async function loadOlder(){if(!detail||!detail.mensajes.length)return;setOlderLoading(true);const box=transcriptRef.current;const before=box?.scrollHeight||0;try{const older=await api<ConversacionDetalle>(`/api/inbox/conversations/${detail.key}?${qs({antes_de:detail.mensajes[0].recibido_el})}`);setDetail(d=>d?{...d,mensajes:[...older.mensajes,...d.mensajes],hay_anteriores:older.hay_anteriores}:d);requestAnimationFrame(()=>{if(box)box.scrollTop=box.scrollHeight-before})}catch(e){setError(String(e))}finally{setOlderLoading(false)}}
 function pick(m:ConsultaBandeja){if(isOut(m))return;setCaseMenu(false);setMoreMenu(false);setMessageId(m.id);setAnalysis(null);setShowReport(false);setSendChannel(m.canal==='Correo'?'Correo':'WhatsApp')}
 async function markUnread(){if(!activeMessage||readonly)return;setBusy(true);try{await api(`/api/inbox/${activeMessage.id}/read`,{method:'POST',body:JSON.stringify({read:false})});setSelected(null);setDetail(null);await loadList('refresh')}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function createNew(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');try{await api('/api/inbox/new',{method:'POST',body:JSON.stringify(newForm)});setNewForm(newBlank);setOpenNew(false);await loadList('reset')}catch(e){setError(String(e))}finally{setBusy(false)}}
 function changeCase(id:number|null){setCaseMenu(false);setMoreMenu(false);setActiveCase(id);setMessageId((detail?.mensajes||[]).filter(m=>!isOut(m)&&(id===null||m.ficha_id===id)).at(-1)?.id||null);setShowReport(false);setAnalysis(null);setNotice('')}
 async function act(action:()=>Promise<unknown>,ok:string){setBusy(true);setError('');try{await action();await refreshAll();setNotice(ok)}catch(e){setError(e instanceof Error?e.message:'No se pudo completar la acción')}finally{setBusy(false)}}
 async function generate(kind:'report'|'draft',regenerate=false,lote=loteMinimo){if(!activeMessage)return;const target=activeMessage.id;setBusy(true);setGenerating(kind);setError('');try{const r=await api<{resultado:ConsultaIA;borrador:string}>(`/api/inbox/${target}/analysis`,{method:'POST',body:JSON.stringify({regenerar:regenerate,informar_lote_minimo:lote})});if(activeMessageIdRef.current!==target)return;setAnalysis(r.resultado);if(kind==='draft'){setDraft(r.borrador);setDraftSaved(r.borrador);composerRef.current?.focus()}if(selectedRef.current)await loadDetail(selectedRef.current);if(kind==='report')setShowReport(true)}catch(e){if(activeMessageIdRef.current===target)setError(e instanceof Error?e.message:'No se pudo generar')}finally{setBusy(false);setGenerating('')}}
 // La IA es una ayuda opcional: si ya hay texto escrito, se pregunta antes de reemplazarlo.
 function suggestWithAI(lote=loteMinimo){setAiMenu(false);if(draft.trim()&&draft!==draftSaved&&!window.confirm('¿Reemplazar lo que escribiste por la respuesta sugerida por la IA?'))return;if(draft.trim()&&draft===draftSaved&&analysis&&!window.confirm('¿Reemplazar el borrador actual por una nueva sugerencia de la IA?'))return;void generate('draft',!!analysis,lote)}
 async function saveAnalysis(){if(!analysis||!currentCase)return;const c=currentCase;setBusy(true);try{await api(`/api/fichas/${c.id}/edit`,{method:'POST',body:JSON.stringify({titulo:c.titulo,cliente:c.cliente,contacto:c.contacto,producto:c.producto||analysis.producto,cantidad:c.cantidad??analysis.cantidad,tipo_consulta:c.tipo_consulta!=='sin_clasificar'?c.tipo_consulta:(analysis.tipo_consulta||'sin_clasificar'),presentacion:c.presentacion||analysis.presentacion||'',packaging:c.packaging,requisitos:analysis.requisitos,datos_faltantes:analysis.datos_faltantes,resumen:analysis.resumen,origen:'ia'})});await refreshAll();setNotice('Información guardada en la gestión')}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function saveDraft(silent=false){if(!activeMessage)return;const target=activeMessage.id;const snapshot=draft;try{await api(`/api/inbox/${target}/draft`,{method:'POST',body:JSON.stringify({borrador:snapshot})});if(activeMessageIdRef.current===target){setDraftSaved(snapshot);if(!silent)setNotice('Borrador guardado')}}catch(e){if(activeMessageIdRef.current===target)setError(String(e))}}
 async function copyAndRegister(){if(!activeMessage||!draft.trim()||busy)return;const text=draft;try{await navigator.clipboard.writeText(text)}catch{/* Si el navegador no permite copiar, igual se registra la respuesta. */}
  await act(async()=>{await api(`/api/inbox/${activeMessage.id}/reply`,{method:'POST',body:JSON.stringify({texto:text,canal:sendChannel})});await api(`/api/inbox/${activeMessage.id}/draft`,{method:'POST',body:JSON.stringify({borrador:''})}).catch(()=>{});setDraft('');setDraftSaved('')},`Copiado y registrado. Pegalo en ${sendChannel==='Correo'?'el correo':'WhatsApp'} para enviarlo.`)}
 async function newCaseForLatest(){const g=detail?.gestion;if(!detail||!g)return;const closedAt=g.cerrada_en?new Date(g.cerrada_en).getTime():0;const after=detail.mensajes.filter(m=>!isOut(m)&&m.ficha_id===g.id&&new Date(m.recibido_el).getTime()>closedAt);const first=after[0]||detail.mensajes.filter(m=>!isOut(m)).at(-1);if(!first)return;
  await act(async()=>{const c=await api<{id:number}>(`/api/inbox/${first.id}/new-case`,{method:'POST',body:JSON.stringify({titulo:`Nueva consulta de ${detail.cliente}`})});for(const m of after)await api(`/api/inbox/${m.id}/move`,{method:'POST',body:JSON.stringify({ficha_id:c.id})});setActiveCase(c.id)},'Nueva gestión creada con los mensajes posteriores al cierre')}
 const sortedMessages=[...caseMessages].sort((a,b)=>new Date(a.recibido_el).getTime()-new Date(b.recibido_el).getTime());
 const messageDay=(m:ConsultaBandeja)=>new Date(m.recibido_el).toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'short'});
 function closeThread(){if(draft!==draftSaved&&activeMessage&&!readonly)void saveDraft(true);setSelected(null);setDetail(null);setCaseMenu(false);setMoreMenu(false);setAiMenu(false);setShowReport(false);void loadList('refresh')}
 const ownerName=(u?:string)=>owners.find(o=>o.username===u)?.name||u||'';
 const pendientes=currentCase?.datos_a_confirmar||analysis?.datos_a_confirmar||[];
 const extrasIA=(analysis?.datos_faltantes||[]).filter(x=>!pendientes.some(p=>p.toLowerCase()===x.toLowerCase()));
 const canalTexto=sendChannel==='Correo'?'email':'WhatsApp';
 return <Shell><div className="v2-page-head"><div><h1>Bandeja de consultas</h1></div><div className="v2-head-right"><span className="v2-sync">{lastSync?'Sincronizado':'Conectando'}</span>{!readonly&&<button className="btn btn-primary" onClick={()=>setOpenNew(true)}><Plus size={17}/> Nueva consulta</button>}</div></div>
 {error&&<p className="alert error" role="alert">{error}</p>}
 <section className="panel v2-inbox"><div className="v3-inbox-filters"><label className="search"><Search size={17}/><input placeholder="Buscar en conversaciones" value={search} onChange={e=>setSearch(e.target.value)}/></label><div className="v3-switch">{filters.map(([val,label])=><button key={val} className={channel===val?'selected':''} onClick={()=>setChannel(val)}>{label}</button>)}</div>
  <div className="v5-filter-row">
   <select aria-label="Filtro por estado" value={filter} onChange={e=>setFilter(e.target.value)}><option value="abiertas">Abiertas</option><option value="sin_leer">No leídas</option><option value="sin_atender">Sin atender</option><option value="sin_responder">Sin responder</option><option value="cerradas">Cerradas</option><option value="todas">Todas</option></select>
   <select aria-label="Filtro por responsable" value={ownerFilter} onChange={e=>setOwnerFilter(e.target.value)}><option value="todos">Todos los responsables</option>{user&&<option value="mias">Mis consultas</option>}{user&&<option value="mias_y_libres">Mis consultas y sin asignar</option>}<option value="sin_asignar">Sin asignar</option>{owners.filter(o=>o.username!==user?.username).map(o=><option key={o.username} value={`u:${o.username}`}>{o.name}</option>)}</select>
   <select aria-label="Filtro por tipo de servicio" value={typeFilter} onChange={e=>setTypeFilter(e.target.value)}><option value="todos">Todos los servicios</option>{tiposConsulta.map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>
   <select aria-label="Orden" value={order} onChange={e=>setOrder(e.target.value as 'reciente'|'prioridad')}><option value="reciente">Más reciente</option><option value="prioridad">Prioridad</option></select>
  </div></div>
 <div className="v5-list-meta" aria-live="polite">{listLoading?'Cargando…':`${total.toLocaleString('es-AR')} conversaci${total===1?'ón':'ones'}${items.length<total?` · mostrando ${items.length.toLocaleString('es-AR')}`:''}`}</div>
 <div className="v3-conversations">{items.map(t=>{const g=t.gestion;return <button key={t.key} className={`v3-conversation ${t.no_leidos?'is-unread':''} ${lowPriority(t)?'is-low':''}`} onClick={()=>void openConversation(t.key)}><span className="v3-conversation-icon"><MessageCircle size={20}/></span><span className="v3-conversation-body"><span className="v3-conversation-top"><strong>{t.cliente}</strong><small>{dt(t.ultimo)}</small></span><small>{t.contacto} · {t.mensajes_count} mensaje{t.mensajes_count===1?'':'s'}{g?` · ${g.codigo}`:''}</small>
   {g&&<span className="v5-chips"><span className={`v5-chip is-state is-${g.estado_gestion}`}>{estadoGestionNombre[g.estado_gestion]||g.estado_gestion}</span>{g.tipo_consulta!=='sin_clasificar'&&<span className="v5-chip">{tipoConsultaNombre[g.tipo_consulta]}{g.tipo_sugerido_ia?' · IA':''}</span>}{g.cantidad!=null&&<span className="v5-chip">{unidades(g.cantidad)}</span>}<span className="v5-chip">{g.responsable?ownerName(g.responsable):'Sin asignar'}</span>{g.bajo_minimo&&<span className="v5-chip is-warning">Bajo mínimo</span>}{t.respuesta.pendiente&&<span className={`v5-chip ${t.respuesta.horas>=24?'is-danger':'is-attention'}`}><Clock3 size={11}/> Sin responder {tiempoSinRespuesta(t.respuesta.horas)}</span>}{t.mensaje_tras_cierre&&<span className="v5-chip is-attention">Nuevo mensaje en gestión cerrada</span>}</span>}
   <span>{t.ultimo_saliente?'Vos: ':''}{t.ultimo_texto}</span></span>{t.no_leidos>0&&<b className="v3-unread-count">{t.no_leidos}</b>}<ChevronRight size={17}/></button>})}
  {!listLoading&&!items.length&&<div className="v3-empty">No hay conversaciones para estos filtros.</div>}
  {items.length<total&&<button type="button" className="btn btn-outline v5-load-more" onClick={()=>void loadMore()} disabled={moreLoading}>{moreLoading?<><Loader2 size={15} className="v5-spin"/> Cargando…</>:`Cargar ${Math.min(PAGE,total-items.length)} más`}</button>}
 </div></section>
 {openNew&&<div className="modal-backdrop v2-overlay" onMouseDown={()=>setOpenNew(false)}><div className="modal v2-modal" role="dialog" aria-modal="true" aria-label="Nueva consulta" onMouseDown={e=>e.stopPropagation()}><div className="modal-head"><h2>Nueva consulta</h2><button aria-label="Cerrar" className="icon-button" onClick={()=>setOpenNew(false)}><X/></button></div><form className="fields" onSubmit={createNew}><div className="form-row"><label>Empresa<input required value={newForm.cliente} onChange={e=>setNewForm({...newForm,cliente:e.target.value})}/></label><label>Nombre de contacto<input required value={newForm.contacto} onChange={e=>setNewForm({...newForm,contacto:e.target.value})}/></label></div><label>Origen<select value={newForm.canal} onChange={e=>setNewForm({...newForm,canal:e.target.value})}><option>WhatsApp</option><option value="Correo">Email</option><option>Formulario web</option><option>Manual</option></select></label><div className="form-row"><label>Email<input type="email" value={newForm.email_remitente} onChange={e=>setNewForm({...newForm,email_remitente:e.target.value})}/></label><label>Teléfono<input value={newForm.telefono_remitente} onChange={e=>setNewForm({...newForm,telefono_remitente:e.target.value})}/></label></div><label>Asunto (si corresponde)<input value={newForm.asunto} onChange={e=>setNewForm({...newForm,asunto:e.target.value})}/></label><label>Mensaje<textarea required minLength={5} rows={5} value={newForm.texto} onChange={e=>setNewForm({...newForm,texto:e.target.value})}/></label><button className="btn btn-primary" disabled={busy}>Guardar mensaje</button></form></div></div>}
 {selected&&<div className="modal-backdrop v2-overlay" onMouseDown={closeThread}>
  <div className="v3-thread-modal v4-chat-modal" role="dialog" aria-modal="true" aria-label={`Conversación con ${detail?.cliente||''}`} onMouseDown={e=>e.stopPropagation()}>
   <header className="v4-chat-header">
    <span className="v4-chat-avatar" aria-hidden="true">{(detail?.cliente||'·').charAt(0).toUpperCase()}</span>
    <div className="v4-chat-person"><h2>{detail?.cliente||'Cargando…'}</h2><small>{detail?`${detail.contacto} · ${detail.mensajes_count} mensaje${detail.mensajes_count!==1?'s':''}`:''}</small></div>
    {detail&&activeMessage&&<button type="button" className="btn btn-outline btn-sm" aria-label="Informe de la consulta" aria-busy={generating==='report'} onClick={()=>{if(analysis)setShowReport(v=>!v);else void generate('report')}} disabled={busy}><FileText size={15}/> <span className="v5-hide-mobile">{generating==='report'?'Generando…':showReport?'Ocultar informe':'Informe'}</span></button>}
    {detail&&<div className="v4-more-wrap">
     <button className="v4-icon-action" type="button" aria-label="Más acciones de la conversación" aria-expanded={moreMenu} onClick={()=>{setMoreMenu(v=>!v);setCaseMenu(false);setAiMenu(false)}}><MoreHorizontal size={21}/></button>
     {moreMenu&&<div className="v4-more-popover v5-popover-down">
      <div className="v4-menu-heading">Conversación</div>
      {!readonly&&activeMessage&&<button type="button" className="v4-menu-item" onClick={()=>{setMoreMenu(false);void markUnread()}} disabled={busy}><EyeOff size={16}/> Marcar como no leído</button>}
      <Link className="v4-menu-item" href={`/agenda?ficha=${activeCase||''}`}><CalendarDays size={16}/> Agendar actividad</Link>
      {activeCase&&<button type="button" className="v4-menu-item" onClick={()=>{setMoreMenu(false);setFormCase(activeCase)}}><FolderOpen size={16}/> Abrir gestión</button>}
      {activeCase&&!readonly&&currentCase?.tipo_consulta!=='no_comercial'&&!esCerrada(currentCase?.estado_gestion)&&<button type="button" className="v4-menu-item" onClick={()=>{setMoreMenu(false);if(window.confirm('¿Archivar como consulta no comercial? Queda resuelta y no cuenta en los indicadores de ventas.'))void act(()=>api(`/api/fichas/${activeCase}/no-comercial`,{method:'POST'}),'Archivada como no comercial')}}><Archive size={16}/> Archivar como no comercial</button>}
     </div>}
    </div>}
    <button className="v4-icon-action" type="button" aria-label="Cerrar conversación" onClick={closeThread}><X size={19}/></button>
   </header>
   {!detail?<div className="v4-chat-transcript v5-center"><Loader2 className="v5-spin"/> Cargando conversación…</div>:<>
   <div className="v4-chat-context">
    <div className="v4-case-selector-wrap">
     <button className="v4-case-trigger" type="button" aria-expanded={caseMenu} onClick={()=>{setCaseMenu(v=>!v);setMoreMenu(false)}}>
      <FolderOpen size={15} aria-hidden="true"/><span>{activeCase===null?'Todos los mensajes':currentCase?`${currentCase.codigo} · ${currentCase.titulo||currentCase.producto}`:'Sin gestión asociada'}</span><ChevronDown size={15}/>
     </button>
      {caseMenu&&<div className="v4-case-popover" role="menu" aria-label="Ver mensajes por gestión">
       <button type="button" role="menuitem" className={`v4-menu-item ${activeCase===null?'is-current':''}`} onClick={()=>changeCase(null)}><span className="v4-menu-copy"><strong>Todos los mensajes</strong></span>{activeCase===null&&<Check size={15}/>}</button>
       {cases.map(c=><button type="button" role="menuitem" className={`v4-menu-item ${activeCase===c.id?'is-current':''}`} key={c.id} onClick={()=>changeCase(c.id)}><span className="v4-menu-copy"><strong>{c.codigo}</strong><small>{c.titulo||c.producto} · {estadoGestionNombre[c.estado_gestion||'sin_atender']}</small></span>{activeCase===c.id&&<Check size={15}/>}</button>)}
      </div>}
    </div>
    {currentCase&&<div className="v5-context-tools">
     {readonly?<span className="v4-case-state">{estadoGestionNombre[currentCase.estado_gestion||'sin_atender']}</span>:<CaseStatusSelect compact fichaId={currentCase.id} value={currentCase.estado_gestion||'sin_atender'} quote={{monto:currentCase.cotizacion_monto,moneda:currentCase.cotizacion_moneda}} onChanged={async()=>{await refreshAll();setNotice('Estado actualizado')}} onError={setError}/>}
     {currentCase.responsable?<span className="v5-chip"><UserCheck size={12}/> {ownerName(currentCase.responsable)}</span>:!readonly&&user?<button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={()=>void act(()=>api(`/api/fichas/${currentCase.id}/responsable`,{method:'POST',body:JSON.stringify({responsable:user.username})}),'Gestión asignada a vos')}><UserCheck size={14}/> Asignarme</button>:<span className="v5-chip">Sin asignar</span>}
     {currentCase.tipo_consulta!=='sin_clasificar'&&<span className="v5-chip">{tipoConsultaNombre[currentCase.tipo_consulta]}{currentCase.tipo_sugerido_ia?<> · <Sparkles size={11}/> IA</>:null}</span>}
     {currentCase.bajo_minimo&&<span className="v5-chip is-warning"><AlertTriangle size={11}/> Bajo mínimo</span>}
    </div>}
   </div>
   {detail.mensaje_tras_cierre&&!readonly&&detail.gestion&&<div className="v5-banner is-attention v5-chat-banner"><AlertTriangle size={16}/><span>Nuevo mensaje en una gestión cerrada ({detail.gestion.codigo} · {estadoGestionNombre[detail.gestion.estado_gestion]}).</span><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={()=>void act(()=>api(`/api/fichas/${detail.gestion!.id}/estado`,{method:'POST',body:JSON.stringify({estado:'calificada'})}),'Gestión reabierta')}><RotateCcw size={14}/> Reabrir</button><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={()=>void newCaseForLatest()}><Plus size={14}/> Nueva gestión</button></div>}

   <div className="v4-chat-transcript" aria-label="Mensajes de la conversación" ref={transcriptRef}>
    {detail.hay_anteriores&&activeCase===null&&<button type="button" className="btn btn-outline btn-sm v5-older" onClick={()=>void loadOlder()} disabled={olderLoading}><History size={14}/> {olderLoading?'Cargando…':'Ver mensajes anteriores'}</button>}
    {sortedMessages.map((m,i)=><div className={`v4-chat-message-block ${isOut(m)?'is-outgoing':''}`} key={m.id}>
     {(i===0||messageDay(sortedMessages[i-1])!==messageDay(m))&&<div className="v4-chat-day">{messageDay(m)}</div>}
     <button type="button" aria-label={isOut(m)?'Respuesta registrada':`Responder a este mensaje de ${m.canal}`} className={`v4-message-bubble ${isOut(m)?'is-outgoing':''} ${activeMessage?.id===m.id?'is-selected':''}`} onClick={()=>pick(m)}>
      <span className="v4-message-meta">{isOut(m)?<Send size={13}/>:m.canal==='Correo'?<Mail size={13}/>:<MessageCircle size={13}/>} {isOut(m)?`Respuesta registrada${m.usuario?` · ${ownerName(m.usuario)}`:''} · `:''}{m.canal==='Correo'?'Email':m.canal.replace(' (simulado)','')} · {new Date(m.recibido_el).toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit'})}</span>
      {m.asunto&&<strong className="v4-message-subject">{m.asunto}</strong>}
      <span className="v4-message-text">{m.texto}</span>
     </button>
    </div>)}
    {!sortedMessages.length&&<p className="muted v5-center">No hay mensajes para esta gestión.</p>}
   </div>

   {showReport&&<section className="v4-chat-report" aria-label="Informe de la consulta" ref={reportRef}>
    <div className="v3-section-line"><h3>Información de la consulta</h3><button type="button" className="v4-icon-action" onClick={()=>setShowReport(false)} aria-label="Cerrar informe"><X size={16}/></button></div>
    {analysis?<><div className="v4-report-fields"><div><small>Producto</small><strong>{currentCase?.producto||analysis.producto||'Sin definir'}</strong></div><div><small>Cantidad</small><strong>{unidades(currentCase?.cantidad??analysis.cantidad)||'Sin definir'}</strong></div>{currentCase&&<div><small>Tipo de servicio</small><strong>{tipoConsultaNombre[currentCase.tipo_consulta]}</strong></div>}</div>{analysis.resumen&&<p>{analysis.resumen}</p>}
     {!!analysis.requisitos?.length&&<div><h4>Requisitos</h4><ul>{analysis.requisitos.map((v,i)=><li key={i}>{v}</li>)}</ul></div>}
     {!!pendientes.length&&<div><h4>Datos a confirmar</h4><ul>{pendientes.map((v,i)=><li key={i}>{v}</li>)}</ul></div>}
     {!!extrasIA.length&&<div><h4>Otros puntos sugeridos por IA</h4><ul>{extrasIA.map((v,i)=><li key={i}>{v}</li>)}</ul></div>}
     <div className="v4-report-actions">{!readonly&&<button className="btn btn-outline" type="button" onClick={()=>void saveAnalysis()} disabled={busy||!activeCase}>Guardar en gestión</button>}{activeCase&&<button type="button" className="btn btn-outline" onClick={()=>setFormCase(activeCase)}>Editar detalles</button>}{!readonly&&<button type="button" className="btn btn-outline" onClick={()=>void generate('report',true)} disabled={busy}><Sparkles size={14}/> Regenerar</button>}</div></>:<p className="v5-loading" role="status">Generando informe con toda la conversación…</p>}
   </section>}

   {/* Compositor tipo chat: escribir directo, con la IA como ayuda opcional. */}
   {activeMessage&&!readonly&&<footer className="v5-composer">
    <div className="v5-composer-top">
     <span className="v5-reply-to">Respondiendo a: <em>{activeMessage.texto.slice(0,90)}{activeMessage.texto.length>90?'…':''}</em></span>
     <div className="v3-switch v5-channel" role="group" aria-label="Canal de la respuesta"><button className={sendChannel==='WhatsApp'?'selected':''} type="button" onClick={()=>setSendChannel('WhatsApp')}>WhatsApp</button><button className={sendChannel==='Correo'?'selected':''} type="button" onClick={()=>setSendChannel('Correo')}>Email</button></div>
    </div>
    <div className="v5-composer-row">
     <div className="v5-ai-wrap">
      <button type="button" className="v5-ai-button" aria-label="Sugerir respuesta con IA" title="Sugerir respuesta con IA" aria-expanded={aiMenu} disabled={busy} onClick={()=>{if(currentCase?.bajo_minimo){setAiMenu(v=>!v);setMoreMenu(false)}else suggestWithAI()}}>{generating==='draft'?<Loader2 size={18} className="v5-spin"/>:<Sparkles size={18}/>}</button>
      {aiMenu&&<div className="v5-ai-menu" role="menu">
       <button type="button" role="menuitem" className="v4-menu-item" onClick={()=>suggestWithAI(false)}><Sparkles size={15}/> Sugerir respuesta</button>
       <button type="button" role="menuitem" className="v4-menu-item" onClick={()=>{setLoteMinimo(true);suggestWithAI(true)}}><AlertTriangle size={15}/> Sugerir informando el lote mínimo ({unidades(currentCase?.lote_minimo)})</button>
      </div>}
     </div>
     <textarea ref={composerRef} rows={1} aria-label="Escribí tu respuesta" placeholder={generating==='draft'?'La IA está preparando una sugerencia…':`Escribí tu respuesta por ${canalTexto}…`} value={draft} disabled={generating==='draft'}
      onChange={e=>setDraft(e.target.value)} onBlur={()=>{if(draft!==draftSaved)void saveDraft(true)}}
      onKeyDown={e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();void copyAndRegister()}}}/>
     <button type="button" className="btn btn-primary v5-register" aria-label="Copiar y registrar respuesta" disabled={busy||!draft.trim()} onClick={()=>void copyAndRegister()} title="Copia el texto y lo registra en el hilo (Ctrl+Enter)"><Send size={15}/> <span className="v5-hide-mobile">Copiar y registrar</span></button>
    </div>
    <small className="v5-composer-hint">{draft!==draftSaved?'Guardando borrador…':draft?'Borrador guardado':' '} · El envío directo todavía no está integrado: se copia el texto para pegarlo en {canalTexto} y queda registrado en el hilo. Ctrl+Enter para registrar.</small>
   </footer>}
   </>}
   {notice&&<div className="v4-toast" role="status"><Check size={15}/>{notice}<button type="button" onClick={()=>setNotice('')} aria-label="Cerrar aviso"><X size={13}/></button></div>}
  </div>
 </div>}
 {formCase&&<CaseDialog fichaId={formCase} onClose={()=>{setFormCase(null);void refreshAll()}} readOnly={readonly}/>}
 </Shell>;
}
