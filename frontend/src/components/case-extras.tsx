'use client';
import {ChevronDown} from 'lucide-react';
import {FichaConsulta,estadoGestionNombre,tipoConsultaNombre,unidades,fechaCorta} from '@/lib/api';

export type Historial={estado:string;creada_en:string;tramos:{estado:string;desde:string;hasta:string|null;dias:number;actual?:boolean}[];
 eventos:{id:number;tipo:string;valor:string;detalle:string;usuario:string;creado_en:string}[]};

const ETAPAS=['sin_atender','calificada','cotizada','muestra_piloto','concretada'];
const dias=(n:number)=>n===0?'hoy':n===1?'1 día':`${n} días`;

/* Línea de vida: las etapas de la gestión con los días que pasó en cada una, y el historial de cambios. */
export function CaseTimeline({data,open,onToggle,ownerName}:{data:Historial;open:boolean;onToggle:()=>void;ownerName:(u?:string)=>string}){
 const closedBad=['no_concretada','resuelta'].includes(data.estado);
 const byState=new Map<string,number>();data.tramos.forEach(t=>byState.set(t.estado,(byState.get(t.estado)||0)+t.dias));
 const reached=new Set(data.tramos.map(t=>t.estado));
 const currentIdx=ETAPAS.indexOf(data.estado);
 const steps=closedBad?[...ETAPAS.slice(0,-1).filter(e=>reached.has(e)),data.estado]:ETAPAS;
 const describe=(e:Historial['eventos'][number])=>{
  if(e.tipo==='estado')return <>pasó a <b>{estadoGestionNombre[e.valor]||e.valor}</b>{e.detalle?` · ${e.detalle}`:''}</>;
  if(e.tipo==='responsable')return e.valor?<>asignó a <b>{ownerName(e.valor)}</b></>:<>dejó la gestión sin asignar</>;
  if(e.tipo==='cotizacion')return <>generó la cotización <b>{e.valor}</b> · {e.detalle}</>;
  if(e.tipo==='derivacion')return e.valor?<>derivó a <b>{e.valor}</b></>:<>quitó la derivación</>;
  if(e.tipo==='contacto')return <>{e.detalle||'vinculó el contacto'}</>;
  if(e.tipo==='aceptacion')return <>{e.detalle} (<b>{e.valor}</b>)</>;
  return <>{e.tipo} {e.valor}</>};
 return <section className="v7-life" aria-label="Línea de vida de la gestión">
  <ol className="v7-life-steps">{steps.map((st,i)=>{const done=reached.has(st)&&st!==data.estado;const cur=st===data.estado;const future=!reached.has(st)&&!cur&&(!closedBad&&i>currentIdx);
   return <li key={st} className={`${done?'is-done':''} ${cur?'is-current':''} ${future?'is-future':''} ${cur&&closedBad&&st==='no_concretada'?'is-lost':''}`}><span className="v7-life-dot"/><span className="v7-life-name">{estadoGestionNombre[st]}</span><span className="v7-life-days">{byState.has(st)?dias(byState.get(st)!):''}</span></li>})}</ol>
  <button type="button" className="v7-life-toggle" aria-expanded={open} onClick={onToggle}>Historial <ChevronDown size={13} style={{transform:open?'rotate(180deg)':undefined}}/></button>
  {open&&<ul className="v7-life-log">{data.eventos.map(e=><li key={e.id}><time>{fechaCorta(e.creado_en)}</time><span>{e.usuario?<b>{ownerName(e.usuario)} </b>:<b>Sistema </b>}{describe(e)}</span></li>)}
   <li><time>{fechaCorta(data.creada_en)}</time><span>Entró la consulta</span></li></ul>}
 </section>;
}

function Envase({tipo}:{tipo:string}){
 const p={fill:'none',stroke:'currentColor',strokeWidth:2,strokeLinejoin:'round' as const,strokeLinecap:'round' as const};
 switch(tipo){
  case 'Doypack':return <svg viewBox="0 0 48 64" aria-hidden="true"><path {...p} d="M10 10h28l3 46a4 4 0 0 1-4 4H11a4 4 0 0 1-4-4z"/><path {...p} d="M10 16h28M20 4h8v6h-8z"/></svg>;
  case 'Pomo':return <svg viewBox="0 0 48 64" aria-hidden="true"><path {...p} d="M12 8h24l-4 44H16z"/><path {...p} d="M19 52h10v8H19zM12 8l2-4h20l2 4"/></svg>;
  case 'Aerosol':return <svg viewBox="0 0 48 64" aria-hidden="true"><rect {...p} x="13" y="16" width="22" height="44" rx="5"/><path {...p} d="M17 16v-5h14v5M22 11V5h7"/></svg>;
  case 'Roll-on':return <svg viewBox="0 0 48 64" aria-hidden="true"><rect {...p} x="14" y="24" width="20" height="36" rx="6"/><path {...p} d="M16 24c0-10 16-10 16 0"/><circle {...p} cx="24" cy="17" r="5"/></svg>;
  case 'Sachet':return <svg viewBox="0 0 48 64" aria-hidden="true"><rect {...p} x="10" y="10" width="28" height="44" rx="2"/><path {...p} d="M10 16h28M10 48h28"/></svg>;
  default:return <svg viewBox="0 0 48 64" aria-hidden="true"><rect {...p} x="12" y="20" width="24" height="40" rx="6"/><path {...p} d="M18 20v-6h12v6M16 8h16v6H16z"/></svg>;
 }
}

/* Ficha visual del proyecto: qué se pide, de un vistazo. */
export function ProjectCard({ficha,etapas}:{ficha:FichaConsulta;etapas:string[]}){
 if(!ficha.producto&&!ficha.envase&&!etapas.length&&!ficha.cantidad)return null;
 return <section className="v7-project" aria-label="Ficha del proyecto">
  <div className="v7-project-art"><Envase tipo={ficha.envase||''}/>{ficha.presentacion&&<span>{ficha.presentacion}</span>}</div>
  <div className="v7-project-body">
   <strong>{ficha.producto||'Producto a definir'}</strong>
   <span className="v7-project-meta">{[tipoConsultaNombre[ficha.tipo_consulta],ficha.rubro,ficha.envase,ficha.cantidad!=null?unidades(ficha.cantidad):'',ficha.tipo_cliente].filter(Boolean).join(' · ')}</span>
   {!!etapas.length&&<ol className="v7-project-steps">{etapas.map(e=><li key={e}>{e}</li>)}</ol>}
  </div>
 </section>;
}
