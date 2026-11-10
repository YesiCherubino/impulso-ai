'use client';
import {useEffect,useMemo,useState} from 'react';
import {X,Plus,Trash2,Search,FileDown,Loader2,Receipt} from 'lucide-react';
import {api,qs,ArchivoB64,abrirArchivo,Producto,Empresa,FichaConsulta,cotizacionTexto} from '@/lib/api';

type Item={producto_id:number|null;codigo:string;descripcion:string;unidad:string;cantidad:string;precio_unitario:string;descuento_pct:string};
type Cotizacion={id:number;numero:string;fecha:string;moneda:string;total:number;items:{descripcion:string}[]};
const fmt=(n:number,m:string)=>`${m} ${n.toLocaleString('es-AR',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
const num=(s:string)=>{const n=Number(String(s).replace(',','.'));return Number.isFinite(n)?n:0};

/* Cotizador: arma la cotización con la lista de precios, genera el PDF y deja la gestión en "Cotizada". */
export default function QuoteDialog({fichaId,onClose,onSaved}:{fichaId:number;onClose:()=>void;onSaved?:(msg:string)=>void}){
 const [ficha,setFicha]=useState<FichaConsulta|null>(null),[empresa,setEmpresa]=useState<Empresa|null>(null),[previas,setPrevias]=useState<Cotizacion[]>([]);
 const [items,setItems]=useState<Item[]>([]),[moneda,setMoneda]=useState<'ARS'|'USD'>('ARS'),[iva,setIva]=useState(true),[validez,setValidez]=useState('30'),[condiciones,setCondiciones]=useState(''),[notas,setNotas]=useState('');
 const [q,setQ]=useState(''),[results,setResults]=useState<Producto[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{void Promise.all([api<FichaConsulta>(`/api/fichas/${fichaId}`),api<Empresa>('/api/empresa'),api<Cotizacion[]>(`/api/fichas/${fichaId}/cotizaciones`)]).then(([f,e,p])=>{setFicha(f);setEmpresa(e);setCondiciones(e.condiciones);setPrevias(p);
  if(f.cotizacion_moneda==='USD'||f.cotizacion_moneda==='ARS')setMoneda(f.cotizacion_moneda);
  // Primera línea con lo que pidió el cliente, para completar el precio.
  setItems([{producto_id:null,codigo:'',descripcion:[f.producto,f.presentacion].filter(Boolean).join(' · ')||f.titulo,unidad:'unidad',cantidad:f.cantidad?String(f.cantidad):'1',precio_unitario:'',descuento_pct:''}])}).catch(e=>setError(String(e)))},[fichaId]);
 useEffect(()=>{const t=setTimeout(()=>{void api<{items:Producto[]}>(`/api/productos?${qs({q,limit:8})}`).then(r=>setResults(r.items)).catch(()=>{})},250);return()=>clearTimeout(t)},[q]);
 const totals=useMemo(()=>{const sub=items.reduce((s,i)=>s+num(i.cantidad)*num(i.precio_unitario)*(1-num(i.descuento_pct)/100),0);const pct=empresa?.iva_pct??21;const ivaMonto=iva?sub*pct/100:0;return {sub,ivaMonto,total:sub+ivaMonto,pct}},[items,iva,empresa]);
 const patch=(i:number,k:keyof Item,v:string)=>setItems(old=>old.map((it,j)=>j===i?{...it,[k]:v}:it));
 function add(p:Producto){setItems(old=>{const blank=old.length===1&&!old[0].precio_unitario&&!old[0].producto_id;const item={producto_id:p.id,codigo:p.codigo,descripcion:p.descripcion,unidad:p.unidad,cantidad:blank?old[0].cantidad:'1',precio_unitario:p.precio!=null?String(p.precio):'',descuento_pct:''};return blank?[item]:[...old,item]});if(p.moneda!==moneda&&items.every(i=>!i.precio_unitario))setMoneda(p.moneda);setQ('')}
 const valid=items.length>0&&items.every(i=>i.descripcion.trim()&&num(i.cantidad)>0&&i.precio_unitario!=='');
 async function save(){setBusy(true);setError('');try{
  const r=await api<{id:number;numero:string;total:number;moneda:string}>(`/api/fichas/${fichaId}/cotizaciones`,{method:'POST',body:JSON.stringify({moneda,validez_dias:Number(validez)||30,incluye_iva:iva,iva_pct:totals.pct,condiciones,notas,
   items:items.map(i=>({producto_id:i.producto_id,codigo:i.codigo,descripcion:i.descripcion.trim(),unidad:i.unidad||'unidad',cantidad:num(i.cantidad),precio_unitario:num(i.precio_unitario),descuento_pct:num(i.descuento_pct)}))})});
  abrirArchivo(await api<ArchivoB64>(`/api/cotizaciones/${r.id}/pdf`));
  onSaved?.(`Cotización ${r.numero} generada`);onClose();
 }catch(e){setError(e instanceof Error?e.message:'No se pudo generar la cotización')}finally{setBusy(false)}}
 async function reopen(id:number){try{abrirArchivo(await api<ArchivoB64>(`/api/cotizaciones/${id}/pdf`))}catch(e){setError(String(e))}}
 const mixed=results.length>0&&results.some(r=>r.moneda!==moneda);
 return <div className="modal-backdrop v2-overlay v5-front" onMouseDown={onClose}><div className="modal v6-quote" role="dialog" aria-modal="true" aria-label="Cotizador" onMouseDown={e=>e.stopPropagation()}>
  <header className="v3-dialog-head"><div><small>{ficha?.codigo}</small><h2>Nueva cotización</h2><p>{ficha?`${ficha.cliente}${ficha.contacto?` · ${ficha.contacto}`:''}`:'Cargando…'}</p></div><button className="icon-button" onClick={onClose} aria-label="Cerrar"><X/></button></header>
  <div className="v3-dialog-body">
   {!!previas.length&&<div className="v6-prev"><small>Cotizaciones anteriores:</small>{previas.map(p=><button key={p.id} type="button" className="v5-chip" onClick={()=>void reopen(p.id)} title="Abrir PDF"><FileDown size={11}/> {p.numero} · {fmt(p.total,p.moneda)}</button>)}</div>}
   <div className="v6-quote-top">
    <label className="search v6-product-search"><Search size={16}/><input placeholder="Buscar en la lista de precios (código, producto o línea)" value={q} onChange={e=>setQ(e.target.value)}/></label>
    <select aria-label="Moneda" value={moneda} onChange={e=>setMoneda(e.target.value as 'ARS'|'USD')}><option value="ARS">Pesos (ARS)</option><option value="USD">Dólares (USD)</option></select>
   </div>
   {q&&<div className="v6-results">{results.map(p=><button type="button" key={p.id} onClick={()=>add(p)}><span><strong>{p.descripcion}</strong><small>{p.codigo} · {p.linea||'Sin línea'} · {p.unidad}</small></span><b className={p.moneda!==moneda?'is-other':''}>{p.precio!=null?fmt(p.precio,p.moneda):'Sin precio'}</b></button>)}{!results.length&&<p className="muted">Sin resultados para "{q}".</p>}{mixed&&<small className="muted">Los precios en otra moneda no se convierten.</small>}</div>}
   <div className="v5-table-wrap"><table className="v6-items"><thead><tr><th>Descripción</th><th>Cant.</th><th>Precio unit.</th><th>Desc. %</th><th>Importe</th><th></th></tr></thead><tbody>
    {items.map((it,i)=><tr key={i}><td><input aria-label="Descripción" value={it.descripcion} onChange={e=>patch(i,'descripcion',e.target.value)}/>{it.codigo&&<small>{it.codigo}</small>}</td>
     <td><input aria-label="Cantidad" inputMode="decimal" value={it.cantidad} onChange={e=>patch(i,'cantidad',e.target.value)}/></td>
     <td><input aria-label="Precio unitario" inputMode="decimal" placeholder="0,00" value={it.precio_unitario} onChange={e=>patch(i,'precio_unitario',e.target.value)}/></td>
     <td><input aria-label="Descuento" inputMode="decimal" placeholder="0" value={it.descuento_pct} onChange={e=>patch(i,'descuento_pct',e.target.value)}/></td>
     <td className="v6-amount">{fmt(num(it.cantidad)*num(it.precio_unitario)*(1-num(it.descuento_pct)/100),moneda)}</td>
     <td><button type="button" className="v4-icon-action" aria-label="Quitar línea" onClick={()=>setItems(old=>old.filter((_,j)=>j!==i))}><Trash2 size={15}/></button></td></tr>)}
   </tbody></table></div>
   <button type="button" className="v3-text-action" onClick={()=>setItems(old=>[...old,{producto_id:null,codigo:'',descripcion:'',unidad:'unidad',cantidad:'1',precio_unitario:'',descuento_pct:''}])}><Plus size={14}/> Agregar línea manual</button>
   <div className="v6-quote-bottom">
    <div className="v3-fields">
     <label>Validez (días)<input type="number" min="1" max="365" value={validez} onChange={e=>setValidez(e.target.value)}/></label>
     <label className="v3-config-check"><input type="checkbox" checked={iva} onChange={e=>setIva(e.target.checked)}/> Sumar IVA {totals.pct}%</label>
     <label className="wide">Condiciones<textarea rows={2} value={condiciones} onChange={e=>setCondiciones(e.target.value)}/></label>
     <label className="wide">Observaciones para el cliente<textarea rows={2} value={notas} onChange={e=>setNotas(e.target.value)} placeholder="Opcional"/></label>
    </div>
    <dl className="v6-totals"><div><dt>Subtotal</dt><dd>{fmt(totals.sub,moneda)}</dd></div>{iva&&<div><dt>IVA {totals.pct}%</dt><dd>{fmt(totals.ivaMonto,moneda)}</dd></div>}<div className="is-total"><dt>Total</dt><dd>{fmt(totals.total,moneda)}</dd></div></dl>
   </div>
   {error&&<p className="alert error" role="alert">{error}</p>}
   <div className="v6-actions"><small className="muted">La gestión pasa a Cotizada con este total.</small><button type="button" className="btn btn-outline" onClick={onClose}>Cancelar</button><button type="button" className="btn btn-primary" disabled={busy||!valid} onClick={()=>void save()}>{busy?<Loader2 size={16} className="v5-spin"/>:<FileDown size={16}/>} Generar PDF</button></div>
  </div>
 </div></div>;
}
