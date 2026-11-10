# Impulso — Ajustes de bandeja (UI, sin cambios en backend)

## Qué cambia
- Distribución ~38% lista / 62% detalle en escritorio.
- Selección automática de la primera consulta sin atender al entrar en escritorio.
- Filtros sin barra horizontal: botones que pueden ajustarse en escritorio y selector de estado en tablet/celular.
- Gestión de consulta más compacta; acciones: Marcar en gestión, Preparar respuesta, Crear oportunidad (habilitada tras analizar), Marcar resuelta.
- La información extraída y el borrador editable permanecen dentro del detalle.
- En móvil la lista y el detalle se muestran en pantallas separadas; los botones tienen tamaño táctil.

## Instalación
1. Hacer una copia o un commit del proyecto actual.
2. Copiar `frontend/src/app/consultas/page.tsx` y `frontend/src/app/office-overrides.css` sobre los archivos respectivos en `C:\Users\yesica.cherubino\Downloads\impulso\frontend`.
3. Mantener `frontend/.env.local`, credenciales y backend sin cambios.
4. En PowerShell, desde `frontend`: `npm run typecheck`, `npm run build`, `npm run dev -- -p 3001`.
5. Mantener FastAPI en 8001 y entrar a `http://localhost:3001/consultas`.
6. En Chrome, F12 → Device toolbar (Ctrl+Shift+M) y probar 390px y 768px; probar seleccionar una consulta, generar borrador y volver a la lista.

## Nota
El código se revisó sintácticamente (TSX y CSS). No se ejecutó `next build` por falta de dependencias locales en este entorno. No subir a GitHub ni redesplegar hasta verificar en tu computadora.

Si aparece «Código de acceso incorrecto o ausente» en acciones POST, el código guardado en la sesión puede estar desactualizado: cerrar y reabrir la pestaña, reingresar el código cuando se solicite y verificar `DEMO_ACCESS_CODE` del backend local (no compartirlo).
