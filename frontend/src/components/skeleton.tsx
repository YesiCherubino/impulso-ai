'use client';
/* Esqueletos de carga: la forma de lo que viene, en gris suave con un brillo que pasa.
   No llevan texto; el lector de pantalla recibe un único "Cargando" por bloque. */
import {useEffect,useRef,useState} from 'react';
import {usePathname} from 'next/navigation';
import ImpulsoMark from '@/components/impulso-mark';

const Sk=({w='100%',h=12,r=6,className=''}:{w?:number|string;h?:number;r?:number;className?:string})=>
 <span className={`v11-sk ${className}`} style={{width:w,height:h,borderRadius:r}} aria-hidden="true"/>;
export default Sk;

const anchos=['72%','58%','84%','64%','77%','52%','69%','81%'];

/** Lista de conversaciones (Bandeja). */
export function SkConversaciones({n=7}:{n?:number}){
 return <div className="v11-sk-block" role="status" aria-label="Cargando">{Array.from({length:n},(_,i)=><div key={i} className="v11-sk-conv">
  <Sk w={36} h={36} r={18}/><span className="v11-sk-lines"><Sk w="45%" h={13}/><Sk w={anchos[i%8]} h={10}/><Sk w="30%" h={10}/></span><Sk w={28} h={10}/></div>)}</div>;
}

/** Conversación abierta: burbujas a uno y otro lado. */
export function SkChat(){
 return <div className="v11-sk-chat" role="status" aria-label="Cargando conversación">
  {[['in','62%',58],['out','54%',44],['in','70%',72],['out','40%',36]].map(([lado,w,h],i)=><div key={i} className={`v11-sk-bubble is-${lado}`}><Sk w={w as string} h={h as number} r={12}/></div>)}</div>;
}

/** Filas de tabla (Contactos, Finalizados, Cotizaciones). */
export function SkFilas({n=8,cols}:{n?:number;cols:number}){
 return <>{Array.from({length:n},(_,i)=><tr key={i} className="v11-sk-row" aria-hidden="true">{Array.from({length:cols},(_,j)=><td key={j}>
  {j===0?<span className="v11-sk-lines"><Sk w="70%" h={12}/><Sk w="45%" h={10}/></span>:<Sk w={j===cols-1?'50%':anchos[(i+j)%8]} h={11}/>}</td>)}</tr>)}</>;
}

/** Tablero de Mi día: dos columnas con tarjetas. */
export function SkTablero(){
 const col=(n:number)=><div className="v11-sk-col">{[0,1].map(i=><Sk key={i} w={i?'26%':'38%'} h={i?10:14}/>)}{Array.from({length:n},(_,i)=><div key={i} className="v11-sk-card"><Sk w="55%" h={13}/><Sk w={anchos[i%8]} h={10}/><span className="v11-sk-chips"><Sk w={64} h={18} r={9}/><Sk w={80} h={18} r={9}/></span></div>)}</div>;
 return <div className="v11-sk-board" role="status" aria-label="Cargando">{col(4)}{col(3)}</div>;
}

/** Bloque genérico de texto (paneles de Ajustes, ficha). */
export function SkPanel({lineas=4}:{lineas?:number}){
 return <div className="v11-sk-panel" role="status" aria-label="Cargando"><Sk w="32%" h={16}/>{Array.from({length:lineas},(_,i)=><Sk key={i} w={anchos[i%8]} h={11}/>)}</div>;
}

/** Pantalla de entrada: el logo con las barras latiendo. Solo aparece si la carga tarda. */
export function CargaInicial(){
 const [ver,setVer]=useState(false);
 useEffect(()=>{const t=setTimeout(()=>setVer(true),250);return()=>clearTimeout(t)},[]);
 return <div className="v11-splash" role="status" aria-label="Cargando Impulso Comercial">{ver&&<div className="v11-splash-in"><span className="v11-splash-mark"><ImpulsoMark size={44}/></span><span className="v10-wordmark"><strong>Impulso</strong><small>Comercial</small></span></div>}</div>;
}

/** Barra fina arriba mientras se cambia de sección. */
export function BarraNavegacion(){
 const pathname=usePathname();
 const [estado,setEstado]=useState<'off'|'on'|'fin'>('off');
 const prev=useRef(pathname);
 useEffect(()=>{const onClick=(e:MouseEvent)=>{
   if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
   const a=(e.target as HTMLElement)?.closest?.('a');if(!a||a.target==='_blank'||a.hasAttribute('download'))return;
   const url=new URL(a.href,location.href);if(url.origin!==location.origin||url.pathname===location.pathname||/\.[a-z0-9]+$/i.test(url.pathname))return;
   setEstado('on')};
  document.addEventListener('click',onClick,true);return()=>document.removeEventListener('click',onClick,true)},[]);
 useEffect(()=>{if(prev.current===pathname)return;prev.current=pathname;setEstado(s=>s==='on'?'fin':s)},[pathname]);
 useEffect(()=>{if(estado==='fin'){const t=setTimeout(()=>setEstado('off'),350);return()=>clearTimeout(t)}if(estado==='on'){const t=setTimeout(()=>setEstado('off'),8000);return()=>clearTimeout(t)}},[estado]);
 return <div className={`v11-navbar is-${estado}`} aria-hidden="true"/>;
}
