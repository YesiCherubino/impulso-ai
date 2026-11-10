# Impulso — rediseño de backoffice comercial

Esta entrega convierte la aplicación en una herramienta de uso diario para ventas. El nuevo foco es **Consultas**: una bandeja de mensajes ficticios que ejemplifica cómo se podrían gestionar muchas conversaciones recibidas por WhatsApp Business.

## Alcance de esta versión

- Bandeja con **7 conversaciones ficticias**, búsqueda y filtros por estado.
- Detalle de consulta, con canal claramente etiquetado **WhatsApp (simulado)**.
- Cambiar estado entre **Sin atender**, **En gestión** y **Resuelta** (persiste en SQLite).
- Analizar el texto de una consulta usando el endpoint OpenAI existente (`POST /api/ai/analyze-inquiry`).
- Ver campos extraídos y un borrador editable (sin envío).
- Crear una oportunidad y **vincularla** a la consulta, evitando cargar los datos dos veces. La relación persiste en SQLite.
- Panel comercial simplificado, navegación por tareas y menú móvil.

**No existe integración real con WhatsApp** en este prototipo. No lee ni envía mensajes de clientes. Todos los datos son ficticios. Para un caso real habría que integrar WhatsApp Business Platform (API oficial de Meta), verificación del negocio/número, webhooks, consentimiento, manejo de plantillas, autorización de usuarios y política de datos. También se podría añadir Gmail API.

## Incorporación al proyecto existente

Copiar las carpetas `backend` y `frontend` de este ZIP sobre el proyecto local `impulso`, reemplazando solo los archivos coincidentes. No se incluyen ni deben sobrescribirse los `.env`, `.env.local`, base de datos, `package.json` ni `package-lock.json`.

En `backend`, ejecutar:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001 --env-file .env
```

En `frontend`, ejecutar:

```powershell
npm run typecheck
npm run build
npm run dev -- -p 3001
```

Ir a `http://localhost:3001/consultas` y probar también con las herramientas de dispositivo de Chrome, tamaño móvil (375 x 812 px).

## Despliegue sobre los servicios existentes

**No hace falta crear otro proyecto.** Tras verificar localmente, desde la carpeta `impulso`:

```powershell
git add backend/app/db.py backend/app/main.py backend/tests/conftest.py backend/tests/test_inbox.py frontend/src/app/page.tsx frontend/src/app/consultas/page.tsx frontend/src/app/globals.css frontend/src/components/shell.tsx frontend/src/lib/api.ts MEJORAS_BACKOFFICE.md
git commit -m "Redesign sales backoffice with simulated messaging inbox"
git push origin main
```

Si Railway tiene Auto Deploy deshabilitado, activar manualmente un **nuevo despliegue desde el último commit**. Vercel puede redesplegarse automáticamente si tiene Git conectado. Verificar `GET /api/inbox` en Railway y `/consultas` en Vercel. No repetir el `git init` ni crear repositorios nuevos.

Mantener las variables privadas solo en Railway, la configuración de CORS para el dominio de Vercel y el volumen de SQLite. **No subir secretos a GitHub**.

## Pruebas incluidas y límites de verificación

Se ejecutaron 24 pruebas de backend usando un sustituto de OpenAI para no consumir créditos. Se validó la sintaxis de todos los componentes TypeScript. La instalación de Node/compilación real de Next.js no pudo ejecutarse en este entorno, por lo que `npm run typecheck` y `npm run build` deben confirmarse localmente antes de subir.

La bandeja de demostración actual ofrece una referencia visual y funcional para la automatización de WhatsApp. Una integración real agregaría recepción de mensajes en segundo plano, agrupación por conversaciones, mensajes salientes supervisados y controles contra duplicados; no están implementados aquí.
