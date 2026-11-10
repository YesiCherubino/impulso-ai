'use client';
import {useCallback,useEffect,useState} from 'react';
import Link from 'next/link';
import {Search,FileDown,Link2,Check,Loader2,MessageSquareReply} from 'lucide-react';
import Shell from '@/components/shell';
import ExportButton from '@/components/export-button';
import CaseDialog from '@/components/case-dialog';
import {api,qs,ArchivoB64,abrirArchivo,UsuarioSesion,Responsable,fechaCorta,puede,cotizacionTexto} from '@/lib/api';

type Estado='enviada'|'aceptada'|'vencida'|'no_concretada'|'reemplazada';
type Item={id:number;numero:string;fecha:string;vence:string;estado:Estado;moneda:string;total:number;creada_por:string;token:string|null;aceptada_en:string|null;aceptada_por:string|null;ficha_id:number;codigo:string;cliente:string;titulo:string;responsable:string;conversacion:string};
type Resp={total:number;items:Item[];resumen:{cantidad:number;aceptadas:number;tasa:number|null;cotizado:Record<string,number>;aceptado:Record<string,number>;por_estado:Record<Estado,number>}};
const NOMBRES:Record<Estado,string>={enviada:'Enviada',aceptada:'Aceptada',vencida:'Vencida',no_concretada:'No concretada',reemplazada:'Reemplazada'};
const FILTROS:[''|Estado,string][]=[['','Todas'],['enviada','Enviadas'],['aceptada','Aceptadas'],['vencida','Vencidas'],['no_concretada','No concretadas']];
const PERIODOS=[['mes','Este mes'],['trimestre','90 días'],['todos','Todo']];
const PAGE=50;
const montos=(m:Record<string,number>)=>{const e=Object.entries(m);return e.length?e.map(([k,v])=><span key={k}><em>{k}</em> {v.toLocaleString('es-AR',{maximumFractionDigits:0})}</span>):'—'};
const dias=(iso:string)=>Math.round((new Date(`${iso}T23:59:59`).getTime()-Date.now())/864e5);

