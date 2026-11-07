# Impulso — Asistente comercial con IA

MVP de portfolio independiente, con datos ficticios. **No es software de una empresa real.**

## Qué resuelve

- Dashboard de oportunidades y alertas de seguimiento con reglas de negocio reproducibles.
- Registro de oportunidades e interacciones con persistencia SQLite.
- Interpretación de consultas con OpenAI (extracción estructurada + borrador de respuesta).
- Borradores de correos de seguimiento con IA y revisión humana.
- **Resumen gerencial:** prioridades por días sin contacto, sin inventar predicciones ni consumir IA.

Stack: Next.js 15 / React / TypeScript, FastAPI, Pydantic, SQLite y API de OpenAI.

## Desarrollo local en Windows

Backend (`backend/`):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Editar .env y agregar OPENAI_API_KEY real. NO compartas el archivo.
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

Frontend (`frontend/`, otra terminal):

```powershell
npm install
Copy-Item .env.example .env.local
npm run typecheck
npm run build
npm audit
npm run dev -- -p 3001
```

Abrir http://localhost:3001 y http://127.0.0.1:8001/docs.

Si ya tenés `.env`/`.env.local` no los reemplaces. Si FastAPI usa el puerto 8001, `NEXT_PUBLIC_API_BASE_URL` debe apuntar a `http://127.0.0.1:8001`. CORS acepta 3000/3001 solamente en desarrollo.

## Activar el código de acceso de la demo

En `backend/.env`:

```dotenv
PUBLIC_DEMO=true
DEMO_ACCESS_CODE=UN_VALOR_ALEATORIO_LARGO
AI_DAILY_LIMIT=12
```

En `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001
NEXT_PUBLIC_DEMO_REQUIRES_CODE=true
```

El código de acceso **solo va en el backend**. En el frontend se solicita al usuario la primera vez que hace una operación de escritura. Se mantiene durante la pestaña abierta (sessionStorage). En caso de código incorrecto se solicita nuevamente. Para pruebas locales sin código, dejá `PUBLIC_DEMO=false`, `DEMO_ACCESS_CODE=` y `NEXT_PUBLIC_DEMO_REQUIRES_CODE=false`.

El límite de IA se reserva en una transacción SQLite y persiste entre reinicios, **siempre que el archivo de SQLite esté en un disco persistente**. No supone protección frente a abusos distribuidos; incorporar autenticación real y rate limiting por usuario para un producto comercial.

## Publicación: requisitos antes de compartir

1. Revocar y regenerar claves vistas en capturas, no comprometer secretos en Git.
2. Revisar `npm audit` y `npm run build`; actualizar versiones vulnerables sin usar `--force` a ciegas.
3. Configurar variables de backend solo en el hosting de la API. **Nunca** usar `NEXT_PUBLIC_` para claves.
4. Usar un volumen persistente para SQLite, o migrar a Postgres. Si el disco es efímero, se pierden datos y se reinicia el contador de llamadas.
5. Configurar `CORS_ORIGINS=https://tu-app.vercel.app` en el backend. No usar `*` en una demo pública.
6. En frontend configurar `NEXT_PUBLIC_API_BASE_URL` con la URL HTTPS pública de FastAPI. En backend usar `PUBLIC_DEMO=true` y `DEMO_ACCESS_CODE`.
7. Limitar presupuesto en OpenAI y probar desde incógnito. No colocar contactos reales ni información confidencial en esta demo.
8. El código compartido es una protección básica de portfolio, **no autenticación por usuarios ni control de permisos corporativos**.

## Presentación sugerida (2 minutos)

1. Abrir resumen gerencial para ver prioridades calculadas.
2. Analizar una consulta comercial ficticia con IA.
3. Revisar campos extraídos y crear una oportunidad.
4. Abrir ficha, ver historial y generar un correo editable de seguimiento.

No se envían correos automáticamente, ni se inventan cotizaciones, precios o plazos.
