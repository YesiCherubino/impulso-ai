'use client';
import Link from 'next/link';
import {useCallback,useEffect,useState} from 'react';
import {ArrowUpRight,Search,RotateCcw,Loader2} from 'lucide-react';
import Shell from '@/components/shell';
import CaseDialog from '@/components/case-dialog';
import {api,qs,FichaConsulta,Pagina,UsuarioSesion,cotizacionTexto} from '@/lib/api';
type Filtro='cerradas'|'concretada'|'no_concretada'|'resuelta';
const names:Record<string,string>={concretada:'Concretada',no_concretada:'No concretada',resuelta:'Resuelta'};
const PAGE=50;
export default function Finalizados(){
 const [items,setItems]=useState<FichaConsulta[]>([]),[total,setTotal]=useState(0),[conteos,setConteos]=useState<Record<string,number>>({}),[selected,setSelected]=useState<number|null>(null),[user,setUser]=useState<UsuarioSesion|null>(null);
 const [error,setError]=useState(''),[search,setSearch]=useState(''),[query,setQuery]=useState(''),[filtro,setFiltro]=useState<Filtro>('cerradas'),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[more,setMore]=useState(false);
 // Paginado en el servidor: con años de historia no se cargan todas las gestiones cerradas.
 const load=useCallback(async()=>{setLoading(true);try{const page=await api<Pagina<FichaConsulta>>(`/api/fichas-search?${qs({estado:filtro,q:query,limit:PAGE,offset:0})}`);setItems(page.items);setTotal(page.total);setConteos(page.conteos||{});setError('')}catch(e){setError(e instanceof Error?e.message:'No se pudieron cargar las gestiones')}finally{setLoading(false)}},[filtro,query]);
 useEffect(()=>{void fetch('/api/session/me').then(r=>r.ok?r.json():null).then(setUser).catch(()=>{})},[]);
 useEffect(()=>{const t=setTimeout(()=>setQuery(search.trim()),300);return()=>clearTimeout(t)},[search]);
 useEffect(()=>{void load()},[load]);
 async function loadMore(){setMore(true);try{const page=await api<Pagina<FichaConsulta>>(`/api/fichas-search?${qs({estado:filtro,q:query,limit:PAGE,offset:items.length})}`);setItems(old=>[...old,...page.items]);setTotal(page.total)}catch(e){setError(String(e))}finally{setMore(false)}}
 async function reactivate(id:number){setBusy(true);try{await api(`/api/fichas/${id}/estado`,{method:'POST',body:JSON.stringify({estado:'calificada'})});await load()}catch(e){setError(String(e))}finally{setBusy(false)}}
 const count=(k:Filtro)=>k==='cerradas'?(conteos.concretada||0)+(conteos.no_concretada||0)+(conteos.resuelta||0):(conteos[k]||0);
 return <Shell><div className="v2-page-head"><h1>Finalizados</h1></div>{error&&<p className="alert error" role="alert">{error}</p>}
 <section className="panel v2-contact-table"><div className="v2-inbox-toolbar"><div className="v3-switch">{([{value:'cerradas',label:'Todos'},{value:'concretada',label:'Concretadas'},{value:'no_concretada',label:'No concretadas'},{value:'resuelta',label:'Resueltas'}] as const).map(f=><button key={f.value} className={filtro===f.value?'selected':''} onClick={()=>setFiltro(f.value)}>{f.label} {count(f.value).toLocaleString('es-AR')}</button>)}</div><label className="search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar contacto o gestión"/></label></div>
 <div className="table-scroll"><table><thead><tr><th>GESTIÓN</th><th>CONTACTO</th><th>RESULTADO</th><th>FECHA DE CIERRE</th><th></th></tr></thead><tbody>{items.map(c=><tr key={c.id}><td><button className="v3-text-action" onClick={()=>setSelected(c.id)}><strong>{c.codigo}</strong> · {c.titulo||c.producto||'Gestión comercial'}</button></td><td>{c.cliente}<small>{c.contacto}</small></td><td><span className={`v2-state ${c.estado_gestion==='concretada'?'resuelta':c.estado_gestion==='no_concretada'?'nueva':'en_gestion'}`}>{names[c.estado_gestion||'']||'—'}</span>{c.motivo_cierre&&<small>{c.motivo_cierre}</small>}{c.cotizacion_monto!=null&&<small>{cotizacionTexto(c.cotizacion_monto,c.cotizacion_moneda)}</small>}</td><td>{c.cerrada_en?new Date(c.cerrada_en).toLocaleDateString('es-AR'):'—'}</td><td><div className="v3-thread-tools">{c.oportunidad_id&&<Link href={`/oportunidades/${c.oportunidad_id}`} aria-label={`Ver contacto ${c.cliente}`}><ArrowUpRight size={16}/></Link>}{user?.role!=='gerencia'&&<button className="v3-text-action" disabled={busy} onClick={()=>void reactivate(c.id)} title="Reactivar gestión"><RotateCcw size={15}/> Reactivar</button>}</div></td></tr>)}</tbody></table>{!loading&&!items.length&&<p className="empty muted">No hay gestiones para estos filtros.</p>}</div>
 {items.length<total&&<button type="button" className="btn btn-outline v5-load-more" onClick={()=>void loadMore()} disabled={more}>{more?<><Loader2 size={15} className="v5-spin"/> Cargando…</>:`Cargar ${Math.min(PAGE,total-items.length)} más`}</button>}
 <div className="table-foot">{loading?'Cargando…':`${total.toLocaleString('es-AR')} gestiones${items.length<total?` · mostrando ${items.length.toLocaleString('es-AR')}`:''}`}</div></section>
 {selected!==null&&<CaseDialog fichaId={selected} readOnly={user?.role==='gerencia'} allowMove onClose={()=>{setSelected(null);void load()}}/>}</Shell>;
}
