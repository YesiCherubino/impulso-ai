import type { Metadata, Viewport } from 'next';
import '@fontsource-variable/instrument-sans';
import './globals.css';
import './office-overrides.css';
import './impulso-theme.css';
import './impulso-v2.css';
import './impulso-v3.css';
import './impulso-v5.css';
import './impulso-v6.css';
export const metadata:Metadata={title:'Impulso | Backoffice comercial',description:'Sistema de gestión de consultas y contactos comerciales.',manifest:'/manifest.webmanifest',icons:{icon:'/favicon-64.png',apple:'/apple-touch-icon.png'},appleWebApp:{capable:true,title:'Impulso',statusBarStyle:'default'}};
export const viewport:Viewport={themeColor:'#2e6a57',width:'device-width',initialScale:1};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="es" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:"var d=document.documentElement;try{d.dataset.theme=localStorage.getItem('impulso-theme')==='dark'?'dark':'light';var b=localStorage.getItem('impulso-brand');if(b&&/^#[0-9a-f]{6}$/i.test(b))d.style.setProperty('--brand',b);d.dataset.density=localStorage.getItem('impulso-density')==='compacta'?'compacta':'comoda'}catch(e){d.dataset.theme='light'}"}}/></head><body>{children}</body></html>}
