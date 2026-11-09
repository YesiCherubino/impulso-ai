'use client';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import Link from 'next/link';
import {ArrowLeft, ArrowRight, ClipboardList, Inbox, LoaderCircle, Search, RefreshCcw} from 'lucide-react';
import Shell from '@/components/shell';
import {api,ConsultaBandeja,ConsultaIA,Detalle,TipoConsulta,CanalOrigen,tipoConsultaNombre,tiposConsulta,canalesOrigen} from '@/lib/api';

type EstadoFiltro='todas'|'nueva'|'en_gestion'|'resuelta';
const nombreEstado={nueva:'Sin atender',en_gestion:'En gestión',resuelta:'Resuelta'};
// Sólo precarga sugerida: la persona siempre puede corregirla antes de guardar.
function extractFromMessage(text:string){
 const quantityMatch=text.match(/(?:producir|fabricar|pedido de|producción de|lote de)?\s*([\d][\d.,]*)\s*(?:unidades|uds?\.?|piezas)/i);
 const raw=quantityMatch?.[1].replace(/[.,](?=\d{3}(?:\D|$))/g,'').replace(/,/g,'.');
 const quantity=raw&&Number.isFinite(Number(raw))&&Number(raw)>0?String(Math.round(Number(raw))):'';
 const names=['crema corporal','jabón líquido','máscara capilar','shampoo','acondicionador','crema facial','perfume','gel de ducha'];
 const name=names.find(p=>text.toLocaleLowerCase('es').includes(p));
 const size=text.match(/\b(?:de\s+)?(\d{1,4})\s*(ml|gr|g|l)\b/i);
 return {producto:name?`${name}${size?' '+size[1]+' '+size[2]:''}`:'',cantidad:quantity};
}
function inferType(text:string):TipoConsulta{
 const lower=text.toLocaleLowerCase('es');
 if(/mayorista|distribuidora|distribución comercial/.test(lower))return 'mayorista';
 if(/desarroll(?:ar|o) (?:una? )?f[oó]rmula|formular (?:un|una)|nueva f[oó]rmula/.test(lower))return 'desarrollo_formula';
 if(/(?:solo |únicamente )?(?:envasar|envasado|envasamiento)/.test(lower))return 'elaboracion_envasado';
 if(/marca propia|fabricar|producci[oó]n para terceros/.test(lower))return 'fabricacion_terceros';
 return 'sin_clasificar';
}
function fechaHora(value:string){const date=new Date(value);return Number.isNaN(date.getTime())?value:date.toLocaleString('es-AR',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});}

