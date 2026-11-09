import {NextRequest, NextResponse} from 'next/server';

export const runtime = 'nodejs';

export async function POST(req:NextRequest){
 const origin=req.headers.get('origin');
 if(origin && new URL(origin).host !== req.headers.get('host'))return NextResponse.json({detail:'Origen no autorizado'},{status:403});
 let input:{username?:string;password?:string};
 try{input=await req.json()}catch{return NextResponse.json({detail:'Solicitud inválida'},{status:400})}
 if(!input.username || !input.password)return NextResponse.json({detail:'Ingresá usuario y contraseña'},{status:400});
 const api=(process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001').replace(/\/$/,'');
 let upstream:Response;
 try{
  upstream=await fetch(`${api}/api/auth/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input),cache:'no-store',signal:AbortSignal.timeout(10000)});
 }catch(err){
  // El detalle técnico queda en la terminal de Next.js; nunca mostrar URL interna ni contraseña al usuario.
  console.error('Fallo de conexión entre Next.js y FastAPI al iniciar sesión', err);
  return NextResponse.json({detail:'No se pudo conectar con el servidor'},{status:502});
 }
 const data=await upstream.json().catch(()=>({}));
 if(!upstream.ok){
  const status=upstream.status;
  if(status===401)return NextResponse.json({detail:'Usuario o contraseña incorrectos'},{status:401});
  if(status===429)return NextResponse.json({detail:'Demasiados intentos. Intentá más tarde'},{status:429});
  if(status>=500)return NextResponse.json({detail:'No se pudo conectar con el servidor'},{status:502});
  return NextResponse.json({detail:'No se pudo iniciar sesión'},{status:status>=400&&status<500?status:400});
 }
 if(typeof data.token!=='string' || !data.user)return NextResponse.json({detail:'Respuesta de autenticación inválida'},{status:502});
 const result=NextResponse.json({user:data.user});
 result.cookies.set('impulso_session',data.token,{httpOnly:true,secure:process.env.NODE_ENV==='production',sameSite:'lax',path:'/',maxAge:8*60*60});
 return result;
}
