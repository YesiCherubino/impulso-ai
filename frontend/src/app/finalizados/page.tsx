'use client';
import Link from 'next/link';
import {useCallback,useEffect,useMemo,useState} from 'react';
import {ArrowUpRight,Search,RotateCcw} from 'lucide-react';
import Shell from '@/components/shell';
import CaseDialog from '@/components/case-dialog';
import {api,FichaConsulta,UsuarioSesion} from '@/lib/api';
type Filtro='todos'|'concretada'|'no_concretada'|'resuelta';
const names:Record<string,string>={concretada:'Concretada',no_concretada:'No concretada',resuelta:'Resuelta'};
export default function Finalizados(){
 const [items,setItems]=useState<FichaConsulta[]>([]),[selected,setSelected]=useState<number|null>(null),[user,setUser]=useState<UsuarioSesion|null>(null);
 const [error,setError]=useState(''),[search,setSearch]=useState(''),[filtro,setFiltro]=useState<Filtro>('todos'),[busy,setBusy]=useState(false);
 const load=useCallback(async()=>{try{setItems(await api<FichaConsulta[]>('/api/fichas'));setError('')}catch(e){setError(e instanceof Error?e.message:'No se pudieron cargar las gestiones')}},[]);
 useEffect(()=>{void load();void fetch('/api/session/me').then(r=>r.ok?r.json():null).then(setUser).catch(()=>{})},[load]);
 const closed=useMemo(()=>items.filter(x=>['concretada','no_concretada','resuelta'].includes(x.estado_gestion||'')),[items]);
 const visible=useMemo(()=>closed.filter(x=>(filtro==='todos'||x.estado_gestion===filtro)&&[x.cliente,x.contacto,x.titulo,x.codigo,x.producto].some(v=>String(v||'').toLocaleLowerCase('es').includes(search.toLocaleLowerCase('es')))).sort((a,b)=>(b.cerrada_en||b.actualizada_en).localeCompare(a.cerrada_en||a.actualizada_en)),[closed,filtro,search]);
 async function reactivate(id:number){setBusy(true);try{await api(`/api/fichas/${id}/estado`,{method:'POST',body:JSON.stringify({estado:'en_gestion'})});await load()}catch(e){setError(String(e))}finally{setBusy(false)}}
 return <Shell><div className="v2-page-head"><h1>Finalizados</h1></div>{error&&<p className="alert error" role="alert">{error}</p>}
 <section className="panel v2-contact-table"><div className="v2-inbox-toolbar"><div className="v3-switch">{([{value:'todos',label:'Todos'},{value:'concretada',label:'Concretadas'},{value:'no_concretada',label:'No concretadas'},{value:'resuelta',label:'Resueltas'}] as const).map(f=><button key={f.value} className={filtro===f.value?'selected':''} onClick={()=>setFiltro(f.value)}>{f.label} {f.value==='todos'?closed.length:closed.filter(c=>c.estado_gestion===f.value).length}</button>)}</div><label className="search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar contacto o gestión"/></label></div>
 <div className="table-scroll"><table><thead><tr><th>GESTIÓN</th><th>CONTACTO</th><th>RESULTADO</th><th>FECHA DE CIERRE</th><th></th></tr></thead><tbody>{visible.map(c=><tr key={c.id}><td><button className="v3-text-action" onClick={()=>setSelected(c.id)}><strong>{c.codigo}</strong> · {c.titulo||c.producto||'Gestión comercial'}</button></td><td>{c.cliente}<small>{c.contacto}</small></td><td><span className={`v2-state ${c.estado_gestion==='concretada'?'resuelta':c.estado_gestion==='no_concretada'?'nueva':'en_gestion'}`}>{names[c.estado_gestion||'']||'—'}</span></td><td>{c.cerrada_en?new Date(c.cerrada_en).toLocaleDateString('es-AR'):'—'}</td><td><div className="v3-thread-tools">{c.oportunidad_id&&<Link href={`/oportunidades/${c.oportunidad_id}`} aria-label={`Ver contacto ${c.cliente}`}><ArrowUpRight size={16}/></Link>}{user?.role!=='gerencia'&&<button className="v3-text-action" disabled={busy} onClick={()=>void reactivate(c.id)} title="Reactivar gestión"><RotateCcw size={15}/> Reactivar</button>}</div></td></tr>)}</tbody></table>{!visible.length&&<p className="empty muted">No hay gestiones para estos filtros.</p>}</div><div className="table-foot">{visible.length} gestiones</div></section>
 {selected!==null&&<CaseDialog fichaId={selected} readOnly={user?.role==='gerencia'} allowMove onClose={()=>{setSelected(null);void load()}}/>}</Shell>;
}
