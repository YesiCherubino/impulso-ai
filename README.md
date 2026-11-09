# IMPULSO V3 — Actualización para aplicar sobre V2

Esta entrega contiene el código de Impulso V3. **No está desplegada**. Aplicar el ZIP no modifica directamente Railway ni Vercel.

## Funcionalidades incluidas

- **Bandeja conversacional:** agrupa mensajes por contacto, distingue WhatsApp, Email y Formulario web simulado, conserva la conversación y permite identificar/seleccionar la gestión comercial activa.
- **Gestiones numeradas:** un número por gestión, no por mensaje; posibilidad de crear otra gestión, cambiar su asociación y finalizarla. La información e historial permanecen vinculados al contacto.
- **Ficha de contactos:** reorganización del detalle de consultas en ventanas, campos editables y checklists; vistas Lista y Tablero con movimiento de tarjetas entre estados. Vista preferida por usuario.
- **Agenda comercial:** vistas semanal, mensual y lista; actividades, responsables y vinculación a gestiones. Se pueden mover eventos de fecha desde el calendario.
- **IA:** configuración administrativa del estilo de las respuestas (tono, tratamiento, extensión y signos de apertura).
- **Administración y demo:** carga manual e idempotente de **30 mensajes simulados**, 15 de WhatsApp y 15 de Email, para 20 contactos, más **5 entradas web opcionales**. Se carga una única vez desde Administración → Datos de prueba → Cargar ejemplos. No se borran los mensajes anteriores.
- **Interfaz:** tema oscuro más sobrio, diseño lineal y más compacto, y guía de usuario actualizada.
- **Integraciones:** Google Calendar y Formulario web de Pasmanter aparecen como integraciones pendientes. **No hay conexión real a Google, Gmail, WhatsApp ni al formulario del sitio.**

## Instalación en Windows

1. Antes de reemplazar nada, guardá una copia del proyecto actual y **un backup actualizado de SQLite en Railway**. La versión modifica el esquema de base de datos.
2. Descomprimí `Impulso_V3_Solo_Cambios.zip` sobre `C:\Users\yesica.cherubino\Downloads\impulso`, fusionando `backend` y `frontend`, sin crear una carpeta adicional dentro del proyecto. No reemplaces archivos `.env` existentes.
3. Verificá el backend:

   ```powershell
   cd C:\Users\yesica.cherubino\Downloads\impulso\backend
   python -m pip install -r requirements.txt
   python -m pytest -q
   ```

4. Verificá el frontend:

   ```powershell
   cd ..\frontend
   npm install
   npm run typecheck
   npm run build
   ```

5. Si todo termina bien, revisá los archivos antes de publicar:

   ```powershell
   cd ..
   git status --short
   git add backend/app backend/tests frontend/src frontend/public/guia-de-uso.pdf
   git diff --cached --check
   git diff --cached --stat
   ```

   Confirmá que estén incluidos los **archivos nuevos** como `backend/app/business_v3.py`, `frontend/src/app/agenda/page.tsx`, `frontend/src/app/impulso-v3.css`, `frontend/src/components/case-dialog.tsx`, `frontend/src/components/checklist-editor.tsx` y `backend/tests/test_v3_workflows.py`.

6. **Solo después** del backup y del build local, podés hacer el commit/push habitual. Comprobá los despliegues y probá las funciones desde el navegador, sin asumir que todo funciona únicamente porque el build terminó bien.

## Resultados de verificación en este entorno

- **44 pruebas de backend aprobadas**, ejecutadas con un sustituto local de la librería `openai` por falta de disponibilidad de esa dependencia aquí. No son pruebas de una llamada real a OpenAI.
- **21 archivos TypeScript/TSX comprobados sin errores de sintaxis**.
- **No se pudo hacer `npm run build` de Next.js aquí** por falta de dependencias npm instaladas. Es obligatorio hacerlo en tu computadora antes de desplegar.
- La guía PDF incluida se generó, pero conviene verificar el acceso desde la interfaz tras el despliegue.
- No se incluyeron contraseñas, bases de datos, respaldos ni archivos `.env.local`.

## Advertencias importantes

- En producción, los mensajes de WhatsApp, correo y web siguen siendo **simulados o cargados manualmente**. La actualización automática de la bandeja solo sincroniza mensajes ya registrados en Impulso.
- Las operaciones de envío de respuestas y la conexión real de Google Calendar/Gmail/WhatsApp están pendientes. No se debe presentar la app como conectada a esos servicios.
- La carga de ejemplos agregará datos ficticios a la base existente; no se ejecuta automáticamente en cada despliegue.
- Esta V3 es una actualización sustancial. Probar el login, las migraciones, las gestiones, permisos, agenda, reportes, tema y fichas después de desplegar.