export default function BandejaConsultas(){
 const [consultas,setConsultas]=useState<ConsultaBandeja[]>([]),[seleccion,setSeleccion]=useState<number|null>(null),[filtro,setFiltro]=useState<EstadoFiltro>('todas'),[texto,setTexto]=useState('');
 const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState<ConsultaIA|null>(null),[created,setCreated]=useState<Detalle|null>(null),[draft,setDraft]=useState(''),[copyText,setCopyText]=useState('Copiar respuesta');
 const [createOpen,setCreateOpen]=useState(false);
 const [newOpen,setNewOpen]=useState(false),[newBusy,setNewBusy]=useState(false);
 const [newForm,setNewForm]=useState<{cliente:string;contacto:string;texto:string;canal:CanalOrigen}>({cliente:'',contacto:'',texto:'',canal:'Manual'});
 const [savedDraft,setSavedDraft]=useState(''),[analysisVersion,setAnalysisVersion]=useState(0),[savingDraft,setSavingDraft]=useState(false);
 const [showContactData,setShowContactData]=useState(false);
 const [linkedDetail,setLinkedDetail]=useState<Detalle|null>(null);
 const [contactForm,setContactForm]=useState<{cliente:string;contacto:string;producto:string;cantidad:string;tipo_consulta:TipoConsulta;presentacion:string;packaging:string}>({cliente:'',contacto:'',producto:'',cantidad:'',tipo_consulta:'sin_clasificar',presentacion:'',packaging:''});
 const usedUrlRef=useRef(false);
 function beginContact(){
  if(!actual || actual.estado==='resuelta' || actual.oportunidad_id)return;
  const inferred=extractFromMessage(actual.texto);
  setContactForm({cliente:result?.cliente||actual.cliente,contacto:result?.contacto||actual.contacto,producto:result?.producto||inferred.producto,cantidad:result?.cantidad!=null?String(result.cantidad):inferred.cantidad,tipo_consulta:result?.tipo_consulta||inferType(actual.texto),presentacion:result?.presentacion||'',packaging:result?.necesita_packaging==='si'?'Requiere packaging (confirmar especificaciones)':''});
  setCreateOpen(true);setShowContactData(false);setError('');
 }
 const fetchAll=useCallback(async()=>{setLoading(true);setError('');try{const rows=await api<ConsultaBandeja[]>('/api/inbox');setConsultas(rows);setSeleccion(old=>old&&rows.some(r=>r.id===old)?old:null);}catch(e){setError(e instanceof Error?e.message:'Error cargando consultas');}finally{setLoading(false)}},[]);
 useEffect(()=>{void fetchAll()},[fetchAll]);
 const counts=useMemo(()=>({todas:consultas.length,nueva:consultas.filter(c=>c.estado==='nueva').length,en_gestion:consultas.filter(c=>c.estado==='en_gestion').length,resuelta:consultas.filter(c=>c.estado==='resuelta').length}),[consultas]);
 const visible=useMemo(()=>consultas.filter(c=>(filtro==='todas'||c.estado===filtro)&&[c.cliente,c.contacto,c.texto].some(x=>x.toLocaleLowerCase('es').includes(texto.toLocaleLowerCase('es')))),[consultas,filtro,texto]);
 const actual=consultas.find(c=>c.id===seleccion);
 useEffect(()=>{
  if(loading||usedUrlRef.current)return;
  usedUrlRef.current=true;
  const queryId=Number(new URLSearchParams(window.location.search).get('consulta'));
  if(queryId>0&&consultas.some(c=>c.id===queryId))setSeleccion(queryId);
 },[loading,consultas]);
 useEffect(()=>{
  const open=(event:Event)=>{const id=(event as CustomEvent<number>).detail;if(consultas.some(c=>c.id===id))setSeleccion(id)};
  window.addEventListener('impulso:open-consulta',open);
  return()=>window.removeEventListener('impulso:open-consulta',open);
 },[consultas]);
 useEffect(()=>{
  if(!seleccion){setResult(null);setDraft('');setSavedDraft('');setAnalysisVersion(0);return}
  let active=true;
  void api<{analisis:{version:number;resultado:ConsultaIA;borrador:string}|null}>(`/api/inbox/${seleccion}/analysis`)
   .then(d=>{if(!active)return;setResult(d.analisis?.resultado??null);setDraft(d.analisis?.borrador??'');setSavedDraft(d.analisis?.borrador??'');setAnalysisVersion(d.analisis?.version??0)})
   .catch(()=>{if(active){setResult(null);setDraft('');setSavedDraft('')}});
  return()=>{active=false};
 },[seleccion]);

 useEffect(()=>{
  const linkedId=actual?.oportunidad_id;
  setLinkedDetail(null);
  if(!linkedId)return;
  let live=true;
  void api<Detalle>(`/api/opportunities/${linkedId}`).then(d=>{if(live)setLinkedDetail(d)}).catch(()=>{});
  return()=>{live=false};
 },[actual?.oportunidad_id]);
 useEffect(()=>{if(seleccion!==null&&!visible.some(c=>c.id===seleccion)){setSeleccion(null);setResult(null);setDraft('');}},[seleccion,visible]);
 // En escritorio mostramos el primer mensaje pendiente; en celular se conserva la vista de lista.
 useEffect(()=>{
  if (loading || seleccion!==null || !visible.length || typeof window==='undefined') return;
  if (window.matchMedia('(min-width: 801px)').matches) {
   setSeleccion(visible.find(c=>c.estado==='nueva')?.id ?? visible[0].id);
  }
 },[loading,seleccion,visible]);
 function choose(id:number){setSeleccion(id);setError('');setResult(null);setCreated(null);setDraft('');setSavedDraft('');setAnalysisVersion(0);setCreateOpen(false);setShowContactData(false);}
 async function changeStatus(estado:ConsultaBandeja['estado']){if(!actual)return;setBusy(true);setError('');try{const updated=await api<ConsultaBandeja>(`/api/inbox/${actual.id}/status`,{method:'POST',body:JSON.stringify({estado})});setConsultas(cs=>cs.map(c=>c.id===updated.id?updated:c));if(estado==='resuelta')setCreateOpen(false);setShowContactData(false);}catch(e){setError(e instanceof Error?e.message:'No se pudo actualizar el estado');}finally{setBusy(false)}}
 async function analyze(regenerar=false){if(!actual)return;setBusy(true);setError('');try{
  const stored=await api<{version:number;resultado:ConsultaIA;borrador:string}>(`/api/inbox/${actual.id}/analysis`,{method:'POST',body:JSON.stringify({regenerar})});
  setResult(stored.resultado);setDraft(stored.borrador);setSavedDraft(stored.borrador);setAnalysisVersion(stored.version);
 }catch(e){setError(e instanceof Error?e.message:'No se pudo preparar la respuesta')}finally{setBusy(false)}}
 async function persistDraft(){if(!actual||!result||draft===savedDraft)return;setSavingDraft(true);setError('');try{
  const stored=await api<{borrador:string}>(`/api/inbox/${actual.id}/draft`,{method:'POST',body:JSON.stringify({borrador:draft})});setSavedDraft(stored.borrador);
 }catch(e){setError(e instanceof Error?e.message:'No se pudo guardar la respuesta')}finally{setSavingDraft(false)}}
 async function addNew(e:React.FormEvent){e.preventDefault();setNewBusy(true);setError('');try{
  const saved=await api<ConsultaBandeja>('/api/inbox',{method:'POST',body:JSON.stringify(newForm)});
  setNewOpen(false);setNewForm({cliente:'',contacto:'',texto:'',canal:'Manual'});setFiltro('todas');setTexto('');await fetchAll();setSeleccion(saved.id);
 }catch(e){setError(e instanceof Error?e.message:'No se pudo registrar la consulta')}finally{setNewBusy(false)}}
 async function create(e:React.FormEvent){e.preventDefault();if(!actual)return;setBusy(true);setError('');try{const saved=await api<Detalle>('/api/opportunities',{method:'POST',body:JSON.stringify({cliente:contactForm.cliente.trim(),contacto:contactForm.contacto.trim(),producto:contactForm.producto.trim(),cantidad:contactForm.cantidad?Number(contactForm.cantidad):null,monto_estimado_usd:null,tipo_consulta:contactForm.tipo_consulta,canal_origen:actual.canal.startsWith("WhatsApp")?"WhatsApp":canalesOrigen.includes(actual.canal as CanalOrigen)?actual.canal:"Manual",presentacion:contactForm.presentacion,packaging:contactForm.packaging,notas:`Consulta original (${actual.canal}): ${actual.texto}${result?`\nRequisitos: ${result.requisitos.join('; ')}\nDatos pendientes: ${result.datos_faltantes.join('; ')}`:''}`})});setCreated(saved);setLinkedDetail(saved);setCreateOpen(false);setShowContactData(true);const linked=await api<ConsultaBandeja>(`/api/inbox/${actual.id}/link-opportunity`,{method:'POST',body:JSON.stringify({opportunity_id:saved.id})});setConsultas(cs=>cs.map(c=>c.id===linked.id?linked:c));}catch(e){setError(e instanceof Error?e.message:'No se pudo registrar el contacto comercial');}finally{setBusy(false)}}
 async function copy(){try{await navigator.clipboard.writeText(draft);setCopyText('Copiado')}catch{setCopyText('Seleccioná el texto y copialo')}}
 return <Shell><div className="bo-head"><div><div className="bo-breadcrumb">GESTIÓN COMERCIAL / CONSULTAS</div><h1>Bandeja de consultas</h1></div><div className="bo-head-actions"><button className="btn btn-outline" onClick={()=>setNewOpen(v=>!v)}>Nueva consulta</button><button className="btn btn-outline" onClick={()=>void fetchAll()}><RefreshCcw size={16}/> Actualizar</button></div></div>
 
 
 {newOpen&&<form className="panel new-consultation-form" onSubmit={e=>void addNew(e)}><h2>Nueva consulta</h2><p className="form-hint">Carga manual de un mensaje recibido por WhatsApp, correo, formulario u otro medio. No se sincroniza automáticamente.</p><div className="bo-data-grid"><label>Cliente<input required minLength={2} maxLength={120} value={newForm.cliente} onChange={e=>setNewForm({...newForm,cliente:e.target.value})}/></label><label>Persona de contacto<input required minLength={2} maxLength={120} value={newForm.contacto} onChange={e=>setNewForm({...newForm,contacto:e.target.value})}/></label></div><label>Canal de origen<select value={newForm.canal} onChange={e=>setNewForm({...newForm,canal:e.target.value as CanalOrigen})}>{canalesOrigen.map(c=><option key={c} value={c}>{c}</option>)}</select></label><label>Mensaje<textarea required minLength={5} maxLength={5000} rows={4} value={newForm.texto} onChange={e=>setNewForm({...newForm,texto:e.target.value})}/></label><div className="new-consultation-actions"><button type="submit" disabled={newBusy} className="btn btn-primary">{newBusy?'Guardando...':'Guardar consulta'}</button><button type="button" className="btn btn-outline" onClick={()=>setNewOpen(false)}>Cancelar</button></div></form>}
 {error&&<div className="alert error" role="alert">{error}<button onClick={()=>setError('')}>Cerrar</button></div>}
 <div className={`bo-layout ${seleccion?'bo-selected':''}`}><section className="bo-list panel" aria-label="Lista de consultas"><div className="bo-list-header"><strong>Mensajes recibidos</strong><span>{visible.length} resultados</span></div><label className="bo-search"><Search size={17}/><input value={texto} onChange={e=>setTexto(e.target.value)} placeholder="Buscar por cliente, contacto o texto" aria-label="Buscar consulta"/></label><div className="bo-filters" role="group" aria-label="Filtrar consultas">{(['todas','nueva','en_gestion','resuelta'] as EstadoFiltro[]).map(f=><button key={f} onClick={()=>setFiltro(f)} className={`bo-filter-tab bo-filter-${f} ${filtro===f?'selected':''}`}>{f==='todas'?'Todas':nombreEstado[f]} <span>{counts[f]}</span></button>)}<label className="bo-filter-select"><span className="sr-only">Filtrar consultas por estado</span><select aria-label="Estado de la consulta" value={filtro} onChange={e=>setFiltro(e.target.value as EstadoFiltro)}><option value="todas">Todas ({counts.todas})</option><option value="nueva">Sin atender ({counts.nueva})</option><option value="en_gestion">En gestión ({counts.en_gestion})</option><option value="resuelta">Resueltas ({counts.resuelta})</option></select></label></div>
 <div className="bo-rows">{visible.map(c=><button key={c.id} className={`bo-row ${seleccion===c.id?'is-selected':''}`} onClick={()=>choose(c.id)}><span className="bo-row-avatar">{c.cliente.charAt(0)}</span><span className="bo-row-main"><span className="bo-row-top"><strong>{c.cliente}</strong><small>{fechaHora(c.recibido_el)}</small></span><span className="bo-row-person">{c.contacto} · {c.canal.startsWith('WhatsApp')?'WhatsApp':c.canal}</span><span className="bo-row-preview">{c.texto}</span><span className={`bo-state bo-state-${c.estado}`}>{nombreEstado[c.estado]}</span></span></button>)}{!visible.length&&<p className="bo-empty">{loading?'Cargando consultas...':'No hay consultas con estos filtros.'}</p>}</div></section>
 <section className="bo-detail panel" aria-label="Detalle de consulta">{actual?<><div className="bo-detail-head"><button className="bo-back" onClick={()=>setSeleccion(null)}><ArrowLeft size={18}/> Volver a la bandeja</button><div className="bo-person"><span className="bo-row-avatar large">{actual.cliente.charAt(0)}</span><div><h2>{actual.cliente}</h2><p>{actual.contacto} · {actual.canal.startsWith('WhatsApp')?'WhatsApp':actual.canal}</p></div></div><span className={`bo-state bo-state-${actual.estado}`}>{nombreEstado[actual.estado]}</span></div><div className="bo-conversation"><p className="bo-time">Mensaje recibido · {fechaHora(actual.recibido_el)}</p><div className="bo-bubble">{actual.texto}</div></div>
 <div className="bo-work">
  <section className="bo-operation-section" aria-label="Estado de la consulta">
   <div className="bo-operation-header"><h3>Estado</h3></div>
   <div className="bo-status-line"><label htmlFor="consultation-status" className="sr-only">Estado de la consulta</label><select id="consultation-status" value={actual.estado} disabled={busy} onChange={e=>void changeStatus(e.target.value as ConsultaBandeja['estado'])}><option value="nueva">Sin atender</option><option value="en_gestion">En gestión</option><option value="resuelta">Resuelta</option></select></div>
  </section>
  <section className="bo-operation-section" aria-label="Preparar respuesta">
   <div className="bo-operation-header"><h3>Respuesta</h3></div>
   {!result&&<button className="btn btn-primary" disabled={busy} onClick={()=>void analyze(false)}>{busy?<LoaderCircle size={16}/>:<ClipboardList size={16}/>} {busy?'Procesando...':'Preparar respuesta'}</button>}{result&&<button type="button" className="btn btn-outline" disabled={busy||draft!==savedDraft} title={draft!==savedDraft?'Guardá primero los cambios del borrador':'Generar una nueva versión'} onClick={()=>void analyze(true)}>Volver a generar</button>}
  </section>
  <section className="bo-operation-section" aria-label="Contacto comercial">
   <div className="bo-operation-header"><h3>Contacto comercial</h3></div>
   {actual.oportunidad_id || created ? <>
      <Link className="btn btn-outline" href={`/oportunidades/${created?.id||actual.oportunidad_id}`}>Datos de contacto <ArrowRight size={15}/></Link>
      {linkedDetail&&<p className="bo-hint">{linkedDetail.cliente} · {linkedDetail.producto}{linkedDetail.cantidad?` · ${linkedDetail.cantidad.toLocaleString('es-AR')} unidades`:''}</p>}
    </> : actual.estado==='resuelta' ? <>
      <button className="btn btn-outline" type="button" onClick={()=>setShowContactData(v=>!v)}>Datos de contacto</button>
      {showContactData&&<div className="bo-contact-summary"><div><small>Cliente</small><strong>{result?.cliente||actual.cliente}</strong></div><div><small>Persona de contacto</small><strong>{result?.contacto||actual.contacto}</strong></div><div><small>Producto</small><strong>{result?.producto||extractFromMessage(actual.texto).producto||'No informado'}</strong></div><div><small>Cantidad</small><strong>{result?.cantidad!=null?result.cantidad.toLocaleString('es-AR'):(extractFromMessage(actual.texto).cantidad||'No informada')}</strong></div><p>Esta consulta no tiene un contacto comercial registrado.</p></div>}
    </> : <button className="btn btn-outline" type="button" disabled={busy} onClick={beginContact}>Registrar contacto comercial <ArrowRight size={15}/></button>}
  </section>
 {createOpen&&<form className="bo-contact-form" onSubmit={e=>void create(e)}><div className="bo-form-title"><strong>Nuevo contacto comercial</strong><button type="button" className="btn btn-quiet" onClick={()=>setCreateOpen(false)}>Cancelar</button></div><div className="bo-data-grid"><label>Cliente<input required minLength={2} maxLength={120} value={contactForm.cliente} onChange={e=>setContactForm({...contactForm,cliente:e.target.value})}/></label><label>Persona de contacto<input required minLength={2} maxLength={120} value={contactForm.contacto} onChange={e=>setContactForm({...contactForm,contacto:e.target.value})}/></label><label>Producto o servicio<input required minLength={2} maxLength={150} placeholder="Producto de interés" value={contactForm.producto} onChange={e=>setContactForm({...contactForm,producto:e.target.value})}/></label><label>Cantidad (opcional)<input type="number" min="1" value={contactForm.cantidad} onChange={e=>setContactForm({...contactForm,cantidad:e.target.value})}/></label></div><div className="bo-data-grid"><label>Tipo de consulta<select value={contactForm.tipo_consulta} onChange={e=>setContactForm({...contactForm,tipo_consulta:e.target.value as TipoConsulta})}>{tiposConsulta.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label><label>Presentación<input maxLength={120} placeholder="Ej. 250 ml" value={contactForm.presentacion} onChange={e=>setContactForm({...contactForm,presentacion:e.target.value})}/></label><label>Packaging<input maxLength={200} placeholder="Ej. Envase personalizado" value={contactForm.packaging} onChange={e=>setContactForm({...contactForm,packaging:e.target.value})}/></label></div><button className="btn btn-primary" type="submit" disabled={busy||!contactForm.cliente.trim()||!contactForm.contacto.trim()||!contactForm.producto.trim()}>{busy?'Guardando...':'Guardar contacto comercial'}</button></form>}
 {result&&<div className="bo-ai-result"><h3><ClipboardList size={17}/> Información de la consulta</h3><p className="bo-saved-indicator">Análisis guardado · Versión {analysisVersion}</p><div className="bo-data-grid"><div><small>Cliente</small><strong>{result.cliente||actual.cliente}</strong></div><div><small>Contacto</small><strong>{result.contacto||actual.contacto}</strong></div><div><small>Producto</small><strong>{result.producto||'No indicado'}</strong></div><div><small>Cantidad</small><strong>{result.cantidad?.toLocaleString('es-AR')??'No indicada'}</strong></div><div><small>Tipo de consulta</small><strong>{tipoConsultaNombre[result.tipo_consulta||'sin_clasificar']}</strong></div><div><small>Presentación</small><strong>{result.presentacion||'No indicada'}</strong></div><div><small>Desarrollo de fórmula</small><strong>{result.necesita_formula==='si'?'Solicitado':result.necesita_formula==='no'?'No solicitado':'A confirmar'}</strong></div><div><small>Packaging</small><strong>{result.necesita_packaging==='si'?'Solicitado':result.necesita_packaging==='no'?'No solicitado':'A confirmar'}</strong></div></div>
 {result.datos_faltantes.length>0&&<div className="bo-missing"><strong>Datos que faltan confirmar</strong><ul>{result.datos_faltantes.map((d,i)=><li key={i}>{d}</li>)}</ul></div>}
 <div className="bo-draft"><label htmlFor="borrador">Respuesta sugerida (editable)</label><textarea id="borrador" rows={5} value={draft} onChange={e=>setDraft(e.target.value)} onBlur={()=>void persistDraft()} /><div className="bo-draft-bottom"><button type="button" className="btn btn-outline" onClick={()=>void persistDraft()} disabled={savingDraft||draft===savedDraft}>{savingDraft?'Guardando...':draft===savedDraft?'Respuesta guardada':'Guardar respuesta'}</button><button className="btn btn-outline" onClick={()=>void copy()} disabled={!draft}>{copyText}</button><small>El mensaje no se envía automáticamente.</small></div></div></div>}
 </div></>:<div className="bo-empty-detail"><Inbox size={28}/><strong>Seleccioná una consulta</strong><span>Elegí un mensaje para ver su detalle.</span></div>}</section></div></Shell>
}
