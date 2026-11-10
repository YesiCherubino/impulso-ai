'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {MessagesSquare,ArrowLeft,X,Send,BellOff,Bell,FolderOpen} from 'lucide-react';
import {api,qs,UsuarioSesion} from '@/lib/api';

type Estado='activo'|'ausente'|'inactivo';
type Miembro={usuario:string;nombre:string;rol:string;estado:Estado;mensaje:string;no_molestar:boolean};
type Gestion={id:number;codigo:string;cliente:string;titulo:string;conversacion:string};
type Mensaje={id:number;canal_id:number;usuario:string;texto:string;ficha_id:number|null;sistema:number;creado_en:string;gestion?:Gestion|null};
type Canal={id:number;tipo:'canal'|'directo';nombre:string;con:string;no_leidos:number;silenciado:boolean;ultimo:Mensaje|null};
type Resumen={yo:string;canales:Canal[];equipo:Miembro[];ultimo_id:number;no_leidos:number;nuevos:(Mensaje&{directo:boolean;mencion:boolean})[];mi_estado:{estado:Estado;mensaje:string;no_molestar:boolean}};
export type GestionCompartida={ficha_id:number;codigo:string;cliente:string;titulo?:string};

const estadoNombre:Record<Estado,string>={activo:'Activo',ausente:'Ausente',inactivo:'Inactivo'};
const hora=(s:string)=>new Date(s).toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit'});
const fecha=(s:string)=>{const d=new Date(s),t=new Date();return d.toDateString()===t.toDateString()?hora(s):d.toLocaleDateString('es-AR',{day:'numeric',month:'short'})+' '+hora(s)};
const TOKEN=/(CON-\d{4}-\d{5}|@[a-z0-9._-]+)/gi;

