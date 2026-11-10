# Impulso - Estados de contacto y Contactos finalizados

## Qué cambió

- Nuevo menú **Contactos finalizados**, con pestañas **Todos**, **Ganados** y **Perdidos**.
- La pantalla principal **Contactos comerciales** muestra solo los contactos activos: Nueva, Contactada, Cotizada o En negociación.
- En la ficha de cada contacto aparece **Estado comercial**, con un selector y el botón **Guardar estado**.
- El estado **Ganada** o **Perdida** retira al contacto de la lista activa y lo muestra en Contactos finalizados.
- Desde la misma ficha se puede volver a cambiar el estado para reabrir la gestión.
- El cambio de estado queda como nota en el historial de interacciones y no modifica la fecha del último contacto.
- La guía de usuario del encabezado incluye estas instrucciones.

## Archivos a copiar

Copiá el contenido de este ZIP encima de `C:\Users\yesica.cherubino\Downloads\impulso\`, respetando las subcarpetas `backend` y `frontend`.

Solo se reemplazan estos archivos y se agregan dos nuevos:

- `backend/app/main.py`
- `backend/tests/test_commercial_status.py` (nuevo)
- `frontend/src/app/page.tsx`
- `frontend/src/app/finalizados/page.tsx` (nuevo)
- `frontend/src/app/oportunidades/[id]/page.tsx`
- `frontend/src/components/shell.tsx`
- `frontend/src/app/office-overrides.css`
- `frontend/public/guia-de-uso.pdf`

No borres ni reemplaces `.env`, `.env.local`, `backend/data`, `.venv`, `node_modules` ni la base SQLite. Hacé una copia de seguridad de todo el proyecto antes de copiar.

## Validar localmente

En una terminal desde `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001 --env-file .env
```

En otra terminal desde `frontend`:

```powershell
npm run typecheck
npm run build
npm run dev -- -p 3001
```

Abrí `http://localhost:3001/` e iniciá sesión si corresponde.

1. Entrá en **Contactos comerciales** y abrí una ficha activa.
2. Seleccioná **Ganada** en Estado comercial y guardá.
3. Volvé a **Contactos comerciales**: ese registro ya no figura entre los activos.
4. Entrá en **Contactos finalizados**: el registro figura como Ganada. Probá los filtros.
5. Volvé a abrir el contacto desde esa sección y cambialo a Contactada: regresa al listado activo.
6. Comprobá el historial de cambios en la ficha.

Los contactos de ejemplo Oliva Labs y Vita Belle aparecen inicialmente en **Contactos finalizados** porque ya están guardados como Ganada y Perdida.

## Verificaciones realizadas para este parche

- 32 tests de backend pasan con un SDK de OpenAI simulado (sin llamadas ni costos de IA).
- 16 archivos TS/TSX analizados sin errores de sintaxis.
- No se pudo ejecutar un `npm run build` completo sin las dependencias de Next.js en este entorno. Hay que correrlo localmente antes de publicar.

**No hagas deploy en Railway/Vercel hasta validar el flujo localmente.**
