'use client';
import {useCallback,useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import {Bell,MessageSquare,Clock3} from 'lucide-react';
import {api} from '@/lib/api';

type Notice={id:number;tipo:'mensaje'|'seguimiento';referencia_id:number;titulo:string;detalle:string;creada_en:string;leida:0|1};
type Response={items:Notice[];sin_leer:number};
export default function Notifications(){
 const router=useRouter();
 const [data,setData]=useState<Response>({items:[],sin_leer:0});
 const [open,setOpen]=useState(false);
 const load=useCallback(async()=>{try{setData(await api<Response>('/api/notifications'))}catch{/* La bandeja no debe quedar bloqueada si fallan los avisos. */}},[]);
 useEffect(()=>{void load();const interval=window.setInterval(()=>void load(),45000);const focused=()=>void load();window.addEventListener('focus',focused);return()=>{clearInterval(interval);window.removeEventListener('focus',focused)}},[load]);
 async function navigate(n:Notice){
  try{await api(`/api/notifications/${n.id}/read`,{method:'POST'});await load()}catch{/* En caso de error, el aviso seguirá pendiente. */}
  setOpen(false);
  if(n.tipo==='mensaje'){window.dispatchEvent(new CustomEvent('impulso:open-consulta',{detail:n.referencia_id}));router.push(`/consultas?consulta=${n.referencia_id}`);}
  else router.push(`/oportunidades/${n.referencia_id}`);
 }
 return <div className="notification-widget"><button type="button" className="notification-trigger" aria-label={`Notificaciones, ${data.sin_leer} sin leer`} aria-haspopup="true" aria-expanded={open} onClick={()=>{setOpen(v=>!v);void load()}}><Bell size={19}/>{data.sin_leer>0&&<span className="notification-badge">{data.sin_leer>99?'99+':data.sin_leer}</span>}</button>
  {open&&<div className="notification-popover" role="region" aria-label="Notificaciones"><div className="notification-heading"><strong>Notificaciones</strong><button type="button" onClick={()=>setOpen(false)} aria-label="Cerrar notificaciones">Cerrar</button></div><div className="notification-list">{data.items.length===0?<p className="notification-empty">Sin notificaciones.</p>:data.items.map(n=><button type="button" className={`notification-item ${n.leida?'is-read':''}`} key={n.id} onClick={()=>void navigate(n)}><span className="notification-item-icon">{n.tipo==='mensaje'?<MessageSquare size={16}/>:<Clock3 size={16}/>}</span><span className="notification-item-body"><strong>{n.titulo}</strong><small>{n.detalle}</small></span>{!n.leida&&<i className="notification-unread" aria-label="Sin leer"/>}</button>)}</div></div>}
 </div>;
}
