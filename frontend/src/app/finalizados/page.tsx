'use client';
import Link from 'next/link';
import {useCallback,useEffect,useMemo,useState} from 'react';
import {ArrowUpRight,RefreshCw,Search} from 'lucide-react';
import Shell from '@/components/shell';
import {api,Oportunidad,estadoNombre,money,dateAR} from '@/lib/api';

type Filtro='todos'|'ganada'|'perdida';
export default function FinalizadosPage(){
 const [items,setItems]=useState<Oportunidad[]>([]);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState('');
 const [search,setSearch]=useState('');
 const [filtro,setFiltro]=useState<Filtro>('todos');
 const load=useCallback(async()=>{
  setLoading(true);setError('');
  try{setItems(await api<Oportunidad[]>('/api/opportunities'))}
  catch(e){setError(e instanceof Error?e.message:'No se pudieron cargar los contactos')}
  finally{setLoading(false)}
 },[]);
 useEffect(()=>{void load()},[load]);
 const closed=useMemo(()=>items.filter(x=>x.estado==='ganada'||x.estado==='perdida'),[items]);
 const visible=useMemo(()=>closed.filter(x=>{
  const matchesState=filtro==='todos'||x.estado===filtro;
  const q=search.trim().toLocaleLowerCase('es');
  const matchesText=[x.cliente,x.contacto,x.producto].some(v=>v.toLocaleLowerCase('es').includes(q));
  return matchesState&&matchesText;
 }).sort((a,b)=>b.ultimo_contacto.localeCompare(a.ultimo_contacto)||b.id-a.id),[closed,filtro,search]);
 const ganados=closed.filter(x=>x.estado==='ganada').length;
 const perdidos=closed.length-ganados;
 return <Shell>
  <div className="page-head simple-head"><h1>Contactos finalizados</h1><button type="button" className="btn btn-outline" onClick={()=>void load()}><RefreshCw size={16}/> Actualizar</button></div>
  {error&&<div className="alert error" role="alert">{error}<button onClick={()=>void load()}>Reintentar</button></div>}
  <section className="panel table-panel compact-contact-table" aria-label="Listado de contactos finalizados">
   <div className="finalizados-toolbar">
    <div className="finalizados-tabs" role="group" aria-label="Filtrar contactos finalizados">
     {([{key:'todos',label:'Todos',count:closed.length},{key:'ganada',label:'Ganados',count:ganados},{key:'perdida',label:'Perdidos',count:perdidos}] as const).map(tab=><button key={tab.key} type="button" className={`finalizados-tab ${filtro===tab.key?'is-selected':''}`} aria-pressed={filtro===tab.key} onClick={()=>setFiltro(tab.key)}>{tab.label} <span>{tab.count}</span></button>)}
    </div>
    <label className="search finalizados-search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar cliente, contacto o producto" aria-label="Buscar contactos finalizados"/></label>
   </div>
   <div className="table-scroll"><table><thead><tr><th>CLIENTE</th><th>PRODUCTO</th><th>RESULTADO</th><th>VALOR ESTIMADO</th><th>ÚLTIMO CONTACTO</th><th></th></tr></thead><tbody>{visible.map(o=><tr key={o.id}>
    <td data-label="Cliente"><Link className="table-client" href={`/oportunidades/${o.id}`}><span><strong>{o.cliente}</strong><small>{o.contacto}</small></span></Link></td>
    <td data-label="Producto">{o.producto}</td>
    <td data-label="Resultado"><span className={`status status-${o.estado}`}>{estadoNombre[o.estado]}</span></td>
    <td data-label="Valor estimado" className="value">{money(o.monto_estimado_usd)}</td>
    <td data-label="Último contacto">{dateAR(o.ultimo_contacto)}</td>
    <td><Link href={`/oportunidades/${o.id}`} className="row-link" aria-label={`Abrir ${o.cliente}`}><ArrowUpRight size={16}/></Link></td>
   </tr>)}</tbody></table>{!visible.length&&<p className="empty muted">{loading?'Cargando contactos...':'No hay contactos con los filtros seleccionados.'}</p>}</div>
   <div className="table-foot">{visible.length} de {closed.length} contactos finalizados</div>
  </section>
 </Shell>;
}
