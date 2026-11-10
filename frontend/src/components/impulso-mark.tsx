/* Isotipo de Impulso: una I inclinada hacia adelante con una estela más corta detrás. */
export default function ImpulsoMark({size=30,solo=false}:{size?:number;solo?:boolean}){
 return <svg viewBox="0 0 40 40" width={size} height={size} fill="currentColor" aria-hidden="true" focusable="false">
  {!solo&&<polygon points="5,34 11,34 16,18 10,18" opacity="0.45"/>}
  <polygon points="15,34 22,34 31,6 24,6"/>
 </svg>;
}
