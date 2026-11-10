'use client';
import {useState} from 'react';
import {X} from 'lucide-react';
import {api,ESTADOS_GESTION,estadoGestionNombre,MOTIVOS_NO_CONCRETADA} from '@/lib/api';

type Quote={monto?:number|null;moneda?:string|null;validez?:number|null};
type Pending={estado:'cotizada'|'no_concretada'};

/* Selector del pipeline único. Pide los datos obligatorios antes de guardar:
   cotización (monto y moneda) para "Cotizada" y motivo para "No concretada". */
export default function CaseStatusSelect({fichaId,value,quote,onChanged,onError,disabled=false,label,compact=false,includeClosed=true}:{fichaId:number;value:string;quote?:Quote;onChanged:(estado:string)=>void|Promise<void>;onError?:(message:string)=>void;disabled?:boolean;label?:string;compact?:boolean;includeClosed?:boolean}){
 const [pending,setPending]=useState<Pending|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [monto,setMonto]=useState(''),[moneda,setMoneda]=useState('USD'),[validez,setValidez]=useState('30'),[motivo,setMotivo]=useState('');
 const current=value==='en_gestion'?'calificada':value;
 const options=includeClosed?ESTADOS_GESTION:ESTADOS_GESTION.filter(e=>!['concretada','no_concretada','resuelta'].includes(e)||e===current);
 async function save(estado:string,extra:Record<string,unknown>={}){setBusy(true);setError('');try{await api(`/api/fichas/${fichaId}/estado`,{method:'POST',body:JSON.stringify({estado,...extra})});setPending(null);await onChanged(estado)}catch(e){const msg=e instanceof Error?e.message:'No se pudo cambiar el estado';setError(msg);onError?.(msg)}finally{setBusy(false)}}
 function choose(estado:string){
  if(estado===current)return;
  if(estado==='cotizada'&&(quote?.monto==null||!quote?.moneda)){setMonto('');setMoneda('USD');setValidez('30');setPending({estado:'cotizada'});return}
  if(estado==='no_concretada'){setMotivo('');setPending({estado:'no_concretada'});return}
  void save(estado);
 }
 return <>
  <select aria-label={label||'Estado de la gestión'} className={compact?'v5-status-select is-compact':'v5-status-select'} value={current} disabled={disabled||busy} onChange={e=>choose(e.target.value)}>
   {options.map(e=><option key={e} value={e}>{estadoGestionNombre[e]}</option>)}
  </select>
  {pending&&<div className="modal-backdrop v2-overlay v5-front" onMouseDown={()=>setPending(null)}><div className="modal v2-modal v5-small-modal" role="dialog" aria-modal="true" aria-label={pending.estado==='cotizada'?'Datos de la cotización':'Motivo de cierre'} onMouseDown={e=>e.stopPropagation()}>
   <div className="modal-head"><h2>{pending.estado==='cotizada'?'Datos de la cotización':'¿Por qué no se concretó?'}</h2><button type="button" className="icon-button" aria-label="Cerrar" onClick={()=>setPending(null)}><X/></button></div>
   {pending.estado==='cotizada'?<form className="fields" onSubmit={e=>{e.preventDefault();void save('cotizada',{cotizacion_monto:Number(monto),cotizacion_moneda:moneda,cotizacion_validez_dias:validez?Number(validez):null})}}>
    <div className="form-row"><label>Monto<input type="number" min="0.01" step="0.01" required autoFocus value={monto} onChange={e=>setMonto(e.target.value)}/></label><label>Moneda<select value={moneda} onChange={e=>setMoneda(e.target.value)}><option value="USD">USD</option><option value="ARS">ARS</option></select></label></div>
    <label>Validez (días)<input type="number" min="1" max="365" value={validez} onChange={e=>setValidez(e.target.value)}/></label>
    <small className="muted">La fecha de cotización se registra hoy.</small>
    <button className="btn btn-primary" disabled={busy||!monto}>Guardar como cotizada</button>
   </form>:<form className="fields" onSubmit={e=>{e.preventDefault();void save('no_concretada',{motivo})}}>
    <div className="v5-reason-list" role="radiogroup" aria-label="Motivo">{MOTIVOS_NO_CONCRETADA.map(m=><label key={m} className="v5-reason"><input type="radio" name="motivo" value={m} checked={motivo===m} onChange={()=>setMotivo(m)}/> {m}</label>)}</div>
    <button className="btn btn-primary" disabled={busy||!motivo}>Cerrar como no concretada</button>
   </form>}
   {error&&<p className="alert error" role="alert">{error}</p>}
  </div></div>}
 </>;
}
