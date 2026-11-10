'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {Target,TrendingUp} from 'lucide-react';
import {api,cotizacionTexto,estadoGestionNombre,UsuarioSesion} from '@/lib/api';

type Data={mes:string;vendedores:{usuario:string;nombre:string;metas:Record<string,number>;real:Record<string,number>;concretadas:number;no_concretadas:number;conversion:number|null;tiempo_respuesta_horas:number|null}[];
 pronostico:Record<string,number>;pronostico_detalle:{estado:string;moneda:string;monto:number;probabilidad:number}[];nota:string};
const pct=(real:number,meta:number)=>meta?Math.round(100*real/meta):0;

/* Metas del mes por vendedor y pronóstico ponderado del pipeline abierto. */
export default function GoalsReport({user}:{user:UsuarioSesion|null}){
 const [mes,setMes]=useState(new Date().toISOString().slice(0,7)),[d,setD]=useState<Data|null>(null),[error,setError]=useState('');
 useEffect(()=>{void api<Data>(`/api/metas?mes=${mes}`).then(x=>{setD(x);setError('')}).catch(e=>setError(e instanceof Error?e.message:'No se pudieron cargar las metas'))},[mes]);
 const hasGoals=d?.vendedores.some(v=>Object.keys(v.metas).length);
 return <section className="panel v5-report-grid" id="metas">
  <div className="v5-report-block is-wide"><div className="v3-section-line"><h3><Target size={17}/> Metas y desempeño por vendedor</h3><input type="month" aria-label="Mes" value={mes} onChange={e=>setMes(e.target.value)}/></div>
   {error&&<p className="alert error">{error}</p>}
   {d&&<div className="v5-table-wrap"><table className="v5-mini-table"><thead><tr><th>Vendedor</th><th>Concretado</th><th>Meta</th><th>Avance</th><th title="Concretadas / no concretadas">Cierres</th><th>Conv.</th><th title="Tiempo promedio de primera respuesta">1.ª resp.</th></tr></thead>
    <tbody>{d.vendedores.map(v=>{const monedas=Array.from(new Set([...Object.keys(v.metas),...Object.keys(v.real)]));return <tr key={v.usuario}><td>{v.nombre}</td>
     <td>{monedas.length?monedas.map(m=><span className="v5-amount" key={m}>{cotizacionTexto(v.real[m]||0,m)}</span>):'—'}</td>
     <td>{Object.keys(v.metas).length?Object.entries(v.metas).map(([m,x])=><span className="v5-amount" key={m}>{cotizacionTexto(x,m)}</span>):'—'}</td>
     <td>{Object.entries(v.metas).map(([m,x])=>{const p=pct(v.real[m]||0,x);return <span key={m} className="v6-goal-cell"><span className="v6-bar"><span style={{width:`${Math.min(100,p)}%`}}/></span><small>{p}% {m}</small></span>})}{!Object.keys(v.metas).length&&'—'}</td>
     <td>{v.concretadas} / {v.no_concretadas}</td><td>{v.conversion==null?'—':`${v.conversion}%`}</td><td>{v.tiempo_respuesta_horas==null?'—':`${v.tiempo_respuesta_horas.toLocaleString('es-AR')} h`}</td></tr>})}</tbody></table></div>}
   {d&&!hasGoals&&<small className="muted">No hay metas cargadas para este mes.{user?.role==='administrador'?<> <Link href="/administracion?tab=metas">Cargarlas en Administración</Link>.</>:''}</small>}
  </div>
  {d&&<div className="v5-report-block is-wide"><h3><TrendingUp size={17}/> Pronóstico del pipeline abierto</h3>
   <div className="v6-forecast">{Object.entries(d.pronostico).filter(([,v])=>v>0).map(([m,v])=><div key={m}><small>Ponderado {m}</small><strong>{cotizacionTexto(Math.round(v),m)}</strong></div>)}{!Object.values(d.pronostico).some(v=>v>0)&&<p className="muted">No hay gestiones abiertas con monto cotizado.</p>}</div>
   {!!d.pronostico_detalle.length&&<div className="v5-table-wrap"><table className="v5-mini-table"><thead><tr><th>Etapa</th><th>Cotizado</th><th>Probabilidad</th><th>Ponderado</th></tr></thead><tbody>{d.pronostico_detalle.map(x=><tr key={x.estado+x.moneda}><td>{estadoGestionNombre[x.estado]}</td><td>{cotizacionTexto(x.monto,x.moneda)}</td><td>{x.probabilidad}%</td><td>{cotizacionTexto(Math.round(x.monto*x.probabilidad/100),x.moneda)}</td></tr>)}</tbody></table></div>}
   <small className="muted">{d.nota}</small></div>}
 </section>;
}
