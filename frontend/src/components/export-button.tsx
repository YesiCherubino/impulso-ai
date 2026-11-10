'use client';
import {useState} from 'react';
import {FileSpreadsheet,Loader2} from 'lucide-react';
import {api,ArchivoB64,guardarArchivo} from '@/lib/api';

/* Descarga un Excel generado por el backend con los mismos filtros de la pantalla. */
export default function ExportButton({path,label='Exportar a Excel',compact=false,onError}:{path:string;label?:string;compact?:boolean;onError?:(m:string)=>void}){
 const [busy,setBusy]=useState(false);
 async function run(){setBusy(true);try{guardarArchivo(await api<ArchivoB64>(path))}catch(e){onError?.(e instanceof Error?e.message:'No se pudo exportar')}finally{setBusy(false)}}
 return <button type="button" className="btn btn-outline" onClick={()=>void run()} disabled={busy} title={label} aria-label={label}>{busy?<Loader2 size={16} className="v5-spin"/>:<FileSpreadsheet size={16}/>}{!compact&&<span className="v5-hide-mobile">{busy?'Exportando…':label}</span>}</button>;
}
