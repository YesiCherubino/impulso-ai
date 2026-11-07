'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {BarChart3,CalendarClock,ArrowRight,RefreshCw} from 'lucide-react';
import Shell from '@/components/shell';
import {api} from '@/lib/api';
type Prioridad={id:number;cliente:string;dias_sin_contacto:number;accion:string};
type Resumen={titulo:string;oportunidades_activas:number;seguimientos_pendientes:number;prioridades:Prioridad[];criterio:string};
export default function ResumenGerencial(){
 const [data,setData]=useState<Resumen|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
 async function load(){setLoading(true);setError('');try{setData(await api<Resumen>('/api/management-summary'))}catch(e){setError(e instanceof Error?e.message:'Error al cargar el resumen')}finally{setLoading(false)}}
 useEffect(()=>{void load()},[]);
 return <Shell><div className="page-head"><div><div className="eyebrow">GERENCIA <span className="eyebrow-line"/></div><h1>Resumen comercial <BarChart3 className="wave" size={24}/></h1><p>Las prioridades del equipo, basadas en actividad registrada.</p></div><button className="btn btn-outline" onClick={()=>void load()}><RefreshCw size={16}/> Actualizar</button></div>
 {error&&<div className="alert error">{error}</div>}
 <div className="stat-grid"><div className="panel ai-box"><div className="section-eyebrow">OPORTUNIDADES ABIERTAS</div><h2 style={{fontSize:38,marginTop:16}}>{data?.oportunidades_activas??'—'}</h2></div><div className="panel ai-box"><div className="section-eyebrow">SEGUIMIENTOS PENDIENTES</div><h2 style={{fontSize:38,marginTop:16}}>{data?.seguimientos_pendientes??'—'}</h2></div></div>
 <section className="panel ai-box"><div className="section-eyebrow">PRIORIDADES DEL DÍA</div><h2><CalendarClock size={21}/> Oportunidades que requieren atención</h2><p className="muted">{data?.criterio??'Preparando información...'}</p>{loading&&<p className="muted">Cargando prioridades...</p>}{!loading&&data?.prioridades.length===0&&<p>Sin seguimientos pendientes.</p>}{data?.prioridades.map(p=><div key={p.id} style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'18px 0',borderBottom:'1px solid #e6ede8',gap:16}}><div><strong>{p.cliente}</strong><p className="muted">{p.dias_sin_contacto} días sin contacto · {p.accion}</p></div><Link className="btn btn-outline" href={`/oportunidades/${p.id}`}>Abrir ficha <ArrowRight size={16}/></Link></div>)}</section>
 <p className="form-hint">Datos ficticios. Este informe utiliza reglas de negocio; no calcula predicciones con IA ni consume créditos de OpenAI.</p></Shell>
}
