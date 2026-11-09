import {NextRequest,NextResponse} from 'next/server';
const API=(process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001').replace(/\/$/,'');
export async function GET(req:NextRequest){
 const token=req.cookies.get('impulso_session')?.value;
 if(!token)return NextResponse.json({detail:'Sesión no iniciada'},{status:401});
 try{
  const resp=await fetch(`${API}/api/auth/me`,{headers:{'X-Session-Token':token},cache:'no-store'});
  if(!resp.ok)return NextResponse.json({detail:'Sesión vencida'},{status:401});
  return NextResponse.json(await resp.json(),{headers:{'Cache-Control':'no-store'}});
 }catch{return NextResponse.json({detail:'Servicio no disponible'},{status:502})}
}
