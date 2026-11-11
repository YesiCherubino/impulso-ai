'use client';
import {useEffect,useState} from 'react';
import {Moon,Sun,Monitor} from 'lucide-react';
import {api} from '@/lib/api';

export type TemaPref='auto'|'claro'|'oscuro';
const KEY='impulso-theme-pref';
let mq:MediaQueryList|null=null,listener:(()=>void)|null=null;

/* Aplica la preferencia: "auto" sigue al sistema/navegador y cambia solo si el sistema cambia. */
export function aplicarTema(pref:TemaPref){
 if(typeof window==='undefined')return;
 const d=document.documentElement;
 if(mq&&listener){mq.removeEventListener('change',listener);listener=null}
 if(pref==='auto'){mq=window.matchMedia('(prefers-color-scheme: dark)');listener=()=>{d.dataset.theme=mq!.matches?'dark':'light'};listener();mq.addEventListener('change',listener)}
 else d.dataset.theme=pref==='oscuro'?'dark':'light';
 try{localStorage.setItem(KEY,pref)}catch{/* sin almacenamiento */}
}
export const temaGuardado=():TemaPref=>{try{const v=localStorage.getItem(KEY);return v==='claro'||v==='oscuro'?v:'auto'}catch{return 'auto'}};

const OPCIONES:[TemaPref,string,typeof Sun][]=[['claro','Claro',Sun],['auto','Automático (como el navegador)',Monitor],['oscuro','Oscuro',Moon]];

/** Selector compacto de tema. Con sesión, se guarda en la cuenta. */
export default function ThemeToggle({userTheme,authenticated=false,onThemeSaved}:{userTheme?:string;authenticated?:boolean;onThemeSaved?:(theme:TemaPref)=>void}){
 const [pref,setPref]=useState<TemaPref>('auto'),[error,setError]=useState('');
 useEffect(()=>{const p=(userTheme==='claro'||userTheme==='oscuro'||userTheme==='auto')?userTheme:temaGuardado();setPref(p);aplicarTema(p)},[userTheme]);
 async function pick(p:TemaPref){if(p===pref)return;const prev=pref;setPref(p);setError('');aplicarTema(p);
  if(authenticated){try{await api('/api/auth/me/theme',{method:'POST',body:JSON.stringify({theme:p})});onThemeSaved?.(p)}catch{setError('No se pudo guardar en tu cuenta');setPref(prev);aplicarTema(prev)}}}
 return <div className="v9-theme" role="radiogroup" aria-label="Tema">
  {OPCIONES.map(([v,l,Icon])=><button key={v} type="button" role="radio" aria-checked={pref===v} aria-label={l} title={l} className={pref===v?'is-on':''} onClick={()=>void pick(v)}><Icon size={14} strokeWidth={1.8}/></button>)}
  {error&&<small role="alert" className="v2-theme-error">{error}</small>}
 </div>;
}
