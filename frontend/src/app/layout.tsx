import type { Metadata, Viewport } from 'next';
import '@fontsource-variable/instrument-sans';
import './globals.css';
import './office-overrides.css';
import './impulso-theme.css';
import './impulso-v2.css';
import './impulso-v3.css';
import './impulso-v5.css';
import './impulso-v6.css';
// Dirección pública para las vistas previas del link (WhatsApp, mail). En Vercel se toma sola.
const sitio=process.env.NEXT_PUBLIC_SITE_URL||(process.env.VERCEL_PROJECT_PRODUCTION_URL?`https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`:'http://localhost:3000');
const descripcion='Consultas de WhatsApp, email y web, cotizaciones online y seguimiento comercial, en un solo lugar.';
export const metadata:Metadata={metadataBase:new URL(sitio),title:'Impulso Comercial',description:descripcion,
 openGraph:{title:'Impulso Comercial',description:descripcion,siteName:'Impulso Comercial',locale:'es_AR',type:'website'},
 twitter:{card:'summary_large_image',title:'Impulso Comercial',description:descripcion},manifest:'/manifest.webmanifest',icons:{icon:'/favicon-64.png',apple:'/apple-touch-icon.png'},appleWebApp:{capable:true,title:'Impulso',statusBarStyle:'default'}};
export const viewport:Viewport={themeColor:'#2e6a57',width:'device-width',initialScale:1};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="es" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:"var d=document.documentElement;try{var t=localStorage.getItem('impulso-theme-pref');d.dataset.theme=t==='oscuro'?'dark':t==='claro'?'light':(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');var b=localStorage.getItem('impulso-brand');if(b&&/^#[0-9a-f]{6}$/i.test(b))d.style.setProperty('--brand',b);d.dataset.density=localStorage.getItem('impulso-density')==='compacta'?'compacta':'comoda'}catch(e){d.dataset.theme=window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}"}}/></head><body>{children}</body></html>}