/* Chat del equipo: canal #ventas, mensajes directos y estado de cada persona. Consulta al servidor cada 4 s. */
export default function TeamChat({user}:{user:UsuarioSesion|null}){
 const router=useRouter();
 const [open,setOpen]=useState(false),[data,setData]=useState<Resumen|null>(null),[canal,setCanal]=useState<number|null>(null);
 const [msgs,setMsgs]=useState<Mensaje[]>([]),[more,setMore]=useState(false),[text,setText]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [share,setShare]=useState<GestionCompartida|null>(null),[attached,setAttached]=useState<GestionCompartida|null>(null),[statusText,setStatusText]=useState('');
 const lastId=useRef<number>(-1),canalRef=useRef<number|null>(null),openRef=useRef(false),scroller=useRef<HTMLDivElement|null>(null),input=useRef<HTMLTextAreaElement|null>(null);
 canalRef.current=canal;openRef.current=open;
 const name=useCallback((u:string)=>data?.equipo.find(m=>m.usuario===u)?.nombre||u,[data]);

 const poll=useCallback(async()=>{
  try{
   const r=await api<Resumen>(`/api/chat/resumen${lastId.current>=0?`?desde_id=${lastId.current}`:''}`);
   setData(r);if(lastId.current<0)setStatusText(r.mi_estado.mensaje);
   lastId.current=r.ultimo_id;
   // Aviso del navegador: mensajes directos y menciones, salvo "No molestar" o si ya se está leyendo ese canal.
   if(r.nuevos.length&&!r.mi_estado.no_molestar&&typeof Notification!=='undefined'&&Notification.permission==='granted'){
    for(const m of r.nuevos){if(openRef.current&&canalRef.current===m.canal_id&&!document.hidden)continue;
     const who=r.equipo.find(e=>e.usuario===m.usuario)?.nombre||m.usuario;
     const n=new Notification(m.directo?who:`${who} te mencionó`,{body:m.texto.slice(0,140),tag:`impulso-chat-${m.id}`});
     n.onclick=()=>{window.focus();setOpen(true);void openChannel(m.canal_id);n.close()}}
   }
  }catch{/* sin sesión o sin conexión: se reintenta en el próximo ciclo */}
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[]);
 useEffect(()=>{if(!user)return;void poll();const t=setInterval(()=>void poll(),4000);return()=>clearInterval(t)},[user,poll]);

 // Mensajes del canal abierto.
 const loadChannel=useCallback(async(id:number)=>{const r=await api<{mensajes:Mensaje[];hay_anteriores:boolean}>(`/api/chat/canales/${id}/mensajes`);if(canalRef.current!==id)return;setMsgs(r.mensajes);setMore(r.hay_anteriores);
  const last=r.mensajes.at(-1);if(last)void api(`/api/chat/canales/${id}/leido`,{method:'POST',body:JSON.stringify({ultimo_id:last.id})});requestAnimationFrame(()=>scroller.current?.scrollTo({top:scroller.current.scrollHeight}))},[]);
 async function openChannel(id:number){setCanal(id);canalRef.current=id;setMsgs([]);setError('');try{await loadChannel(id);setTimeout(()=>input.current?.focus(),30)}catch(e){setError(String(e))}}
 useEffect(()=>{if(!open||canal===null)return;const t=setInterval(async()=>{const last=msgs.at(-1)?.id||0;try{const r=await api<{mensajes:Mensaje[]}>(`/api/chat/canales/${canal}/mensajes?${qs({despues_de:last})}`);if(r.mensajes.length&&canalRef.current===canal){setMsgs(old=>[...old,...r.mensajes.filter(n=>!old.some(o=>o.id===n.id))]);void api(`/api/chat/canales/${canal}/leido`,{method:'POST',body:JSON.stringify({ultimo_id:r.mensajes.at(-1)!.id})});requestAnimationFrame(()=>scroller.current?.scrollTo({top:scroller.current.scrollHeight,behavior:'smooth'}))}}catch{/* reintenta */}},4000);return()=>clearInterval(t)},[open,canal,msgs]);
 async function older(){if(canal===null||!msgs.length)return;const box=scroller.current;const before=box?.scrollHeight||0;const r=await api<{mensajes:Mensaje[];hay_anteriores:boolean}>(`/api/chat/canales/${canal}/mensajes?${qs({antes_de:msgs[0].id})}`);setMsgs(old=>[...r.mensajes,...old]);setMore(r.hay_anteriores);requestAnimationFrame(()=>{if(box)box.scrollTop=box.scrollHeight-before})}
 async function openPerson(u:string){try{const r=await api<{id:number}>('/api/chat/directo',{method:'POST',body:JSON.stringify({usuario:u})});await openChannel(r.id)}catch(e){setError(String(e))}}
 function pick(id:number|null,person?:string){if(share){setAttached(share);setShare(null)}if(person)void openPerson(person);else if(id!==null)void openChannel(id)}

 // Abrir desde la ficha o el chat del cliente: "Consultar con un compañero".
 useEffect(()=>{const onShare=(e:Event)=>{const g=(e as CustomEvent<GestionCompartida>).detail;setShare(g);setCanal(null);setOpen(true)};const onOpen=()=>setOpen(true);
  window.addEventListener('impulso:compartir-gestion',onShare);window.addEventListener('impulso:abrir-chat',onOpen);return()=>{window.removeEventListener('impulso:compartir-gestion',onShare);window.removeEventListener('impulso:abrir-chat',onOpen)}},[]);
 useEffect(()=>{if(!open)return;const onKey=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.stopPropagation();setOpen(false)}};window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey)},[open]);
 useEffect(()=>{if(open&&typeof Notification!=='undefined'&&Notification.permission==='default')void Notification.requestPermission().catch(()=>{})},[open]);

 async function send(){const t=text.trim();if((!t&&!attached)||canal===null||busy)return;setBusy(true);setError('');
  try{const m=await api<Mensaje>(`/api/chat/canales/${canal}/mensajes`,{method:'POST',body:JSON.stringify({texto:t||`${attached!.codigo} · ${attached!.cliente}`,ficha_id:attached?.ficha_id??null})});
   setMsgs(old=>[...old,m]);setText('');setAttached(null);requestAnimationFrame(()=>scroller.current?.scrollTo({top:scroller.current.scrollHeight,behavior:'smooth'}));void poll()}
  catch(e){setError(e instanceof Error?e.message:'No se pudo enviar')}finally{setBusy(false)}}
 async function saveStatus(next:Partial<Resumen['mi_estado']>){if(!data)return;const body={...data.mi_estado,mensaje:statusText,...next};setData({...data,mi_estado:body});try{await api('/api/chat/estado',{method:'POST',body:JSON.stringify(body)});void poll()}catch(e){setError(String(e))}}
 async function toggleMute(c:Canal){try{await api(`/api/chat/canales/${c.id}/silenciar`,{method:'POST',body:JSON.stringify({silenciado:!c.silenciado})});void poll()}catch(e){setError(String(e))}}
 function goGestion(g:Gestion){setOpen(false);if(window.location.pathname==='/consultas')window.dispatchEvent(new CustomEvent('impulso:open-conversacion',{detail:{key:g.conversacion,ficha:g.id}}));else router.push(`/consultas?conversacion=${g.conversacion}&ficha=${g.id}`)}
 async function goCode(code:string){try{const r=await api<{gestiones:{id:number;codigo:string;conversacion:string;cliente:string;titulo:string}[]}>(`/api/buscar?${qs({q:code})}`);const g=r.gestiones.find(x=>x.codigo===code);if(g)goGestion({...g})}catch{/* sin resultado */}}
 function render(t:string){return t.split(TOKEN).map((part,i)=>{if(/^CON-\d{4}-\d{5}$/i.test(part))return <button key={i} type="button" className="v7-ref" onClick={()=>void goCode(part.toUpperCase())}>{part}</button>;if(/^@/.test(part)&&data?.equipo.some(m=>`@${m.usuario}`===part.toLowerCase()))return <span key={i} className="v7-mention">@{name(part.slice(1).toLowerCase())}</span>;return part})}

 if(!user)return null;
 const current=data?.canales.find(c=>c.id===canal);
 const others=(data?.equipo||[]).filter(m=>m.usuario!==data?.yo);
 const dmOf=(u:string)=>data?.canales.find(c=>c.tipo==='directo'&&c.con===u);
 const title=current?(current.tipo==='canal'?`# ${current.nombre}`:name(current.con)):'Chat del equipo';
 const peer=current?.tipo==='directo'?data?.equipo.find(m=>m.usuario===current.con):null;
 return <>
  <button type="button" className="notification-trigger v7-chat-trigger" aria-label={`Chat del equipo${data?.no_leidos?`, ${data.no_leidos} sin leer`:''}`} title="Chat del equipo" onClick={()=>setOpen(v=>!v)}><MessagesSquare size={18}/>{!!data?.no_leidos&&<span className="v7-badge">{data.no_leidos>99?'99+':data.no_leidos}</span>}</button>
  {open&&<><div className="v7-chat-shade" onMouseDown={()=>setOpen(false)}/><aside className="v7-chat" role="dialog" aria-label="Chat del equipo">
   <header>{canal!==null&&<button type="button" className="v7-back" aria-label="Volver" onClick={()=>{setCanal(null);void poll()}}><ArrowLeft size={18}/></button>}
    {peer&&<span className={`v7-dot is-${peer.estado}`}/>}<h2>{title}</h2>
    {current&&<button type="button" className="v4-icon-action" aria-label={current.silenciado?'Activar avisos':'Silenciar'} title={current.silenciado?'Activar avisos':'Silenciar'} onClick={()=>void toggleMute(current)}>{current.silenciado?<BellOff size={16}/>:<Bell size={16}/>}</button>}
    <button type="button" className="v4-icon-action" aria-label="Cerrar" onClick={()=>setOpen(false)}><X size={18}/></button></header>
   {peer&&(peer.mensaje||peer.estado!=='activo')&&<div className="v7-me"><span>{estadoNombre[peer.estado]}{peer.mensaje?` · ${peer.mensaje}`:''}</span></div>}
   {canal===null?<>
    <div className="v7-me">
     <span className={`v7-dot is-${data?.mi_estado.estado||'activo'}`}/>
     <select aria-label="Mi estado" value={data?.mi_estado.estado||'activo'} onChange={e=>void saveStatus({estado:e.target.value as Estado})}><option value="activo">Activo</option><option value="ausente">Ausente</option><option value="inactivo">Inactivo</option></select>
     <input aria-label="Mensaje de estado" placeholder="Estado (ej. en reunión hasta las 15)" value={statusText} maxLength={120} onChange={e=>setStatusText(e.target.value)} onBlur={()=>{if(statusText!==data?.mi_estado.mensaje)void saveStatus({})}} onKeyDown={e=>{if(e.key==='Enter')(e.target as HTMLInputElement).blur()}}/>
     <label><input type="checkbox" checked={!!data?.mi_estado.no_molestar} onChange={e=>void saveStatus({no_molestar:e.target.checked})}/> No molestar</label>
    </div>
    {share&&<div className="v7-share"><span>Elegí con quién consultar <b>{share.codigo}</b> · {share.cliente}</span><button type="button" className="v3-text-action" onClick={()=>setShare(null)}>Cancelar</button></div>}
    <div className="v7-chat-scroll">
     <div className="v7-section">Canales</div>
     {data?.canales.filter(c=>c.tipo==='canal').map(c=><button type="button" key={c.id} className={`v7-item ${c.no_leidos?'is-unread':''}`} onClick={()=>pick(c.id)}><span className="v7-hash">#</span><span className="v7-item-body"><strong>{c.nombre}</strong>{c.ultimo&&<small>{name(c.ultimo.usuario)}: {c.ultimo.texto}</small>}</span>{c.silenciado?<BellOff size={13}/>:c.no_leidos>0&&<span className="v7-count">{c.no_leidos}</span>}</button>)}
     <div className="v7-section">Personas</div>
     {others.map(m=>{const dm=dmOf(m.usuario);return <button type="button" key={m.usuario} className={`v7-item ${dm?.no_leidos?'is-unread':''}`} onClick={()=>pick(dm?.id??null,dm?undefined:m.usuario)}>
      <span className={`v7-dot is-${m.estado}`} title={estadoNombre[m.estado]}/><span className="v7-item-body"><strong>{m.nombre}</strong><small>{dm?.ultimo?`${dm.ultimo.usuario===data?.yo?'Vos: ':''}${dm.ultimo.texto}`:m.mensaje||estadoNombre[m.estado]}</small></span>{dm?.silenciado?<BellOff size={13}/>:!!dm?.no_leidos&&<span className="v7-count">{dm.no_leidos}</span>}</button>})}
     {!others.length&&<p className="v7-empty">Todavía no hay otros usuarios.</p>}
    </div></>:<>
    <div className="v7-msgs" ref={scroller}>
     {more&&<button type="button" className="btn btn-outline btn-sm v7-older" onClick={()=>void older()}>Ver anteriores</button>}
     {msgs.map((m,i)=>{const prev=msgs[i-1];const cont=!!prev&&prev.usuario===m.usuario&&new Date(m.creado_en).getTime()-new Date(prev.creado_en).getTime()<5*60000;
      return <div key={m.id} className={`v7-msg ${cont?'is-cont':''} ${m.sistema?'is-system':''} ${m.sistema&&/^Cerré |aceptó la cotización/.test(m.texto)?'is-win':''}`}><span className="v7-av">{name(m.usuario).charAt(0).toUpperCase()}</span><div>
       {!cont&&<div className="v7-msg-head"><strong>{m.usuario===data?.yo?'Vos':name(m.usuario)}</strong><time>{fecha(m.creado_en)}</time></div>}
       <div className="v7-msg-text">{render(m.texto)}</div>
       {m.gestion&&<button type="button" className="v7-gestion" onClick={()=>goGestion(m.gestion!)}><FolderOpen size={14}/><span><b>{m.gestion.codigo}</b> · {m.gestion.cliente} · {m.gestion.titulo}</span></button>}
      </div></div>})}
     {!msgs.length&&<p className="v7-empty">Sin mensajes todavía.</p>}
    </div>
    <div className="v7-composer">
     {attached&&<div className="v7-attached"><FolderOpen size={13}/><span><b>{attached.codigo}</b> · {attached.cliente}</span><button type="button" aria-label="Quitar gestión" onClick={()=>setAttached(null)}><X size={13}/></button></div>}
     <textarea ref={input} rows={2} value={text} placeholder={current?.tipo==='canal'?`Mensaje en #${current.nombre}`:`Mensaje a ${name(current?.con||'')}`} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void send()}}}/>
     <div className="v7-composer-row"><small>Enter envía · @usuario menciona · CON-… enlaza la gestión</small><button type="button" className="btn btn-primary btn-sm" disabled={busy||(!text.trim()&&!attached)} onClick={()=>void send()}><Send size={13}/> Enviar</button></div>
    </div></>}
   {error&&<p className="alert error" role="alert" style={{margin:10}}>{error}</p>}
  </aside></>}
 </>;
}
