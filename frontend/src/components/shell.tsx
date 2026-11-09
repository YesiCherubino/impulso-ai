'use client';
import Link from 'next/link';
import {usePathname,useRouter} from 'next/navigation';
import {useEffect,useState} from 'react';
import {BriefcaseBusiness,Archive,BarChart3,Inbox,Menu,X,Plug,PanelLeftClose,BookOpen,LogOut} from 'lucide-react';
import Notifications from '@/components/notifications';
const nav=[
 {href:'/consultas',label:'Consultas',icon:Inbox},
 {href:'/',label:'Contactos comerciales',icon:BriefcaseBusiness},
 {href:'/finalizados',label:'Contactos finalizados',icon:Archive},
 {href:'/resumen-gerencial',label:'Reportes',icon:BarChart3},
 {href:'/integraciones',label:'Integraciones',icon:Plug},
];
export default function Shell({children}:{children:React.ReactNode}){
 const pathname=usePathname(),router=useRouter();
 const authEnabled=process.env.NEXT_PUBLIC_AUTH_ENABLED==='true';
 const [sessionReady,setSessionReady]=useState(!authEnabled);
 const [menuOpen,setMenuOpen]=useState(false);
 const [displayUser,setDisplayUser]=useState('Usuario comercial');
 const [editingUser,setEditingUser]=useState(false);
 useEffect(()=>{
  if(!authEnabled){const n=window.localStorage.getItem('impulso-display-user');if(n?.trim())setDisplayUser(n.trim());return}
  let mounted=true;
  fetch('/api/session/me',{cache:'no-store'}).then(async r=>{if(!r.ok)throw Error('Sin sesión');return r.json()}).then((u:{name:string})=>{if(mounted){setDisplayUser(u.name);setSessionReady(true)}}).catch(()=>{if(mounted)router.replace('/login')});
  return()=>{mounted=false};
 },[authEnabled,router]);
 async function signOut(){await fetch('/api/session/logout',{method:'POST'});router.replace('/login');router.refresh()}
 function saveUser(next:string){const name=next.trim().slice(0,60)||'Usuario comercial';setDisplayUser(name);window.localStorage.setItem('impulso-display-user',name);setEditingUser(false)}
 if(!sessionReady)return <div className="login-screen" style={{display:'grid',placeItems:'center',minHeight:'100vh'}}>Comprobando sesión...</div>;
 const title=pathname.startsWith('/oportunidades/')?'Contacto comercial':nav.find(n=>n.href===pathname)?.label??'Impulso';
 return <div className="app-shell office-app">
  <aside className={`sidebar ${menuOpen?'sidebar-open':''}`}>
   <div className="office-brand-row"><Link href="/consultas" className="brand" onClick={()=>setMenuOpen(false)}><span className="brand-icon"><PanelLeftClose size={21}/></span><span><strong>Impulso</strong><small>Gestión comercial</small></span></Link><button type="button" className="office-close-menu" onClick={()=>setMenuOpen(false)} aria-label="Cerrar menú"><X size={19}/></button></div>
   <div className="side-group-label">VENTAS</div>
   <nav className="side-nav" aria-label="Navegación principal">{nav.map(item=>{const Icon=item.icon;const active=pathname===item.href;return <Link key={item.href} href={item.href} className={active?'active':''} aria-current={active?'page':undefined} onClick={()=>setMenuOpen(false)}><Icon size={17}/><span>{item.label}</span></Link>})}</nav>
   <div className="office-sidebar-footer"><div className="office-user-heading">Usuario</div>{!authEnabled&&editingUser?<form className="office-user-edit" onSubmit={e=>{e.preventDefault();saveUser(displayUser)}}><input aria-label="Nombre para mostrar" maxLength={60} value={displayUser} onChange={e=>setDisplayUser(e.target.value)} autoFocus/><button type="submit" className="office-user-save">Guardar</button></form>:<button type="button" className="office-user-button" onClick={()=>{if(!authEnabled)setEditingUser(true)}} title={authEnabled?'Usuario de la sesión':'Cambiar nombre para mostrar'}><span className="office-user-avatar">{displayUser.charAt(0).toUpperCase()}</span><span className="office-user-name">{displayUser}</span></button>}{authEnabled&&<button type="button" className="office-guide-link" onClick={()=>void signOut()}><LogOut size={16}/> Cerrar sesión</button>}</div>
  </aside>
  <div className="workspace"><header className="topbar"><button type="button" className="mobile-nav-toggle" aria-label="Abrir navegación" onClick={()=>setMenuOpen(!menuOpen)}>{menuOpen?<X size={20}/>:<Menu size={20}/>}</button><div className="top-label">Área comercial <span>/</span> {title}</div><div className="topbar-actions"><a href="/guia-de-uso.pdf" className="guide-header-link" aria-label="Guía de usuario" target="_blank" rel="noopener noreferrer"><BookOpen size={16}/> <span>Guía de usuario</span></a><Notifications/></div></header>{menuOpen&&<button type="button" aria-label="Cerrar navegación" className="mobile-nav-shade" onClick={()=>setMenuOpen(false)}/>}<main className="content">{children}</main></div>
 </div>;
}
