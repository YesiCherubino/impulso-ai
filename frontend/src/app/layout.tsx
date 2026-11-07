import type { Metadata } from 'next';
import './globals.css';
export const metadata:Metadata={title:'Impulso | Gestión comercial inteligente',description:'Demo de gestión comercial con oportunidades y seguimiento.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="es"><body>{children}</body></html>}
