# Impulso — Frontend

Interfaz Next.js 15 + TypeScript que consume el backend FastAPI de Impulso.

## Ejecución local

1. Primero, iniciar el backend desde `../backend`:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
   ```
2. En esta carpeta `frontend`:

   ```powershell
   npm install
   Copy-Item .env.example .env.local
   npm run dev
   ```
3. Abrir `http://localhost:3000`.

Si ya existe `.env.local`, no sobrescribirlo. La variable `NEXT_PUBLIC_API_BASE_URL` debe apuntar al backend en `http://127.0.0.1:8001`.

## Qué incluye

- Panel comercial y KPIs tomados de `/api/dashboard`.
- Oportunidades y filtros sobre `/api/opportunities`.
- Creación de oportunidades.
- Perfil con historial y registro de interacciones.
- Alertas de seguimiento calculadas por FastAPI.

**No se incluye IA todavía:** está prevista para el Día 3. Los datos son totalmente ficticios. El backend del MVP no tiene autenticación; no publicarlo sin implementarla.
