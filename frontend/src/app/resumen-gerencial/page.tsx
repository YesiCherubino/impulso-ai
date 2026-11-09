'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {ArrowRight,RefreshCw} from 'lucide-react';
import Shell from '@/components/shell';
import {api} from '@/lib/api';
type Prioridad={id:number;cliente:string;dias_sin_contacto:number;accion:string;fecha_seguimiento:string|null};
type Resumen={oportunidades_activas:number;seguimientos_pendientes:number;prioridades:Prioridad[]};
export default function Reportes(){
 const [data,setData]=useState<Resumen|null>(null),[error,setError]=useState('');
 async function load(){setError('');try{setData(await api<Resumen>('/api/management-summary'))}catch(e){setError(e instanceof Error?e.message:'No se pudo cargar el resumen')}}
 useEffect(()=>{void load()},[]);
 return <Shell><div className="page-head simple-head"><h1>Resumen comercial</h1><button className="btn btn-outline" onClick={()=>void load()}><RefreshCw size={16}/> Actualizar</button></div>
 {error&&<div className="alert error">{error}</div>}
 <div className="report-metrics"><div><span>Contactos abiertos</span><strong>{data?.oportunidades_activas??'—'}</strong></div><div><span>Seguimientos pendientes</span><strong>{data?.seguimientos_pendientes??'—'}</strong></div></div>
 <section className="panel report-pending"><h2>Contactos que requieren atención</h2>{data?.prioridades.length===0&&<p className="muted">Sin seguimientos pendientes.</p>}{data?.prioridades.map(p=><div key={p.id} className="report-pending-row"><div><strong>{p.cliente}</strong><p className="muted">{p.fecha_seguimiento?`Seguimiento programado: ${p.fecha_seguimiento.split('-').reverse().join('/')}`:`${p.dias_sin_contacto} días sin contacto`} · {p.accion}</p></div><Link className="btn btn-outline" href={`/oportunidades/${p.id}`}>Abrir ficha <ArrowRight size={15}/></Link></div>)}</section>
 </Shell>;
}
