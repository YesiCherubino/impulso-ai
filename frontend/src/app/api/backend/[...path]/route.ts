import {NextRequest,NextResponse} from 'next/server';
const API=(process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001').replace(/\/$/,'');
type Ctx={params:Promise<{path:string[]}>};
async function proxy(req:NextRequest,ctx:Ctx){
 const token=req.cookies.get('impulso_session')?.value;
 if(!token)return NextResponse.json({detail:'Sesión no iniciada'},{status:401});
 if(req.method!=='GET'){
  const origin=req.headers.get('origin');
  if(origin && new URL(origin).host!==req.headers.get('host'))return NextResponse.json({detail:'Origen no autorizado'},{status:403});
 }
 const {path}=await ctx.params;
 if(!path?.length || path.some(x=>x==='..'||x.includes('/')||x.includes('\\')))return NextResponse.json({detail:'Ruta inválida'},{status:400});
 const target=`${API}/api/${path.map(encodeURIComponent).join('/')}${req.nextUrl.search}`;
 let response:Response;
 try{response=await fetch(target,{method:req.method,headers:{'Content-Type':'application/json','X-Session-Token':token},body:req.method==='GET'?undefined:await req.text(),cache:'no-store',redirect:'manual'})}
 catch{return NextResponse.json({detail:'No se pudo conectar al servicio'},{status:502})}
 const body=await response.text();
 return new NextResponse(body,{status:response.status,headers:{'Content-Type':response.headers.get('content-type')||'application/json','Cache-Control':'no-store'}});
}
export const GET=proxy;
export const POST=proxy;
