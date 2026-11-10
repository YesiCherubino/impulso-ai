'use client';
import {useEffect,useState} from 'react';
import {useParams} from 'next/navigation';
import {abrirArchivo,ArchivoB64} from '@/lib/api';

type Item={codigo:string;descripcion:string;unidad:string;cantidad:number;precio_unitario:number;descuento_pct:number;importe:number};
type Q={empresa:{razon_social:string;email?:string;telefono?:string;web?:string;domicilio?:string;color_acento?:string};numero:string;fecha:string;vence:string;estado:'pendiente'|'aceptada'|'vencida';aceptada_en:string|null;
 cliente:string;contacto:string;moneda:string;items:Item[];subtotal:number;iva:number;iva_pct:number;incluye_iva:boolean;total:number;condiciones:string;notas:string};
const fmt=(n:number,m:string)=>`${m} ${n.toLocaleString('es-AR',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
const fecha=(s:string)=>new Date(`${s.slice(0,10)}T12:00:00`).toLocaleDateString('es-AR',{day:'numeric',month:'long',year:'numeric'});
async function call<T>(path:string,init?:RequestInit):Promise<T>{const r=await fetch(`/api/publico/cotizaciones/${path}`,{cache:'no-store',...init,headers:{'Content-Type':'application/json'}});const b=await r.json().catch(()=>null);if(!r.ok)throw new Error(b?.detail||'No se pudo cargar la cotización');return b as T}

/* Cotización online: el cliente la revisa y la acepta desde el enlace, sin usuario ni contraseña. */
export default function CotizacionPublica(){
 const {token}=useParams<{token:string}>();
 const [q,setQ]=useState<Q|null>(null),[error,setError]=useState(''),[nombre,setNombre]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{void call<Q>(token).then(r=>{setQ(r);setNombre(r.contacto||'')}).catch(e=>setError(e.message))},[token]);
 async function accept(){setBusy(true);setError('');try{setQ(await call<Q>(`${token}/aceptar`,{method:'POST',body:JSON.stringify({nombre})}))}catch(e){setError(e instanceof Error?e.message:'No se pudo aceptar')}finally{setBusy(false)}}
 async function pdf(){try{abrirArchivo(await call<ArchivoB64>(`${token}/pdf`))}catch(e){setError(e instanceof Error?e.message:'No se pudo abrir')}}
 const brand=q?.empresa.color_acento||'#2e6a57';
 return <main className="v7-public" style={{['--brand' as string]:brand}}>
  {!q?<p className="v7-public-msg">{error||'Cargando cotización…'}</p>:<article className="v7-public-card">
   <header><div><strong className="v7-public-brand">{q.empresa.razon_social}</strong><small>{[q.empresa.web,q.empresa.email,q.empresa.telefono].filter(Boolean).join(' · ')}</small></div>
    <div className="v7-public-num"><span>Cotización</span><strong>{q.numero}</strong><small>{fecha(q.fecha)}</small></div></header>
   <section className="v7-public-to"><small>Para</small><strong>{q.cliente}</strong>{q.contacto&&<span>{q.contacto}</span>}</section>
   <div className="v7-public-table"><table><thead><tr><th>Descripción</th><th>Cant.</th><th>Precio</th><th>Importe</th></tr></thead>
    <tbody>{q.items.map((i,n)=><tr key={n}><td>{i.descripcion}{i.descuento_pct?<small>{i.descuento_pct}% de descuento</small>:null}</td><td>{i.cantidad.toLocaleString('es-AR')}</td><td>{fmt(i.precio_unitario,q.moneda)}</td><td>{fmt(i.importe,q.moneda)}</td></tr>)}</tbody></table></div>
   <dl className="v7-public-totals"><div><dt>Subtotal</dt><dd>{fmt(q.subtotal,q.moneda)}</dd></div>{q.incluye_iva&&<div><dt>IVA {q.iva_pct}%</dt><dd>{fmt(q.iva,q.moneda)}</dd></div>}<div className="is-total"><dt>Total</dt><dd>{fmt(q.total,q.moneda)}</dd></div></dl>
   {(q.condiciones||q.notas)&&<section className="v7-public-notes">{q.condiciones&&<p><b>Condiciones.</b> {q.condiciones}</p>}{q.notas&&<p>{q.notas}</p>}</section>}
   <footer>
    {q.estado==='aceptada'?<p className="v7-public-ok">Cotización aceptada el {fecha(q.aceptada_en||q.fecha)}. Te vamos a contactar para coordinar los próximos pasos.</p>
    :q.estado==='vencida'?<p className="v7-public-msg">Esta cotización venció el {fecha(q.vence)}. Pedinos una actualizada.</p>
    :<div className="v7-public-accept"><label>Tu nombre<input value={nombre} onChange={e=>setNombre(e.target.value)} maxLength={120}/></label><button type="button" disabled={busy} onClick={()=>void accept()}>{busy?'Enviando…':'Aceptar cotización'}</button><small>Válida hasta el {fecha(q.vence)}.</small></div>}
    <button type="button" className="v7-public-pdf" onClick={()=>void pdf()}>Descargar PDF</button>
    {error&&<p className="v7-public-err" role="alert">{error}</p>}
   </footer>
  </article>}
 </main>;
}
