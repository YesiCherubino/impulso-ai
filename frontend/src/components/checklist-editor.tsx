'use client';
import {useEffect,useRef,useState} from 'react';
import {Check,Plus,Trash2} from 'lucide-react';
import {api} from '@/lib/api';
type CheckItem={text:string;done:boolean};
type Data={requisitos:CheckItem[];faltantes:CheckItem[]};
export default function ChecklistEditor({fichaId,readOnly=false}:{fichaId:number;readOnly?:boolean}){
 const [data,setData]=useState<Data>({requisitos:[],faltantes:[]}),[loaded,setLoaded]=useState(false),[dirty,setDirty]=useState(false),[status,setStatus]=useState(''),[error,setError]=useState('');
 const version=useRef(0);
 useEffect(()=>{let active=true;setLoaded(false);setDirty(false);api<Data>(`/api/fichas/${fichaId}/checklists`).then(r=>{if(active){setData(r);setLoaded(true);setError('')}}).catch(e=>{if(active)setError(String(e))});return()=>{active=false}},[fichaId]);
 useEffect(()=>{if(!loaded||!dirty||readOnly)return;const snapshot=JSON.stringify(data);const current=++version.current;setStatus('Guardando…');const timer=window.setTimeout(()=>{void api<Data>(`/api/fichas/${fichaId}/checklists`,{method:'POST',body:snapshot}).then(()=>{if(current===version.current){setDirty(false);setStatus('Guardado');setError('')}}).catch(e=>{if(current===version.current){setError('No se pudo guardar la lista. Reintentá el cambio.');setStatus('Error')}})},700);return()=>window.clearTimeout(timer)},[data,dirty,loaded,readOnly,fichaId]);
 function update(key:keyof Data,index:number,patch:Partial<CheckItem>|null){setData(old=>({...old,[key]:patch===null?old[key].filter((_,i)=>i!==index):old[key].map((x,i)=>i===index?{...x,...patch}:x)}));setDirty(true)}
 function add(key:keyof Data){setData(old=>({...old,[key]:[...old[key],{text:'',done:false}]}));setDirty(true)}
 return <div className="v3-checklists">{([['requisitos','Requisitos'],['faltantes','Datos a confirmar']] as [keyof Data,string][]).map(([key,label])=><section key={key}><div className="v3-section-line"><h4>{label}</h4>{!readOnly&&<button className="v3-text-action" onClick={()=>add(key)}><Plus size={15}/> Agregar</button>}</div><div className="v3-checklist-items">{data[key].map((item,i)=><div className="v3-checklist-item" key={`${key}-${i}`}><input type="checkbox" aria-label={`Confirmar ${item.text}`} checked={item.done} disabled={readOnly} onChange={e=>update(key,i,{done:e.target.checked})}/><input className={item.done?'done':''} aria-label={`${label} ${i+1}`} value={item.text} readOnly={readOnly} placeholder="Escribí un dato…" onChange={e=>update(key,i,{text:e.target.value})}/>{!readOnly&&<button aria-label="Eliminar elemento" className="v3-icon-mini" onClick={()=>update(key,i,null)}><Trash2 size={15}/></button>}</div>)}{!data[key].length&&<p className="muted">Sin elementos.</p>}</div></section>)}{status==='Guardado'&&<small className="v3-saving"><Check size={13}/> Guardado</small>}{status==='Guardando…'&&<small className="v3-saving">Guardando…</small>}{error&&<small className="v3-form-error" role="alert">{error}</small>}</div>;
}
