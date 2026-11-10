import {NextRequest,NextResponse} from 'next/server';
const API=(process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001').replace(/\/$/,'');
type Ctx={params:Promise<{path:string[]}>};
/* Cotización online: rutas públicas (sin sesión). Solo se reenvía /api/publico/cotizaciones/... */
async function proxy(req:NextRequest,ctx:Ctx){
 const {path}=await ctx.params;
 if(!path?.length||path[0]!=='cotizaciones'||path.length>3||path.some(x=>x==='..'||x.includes('/')||x.includes('\\')))return NextResponse.json({detail:'Ruta inválida'},{status:400});
 const target=`${API}/api/publico/${path.map(encodeURIComponent).join('/')}`;
 let response:Response;
 try{response=await fetch(target,{method:req.method,headers:{'Content-Type':'application/json'},body:req.method==='GET'?undefined:await req.text(),cache:'no-store',redirect:'manual'})}
 catch{return NextResponse.json({detail:'No se pudo conectar al servicio'},{status:502})}
 return new NextResponse(await response.text(),{status:response.status,headers:{'Content-Type':response.headers.get('content-type')||'application/json','Cache-Control':'no-store'}});
}
export const GET=proxy;
export const POST=proxy;
