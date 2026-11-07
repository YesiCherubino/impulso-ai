'use client';
import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {LayoutDashboard, TrendingUp, BriefcaseBusiness, ShieldCheck, Sparkles, BarChart3} from 'lucide-react';
export default function Shell({children}:{children:React.ReactNode}){
 const pathname=usePathname();
 return <div className="app-shell"><aside className="sidebar"><Link href="/" className="brand"><span className="brand-icon"><TrendingUp size={23}/></span><span><strong>impulso</strong><small>Gestión comercial</small></span></Link>
 <div className="side-group-label">ESPACIO DE TRABAJO</div><nav className="side-nav"><Link className={pathname==='/'?'active':''} href="/"><LayoutDashboard size={18}/> Panel comercial</Link><Link className={pathname.startsWith('/oportunidades')?'active':''} href="/#oportunidades"><BriefcaseBusiness size={18}/> Oportunidades</Link><Link className={pathname.startsWith("/automatizaciones")?"active":""} href="/automatizaciones"><Sparkles size={18}/> Automatizaciones con IA</Link><Link className={pathname.startsWith("/resumen-gerencial")?"active":""} href="/resumen-gerencial"><BarChart3 size={18}/> Resumen gerencial</Link></nav>
 <div className="sidebar-bottom"><div className="side-info"><Sparkles size={17}/><span>Automatizaciones con IA<br/><small>Analizá consultas en segundos</small></span></div><p>Prototipo independiente<br/>Todos los datos son ficticios.</p></div></aside>
 <div className="workspace"><header className="topbar"><div className="top-label">Workspace <span>/</span> Ventas</div><div className="top-right"><span className="status-dot"/> API comercial <span className="demo-pill"><ShieldCheck size={13}/> DEMO</span></div></header><main className="content">{children}</main></div></div>;
}
