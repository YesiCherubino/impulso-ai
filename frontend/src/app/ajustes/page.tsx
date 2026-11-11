'use client';
import {useCallback,useEffect,useState} from 'react';
import {Plus,UserRound,Check,X,Pencil,Trash2} from 'lucide-react';
import Shell from '@/components/shell';
import {api,Rol,roleName,UsuarioSesion} from '@/lib/api';
import {ImportPanel,EmpresaPanel,ReglasPanel,PlantillasPanel,DocumentosPanel,ChatPanel,IntegracionesPanel} from '@/components/admin-v5';

type Seccion='preferencias'|'usuarios'|'empresa'|'comercial'|'ia'|'contenido'|'chat'|'integraciones'|'datos';
const SECCIONES:[Seccion,string,boolean][]=[['preferencias','Preferencias',false],['usuarios','Usuarios y permisos',true],['empresa','Empresa y apariencia',true],['comercial','Reglas comerciales',true],['ia','Asistente de IA',false],['contenido','Respuestas y documentos',true],['chat','Chat del equipo',true],['integraciones','Integraciones',true],['datos','Datos',true]];
type User={id:number;username:string;name:string;role:Rol;active:boolean;theme:string};
type AISettings={tono:'formal'|'profesional'|'cercano';tratamiento:'vos'|'tu'|'ustedes';signos_apertura:boolean;extension:'breve'|'media'|'detallada';instrucciones:string};
type Matriz={permisos:{clave:string;nombre:string}[];perfiles:Record<'ventas'|'gerencia',Record<string,boolean>>};
const blank={username:'',name:'',password:'',role:'ventas' as Rol};

export default function Ajustes(){
 const [me,setMe]=useState<UsuarioSesion|null>(null),[sec,setSec]=useState<Seccion>('preferencias'),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 const [density,setDensity]=useState('comoda');
 const ok=useCallback((m:string)=>{setMessage(m);setError('')},[]),fail=useCallback((m:string)=>{setError(m);setMessage('')},[]);
 const isAdmin=me?.role==='administrador'||(!me&&process.env.NEXT_PUBLIC_AUTH_ENABLED!=='true');
 useEffect(()=>{void fetch('/api/session/me').then(r=>r.ok?r.json():null).then(setMe).catch(()=>{});setDensity(document.documentElement.dataset.density||'comoda');
  const s=new URLSearchParams(window.location.search).get('s');if(s&&SECCIONES.some(([k])=>k===s))setSec(s as Seccion)},[]);
 function pick(s:Seccion){setSec(s);setMessage('');setError('');window.history.replaceState(null,'',`/ajustes?s=${s}`)}
 function changeDensity(v:string){setDensity(v);document.documentElement.dataset.density=v;try{localStorage.setItem('impulso-density',v)}catch{/* sin almacenamiento */}ok('Guardado')}
 const visibles=SECCIONES.filter(([,,admin])=>!admin||isAdmin);
 return <Shell>
  <div className="v2-page-head"><h1>Ajustes</h1></div>
  <div className="v7-settings">
   <nav className="v7-settings-nav" aria-label="Secciones de ajustes">{visibles.map(([k,l])=><button key={k} type="button" className={sec===k?'is-on':''} aria-current={sec===k?'page':undefined} onClick={()=>pick(k)}>{l}</button>)}</nav>
   <div className="v7-settings-body">
    {error&&<p className="alert error" role="alert">{error}</p>}{message&&<p className="v3-success" role="status">{message}</p>}
    {sec==='preferencias'&&<section className="panel v2-admin-list"><div className="v3-section-line"><h3>Preferencias</h3></div>
     <div className="v7-pref-rows">
      <div className="v7-pref-row"><div><strong>Densidad</strong><small>Cuánta información entra en pantalla.</small></div><div className="v7-seg"><button type="button" className={density==='comoda'?'is-on':''} onClick={()=>changeDensity('comoda')}>Cómoda</button><button type="button" className={density==='compacta'?'is-on':''} onClick={()=>changeDensity('compacta')}>Compacta</button></div></div>
     </div>
     {!isAdmin&&me&&<p className="v8-settings-note">Los usuarios, permisos, datos de la empresa y demás ajustes generales los maneja el administrador.</p>}</section>}
    {sec==='usuarios'&&isAdmin&&<Usuarios me={me} ok={ok} fail={fail} busy={busy} setBusy={setBusy}/>}
    {sec==='empresa'&&isAdmin&&<EmpresaPanel ok={ok} fail={fail}/>}
    {sec==='comercial'&&isAdmin&&<ReglasPanel ok={ok} fail={fail}/>}
    {sec==='ia'&&<><MiAsistente ok={ok} fail={fail} admin={isAdmin}/>{isAdmin&&<Asistente ok={ok} fail={fail}/>}</>}
    {sec==='contenido'&&isAdmin&&<><PlantillasPanel ok={ok} fail={fail}/><DocumentosPanel ok={ok} fail={fail}/></>}
    {sec==='chat'&&isAdmin&&<ChatPanel ok={ok} fail={fail}/>}
    {sec==='integraciones'&&isAdmin&&<IntegracionesPanel/>}
    {sec==='datos'&&isAdmin&&<><ImportPanel ok={ok} fail={fail}/><Datos ok={ok} fail={fail}/></>}
   </div>
  </div>
 </Shell>;
}