/* Todas las cotizaciones: qué se cotizó, a quién y en qué quedó. */
export default function Cotizaciones(){
 const [user,setUser]=useState<UsuarioSesion|null>(null),[owners,setOwners]=useState<Responsable[]>([]),[data,setData]=useState<Resp|null>(null),[error,setError]=useState('');
 const [estado,setEstado]=useState<''|Estado>(''),[period,setPeriod]=useState('trimestre'),[vendedor,setVendedor]=useState<string|null>(null),[search,setSearch]=useState(''),[q,setQ]=useState('');
 const [selected,setSelected]=useState<number|null>(null),[copied,setCopied]=useState<number|null>(null),[more,setMore]=useState(false);
 const todas=puede(user,'ver_todas');
 useEffect(()=>{void fetch('/api/session/me').then(r=>r.ok?r.json():null).then((u:UsuarioSesion|null)=>{setUser(u);setVendedor(u&&u.role==='ventas'?u.username:'')}).catch(()=>setVendedor(''));void api<Responsable[]>('/api/users/responsables').then(setOwners).catch(()=>{})},[]);
 useEffect(()=>{const t=setTimeout(()=>setQ(search.trim()),300);return()=>clearTimeout(t)},[search]);
 const params={estado,period,vendedor:todas?vendedor||'':'',q};
 const load=useCallback(async()=>{if(vendedor===null)return;try{setData(await api<Resp>(`/api/cotizaciones?${qs({estado,period,vendedor:todas?vendedor:'',q,limit:PAGE})}`));setError('')}catch(e){setError(e instanceof Error?e.message:'No se pudieron cargar las cotizaciones')}},[estado,period,vendedor,q,todas]);
 useEffect(()=>{void load()},[load]);
 async function loadMore(){if(!data)return;setMore(true);try{const r=await api<Resp>(`/api/cotizaciones?${qs({...params,limit:PAGE,offset:data.items.length})}`);setData({...data,items:[...data.items,...r.items]})}catch(e){setError(String(e))}finally{setMore(false)}}
 async function pdf(i:Item){try{abrirArchivo(await api<ArchivoB64>(`/api/cotizaciones/${i.id}/pdf`))}catch(e){setError(String(e))}}
 async function copy(i:Item){if(!i.token)return;try{await navigator.clipboard.writeText(`${window.location.origin}/c/${i.token}`);setCopied(i.id);setTimeout(()=>setCopied(c=>c===i.id?null:c),2000)}catch{setError('No se pudo copiar el enlace')}}
 const ownerName=(u:string)=>owners.find(o=>o.username===u)?.name||u||'—';
 const r=data?.resumen;
 return <Shell>
  <div className="v2-page-head"><h1>Cotizaciones</h1>{puede(user,'exportar')&&<ExportButton path={`/api/export/cotizaciones?${qs(params)}`} onError={setError}/>}</div>
  {error&&<p className="alert error" role="alert">{error}</p>}
  <section className="panel v8-quote-summary" aria-label="Resumen">
   <div><small>Cotizado</small><strong className="v8-money">{r?montos(r.cotizado):'—'}</strong><span>{r?`${r.cantidad} cotizaci${r.cantidad===1?'ón':'ones'}`:''}</span></div>
   <div><small>Aceptado</small><strong className="v8-money">{r?montos(r.aceptado):'—'}</strong><span>{r?`${r.aceptadas} aceptada${r.aceptadas===1?'':'s'}`:''}</span></div>
   <div><small>Tasa de aceptación</small><strong>{r?.tasa!=null?`${r.tasa}%`:'—'}</strong><span>sobre las que ya tienen resultado</span></div>
  </section>
  <section className="panel v2-contact-table">
   <div className="v2-inbox-toolbar v8-quote-toolbar">
    <div className="v3-switch">{FILTROS.map(([v,l])=><button key={v||'todas'} className={estado===v?'selected':''} onClick={()=>setEstado(v)}>{l}{v&&r?` ${r.por_estado[v]||0}`:''}</button>)}</div>
    <div className="v8-quote-filters">
     <div className="v7-seg" role="group" aria-label="Período">{PERIODOS.map(([v,l])=><button key={v} type="button" className={period===v?'is-on':''} onClick={()=>setPeriod(v)}>{l}</button>)}</div>
     {todas&&vendedor!==null&&<select aria-label="Vendedor" value={vendedor} onChange={e=>setVendedor(e.target.value)}>{user?.role==='ventas'?<><option value={user.username}>Mías</option><option value="">Todo el equipo</option></>:<><option value="">Todos los vendedores</option>{owners.map(o=><option key={o.username} value={o.username}>{o.name}</option>)}</>}</select>}
     <label className="search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar cliente o número"/></label>
    </div>
   </div>
   <div className="table-scroll"><table><thead><tr><th>Cotización</th><th>Cliente</th><th className="v8-num">Total</th><th>Estado</th><th>Cotizó</th><th></th></tr></thead>
    <tbody>{data?.items.map(i=>{const d=dias(i.vence);const abierta=i.estado==='enviada'||i.estado==='vencida';
     return <tr key={i.id} className={`v8-row ${i.estado==='reemplazada'?'is-muted':''}`} tabIndex={0} title="Abrir la gestión" onClick={()=>setSelected(i.ficha_id)} onKeyDown={e=>{if(e.key==='Enter'&&e.target===e.currentTarget)setSelected(i.ficha_id)}}>
      <td><strong>{i.numero}</strong><small>{fechaCorta(i.fecha,false)}</small></td>
      <td>{i.cliente}<small>{i.codigo}{i.titulo?` · ${i.titulo}`:''}</small></td>
      <td className="v8-num">{cotizacionTexto(i.total,i.moneda)}</td>
      <td><span className={`v8-quote-state is-${i.estado}`}>{NOMBRES[i.estado]}</span><small>{i.estado==='aceptada'?(i.aceptada_por?`por ${i.aceptada_por}`:''):i.estado==='enviada'?<span className={d<=3?'v8-soon':''}>{d<=0?'vence hoy':d===1?'vence mañana':`vence en ${d} días`}</span>:i.estado==='vencida'?`venció el ${fechaCorta(i.vence,false)}`:''}</small></td>
      <td>{ownerName(i.creada_por)}</td>
      <td onClick={e=>e.stopPropagation()}><div className="v8-row-actions">
       <button type="button" className="icon-button" title="Abrir PDF" aria-label={`PDF de ${i.numero}`} onClick={()=>void pdf(i)}><FileDown size={15}/></button>
       {i.token&&i.estado!=='reemplazada'&&<button type="button" className="icon-button" title="Copiar enlace para el cliente" aria-label={`Copiar enlace de ${i.numero}`} onClick={()=>void copy(i)}>{copied===i.id?<Check size={15}/>:<Link2 size={15}/>}</button>}
       {abierta&&puede(user,'responder')&&<Link className="icon-button" title="Preparar seguimiento" aria-label={`Preparar seguimiento de ${i.numero}`} href={`/consultas?conversacion=${i.conversacion}&ficha=${i.ficha_id}&seguimiento=1`}><MessageSquareReply size={15}/></Link>}
      </div></td></tr>})}</tbody></table>
    {data&&!data.items.length&&<p className="empty muted">{q||estado?'No hay cotizaciones para estos filtros.':'Todavía no hay cotizaciones. Se generan desde una gestión, con el botón Cotizar.'}</p>}</div>
   {data&&data.items.length<data.total&&<button type="button" className="btn btn-outline v5-load-more" onClick={()=>void loadMore()} disabled={more}>{more?<><Loader2 size={15} className="v5-spin"/> Cargando…</>:`Cargar ${Math.min(PAGE,data.total-data.items.length)} más`}</button>}
   <div className="table-foot">{data?`${data.total.toLocaleString('es-AR')} cotizaci${data.total===1?'ón':'ones'}`:'Cargando…'}</div>
  </section>
  {selected!==null&&<CaseDialog fichaId={selected} readOnly={!puede(user,'gestionar')} allowMove onClose={()=>{setSelected(null);void load()}}/>}
 </Shell>;
}
