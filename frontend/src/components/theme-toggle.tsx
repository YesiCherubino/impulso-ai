'use client';
import {useEffect,useState} from 'react';
import {Moon,Sun} from 'lucide-react';

/** Preferencia visual local, sin modificar la sesión ni enviar datos al backend. */
export default function ThemeToggle(){
 const [dark,setDark]=useState(false);
 useEffect(()=>{
  setDark(document.documentElement.dataset.theme==='dark');
  const sync=(event:StorageEvent)=>{
   if(event.key!=='impulso-theme')return;
   const next=event.newValue==='dark';
   document.documentElement.dataset.theme=next?'dark':'light';
   setDark(next);
  };
  window.addEventListener('storage',sync);
  return()=>window.removeEventListener('storage',sync);
 },[]);
 function toggle(){
  const next=!dark;
  document.documentElement.dataset.theme=next?'dark':'light';
  try{window.localStorage.setItem('impulso-theme',next?'dark':'light')}catch{}
  setDark(next);
 }
 return <button type="button" className="theme-toggle" onClick={toggle}
   aria-label={dark?'Cambiar a tema claro':'Cambiar a tema oscuro'}
   title={dark?'Activar tema claro':'Activar tema oscuro'} aria-pressed={dark}>
   {dark?<Sun size={17} aria-hidden="true"/>:<Moon size={17} aria-hidden="true"/>}
   <span className="theme-toggle-label">{dark?'Tema claro':'Tema oscuro'}</span>
 </button>;
}
