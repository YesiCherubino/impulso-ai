# IMPULSO V2 — Mejoras para Pasmanter

Esta entrega está preparada para **aplicar sobre la versión actual de tu repositorio `impulso-ai`**. No modifica por sí sola GitHub, Railway ni Vercel.

## Cambios incluidos

1. **Bandeja de consultas**: lista completa al ingresar, detalle en popup, marcas no leído/leído independientes del estado comercial, filtros WhatsApp/Email, sincronización cada 30 segundos y al regresar a la pestaña. El botón «Actualizar» se elimina de esta pantalla.
2. **Popup de consulta**: informe de IA editable, incluidos los datos a confirmar; borrador editable con estado «Borrador guardado»; copiar respuesta y selector de canal con «Enviar» deshabilitado, porque todavía no hay integración de envío.
3. **Consultas numeradas**: cada ficha recibe un código `CON-AAAA-00001`; mensajes de correo o WhatsApp se asocian automáticamente cuando coincide exactamente el email o teléfono guardado en la ficha. Si hay ambigüedad se mantienen separados hasta decidir manualmente. Se pueden mover mensajes a otra ficha o crear otra ficha desde el mensaje.
4. **Ficha de contactos**: la pantalla ya no presenta el resumen de ventas. Se incluyen datos generales editables y la lista de consultas numeradas de cada contacto con su historial.
5. **Finalizados**: las etiquetas visibles son **Concretada / No concretada**. Los valores internos anteriores (`ganada/perdida`) se conservan por compatibilidad histórica. Se permite reactivar el contacto.
6. **Reportes**: resumen comercial arriba, filtros por período/canal/responsable, chat de IA para Gerencia/Administración y PDF sin gráficos. La IA recibe agregados de solo lectura, no SQL ejecutable.
7. **Usuarios**: roles Ventas, Gerencia (solo lectura comercial) y Administrador; administración de cuentas con contraseñas seguras y activación/desactivación. La preferencia de tema se guarda por cuenta y se aplica en nuevos dispositivos.
8. **Interfaz**: línea visual minimalista, íconos finos y acento verde grisáceo. Selector de tema arriba del nombre y rol del usuario, luego «Cerrar sesión», luego «Guía de usuario».
9. **Guía**: `frontend/public/guia-de-uso.pdf` actualizado.

## Antes de reemplazar archivos

- **Hacé un backup actualizado del volumen SQLite de Railway**. La migración es aditiva, pero conviene contar con un punto de recuperación.
- Conservá los `.env` y credenciales que ya funcionan. No es necesario cambiarlos para estas funciones.
- Esta entrega no contiene una base SQLite de producción, backups ni contraseñas.
- El primer inicio del backend actualizado agrega columnas y genera fichas numeradas para los mensajes históricos. No debería borrar contactos ni conversaciones.

## Instalación en Windows, paso a paso

1. Descargá **Impulso_V2_Solo_Cambios.zip** y extraé su contenido directamente sobre:

   `C:\Users\yesica.cherubino\Downloads\impulso`

   Es importante fusionar las carpetas `backend` y `frontend` existentes, no crear un proyecto separado dentro de ellas.

2. Desde PowerShell:

   ```powershell
   cd C:\Users\yesica.cherubino\Downloads\impulso\backend
   python -m pip install -r requirements.txt
   python -m pytest -q

   cd ..\frontend
   npm install
   npm run typecheck
   npm run build
   ```

3. Abrí localmente la aplicación si querés comprobar los flujos manualmente. Verificá especialmente login, guardado de ficha, popup, migración, PDF y temas.

4. **Solo después** de comprobar todo y confirmar el backup:

   ```powershell
   cd C:\Users\yesica.cherubino\Downloads\impulso
   git add backend/app backend/tests backend/requirements.txt frontend/src frontend/public/guia-de-uso.pdf
   git diff --cached --check
   git status --short
   git diff --cached --stat
   git commit -m "Impulso V2: fichas, perfiles y reportes comerciales"
   git push origin main
   ```

   Es importante usar el `git add` explícito para **incluir los archivos nuevos** `backend/app/business_v2.py`, `frontend/src/app/impulso-v2.css`, `frontend/src/app/administracion/page.tsx` y la prueba `test_v2_workflows.py`. En el despliegue anterior Vercel había fallado porque un archivo nuevo no se había incluido en Git.

5. Confirmá `Active` en Railway y `Ready` en Vercel y probá desde una ventana de incógnito.

## Usuarios: detalle importante

El usuario indicado por `ADMIN_USERNAME` en Railway recibirá el rol **Administrador**. Si actualmente ese usuario se llama `ventas`, el sistema lo reconocerá como Administrador: es deliberado para no perder el acceso que permite crear más cuentas. Entrá con ese usuario, abrí «Administración» y creá usuarios de perfil **Ventas** y **Gerencia** con contraseñas propias. No es necesario publicar claves aquí ni en GitHub.

`ADMIN_PASSWORD` conserva el comportamiento anterior: cambiar esa variable **no cambia** una contraseña ya guardada en SQLite. Usá «Administración → Restablecer contraseña» para cuentas existentes.

## Alcance real de la demo

- La entrada de WhatsApp y Email **sigue siendo manual**. El polling sincroniza mensajes **ya registrados en Impulso**, no descarga mensajes externos.
- El envío por WhatsApp o Email está **pendiente** y por eso aparece deshabilitado.
- Los reportes con IA requieren `OPENAI_API_KEY` correctamente configurada, el modelo habilitado y disponibilidad de la cuota `AI_DAILY_LIMIT`. Comparten esa cuota con otras operaciones de IA.
- No se ejecuta SQL generado por la IA. Los datos para reportes se agregan mediante consultas definidas por el backend.
- Las operaciones históricas sin `fecha_cierre` utilizan de forma aproximada su último contacto para los filtros temporales. Los cierres nuevos registran `fecha_cierre` explícitamente.
- El sistema conserva los datos de prueba existentes. Antes de una entrega definitiva, se debe acordar cómo separar demo y datos reales.

## Qué comprobamos antes de entregarte el ZIP

- **40 pruebas del backend aprobadas**, incluidas migraciones, lectura de mensajes, vinculación y movimiento, permisos, preferencia de tema y PDF. Para ejecutar los tests en este entorno sin acceso a Internet se utilizó un sustituto local de la biblioteca `openai` (no se realizaron llamadas reales al modelo).
- Migración del esquema anterior ensayada sin pérdida de contactos ni mensajes.
- Los 18 archivos TypeScript/TSX del frontend fueron analizados sin errores de sintaxis.
- **No se pudo ejecutar la compilación completa de Next.js aquí**, porque este entorno no tiene instaladas las dependencias de npm y no puede descargarlas. **Antes del push, ejecutá `npm run typecheck` y `npm run build` en tu computadora.**
- La generación del PDF está probada; su flujo real de descarga desde el navegador también se debe comprobar localmente.

## Si el build de frontend falla

No hagas `git push`. Mandame la última parte de la salida de `npm run typecheck` o `npm run build` y corregimos el archivo que lo provoque. Si Vercel muestra `Module not found`, verificá que la ruta señalada aparezca en los archivos seleccionados por Git.
