/* Isotipo de Impulso: flecha ascendente. Reemplaza al ícono genérico de "colapsar panel". */
export default function ImpulsoMark({size=34}:{size?:number}){
 return <svg viewBox="0 0 34 34" width={size} height={size} fill="none" aria-hidden="true" focusable="false">
  <path d="M7 25.5L14.5 18L19 22.5L27 14.5" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round"/>
  <path d="M20.5 14.5H27V21" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round"/>
 </svg>;
}
