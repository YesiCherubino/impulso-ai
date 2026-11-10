# Impulso — Rediseño de backoffice comercial

## Qué cambia
- Identidad visual sobria: azul petróleo, grises, tablas y bordes discretos.
- Bandeja de Consultas prioritaria: lista izquierda y detalle a la derecha en escritorio.
- En celular: una sola vista a la vez, con navegación por menú y vuelta a la bandeja.
- Acciones con nombres operativos, sin iconografía o mensajes promocionales de IA.
- Nueva pantalla **Integraciones** que documenta WhatsApp Business, Gmail y Tango Gestión como **futuras**, no activas.
- Mensajes de error comprensibles para el usuario, sin mencionar puertos locales.

## Aplicar sobre el proyecto que ya tenés
1. Detené el frontend Next.js con Ctrl + C.
2. Copiá la carpeta `frontend` del ZIP sobre `C:\Users\yesica.cherubino\Downloads\impulso\frontend` reemplazando archivos existentes.
3. **No reemplaces ni borres** `.env.local`, `package.json`, `package-lock.json` o `node_modules`.
4. Mantené FastAPI en ejecución en el puerto 8001.
5. Desde `impulso/frontend`:
   - `npm run typecheck`
   - `npm run build`
   - `npm run dev -- -p 3001`
6. Abrí `http://localhost:3001/consultas`, probá bandeja y detalle, y usá Chrome DevTools (F12) en vista móvil (375 px).
7. Revisá también `/integraciones`, `/`, y la creación de oportunidades.

## Atención al backend
Este paquete de cambios **es visual** y espera que ya tengas instalado el backend con `/api/inbox` de la versión previa (Impulso_Backoffice_Comercial_Responsive.zip). Si aparece un error de carga de consultas, probá `http://127.0.0.1:8001/api/inbox` en tu navegador. Si falla, primero incorporá el backend de esa versión.

## Publicación luego de probar localmente
No afectará los servicios en la nube hasta hacer commit y push a GitHub.
- `git add frontend/src`
- `git commit -m "Redesign sales backoffice responsive interface"`
- `git push origin main`
- Vercel redeploy de Production si no está habilitado auto-deploy.
Si solo cambia la interfaz, **Railway no necesita redesplegarse**. Una futura integración real con Tango o WhatsApp sí requerirá desarrollo de backend, seguridad y autorizaciones.

## Validaciones
- Se revisó la estructura de los archivos y se verificó la sintaxis Python del backend base por separado.
- La compilación Next.js **no pudo ejecutarse aquí**: la instalación de dependencias Node no se completó por limitaciones del entorno. Confirmar en Windows antes de publicar.
- El diseño responsive sigue siendo necesario validarlo visualmente en un navegador móvil real o DevTools.