function Usuarios({me,ok,fail,busy,setBusy}:{me:UsuarioSesion|null;ok:(m:string)=>void;fail:(m:string)=>void;busy:boolean;setBusy:(b:boolean)=>void}){
 const [users,setUsers]=useState<User[]>([]),[matriz,setMatriz]=useState<Matriz|null>(null),[newOpen,setNewOpen]=useState(false),[form,setForm]=useState(blank);
 const load=useCallback(async()=>{try{const [u,m]=await Promise.all([api<User[]>('/api/admin/users'),api<Matriz>('/api/permisos')]);setUsers(u);setMatriz(m)}catch(e){fail(e instanceof Error?e.message:'No se pudo cargar')}},[fail]);
 useEffect(()=>{void load()},[load]);
 async function add(e:React.FormEvent){e.preventDefault();setBusy(true);try{await api('/api/admin/users',{method:'POST',body:JSON.stringify(form)});setForm(blank);setNewOpen(false);ok('Usuario creado');await load()}catch(x){fail(x instanceof Error?x.message:'No se pudo crear')}finally{setBusy(false)}}
 const [edit,setEdit]=useState<{u:User;name:string;role:Rol;active:boolean;password:string}|null>(null),[undo,setUndo]=useState<{u:User;fichas:number[];activo:boolean;texto:string}|null>(null);
 async function save(e:React.FormEvent){e.preventDefault();if(!edit)return;if(edit.password&&edit.password.length<12){fail('La contraseña debe tener al menos 12 caracteres');return}
  setBusy(true);try{await api(`/api/admin/users/${edit.u.id}`,{method:'POST',body:JSON.stringify({name:edit.name.trim(),role:edit.role,active:edit.active,password:edit.password||null})});setEdit(null);setUndo(null);ok(edit.password?'Guardado. La clave nueva ya está activa.':'Guardado');await load()}catch(x){fail(x instanceof Error?x.message:'No se pudo guardar')}finally{setBusy(false)}}
 async function remove(u:User){setBusy(true);try{const r=await api<{fichas:number[];activo:boolean}>(`/api/admin/users/${u.id}/eliminar`,{method:'POST',body:'{}'});setEdit(null);ok('');
  setUndo({u,fichas:r.fichas,activo:r.activo,texto:`${u.name} fue eliminado${r.fichas.length?` y sus ${r.fichas.length} gestion${r.fichas.length===1?'':'es'} abierta${r.fichas.length===1?' quedó':'s quedaron'} sin asignar`:''}.`});await load()}catch(x){fail(x instanceof Error?x.message:'No se pudo eliminar')}finally{setBusy(false)}}
 async function restore(){if(!undo)return;const x=undo;setUndo(null);setBusy(true);try{await api(`/api/admin/users/${x.u.id}/restaurar`,{method:'POST',body:JSON.stringify({fichas:x.fichas,activo:x.activo})});ok(`${x.u.name} volvió`);await load()}catch(e){fail(e instanceof Error?e.message:'No se pudo deshacer')}finally{setBusy(false)}}
 async function toggle(rol:'ventas'|'gerencia',permiso:string,permitido:boolean){if(!matriz)return;setMatriz({...matriz,perfiles:{...matriz.perfiles,[rol]:{...matriz.perfiles[rol],[permiso]:permitido}}});
  try{await api('/api/permisos',{method:'POST',body:JSON.stringify({rol,permiso,permitido})})}catch(x){fail(x instanceof Error?x.message:'No se pudo guardar');void load()}}
 return <>
  <section className="panel v2-admin-list"><div className="v3-section-line"><h3>Usuarios</h3><button className="btn btn-outline btn-sm" type="button" onClick={()=>setNewOpen(true)}><Plus size={14}/> Nuevo usuario</button></div>
   {undo&&<p className="v3-success v9-undo-line" role="status">{undo.texto}<button type="button" className="v7-undo" onClick={()=>void restore()}>Deshacer</button></p>}
   <div className="v9-user-list">{users.map(u=><div key={u.id} className={`v9-user-row ${u.active?'':'is-off'}`}><span className="v2-avatar" aria-hidden="true">{u.name.slice(0,1).toUpperCase()}</span>
    <div className="v9-user-data"><strong>{u.name}{u.id===me?.id&&<small> (vos)</small>}</strong><small>{u.username}{!u.active&&' · inactivo'}</small></div>
    <span className={`v8-role is-${u.role}`}>{roleName[u.role]}</span>
    <div className="v8-row-actions"><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={()=>setEdit({u,name:u.name,role:u.role,active:Boolean(u.active),password:''})}><Pencil size={13}/> Editar</button>
     {u.id!==me?.id&&<button type="button" className="icon-button" title={`Eliminar a ${u.name}`} aria-label={`Eliminar a ${u.name}`} disabled={busy} onClick={()=>void remove(u)}><Trash2 size={15}/></button>}</div></div>)}</div></section>
  {matriz&&<section className="panel v2-admin-list"><div className="v3-section-line"><h3>Permisos por perfil</h3></div>
   <div className="v5-table-wrap"><table className="v5-mini-table v7-perms"><thead><tr><th>Permiso</th><th>Ventas</th><th>Gerencia</th><th>Administrador</th></tr></thead>
    <tbody>{matriz.permisos.map(p=><tr key={p.clave}><td>{p.nombre}</td>{(['ventas','gerencia'] as const).map(r=><td key={r}><input type="checkbox" aria-label={`${p.nombre} para ${roleName[r]}`} checked={!!matriz.perfiles[r][p.clave]} onChange={e=>void toggle(r,p.clave,e.target.checked)}/></td>)}<td><input type="checkbox" checked disabled aria-label="Administrador tiene todos los permisos"/></td></tr>)}</tbody></table></div>
   <p className="muted">El perfil Administrador tiene siempre todos los permisos. Para revisar cómo queda cada perfil, usá "Ver como" en el menú lateral.</p></section>}
  {newOpen&&<div className="modal-backdrop v2-overlay" onMouseDown={()=>setNewOpen(false)}><div className="modal" role="dialog" aria-modal="true" aria-label="Nuevo usuario" onMouseDown={e=>e.stopPropagation()}><div className="modal-head"><h2>Nuevo usuario</h2><button className="icon-button" aria-label="Cerrar" onClick={()=>setNewOpen(false)}><X size={18}/></button></div>
   <form className="fields" onSubmit={e=>void add(e)}><label>Usuario<input required minLength={3} maxLength={60} value={form.username} onChange={e=>setForm({...form,username:e.target.value})}/></label><label>Nombre<input required minLength={2} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><label>Contraseña<input required type="password" minLength={12} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label><label>Perfil<select value={form.role} onChange={e=>setForm({...form,role:e.target.value as Rol})}>{Object.entries(roleName).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label><button className="btn btn-primary" type="submit" disabled={busy}>Crear usuario</button></form></div></div>}
  {edit&&<div className="modal-backdrop v2-overlay" onMouseDown={()=>setEdit(null)}><div className="modal" role="dialog" aria-modal="true" aria-label={`Editar a ${edit.u.name}`} onMouseDown={e=>e.stopPropagation()}><div className="modal-head"><h2>Editar usuario</h2><button className="icon-button" aria-label="Cerrar" onClick={()=>setEdit(null)}><X size={18}/></button></div>
   <form className="fields" onSubmit={e=>void save(e)}>
    <label>Nombre<input required minLength={2} maxLength={120} autoFocus value={edit.name} onChange={e=>setEdit({...edit,name:e.target.value})}/></label>
    <label>Usuario<input value={edit.u.username} disabled/><small className="muted">Es con lo que entra y queda en el historial; no se cambia.</small></label>
    <label>Perfil<select value={edit.role} disabled={edit.u.id===me?.id} onChange={e=>setEdit({...edit,role:e.target.value as Rol})}>{Object.entries(roleName).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
    <label>Clave nueva<input type="password" minLength={12} autoComplete="new-password" placeholder="Dejala vacía para no cambiarla" value={edit.password} onChange={e=>setEdit({...edit,password:e.target.value})}/></label>
    {edit.u.id!==me?.id&&<label className="v3-config-check"><input type="checkbox" checked={edit.active} onChange={e=>setEdit({...edit,active:e.target.checked})}/> Activo <small className="muted">(si lo desactivás no puede entrar; lo podés reactivar cuando quieras)</small></label>}
    <div className="v9-modal-actions">{edit.u.id!==me?.id&&<button type="button" className="btn btn-outline v9-danger" disabled={busy} onClick={()=>void remove(edit.u)}><Trash2 size={14}/> Eliminar usuario</button>}<button className="btn btn-primary" type="submit" disabled={busy}><Check size={15}/> Guardar</button></div>
   </form></div></div>}
 </>;
}

function Asistente({ok,fail}:{ok:(m:string)=>void;fail:(m:string)=>void}){
 const [ai,setAI]=useState<AISettings|null>(null),[busy,setBusy]=useState(false);
 useEffect(()=>{void api<AISettings>('/api/ai/settings').then(setAI).catch(e=>fail(String(e)))},[fail]);
 if(!ai)return <section className="panel v2-admin-list"><p className="muted">Cargando…</p></section>;
 async function save(e:React.FormEvent){e.preventDefault();setBusy(true);try{await api('/api/ai/settings',{method:'POST',body:JSON.stringify(ai)});ok('Guardado')}catch(x){fail(String(x))}finally{setBusy(false)}}
 return <section className="panel v2-admin-list"><div className="v3-section-line"><h3>Configuración de la empresa</h3></div><p className="muted">La base para todos. Las indicaciones y el tratamiento valen para todo el equipo; tono, extensión y signos, cada uno puede cambiarlos para sí.</p><form className="fields" onSubmit={e=>void save(e)}><div className="v3-fields">
  <label>Tono<select value={ai.tono} onChange={e=>setAI({...ai,tono:e.target.value as AISettings['tono']})}><option value="profesional">Profesional y cordial</option><option value="cercano">Cercano</option><option value="formal">Formal</option></select></label>
  <label>Tratamiento<select value={ai.tratamiento} onChange={e=>setAI({...ai,tratamiento:e.target.value as AISettings['tratamiento']})}><option value="vos">Vos</option><option value="ustedes">Ustedes</option><option value="tu">Tú</option></select></label>
  <label>Extensión<select value={ai.extension} onChange={e=>setAI({...ai,extension:e.target.value as AISettings['extension']})}><option value="breve">Breve</option><option value="media">Media</option><option value="detallada">Detallada</option></select></label>
  <label className="v3-config-check"><input type="checkbox" checked={ai.signos_apertura} onChange={e=>setAI({...ai,signos_apertura:e.target.checked})}/> Signos de apertura (¿ ¡)</label>
  <label className="wide">Indicaciones de estilo<textarea rows={3} maxLength={1000} value={ai.instrucciones} onChange={e=>setAI({...ai,instrucciones:e.target.value})} placeholder="Ej.: saludos breves, sin tecnicismos"/></label></div>
  <button type="submit" className="btn btn-primary" disabled={busy}><Check size={16}/> Guardar</button></form></section>;
}

/* Lo que cada uno ajusta para sí: lo que deja en "Como la empresa" usa la base. */
type MisPrefs={base:{tono:string;tratamiento:string;extension:string;signos_apertura:boolean|number};propias:{tono:string|null;extension:string|null;signos_apertura:boolean|null;firma:string}};
const TONOS:Record<string,string>={profesional:'Profesional y cordial',cercano:'Cercano',formal:'Formal'};
const EXTENSIONES:Record<string,string>={breve:'Breve',media:'Media',detallada:'Detallada'};
function MiAsistente({ok,fail,admin}:{ok:(m:string)=>void;fail:(m:string)=>void;admin:boolean}){
 const [p,setP]=useState<MisPrefs|null>(null),[busy,setBusy]=useState(false);
 useEffect(()=>{void api<MisPrefs>('/api/ai/mis-preferencias').then(setP).catch(e=>fail(String(e)))},[fail]);
 if(!p)return <section className="panel v2-admin-list"><p className="muted">Cargando…</p></section>;
 const o=p.propias,b=p.base,set=(x:Partial<MisPrefs['propias']>)=>setP({...p,propias:{...o,...x}});
 async function save(e:React.FormEvent){e.preventDefault();setBusy(true);try{await api('/api/ai/mis-preferencias',{method:'POST',body:JSON.stringify(o)});ok('Guardado')}catch(x){fail(String(x))}finally{setBusy(false)}}
 const signos=o.signos_apertura===null?'':o.signos_apertura?'si':'no';
 return <section className="panel v2-admin-list"><div className="v3-section-line"><h3>Mis respuestas</h3></div>
  <p className="muted">Cómo te sugiere las respuestas el asistente a vos. Lo que dejes en “Como la empresa” sigue la configuración general{admin?' (más abajo)':''}.</p>
  <form className="fields" onSubmit={e=>void save(e)}><div className="v3-fields">
  <label>Tono<select value={o.tono||''} onChange={e=>set({tono:e.target.value||null})}><option value="">Como la empresa ({TONOS[b.tono]||b.tono})</option>{Object.entries(TONOS).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
  <label>Extensión<select value={o.extension||''} onChange={e=>set({extension:e.target.value||null})}><option value="">Como la empresa ({EXTENSIONES[b.extension]||b.extension})</option>{Object.entries(EXTENSIONES).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
  <label>Signos de apertura (¿ ¡)<select value={signos} onChange={e=>set({signos_apertura:e.target.value===''?null:e.target.value==='si'})}><option value="">Como la empresa ({b.signos_apertura?'sí':'no'})</option><option value="si">Sí</option><option value="no">No</option></select></label>
  <label className="wide">Firma<input value={o.firma} maxLength={200} onChange={e=>set({firma:e.target.value})} placeholder="Ej.: Lucía Gómez · Ventas Empresa S.A."/></label></div>
  <button type="submit" className="btn btn-primary" disabled={busy}><Check size={16}/> Guardar</button></form></section>;
}

function Datos({ok,fail}:{ok:(m:string)=>void;fail:(m:string)=>void}){
 const [busy,setBusy]=useState(false),[dups,setDups]=useState<{gestiones:{origen:string;destino:string;cliente:string}[];contactos:{origen:number;destino:number;cliente:string}[]}|null>(null);
 async function seed(){setBusy(true);try{const r=await api<{added:number}>('/api/demo/seed',{method:'POST',body:JSON.stringify({incluir_web:true})});ok(r.added?`${r.added} consultas agregadas`:'Ya estaban cargadas')}catch(e){fail(String(e))}finally{setBusy(false)}}
 async function preview(){setBusy(true);try{setDups(await api('/api/admin/duplicados'))}catch(e){fail(String(e))}finally{setBusy(false)}}
 async function unify(){if(!window.confirm('¿Unificar las gestiones y los contactos duplicados? No se borra nada.'))return;setBusy(true);try{const r=await api<{gestiones_fusionadas:number;contactos_unificados:number}>('/api/admin/duplicados/unificar',{method:'POST'});ok(`${r.gestiones_fusionadas} gestiones y ${r.contactos_unificados} contactos unificados`);setDups(null)}catch(e){fail(String(e))}finally{setBusy(false)}}
 return <>
  <section className="panel v2-admin-list"><div className="v3-section-line"><h3>Datos de prueba</h3></div><p className="muted">40 consultas ficticias de WhatsApp, Email y formulario web. Si ya están cargadas no se duplican.</p><button className="btn btn-outline" disabled={busy} onClick={()=>void seed()}><Plus size={15}/> Cargar ejemplos</button></section>
  <section className="panel v2-admin-list"><div className="v3-section-line"><h3>Unificar duplicados</h3></div><p className="muted">Une gestiones abiertas y contactos de la misma empresa. No se borra nada.</p>
   <div className="v5-inline"><button className="btn btn-outline" disabled={busy} onClick={()=>void preview()}>Revisar duplicados</button>{dups&&(dups.gestiones.length||dups.contactos.length)?<button className="btn btn-primary" disabled={busy} onClick={()=>void unify()}>Unificar {dups.gestiones.length} gestiones y {dups.contactos.length} contactos</button>:null}</div>
   {dups&&!dups.gestiones.length&&!dups.contactos.length&&<p className="muted">No hay duplicados.</p>}
   {dups&&!!dups.gestiones.length&&<ul className="v5-dup-list">{dups.gestiones.slice(0,30).map(g=><li key={g.origen}>{g.cliente}: {g.origen} → {g.destino}</li>)}</ul>}</section>
 </>;
}
