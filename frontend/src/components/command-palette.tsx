'use client';
import {useEffect,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {Search,MessageCircle,ContactRound,CornerDownLeft,Sun,Inbox,CalendarDays,FileText,FileCheck2} from 'lucide-react';
import {api,qs,estadoGestionNombre} from '@/lib/api';

type Result={contactos:{id:number;cliente:string;contacto:string;codigo_tango:string;localidad:string}[];gestiones:{id:number;codigo:string;cliente:string;titulo:string;estado_gestion:string;conversacion:string;tiene_mensajes:boolean}[]};
type Option={key:string;label:string;sub?:string;icon:React.ReactNode;go:()=>void};
const pages=[{href:'/consultas',label:'Bandeja',icon:<Inbox size={16}/>},{href:'/mi-dia',label:'Mi día',icon:<Sun size={16}/>},{href:'/contactos',label:'Contactos',icon:<ContactRound size={16}/>},{href:'/agenda',label:'Agenda',icon:<CalendarDays size={16}/>},{href:'/finalizados',label:'Finalizados',icon:<FileCheck2 size={16}/>},{href:'/resumen-gerencial',label:'Reportes',icon:<FileText size={16}/>}];

/* Búsqueda global (Ctrl+K): empresas, contactos, códigos de gestión y pantallas. */
export default function CommandPalette({open,onClose}:{open:boolean;onClose:()=>void}){
 const router=useRouter();
 const [q,setQ]=useState(''),[res,setRes]=useState<Result|null>(null),[idx,setIdx]=useState(0),[loading,setLoading]=useState(false);
 const input=useRef<HTMLInputElement|null>(null);
 useEffect(()=>{if(open){setQ('');setRes(null);setIdx(0);setTimeout(()=>input.current?.focus(),20)}},[open]);
 useEffect(()=>{if(!open||q.trim().length<2){setRes(null);return}setLoading(true);const t=setTimeout(()=>{void api<Result>(`/api/buscar?${qs({q:q.trim()})}`).then(r=>{setRes(r);setIdx(0)}).catch(()=>setRes(null)).finally(()=>setLoading(false))},200);return()=>clearTimeout(t)},[q,open]);
 const go=(href:string)=>{onClose();router.push(href)};
 const term=q.trim().toLowerCase();
 const options:Option[]=[
  ...(res?.gestiones||[]).map(g=>({key:`g${g.id}`,label:`${g.cliente} · ${g.codigo}`,sub:`${g.titulo} · ${estadoGestionNombre[g.estado_gestion]||g.estado_gestion}`,icon:<MessageCircle size={16}/>,go:()=>{if(window.location.pathname==='/consultas'){onClose();window.dispatchEvent(new CustomEvent('impulso:open-conversacion',{detail:{key:g.conversacion,ficha:g.id}}))}else go(`/consultas?conversacion=${g.conversacion}&ficha=${g.id}`)}})),
  ...(res?.contactos||[]).map(c=>({key:`c${c.id}`,label:c.cliente,sub:[c.contacto,c.codigo_tango&&`Tango ${c.codigo_tango}`,c.localidad].filter(Boolean).join(' · '),icon:<ContactRound size={16}/>,go:()=>go(`/oportunidades/${c.id}`)})),
  ...pages.filter(p=>!term||p.label.toLowerCase().includes(term)).map(p=>({key:p.href,label:p.label,sub:'Ir a la pantalla',icon:p.icon,go:()=>go(p.href)})),
 ];
 if(!open)return null;
 function onKey(e:React.KeyboardEvent){if(e.key==='Escape'){e.preventDefault();onClose()}else if(e.key==='ArrowDown'){e.preventDefault();setIdx(i=>Math.min(options.length-1,i+1))}else if(e.key==='ArrowUp'){e.preventDefault();setIdx(i=>Math.max(0,i-1))}else if(e.key==='Enter'){e.preventDefault();options[idx]?.go()}}
 return <div className="modal-backdrop v2-overlay v6-palette-backdrop" onMouseDown={onClose}><div className="v6-palette" role="dialog" aria-modal="true" aria-label="Búsqueda global" onMouseDown={e=>e.stopPropagation()}>
  <label className="v6-palette-input"><Search size={18}/><input ref={input} autoFocus value={q} onChange={e=>setQ(e.target.value)} onKeyDown={onKey} placeholder="Buscar empresa, contacto, código CON-… o pantalla" aria-label="Buscar"/><kbd>Esc</kbd></label>
  <div className="v6-palette-list" role="listbox">
   {loading&&!res&&<p className="muted">Buscando…</p>}
   {res&&!res.gestiones.length&&!res.contactos.length&&<p className="muted">Sin resultados para “{q}”.</p>}
   {options.map((o,i)=><button type="button" role="option" aria-selected={i===idx} key={o.key} className={i===idx?'is-active':''} onMouseEnter={()=>setIdx(i)} onClick={o.go}>{o.icon}<span><strong>{o.label}</strong>{o.sub&&<small>{o.sub}</small>}</span>{i===idx&&<CornerDownLeft size={14}/>}</button>)}
  </div>
  <div className="v6-palette-foot"><span><kbd>↑</kbd><kbd>↓</kbd> moverse</span><span><kbd>Enter</kbd> abrir</span><span><kbd>Ctrl</kbd>+<kbd>K</kbd> desde cualquier pantalla</span></div>
 </div></div>;
}
