import {NextRequest,NextResponse} from 'next/server';
const API=(process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001').replace(/\/$/,'');
export async function POST(req:NextRequest){
 const origin=req.headers.get('origin');
 if(origin && new URL(origin).host!==req.headers.get('host'))return NextResponse.json({detail:'Origen no autorizado'},{status:403});
 const token=req.cookies.get('impulso_session')?.value;
 if(token){try{await fetch(`${API}/api/auth/logout`,{method:'POST',headers:{'X-Session-Token':token},cache:'no-store'})}catch{}}
 const resp=NextResponse.json({ok:true});
 resp.cookies.set('impulso_session','',{httpOnly:true,path:'/',maxAge:0});
 return resp;
}
