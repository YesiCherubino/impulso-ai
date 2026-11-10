'use client';
import {useState, type FormEvent} from 'react';
import {useRouter} from 'next/navigation';
import {Eye,EyeOff,AlertCircle} from 'lucide-react';
import ImpulsoMark from '@/components/impulso-mark';
import './login.css';
import ThemeToggle from '@/components/theme-toggle';

export default function Login(){
 const router=useRouter();
 const [username,setUsername]=useState('');
 const [password,setPassword]=useState('');
 const [showPassword,setShowPassword]=useState(false);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 async function signIn(e:FormEvent<HTMLFormElement>){
  e.preventDefault();
  if(busy)return;
  setBusy(true);setError('');
  try{
   const res=await fetch('/api/session/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username.trim(),password}),cache:'no-store'});
   const data:unknown=await res.json().catch(()=>null);
   if(!res.ok){
    // Error funcional y error de conectividad son distintos. Nunca mostrar URLs internas.
    const detail=typeof data==='object'&&data!==null&&'detail' in data&&typeof data.detail==='string'?data.detail:'';
    if(res.status===401)setError('Usuario o contraseña incorrectos');
    else if(res.status===403)setError('No se pudo iniciar sesión');
    else if(res.status===400)setError('Ingresá usuario y contraseña');
    else if(res.status===429)setError('Demasiados intentos. Intentá más tarde');
    else if(res.status===502||res.status===503||res.status>=500)setError('No se pudo conectar con el servidor');
    else setError(detail||'No se pudo iniciar sesión');
    return;
   }
   router.replace('/consultas');router.refresh();
  }catch{setError('No se pudo conectar con el servidor')}
  finally{setBusy(false)}
 }
 return <main className="login-screen"><div className="login-theme-control"><ThemeToggle/></div><form className="login-panel" onSubmit={signIn}>
  <div className="login-brand"><span className="login-mark"><ImpulsoMark size={26}/></span><span><strong>Impulso</strong><small>Gestión comercial</small></span></div>
  <div className="login-heading"><h1>Iniciar sesión</h1></div>
  <label htmlFor="usuario">Usuario</label>
  <input id="usuario" name="username" autoComplete="username" required maxLength={120} value={username} onChange={e=>{setUsername(e.target.value);if(error)setError('')}}/>
  <label htmlFor="password">Contraseña</label>
  <div className="password-field">
   <input id="password" name="password" type={showPassword?'text':'password'} autoComplete="current-password" required value={password} onChange={e=>{setPassword(e.target.value);if(error)setError('')}}/>
   <button type="button" className="password-toggle" onClick={()=>setShowPassword(v=>!v)} aria-label={showPassword?'Ocultar contraseña':'Mostrar contraseña'} aria-pressed={showPassword} title={showPassword?'Ocultar contraseña':'Mostrar contraseña'}>{showPassword?<EyeOff size={19}/>:<Eye size={19}/>}</button>
  </div>
  {error&&<div className="login-error" role="alert"><AlertCircle size={18} aria-hidden="true"/><span>{error}</span></div>}
  <button className="login-submit" type="submit" disabled={busy}>{busy?'Ingresando...':'Ingresar'}</button>
 </form></main>
}
