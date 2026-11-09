import type { Metadata } from 'next';
import './globals.css';
import './office-overrides.css';
export const metadata:Metadata={title:'Impulso | Backoffice comercial',description:'Sistema de gestión de consultas y contactos comerciales.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="es"><body>{children}</body></html>}
