'use client';
import {useRouter} from 'next/navigation';
import {useCallback,useEffect,useState} from 'react';
import {Search,RotateCcw,Loader2,UserRound,UserPlus} from 'lucide-react';
import Shell from '@/components/shell';
import {SkFilas} from '@/components/skeleton';
import ExportButton from '@/components/export-button';
import CaseDialog from '@/components/case-dialog';
import {api,qs,FichaConsulta,Pagina,UsuarioSesion,cotizacionTexto,fechaCorta,puede} from '@/lib/api';
type Filtro='cerradas'|'concretada'|'no_concretada'|'resuelta';
const names:Record<string,string>={concretada:'Concretada',no_concretada:'No concretada',resuelta:'Resuelta'};
const PAGE=50;
export default function Finalizados(){
 const router=useRouter();
 const [items,setItems]=useState<FichaConsulta[]>([]),[total,setTotal]=useState(0),[conteos,setConteos]=useState<Record<string,number>>({}),[selected,setSelected]=useState<number|null>(null),[user,setUser]=useState<UsuarioSesion|null>(null);
 const [error,setError]=useState(''),[search,setSearch]=useState(''),[query,setQuery]=useState(''),[filtro,setFiltro]=useState<Filtro>('cerradas'),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[more,setMore]=useState(false);
 // Paginado en el servidor: con años de historia no se cargan todas las gestiones cerradas.
 const load=useCallback(async()=>{setLoading(true);try{const page=await api<Pagina<FichaConsulta>>(`/api/fichas-search?${qs({estado:filtro,q:query,limit:PAGE,offset:0})}`);setItems(page.items);setTotal(page.total);setConteos(page.conteos||{});setError('')}catch(e){setError(e instanceof Error?e.message:'No se pudieron cargar las gestiones')}finally{setLoading(false)}},[filtro,query]);
 useEffect(()=>{void fetch('/api/session/me').then(r=>r.ok?r.json():null).then(setUser).catch(()=>{})},[]);
 useEffect(()=>{const t=setTimeout(()=>setQuery(search.trim()),300);return()=>clearTimeout(t)},[search]);
 useEffect(()=>{void load()},[load]);
 async function loadMore(){setMore(true);try{const page=await api<Pagina<FichaConsulta>>(`/api/fichas-search?${qs({estado:filtro,q:query,limit:PAGE,offset:items.length})}`);setItems(old=>[...old,...page.items]);setTotal(page.total)}catch(e){setError(String(e))}finally{setMore(false)}}
 async function reactivate(id:number){setBusy(true);try{await api(`/api/fichas/${id}/estado`,{method:'POST',body:JSON.stringify({estado:'calificada'})});await load()}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function contacto(c:FichaConsulta){if(c.oportunidad_id){router.push(`/oportunidades/${c.oportunidad_id}`);return}setBusy(true);try{const r=await api<{oportunidad_id:number}>(`/api/fichas/${c.id}/crear-contacto`,{method:'POST',body:'{}'});router.push(`/oportunidades/${r.oportunidad_id}`)}catch(e){setError(e instanceof Error?e.message:'No se pudo crear el contacto');setBusy(false)}}
 const stop=(e:React.SyntheticEvent)=>e.stopPropagation();
 const count=(k:Filtro)=>k==='cerradas'?(conteos.concretada||0)+(conteos.no_concretada||0)+(conteos.resuelta||0):(conteos[k]||0);
 return <Shell><div className="v2-page-head"><h1>Finalizados</h1>{puede(user,'exportar')&&<ExportButton path={`/api/export/gestiones?${qs({estado:filtro,q:query})}`} onError={setError}/>}</div>{error&&<p className="alert error" role="alert">{error}</p>}
 <section className="panel v2-contact-table"><div className="v2-inbox-toolbar"><div className="v3-switch">{([{value:'cerradas',label:'Todos'},{value:'concretada',label:'Concretadas'},{value:'no_concretada',label:'No concretadas'},{value:'resuelta',label:'Resueltas'}] as const).map(f=><button key={f.value} className={filtro===f.value?'selected':''} onClick={()=>setFiltro(f.value)}>{f.label} {count(f.value).toLocaleString('es-AR')}</button>)}</div><label className="search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar contacto o gestión"/></label></div>
 <div className="table-scroll"><table><thead><tr><th>Gestión</th><th>Contacto</th><th>Resultado</th><th>Cierre</th><th></th></tr></thead><tbody>{loading&&!items.length&&<SkFilas cols={5}/>}{items.map(c=><tr key={c.id} className="v8-row" tabIndex={0} onClick={()=>setSelected(c.id)} onKeyDown={e=>{if(e.key==='Enter'&&e.target===e.currentTarget)setSelected(c.id)}} title="Abrir la gestión"><td><strong>{c.codigo}</strong> · {c.titulo||c.producto||'Gestión comercial'}</td><td>{c.cliente}<small>{c.contacto}</small></td><td><span className={`v7-result is-${c.estado_gestion}`}>{names[c.estado_gestion||'']||'—'}</span>{(c.motivo_cierre||c.cotizacion_monto!=null)&&<small>{[c.estado_gestion==='no_concretada'?c.motivo_cierre:'',c.cotizacion_monto!=null?cotizacionTexto(c.cotizacion_monto,c.cotizacion_moneda):''].filter(Boolean).join(' · ')}</small>}</td><td>{fechaCorta(c.cerrada_en,false)||'—'}</td><td onClick={stop}><div className="v8-row-actions">{(c.oportunidad_id||puede(user,'contactos'))&&<button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={()=>void contacto(c)} title={c.oportunidad_id?'Abrir la ficha del contacto':'Crear el contacto con los datos de la gestión'}>{c.oportunidad_id?<><UserRound size={13}/> Ver contacto</>:<><UserPlus size={13}/> Crear contacto</>}</button>}{puede(user,'gestionar')&&<button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={()=>void reactivate(c.id)} title="Volver a abrir la gestión"><RotateCcw size={13}/> Reactivar</button>}</div></td></tr>)}</tbody></table>{!loading&&!items.length&&<p className="empty muted">No hay gestiones para estos filtros.</p>}</div>
 {items.length<total&&<button type="button" className="btn btn-outline v5-load-more" onClick={()=>void loadMore()} disabled={more}>{more?<><Loader2 size={15} className="v5-spin"/> Cargando…</>:`Cargar ${Math.min(PAGE,total-items.length)} más`}</button>}
 <div className="table-foot">{loading?'Cargando…':`${total.toLocaleString('es-AR')} gestiones${items.length<total?` · mostrando ${items.length.toLocaleString('es-AR')}`:''}`}</div></section>
 {selected!==null&&<CaseDialog fichaId={selected} readOnly={!puede(user,'gestionar')} allowMove onClose={()=>{setSelected(null);void load()}}/>}</Shell>;
}
