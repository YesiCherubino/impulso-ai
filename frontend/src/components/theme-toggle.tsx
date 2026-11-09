'use client';
import {useEffect,useState} from 'react';
import {Moon,Sun} from 'lucide-react';
import {api} from '@/lib/api';
/** Preferencia local en login; sincronizada con la cuenta al iniciar sesión. */
export default function ThemeToggle({userTheme,authenticated=false,onThemeSaved}:{userTheme?:string;authenticated?:boolean;onThemeSaved?:(theme:'claro'|'oscuro')=>void}){
 const [dark,setDark]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState('');
 useEffect(()=>{
  const next=userTheme?userTheme==='oscuro':document.documentElement.dataset.theme==='dark';
  document.documentElement.dataset.theme=next?'dark':'light';setDark(next);
 },[userTheme]);
 async function toggle(){
  const next=!dark;setError('');setDark(next);document.documentElement.dataset.theme=next?'dark':'light';
  try{window.localStorage.setItem('impulso-theme',next?'dark':'light')}catch{}
  if(authenticated){setSaving(true);try{await api('/api/auth/me/theme',{method:'POST',body:JSON.stringify({theme:next?'oscuro':'claro'})});onThemeSaved?.(next?'oscuro':'claro')}
  catch{setError('No se pudo guardar la preferencia en tu cuenta.');}finally{setSaving(false)}}
 }
 return <div className="v2-theme-line"><button type="button" className="v2-theme-button" onClick={()=>void toggle()} aria-label={dark?'Cambiar a tema claro':'Cambiar a tema oscuro'} aria-pressed={dark} disabled={saving}>
   {dark?<Sun size={18} strokeWidth={1.6}/>:<Moon size={18} strokeWidth={1.6}/>}<span>{dark?'Tema claro':'Tema oscuro'}</span><span className={`v2-switch ${dark?'is-on':''}`} aria-hidden="true"/></button>
   {error&&<small role="alert" className="v2-theme-error">{error}</small>}
 </div>;
}
