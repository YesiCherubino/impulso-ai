/* Pulso del día: consultas entrantes por hora, con un punto que late en la hora actual. */
export default function Pulso({datos}:{datos:number[]}){
 const W=600,H=44,pad=4,max=Math.max(1,...datos);
 const hour=new Date().getHours();
 const pts=datos.slice(0,hour+1).map((v,i)=>[pad+i*(W-2*pad)/23,H-pad-(v/max)*(H-2*pad-6)] as const);
 const d=pts.map(([x,y],i)=>`${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
 const last=pts.at(-1);const total=datos.reduce((a,b)=>a+b,0);
 return <div className="v7-pulse" title={`${total} consultas hoy`}>
  <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={`${total} consultas recibidas hoy, por hora`}>
   <line x1={pad} x2={W-pad} y1={H-pad} y2={H-pad} className="v7-pulse-base"/>
   {d&&<path d={d} className="v7-pulse-line" vectorEffect="non-scaling-stroke"/>}
  </svg>
  {last&&<span className="v7-pulse-dot" style={{left:`${(last[0]/W)*100}%`,top:`${(last[1]/H)*100}%`}}/>}
  <span className="v7-pulse-label"><b>{total}</b> hoy</span>
 </div>;
}
