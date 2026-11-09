'use client';
import Link from 'next/link';
import {usePathname,useRouter} from 'next/navigation';
import {useEffect,useState} from 'react';
import {Inbox, ContactRound, FileCheck2, FileText, Link2, Settings, LogOut, BookOpen, Menu, X} from 'lucide-react';
import Notifications from '@/components/notifications';
import ThemeToggle from '@/components/theme-toggle';
import {api, UsuarioSesion, roleName} from '@/lib/api';

const nav=[
 {href:'/consultas',label:'Bandeja de consultas',icon:Inbox},
 {href:'/',label:'Ficha de contactos',icon:ContactRound},
 {href:'/finalizados',label:'Finalizados',icon:FileCheck2},
 {href:'/resumen-gerencial',label:'Reportes',icon:FileText},
 {href:'/integraciones',label:'Integraciones',icon:Link2},
];
export default function Shell({children}:{children:React.ReactNode}){
 const pathname=usePathname(),router=useRouter();
 const authEnabled=process.env.NEXT_PUBLIC_AUTH_ENABLED==='true';
 const [sessionReady,setSessionReady]=useState(!authEnabled);
 const [menuOpen,setMenuOpen]=useState(false);
 const [user,setUser]=useState<UsuarioSesion|null>(null);
 useEffect(()=>{
  if(!authEnabled){setSessionReady(true);return}
  let active=true;
  fetch('/api/session/me',{cache:'no-store'}).then(async r=>{if(!r.ok)throw Error('Sin sesión');return r.json()})
   .then((u:UsuarioSesion)=>{if(active){setUser(u);setSessionReady(true);const tema=u.theme==='oscuro'?'dark':'light';document.documentElement.dataset.theme=tema;window.localStorage.setItem('impulso-theme',tema);}})
   .catch(()=>{if(active)router.replace('/login')});
  return()=>{active=false};
 },[authEnabled,router]);
 async function signOut(){await fetch('/api/session/logout',{method:'POST'});router.replace('/login');router.refresh()}
 if(!sessionReady)return <div className="login-screen" style={{display:'grid',placeItems:'center',minHeight:'100vh'}}>Comprobando sesión...</div>;
 const title=pathname.startsWith('/oportunidades/')?'Ficha de contacto':pathname.startsWith('/administracion')?'Administración':nav.find(n=>n.href===pathname)?.label??'Impulso';
 return <div className="app-shell office-app v2-office">
  <aside className={`sidebar ${menuOpen?'sidebar-open':''}`}>
   <div className="office-brand-row"><Link href="/consultas" className="brand v2-brand" onClick={()=>setMenuOpen(false)}><span className="impulso-mark" aria-hidden="true"><svg viewBox="0 0 34 34" width="34" height="34" fill="none"><path d="M7 24L21 9M16 27L30 12" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round"/></svg></span><span><strong>Impulso</strong><small>Gestión comercial</small></span></Link><button className="office-close-menu" onClick={()=>setMenuOpen(false)} aria-label="Cerrar menú"><X size={19}/></button></div>
   <div className="side-group-label">GESTIÓN COMERCIAL</div>
   <nav className="side-nav" aria-label="Navegación principal">{[...nav,...(user?.role==='administrador'?[{href:'/administracion',label:'Administración',icon:Settings}]:[])].map(item=>{const Icon=item.icon;const active=pathname===item.href;return <Link key={item.href} href={item.href} className={active?'active':''} aria-current={active?'page':undefined} onClick={()=>setMenuOpen(false)}><Icon size={18} strokeWidth={1.6}/><span>{item.label}</span></Link>})}</nav>
   <div className="office-sidebar-footer v2-sidebar-footer">
    <ThemeToggle userTheme={user?.theme} authenticated={authEnabled && !!user} onThemeSaved={theme=>setUser(old=>old?{...old,theme}:old)}/>
    <div className="v2-user-label"><span className="v2-avatar">{(user?.name||'Usuario').slice(0,1).toUpperCase()}</span><span><strong>{user?.name||'Usuario comercial'}</strong><small>{roleName[user?.role||'ventas']}</small></span></div>
    {authEnabled&&<button type="button" className="v2-footer-action" onClick={()=>void signOut()}><LogOut size={18} strokeWidth={1.6}/> Cerrar sesión</button>}
    <a href="/guia-de-uso.pdf" className="v2-footer-action" target="_blank" rel="noopener noreferrer"><BookOpen size={18} strokeWidth={1.6}/> Guía de usuario</a>
   </div>
  </aside>
  <div className="workspace"><header className="topbar"><button type="button" className="mobile-nav-toggle" aria-label="Abrir navegación" onClick={()=>setMenuOpen(!menuOpen)}>{menuOpen?<X size={20}/>:<Menu size={20}/>}</button><div className="top-label">Área comercial <span>/</span> {title}</div><div className="topbar-actions"><Notifications/></div></header>{menuOpen&&<button className="mobile-nav-shade" aria-label="Cerrar navegación" onClick={()=>setMenuOpen(false)}/>}<main className="content">{children}</main></div>
 </div>;
}
