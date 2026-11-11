'use client';
import {MessageCircle,Mail,Globe,Boxes,CalendarDays,FileSpreadsheet,FileDown,FileCheck2,Send,Factory,ShieldCheck,ShoppingCart,Landmark,Headset,ArrowRight,ArrowDown} from 'lucide-react';
import Shell from '@/components/shell';
import ImpulsoMark from '@/components/impulso-mark';

type Estado='hoy'|'proximo'|'medida';
type Integracion={nombre:string;resuelve:string;icon:typeof Mail;estado:Estado};

const INTEGRACIONES:Integracion[]=[
 {nombre:'Cotización online',resuelve:'El cliente abre la cotización desde un link y la acepta; la gestión pasa sola a Concretada.',icon:FileCheck2,estado:'hoy'},
 {nombre:'Importar desde Tango (Excel o CSV)',resuelve:'Clientes y artículos con precios, sin cargarlos a mano.',icon:FileSpreadsheet,estado:'hoy'},
 {nombre:'Exportar a Excel',resuelve:'Gestiones, contactos, cotizaciones y reportes, listos para compartir.',icon:FileDown,estado:'hoy'},
 {nombre:'WhatsApp Business',resuelve:'Las consultas entran solas y se responden desde Impulso, sin copiar y pegar.',icon:MessageCircle,estado:'proximo'},
 {nombre:'Gmail u Outlook',resuelve:'Los mails de clientes llegan a la bandeja y las respuestas salen desde acá.',icon:Mail,estado:'proximo'},
 {nombre:'Formulario de la web',resuelve:'Cada consulta del sitio entra con producto, cantidad y localidad.',icon:Globe,estado:'proximo'},
 {nombre:'Envío de cotizaciones por mail',resuelve:'La cotización y su link de aceptación le llegan directo al cliente.',icon:Send,estado:'proximo'},
 {nombre:'Tango Gestión en línea',resuelve:'Clientes, precios y pedidos sincronizados, sin importar archivos.',icon:Boxes,estado:'medida'},
 {nombre:'Google Calendar u Outlook',resuelve:'Llamadas, reuniones y seguimientos en el calendario de cada vendedor.',icon:CalendarDays,estado:'medida'},
];
const GRUPOS:[Estado,string,string][]=[
 ['hoy','Ya funciona','Disponible en esta demo.'],
 ['proximo','Próximo paso','Se conectan con los accesos de la empresa.'],
 ['medida','A medida','Según los sistemas que usa cada área.'],
];
const AREAS:[string,string,typeof Factory][]=[
 ['Producción y planificación','Recibe la orden cuando se concreta una venta y ve fechas y cantidades comprometidas.',Factory],
 ['Calidad y ANMAT','Sigue los trámites, registros y fórmulas de cada proyecto.',ShieldCheck],
 ['Compras','Ve los insumos y envases que necesita cada pedido.',ShoppingCart],
 ['Administración','Factura y hace el seguimiento de cobranzas de lo cerrado.',Landmark],
 ['Posventa','Atiende reclamos y recompras con el historial completo del cliente.',Headset],
];

/* Integraciones: qué se conecta hoy, qué sigue y cómo se extiende a otras áreas. Se lee en 30 segundos. */
export default function Integraciones(){
 return <Shell>
  <div className="v2-page-head"><h1>Integraciones</h1></div>
  <section className="panel v12-flow" aria-label="Cómo se conecta">
   <div className="v12-flow-col"><small>Llegan las consultas</small>
    {([['WhatsApp',MessageCircle],['Email',Mail],['Formulario web',Globe]] as [string,typeof Mail][]).map(([n,I])=><span key={n} className="v12-node"><I size={16}/>{n}</span>)}</div>
   <span className="v12-arrow" aria-hidden="true"><ArrowRight size={20} className="v12-arrow-h"/><ArrowDown size={20} className="v12-arrow-v"/></span>
   <div className="v12-hub"><span className="v12-hub-mark"><ImpulsoMark size={34}/></span><strong>Impulso Comercial</strong><small>Bandeja, gestión, cotizaciones y reportes, con IA</small></div>
   <span className="v12-arrow" aria-hidden="true"><ArrowRight size={20} className="v12-arrow-h"/><ArrowDown size={20} className="v12-arrow-v"/></span>
   <div className="v12-flow-col"><small>Se conecta con</small>
    {([['Tango Gestión',Boxes],['Google Calendar',CalendarDays],['Excel',FileSpreadsheet]] as [string,typeof Mail][]).map(([n,I])=><span key={n} className="v12-node"><I size={16}/>{n}</span>)}</div>
  </section>

  <div className="v12-groups">{GRUPOS.map(([e,titulo,nota])=><section key={e} className={`v12-group is-${e}`} aria-label={titulo}>
   <h2><span className="v12-dot"/>{titulo}<small>{nota}</small></h2>
   <ul>{INTEGRACIONES.filter(i=>i.estado===e).map(i=>{const I=i.icon;return <li key={i.nombre}><span className="v12-icon"><I size={18}/></span><span><strong>{i.nombre}</strong><small>{i.resuelve}</small></span></li>})}</ul>
  </section>)}</div>

  <section className="panel v12-areas" aria-label="Otras áreas">
   <h2>La misma base, para otras áreas</h2>
   <p className="muted">Empezamos por Ventas. Cada área vería lo suyo y el pase entre áreas quedaría registrado en la misma gestión.</p>
   <ul>{AREAS.map(([n,d,I])=><li key={n}><span className="v12-icon"><I size={18}/></span><span><strong>{n}</strong><small>{d}</small></span></li>)}</ul>
  </section>
  <p className="v12-foot">Demo con datos de prueba. Las integraciones se configuran con los accesos de la empresa.</p>
 </Shell>;
}
