import type { Metadata } from 'next';
import './globals.css';
import './office-overrides.css';
import './impulso-theme.css';
import './impulso-v2.css';
import './impulso-v3.css';
import './impulso-v5.css';
export const metadata:Metadata={title:'Impulso | Backoffice comercial',description:'Sistema de gestión de consultas y contactos comerciales.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="es" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:"try{document.documentElement.dataset.theme=localStorage.getItem('impulso-theme')==='dark'?'dark':'light'}catch(e){document.documentElement.dataset.theme='light'}"}}/></head><body>{children}</body></html>}
