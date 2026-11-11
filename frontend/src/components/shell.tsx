'use client';
import Link from 'next/link';
import {usePathname,useRouter} from 'next/navigation';
import {useEffect,useRef,useState} from 'react';
import {Inbox,ContactRound,CalendarDays,FileCheck2,FileText,Settings,LogOut,BookOpen,Menu,X,Sun,Search,MessagesSquare,Eye,Receipt,Plug} from 'lucide-react';
import Notifications from '@/components/notifications';
import ImpulsoMark from '@/components/impulso-mark';
import {CargaInicial,BarraNavegacion} from '@/components/skeleton';
import CommandPalette from '@/components/command-palette';
import TeamChat from '@/components/team-chat';
import ThemeToggle,{aplicarTema} from '@/components/theme-toggle';
import {api,UsuarioSesion,roleName,setVerComo} from '@/lib/api';

const nav=[
 {href:'/consultas',label:'Bandeja',icon:Inbox},
 {href:'/mi-dia',label:'Mi día',icon:Sun},
 {href:'/contactos',label:'Contactos',icon:ContactRound},
 {href:'/cotizaciones',label:'Cotizaciones',icon:Receipt},
 {href:'/agenda',label:'Agenda',icon:CalendarDays},
 {href:'/finalizados',label:'Finalizados',icon:FileCheck2},
 {href:'/resumen-gerencial',label:'Reportes',icon:FileText},
 {href:'/integraciones',label:'Integraciones',icon:Plug},
 {href:'/ajustes',label:'Ajustes',icon:Settings},
];
export default function Shell({children}:{children:React.ReactNode}){
 const pathname=usePathname(),router=useRouter();
 const authEnabled=process.env.NEXT_PUBLIC_AUTH_ENABLED==='true';
 const [sessionReady,setSessionReady]=useState(!authEnabled);
 const [menuOpen,setMenuOpen]=useState(false);
 const [user,setUser]=useState<UsuarioSesion|null>(null);
 const [palette,setPalette]=useState(false),[keys,setKeys]=useState(false);
 // Color de acento del cliente: se aplica al instante y se recuerda para la próxima carga.
 useEffect(()=>{if(!sessionReady)return;void api<{color_acento?:string}>('/api/empresa').then(e=>{if(e.color_acento){document.documentElement.style.setProperty('--brand',e.color_acento);try{localStorage.setItem('impulso-brand',e.color_acento)}catch{/* sin almacenamiento */}}}).catch(()=>{})},[sessionReady]);
 // Atajos globales: "?" muestra la ayuda, "c" abre el chat del equipo y Ctrl+K busca.
 useEffect(()=>{const onKey=(e:KeyboardEvent)=>{
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();setPalette(v=>!v);return}
  const t=e.target as HTMLElement;if(t&&(t.isContentEditable||/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))||e.ctrlKey||e.metaKey||e.altKey)return;
  if(e.key==='f'&&!document.querySelector('[role=dialog]')){e.preventDefault();if(window.location.pathname==='/consultas')window.dispatchEvent(new Event('impulso:foco'));else router.push('/consultas?foco=1');return}
  if(e.key==='?'){e.preventDefault();setKeys(v=>!v)}else if(e.key==='c'&&!document.querySelector('[role=dialog]')){e.preventDefault();window.dispatchEvent(new Event('impulso:abrir-chat'))}else if(e.key==='Escape')setKeys(false)};
  window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey)},[router]);
 useEffect(()=>{
  if(!authEnabled){setSessionReady(true);return}
  let active=true;
  fetch('/api/session/me',{cache:'no-store'}).then(async r=>{if(!r.ok)throw Error('Sin sesión');return r.json()})
   .then((u:UsuarioSesion)=>{if(active){setUser(u);setSessionReady(true);aplicarTema(u.theme==='claro'||u.theme==='oscuro'?u.theme:'auto');}})
   .catch(()=>{if(active)router.replace('/login')});
  return()=>{active=false};
 },[authEnabled,router]);
 // Menú lateral en celular: sin scroll de la página de atrás, Esc para cerrar y arrastre hacia la izquierda.
 const asideRef=useRef<HTMLElement|null>(null),drag=useRef<{x:number;y:number;dx:number;lock:boolean|null}|null>(null);
 useEffect(()=>{if(!menuOpen)return;const b=document.body,h=document.documentElement,prevO=b.style.overflow,prevH=h.style.overflow;b.style.overflow='hidden';h.style.overflow='hidden';
  const k=(e:KeyboardEvent)=>{if(e.key==='Escape')setMenuOpen(false)};window.addEventListener('keydown',k);
  return()=>{b.style.overflow=prevO;h.style.overflow=prevH;window.removeEventListener('keydown',k)}},[menuOpen]);
 useEffect(()=>{setMenuOpen(false)},[pathname]);
 function touchStart(e:React.TouchEvent){if(!menuOpen)return;const t=e.touches[0];drag.current={x:t.clientX,y:t.clientY,dx:0,lock:null}}
 function touchMove(e:React.TouchEvent){const d=drag.current;if(!d)return;const t=e.touches[0];const dx=t.clientX-d.x,dy=t.clientY-d.y;
  if(d.lock===null&&(Math.abs(dx)>8||Math.abs(dy)>8))d.lock=Math.abs(dx)>Math.abs(dy);
  if(d.lock){d.dx=Math.min(0,dx);if(asideRef.current){asideRef.current.style.transition='none';asideRef.current.style.transform=`translateX(${d.dx}px)`}}}
 function touchEnd(){const d=drag.current;drag.current=null;const el=asideRef.current;if(!d||!el)return;el.style.transition='';el.style.transform='';
  if(d.lock&&d.dx<-70)setMenuOpen(false)}
 async function signOut(){document.cookie='impulso_ver_como=; path=/; max-age=0';await fetch('/api/session/logout',{method:'POST'});router.replace('/login');router.refresh()}
 if(!sessionReady)return <CargaInicial/>;
 const title=pathname.startsWith('/oportunidades/')?'Contacto':nav.find(n=>pathname.startsWith(n.href))?.label??'Impulso Comercial';
 const isAdmin=user?.role==='administrador'||user?.rol_real==='administrador';
 const go=(href:string)=>()=>setMenuOpen(false);
 return <div className="app-shell office-app v2-office">
  <BarraNavegacion/>
  <aside ref={asideRef} className={`sidebar ${menuOpen?'sidebar-open':''}`} onTouchStart={touchStart} onTouchMove={touchMove} onTouchEnd={touchEnd} onTouchCancel={touchEnd}>
   <div className="office-brand-row"><Link href="/consultas" className="brand v2-brand v7-brand" onClick={go('/consultas')}><span className="impulso-mark" aria-hidden="true"><ImpulsoMark/></span><span className="v10-wordmark"><strong>Impulso</strong><small>Comercial</small></span></Link><button className="office-close-menu" onClick={()=>setMenuOpen(false)} aria-label="Cerrar menú"><X size={19}/></button></div>
   <nav className="side-nav" aria-label="Navegación principal">{nav.map(item=>{const Icon=item.icon;const active=pathname.startsWith(item.href)||(item.href==='/contactos'&&pathname.startsWith('/oportunidades/'));return <Link key={item.href} href={item.href} className={active?'active':''} aria-current={active?'page':undefined} onClick={go(item.href)}><Icon size={17} strokeWidth={1.6}/><span>{item.label}</span></Link>})}</nav>
   <div className="office-sidebar-footer v2-sidebar-footer">
    <ThemeToggle userTheme={user?.theme} authenticated={!!user} onThemeSaved={t=>setUser(o=>o?{...o,theme:t}:o)}/>
    <div className="v2-user-label"><span className="v2-avatar">{(user?.name||'Usuario').slice(0,1).toUpperCase()}</span><span><strong>{user?.name||'Usuario'}</strong>{user&&<small className={`v8-role is-${user.rol_real||user.role}`}>{roleName[user.rol_real||user.role]}</small>}</span></div>
    {isAdmin&&<label className="v7-pref"><span><Eye size={14}/> Ver como</span><select aria-label="Ver como" value={user?.viendo_como||''} onChange={e=>setVerComo(e.target.value as ''|'ventas'|'gerencia')}><option value="">Administrador</option><option value="ventas">Ventas</option><option value="gerencia">Gerencia</option></select></label>}
    {authEnabled&&<button type="button" className="v2-footer-action" onClick={()=>void signOut()}><LogOut size={17} strokeWidth={1.6}/> Cerrar sesión</button>}
    <a href="/guia-de-uso.pdf" className="v2-footer-action" target="_blank" rel="noopener noreferrer"><BookOpen size={17} strokeWidth={1.6}/> Guía de usuario</a>
   </div>
  </aside>
  <div className="workspace">
   {user?.viendo_como&&<div className="v7-viewas" role="status"><Eye size={14}/> Estás viendo como <b>{roleName[user.viendo_como]}</b><button type="button" onClick={()=>setVerComo('')}>Volver a Administrador</button></div>}
   <header className="topbar"><button type="button" className="mobile-nav-toggle" aria-label="Abrir navegación" aria-expanded={menuOpen} onClick={()=>setMenuOpen(!menuOpen)}><Menu size={20}/></button><div className="top-label">{title}</div><div className="topbar-actions"><button type="button" className="v6-search-trigger" onClick={()=>setPalette(true)} aria-label="Buscar (Ctrl+K)" title="Buscar (Ctrl+K)"><Search size={16}/><span className="v5-hide-mobile">Buscar</span><kbd className="v5-hide-mobile">Ctrl K</kbd></button><TeamChat user={user}/><Notifications/></div></header>
   <button type="button" className={`mobile-nav-shade v11-shade ${menuOpen?'is-open':''}`} aria-label="Cerrar navegación" tabIndex={menuOpen?0:-1} aria-hidden={!menuOpen} onClick={()=>setMenuOpen(false)}/>
   <main className="content">{children}</main>
  </div>
  <nav className="v7-bottom-nav" aria-label="Accesos rápidos">
   <Link href="/consultas" className={pathname.startsWith('/consultas')?'active':''}><Inbox size={19}/><span>Bandeja</span></Link>
   <Link href="/mi-dia" className={pathname.startsWith('/mi-dia')?'active':''}><Sun size={19}/><span>Mi día</span></Link>
   <button type="button" onClick={()=>window.dispatchEvent(new Event('impulso:abrir-chat'))}><MessagesSquare size={19}/><span>Chat</span></button>
   <button type="button" onClick={()=>setPalette(true)}><Search size={19}/><span>Buscar</span></button>
  </nav>
  <CommandPalette open={palette} onClose={()=>setPalette(false)}/>
  {keys&&<div className="modal-backdrop v2-overlay" onMouseDown={()=>setKeys(false)}><div className="modal v5-small-modal" role="dialog" aria-label="Atajos de teclado" onMouseDown={e=>e.stopPropagation()}><div className="modal-head"><h2>Atajos de teclado</h2><button className="icon-button" aria-label="Cerrar" onClick={()=>setKeys(false)}><X size={18}/></button></div>
   <dl className="v7-keys"><dt><kbd>Ctrl</kbd> <kbd>K</kbd></dt><dd>Buscar</dd><dt><kbd>F</kbd></dt><dd>Modo foco: la siguiente consulta a responder</dd><dt><kbd>C</kbd></dt><dd>Chat del equipo</dd><dt><kbd>J</kbd> <kbd>K</kbd></dt><dd>Moverse por la bandeja</dd><dt><kbd>Enter</kbd></dt><dd>Abrir la conversación</dd><dt><kbd>R</kbd></dt><dd>Escribir la respuesta</dd><dt><kbd>A</kbd></dt><dd>Asignarme la gestión</dd><dt><kbd>/</kbd></dt><dd>Respuestas rápidas</dd><dt><kbd>Ctrl</kbd> <kbd>Enter</kbd></dt><dd>Copiar y registrar</dd><dt><kbd>Esc</kbd></dt><dd>Cerrar</dd><dt><kbd>?</kbd></dt><dd>Esta ayuda</dd></dl></div></div>}
 </div>;
}
