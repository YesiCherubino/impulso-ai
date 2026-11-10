# Impulso - Mejoras comerciales y tema oscuro (noviembre 2026)

Versión basada en el proyecto que veníamos trabajando. **No incluye base SQLite, contraseñas, tokens ni archivos `.env`**.

## Qué incorporamos

- **Tema claro/oscuro** en la aplicación y en el login, con preferencia persistente en `localStorage` del navegador (`impulso-theme`). No cambia la autenticación ni los datos.
- **Estética Industrial Moderno**: colores azul petróleo y grises neutros, contraste nocturno, formularios y controles sobrios, selector accesible en la barra superior y móvil.
- **Consultas manuales**: seleccionás canal de origen (WhatsApp, Correo, Formulario web, Teléfono, Otro o Manual). Es una etiqueta descriptiva: **no integra ni lee esos canales**.
- **Contactos comerciales**: tipo de consulta (fabricación para terceros, desarrollo de fórmula, elaboración y envasado, mayorista, otra/sin clasificar), canal, presentación, packaging y responsable. Se pueden crear y **editar** en la ficha.
- **Listado comercial**: filtro por tipo de consulta y visualización de próxima fecha de seguimiento.
- **IA**: extracción adicional de tipo de consulta, presentación, necesidades de fórmula y packaging; borradores sujetos a revisión humana. Datos previos de análisis siguen siendo legibles.
- **Seguimiento programado**: fecha y motivo por contacto. Una fecha futura suspende la alerta automática de siete días. Al llegar la fecha se considera pendiente y aparece en las notificaciones. Las llamadas, reuniones o correos registrados desde esa fecha cumplen el recordatorio.
- **Reportes**: los seguimientos con fecha vencida se priorizan.
- **Guía de usuario** actualizada en `frontend/public/guia-de-uso.pdf`.

## Cómo aplicar (Windows PowerShell, proyecto existente)

1. Cerrá Visual Studio/servidores locales. **Hacé un backup actual de Railway SQLite** antes de desplegar los cambios. Si solo trabajás localmente, copiá el archivo SQLite fuera del repo. El ZIP no incluye bases ni secretos.
2. Guardá el ZIP de *Solo cambios* en Descargas, y descomprimilo **sobre la carpeta raíz del repo** (la que contiene `backend`, `frontend` y `.git`):

   ```powershell
   Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\Impulso_Pasmanter_Solo_Cambios.zip" -DestinationPath "$env:USERPROFILE\Downloads\impulso" -Force
   ```

   **No lo descomprimas dentro de `frontend` ni de `backend`**. Sobrescribirá solo los archivos del código que cambiaron, no `node_modules`, `.env` ni la base SQLite.

3. Corré los checks del proyecto:

   ```powershell
   cd "$env:USERPROFILE\Downloads\impulso\backend"
   python -m pip install -r requirements.txt
   python -m pytest -q

   cd "..\frontend"
   npm install
   npm run typecheck
   npm run build
   ```

4. Si todas las pruebas y el build terminan sin errores:

   ```powershell
   cd "$env:USERPROFILE\Downloads\impulso"
   git status
   git add backend/app backend/tests frontend/src frontend/public/guia-de-uso.pdf LEEME_MEJORAS_PASMANTER.md
   git commit -m "Impulso: tema oscuro y mejoras comerciales para Pasmanter"
   git push origin main
   ```

5. Railway y Vercel deberían desplegar los cambios según la configuración que ya tenías. **No cambies** las variables de autenticación: mantené `AUTH_ENABLED=true` en Railway, `NEXT_PUBLIC_AUTH_ENABLED=true` y `NEXT_PUBLIC_DEMO_REQUIRES_CODE=false` en Vercel.
6. En incógnito, comprobá login, tema oscuro, una consulta manual, creación/edición de contacto, programación de seguimiento, reportes y los contactos que ya existían.

## Cómo funciona la migración

- En el inicio del backend se ejecuta una **migración aditiva de SQLite**: se agregan siete columnas a `oportunidades` si faltan.
- No se eliminan ni alteran contactos, historial, mensajes, usuarios o sesiones anteriores.
- Los contactos previos quedan con `tipo_consulta='sin_clasificar'`, `canal_origen='Manual'`, sin fecha programada; el vendedor puede completar la información desde su ficha.
- No modifica el proyecto de Railway, el volumen ni las variables. Si el servicio sigue usando `/app/data/impulso.sqlite3`, la migración se aplicará allí al reiniciar.
- Si necesitás volver al código anterior, desplegá el commit anterior (las columnas adicionales de SQLite pueden quedar; no requieren eliminar datos).

## Comprobaciones efectuadas aquí

- `37` pruebas backend superadas con un sustituto local del SDK de OpenAI (el SDK real no estaba instalado en este entorno aislado y **no se incluyó el sustituto** en el proyecto entregado).
- Sintaxis TS/TSX comprobada sobre los `17` archivos con TypeScript global: 0 diagnósticos de sintaxis.
- **Pendiente en tu PC**: `npm run typecheck`, `npm run build`, y una prueba integrada con el SDK de OpenAI real y el servidor desplegado. No afirmamos que el despliegue ya esté realizado.

## Pendiente para otro sprint

- Integraciones reales con WhatsApp / Gmail / Tango (requieren cuentas, permisos, acuerdos de campos y reglas del negocio).
- Usuarios individuales y auditoría completa de cambios; el campo "responsable" por ahora es descriptivo.
- Validación comercial de categorías, cantidades, cotizaciones, permisos y textos con el equipo de Pasmanter antes de datos reales.
