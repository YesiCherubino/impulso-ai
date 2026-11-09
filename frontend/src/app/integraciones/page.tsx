import Shell from '@/components/shell';
import {ArrowUpRight, Database, Mail, MessageSquareText, CalendarDays, Globe} from 'lucide-react';

const integrations=[
 {title:'WhatsApp Business', label:'Canal de atención', icon:MessageSquareText, details:'Recepción de consultas, identificación de conversaciones y preparación de respuestas. Requiere cuenta, permisos y API oficial de WhatsApp Business.'},
 {title:'Google Calendar', label:'Agenda y eventos', icon:CalendarDays, details:'Conexión de una cuenta Google para sincronizar actividades comerciales. Requiere autorización OAuth; todavía no está conectada.'},
 {title:'Formulario web de Pasmanter', label:'Canal de consultas · Demo', icon:Globe, details:'Entradas simuladas con origen Web. La integración real con el formulario del sitio se realizará en una etapa posterior.'},
 {title:'Gmail', label:'Correo comercial', icon:Mail, details:'Importación y clasificación de correos entrantes. Eventual creación de borradores para revisión, con autorización de la cuenta y controles de privacidad.'},
 {title:'Tango Gestión', label:'Sistema de gestión / ERP', icon:Database, details:'Posible consulta de clientes, artículos, presupuestos y pedidos. El alcance depende de los módulos y los mecanismos de integración disponibles en la instalación de cada empresa.'},
];
export default function Integraciones(){return <Shell>
 <div className="office-page-title"><div><h1>Integraciones</h1></div></div>
 <div className="office-integrations-list">{integrations.map(c=>{const Icon=c.icon;return <section key={c.title} className="office-integration"><div className="office-integration-logo"><Icon size={21}/></div><div className="office-integration-main"><div className="office-integration-header"><h2>{c.title}</h2><span className="office-planned">Pendiente</span></div><small>{c.label}</small><p>{c.details}</p></div><ArrowUpRight className="office-integration-arrow" size={18}/></section>})}</div>

 </Shell>}
