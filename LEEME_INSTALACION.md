# Impulso — Actualización integral de backoffice

Esta actualización reúne las correcciones aprobadas en la conversación. Está pensada para instalarse **sobre tu proyecto existente** y probarse localmente antes de publicarse.

## Qué cambia

- El menú conserva **Consultas**, **Contactos comerciales**, **Reportes** e **Integraciones**.
- La **Guía de usuario** se abre desde el encabezado superior derecho, sin decir «(PDF)».
- **Contactos comerciales** reúne el resumen administrativo (filas seleccionables) y la tabla de contactos.
- Seleccionar una fila del resumen filtra los contactos de la tabla; permite deshacer el filtro. También hay búsqueda, filtro por estado y orden por último contacto, prioridad, nombre y valor.
- Se eliminan las tarjetas y textos redundantes del panel, reportes, bandeja e integraciones.
- En **Consultas** hay filtros por estado más visibles, con colores consistentes. No hay contadores repetidos encima de la bandeja.
- **Nueva consulta** permite registrar mensajes de manera manual. No existe aún recepción real de WhatsApp.
- **Preparar respuesta** guarda el análisis, el borrador y sus versiones en SQLite. Al abrir de nuevo la consulta recupera la última versión; «Volver a generar» hace una nueva consulta a OpenAI.
- En la ficha comercial, los borradores de seguimiento también se conservan en SQLite y pueden editarse y guardarse.
- La campanita de notificaciones muestra consultas nuevas y contactos abiertos con **más de siete días** sin contacto. Los avisos tienen clave única y el estado de lectura se conserva por usuario.
- La guía explica que los mensajes y contactos precargados son ficticios; esa aclaración no ocupa espacio en la UI.

## Instalación recomendada

1. Guardá una copia de tu carpeta `C:\Users\yesica.cherubino\Downloads\impulso`.
2. Extraé el ZIP **Solo cambios** en la carpeta raíz `impulso`, respetando `backend/` y `frontend/` y permitiendo reemplazar los archivos incluidos.
3. **No elimines**: `backend/.env`, `frontend/.env.local`, `backend/data/`, `.venv/`, `node_modules/`, ni la base SQLite.
4. Dejá las variables de autenticación ya configuradas. No agregues secretos a GitHub.
5. Backend: desde `impulso/backend`, ejecutá:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001 --env-file .env
```

6. Frontend: desde `impulso/frontend`, ejecutá:

```powershell
npm run typecheck
npm run build
npm run dev -- -p 3001
```

7. Abrí `http://localhost:3001/login` si tenés `NEXT_PUBLIC_AUTH_ENABLED=true`; en caso contrario abrí `http://localhost:3001/consultas`.

## Qué probar

1. Login y cerrar sesión; confirmar que no aparece error 502 (FastAPI debe estar corriendo).
2. Abrir Consultas, usar los filtros de estado y registrar una consulta nueva. Verificar que aparezca una notificación.
3. Analizar una consulta, editar y guardar la respuesta, cambiar de pantalla y volver: se debe recuperar. «Volver a generar» usa OpenAI y el cupo diario.
4. Registrar un contacto comercial desde una consulta; abrir «Datos de contacto».
5. Entrar a Contactos comerciales, seleccionar cada fila del resumen y comprobar que filtre la tabla. Probar los ordenamientos.
6. Abrir una ficha, generar y guardar el borrador de seguimiento y volver a entrar.
7. Revisar Reportes, Integraciones, el enlace Guía de usuario y la vista de celular (390 px).
8. Validar notificaciones después de reiniciar FastAPI y que los avisos leídos no reaparezcan como nuevos.

## Publicación — IMPORTANTE

**No hagas `git push` hasta que los pasos anteriores funcionen en local.** Para publicar, luego se desplegará primero el backend actualizado en Railway (nuevas tablas/rutas) y después el frontend actualizado en Vercel.

Las tablas SQLite se crean automáticamente al iniciar FastAPI, sin borrar los registros existentes. Aun así, hacé una copia o backup del volumen antes de actualizar producción.

Asegurate de que `AUTH_ENABLED=true` en Railway y `NEXT_PUBLIC_AUTH_ENABLED=true` en Vercel si querés exigir login. Verificá la contraseña de tu cuenta ya creada: **cambiar `ADMIN_PASSWORD` en `.env` no reemplaza automáticamente la contraseña almacenada**.

## Alcance y limitaciones

- **WhatsApp Business, Gmail y Tango no están conectados**; las opciones de la UI son propuestas de integración futura.
- Las notificaciones son **internas**, consultadas cada 45 segundos con la aplicación abierta; no son notificaciones push del teléfono.
- Las consultas que se ingresan manualmente sí se guardan en la bandeja y generan aviso. Los mensajes de WhatsApp reales aún no llegan automáticamente.
- Para un entorno corporativo multiusuario con datos reales hacen falta autorización por roles, control de acceso por equipos, privacidad, auditoría y reglas de retención adicionales.
- El backend fue verificado con 29 pruebas (usando un adaptador de OpenAI **solo durante las pruebas offline**). La sintaxis TypeScript fue revisada; el `npm run build` integral no pudo completarse aquí porque las dependencias de npm no están disponibles en este entorno.
