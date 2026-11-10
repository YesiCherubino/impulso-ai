# Impulso V4 — Mejoras para el área comercial de Pasmanter

Instrucciones para aplicar sobre la V3 actual (FastAPI + SQLite en `backend/`, Next.js en `frontend/`).
Surgen de revisar el backoffice desplegado con la mirada de un vendedor o gerente de Pasmanter.
Cada punto indica **qué falla**, **dónde está la causa en el código** y **cómo se verifica**.

> Si le pasás este archivo a un agente de código: trabajá **un bloque por vez**, en orden. Al cerrar cada bloque, corré `pytest` y `npm run typecheck`, y explicá qué cambió y cómo se prueba. No cambies la estética general ni agregues dependencias sin consultar. Si algo choca con la arquitectura actual, frená y preguntá antes de rediseñar.

---

## Contexto del negocio (para orientar las decisiones)

Roberto Pasmanter S.A. es un laboratorio que fabrica cosmética, higiene y perfumería. Tiene tres líneas de venta:

- **Fabricación para terceros / marca propia.** Es el CTA principal del sitio ("Quiero producir mi línea"). Lote mínimo: **10.000 unidades**. Son proyectos de semanas o meses: fórmula, ANMAT, packaging, piloto y producción.
- **Venta mayorista de marcas propias** (Dermogreen, Acqua Di Fiore, Tango) a cadenas, droguerías y distribuidoras.
- **Exportación** (más de 15 países).

También llegan consultas que no son ventas: CVs, proveedores, consumidores finales.
El vendedor necesita saber **qué tipo de oportunidad es y cuánto pesa** de un vistazo, y el gerente necesita **números que coincidan entre pantallas**.

---

## Bloque 1 — Confianza (crítico, hacer primero)

### 1.1 La IA analiza un solo mensaje y pide datos que el cliente ya dio

**Síntoma:** en `CON-2026-00011` (Botánica Studio), el formulario web dice *"Cantidad estimada: 5000 unidades"*, pero el informe muestra *Cantidad: Sin definir* y el borrador le pregunta la cantidad al cliente.

**Causa:** en `backend/app/main.py`, `analyze_saved_inbox` hace `SELECT texto FROM bandeja_consultas WHERE id=?` y le pasa a `analizar_consulta` **solo el texto del mensaje seleccionado**. No incluye el resto de los mensajes de la gestión ni los datos que ya están en `fichas_consulta`.

**Cambios:**
- [ ] Crear `build_case_context(con, ficha_id)` (en `business_v3.py` o un módulo nuevo) que arme el contexto con:
  - los datos actuales de la ficha (`producto`, `cantidad`, `presentacion`, `packaging`, `tipo_consulta`, `requisitos`);
  - **todos** los mensajes de la gestión (`bandeja_consultas WHERE ficha_id=?`) en orden cronológico, con canal y fecha.
- [ ] `analyze_saved_inbox` usa ese contexto cuando el mensaje tiene `ficha_id`. Si no tiene, sigue usando el texto suelto.
- [ ] En `ai.py`, agregar al `instructions` de `analizar_consulta`: *"Los datos de la FICHA y de mensajes anteriores ya fueron informados por el cliente: no los incluyas en `datos_faltantes` ni los vuelvas a preguntar en `respuesta_sugerida`."*
- [ ] Extracción determinística del formulario web, **sin depender de la IA**: al recibir un mensaje con `canal='Formulario web'`, parsear `Producto:`, `Cantidad estimada: N unidades` y `Localidad:` con regex y volcarlos en la ficha si esos campos están vacíos.
- [ ] Después del análisis, **no pisar** campos que el vendedor ya editó a mano. Solo completar los vacíos, salvo que el vendedor elija "Regenerar".
- [ ] Post-validación: si `ficha.cantidad` tiene valor, quitar de `datos_faltantes` cualquier ítem que mencione "cantidad" o "unidades".

**Aceptación:**
- Test nuevo en `tests/test_v4.py`: una gestión con un mensaje de formulario web de 5000 unidades y un WhatsApp sin cantidad → la ficha queda con `cantidad=5000`, y el contexto que recibe el mock de IA incluye ambos mensajes.
- En la UI, `CON-2026-00011` muestra 5000 unidades y el borrador no pregunta la cantidad.

---

### 1.2 Clientes duplicados (dos gestiones por empresa)

**Síntoma:** Natural Care, Botánica Studio, Nova Beauty, Estudio Luma, Esencia Sur y Oliva Labs aparecen dos veces en Ficha de contactos (por ejemplo `CON-2026-00003` "Consulta de Botánica Studio" y `CON-2026-00011` "Consulta sobre Máscara capilar…").

**Causa:**
- `db.py` (`init_db`) crea una ficha por cada mensaje histórico de `INBOX_SEED` sin `ficha_id` (CON-00001 a CON-00007). Esos mensajes **no tienen email ni teléfono**.
- `seed_demo_v3` crea otra ficha para el mismo cliente, porque `find_sender_ficha` nunca vincula por nombre, a propósito (está bien que no lo haga automáticamente).

**Cambios:**
- [ ] **Fusionar gestiones**: endpoint `POST /api/fichas/{origen_id}/merge` con body `{destino_id}`. Mueve los mensajes (`bandeja_consultas.ficha_id`), las actividades (`actividades_comerciales.ficha_id`), los checklists y las claves de `remitentes_gestiones` al destino. Completa en el destino los campos vacíos con los del origen. Marca el origen como `estado_gestion='fusionada'`, con `motivo_cierre='Fusionada en CON-…'`. **No borra nada.** Solo administración y ventas; gerencia, no.
- [ ] En la ficha, botón **"Fusionar con…"** que lista las otras gestiones abiertas del mismo cliente (comparando el nombre en minúsculas y sin acentos).
- [ ] **Sugerencia de duplicado**: cuando el nombre normalizado del cliente coincide con otra gestión abierta, mostrar un aviso en la ficha ("Hay otra gestión abierta de Botánica Studio: CON-2026-00003 · Fusionar"). Solo sugerir, nunca fusionar automáticamente.
- [ ] Script `backend/scripts/fusionar_demo.py` (idempotente, con backup previo) para fusionar las gestiones demo duplicadas en la base actual.
- [ ] `estado_gestion='fusionada'` no aparece en Bandeja, Contactos, Finalizados ni Reportes.

**Aceptación:** test de fusión: los mensajes pasan al destino, el origen queda `fusionada`, y los conteos de Reportes no cambian salvo que el origen ya no cuenta. En la UI, cada empresa demo aparece una sola vez.

---

### 1.3 Los números no coinciden entre pantallas

**Síntomas:**
- Reportes dice **5 concretadas** y Finalizados muestra **4**.
- Reportes dice **1 seguimiento vencido** y la Agenda está vacía.
- Aurora Cosmética está concretada pero sigue primera en la bandeja.

**Causas (en `business_v2.py` → `report_data`):**
- `concretadas` suma `cases_closed` (fichas) **más** `legacy_closed` (oportunidades con `estado='ganada'` sin ficha vinculada). Finalizados solo lista fichas, de ahí la diferencia.
- `seguimientos_vencidos` se calcula sobre `oportunidades.fecha_seguimiento` o con la regla de "7 días sin contacto". La Agenda lee `actividades_comerciales`. Son dos fuentes distintas.
- `/api/inbox/threads` ordena solo por `ultimo` mensaje y no tiene en cuenta si la gestión está cerrada.

**Cambios:**
- [ ] Crear `backend/app/metrics.py` con **una sola función por indicador** (`count_concretadas`, `count_no_concretadas`, `list_seguimientos_vencidos`, `count_sin_atender`…), con los mismos filtros (`period`, `canal`, `responsable`). Reportes, Finalizados, Notificaciones y el asistente de reportes las usan todas. Nada de queries paralelas.
- [ ] Decidir el tratamiento de las oportunidades legacy: **migrarlas** (crear la ficha faltante con `estado_gestion` equivalente: `ganada`→`concretada`, `perdida`→`no_concretada`) para que aparezcan también en Finalizados. Es preferible a dejarlas fuera del conteo.
- [ ] Seguimientos vencidos: un seguimiento es una fila de `actividades_comerciales` con `tipo='seguimiento'`, `estado='programada'` e `inicio < ahora`. Al programar un seguimiento desde la ficha (`fecha_seguimiento` de la oportunidad), crear o actualizar también la actividad de agenda. La alerta automática de 7 días sin contacto se muestra aparte ("Sin contacto hace +7 días"), no como seguimiento vencido.
- [ ] En la Agenda, vista **Lista**: sección "Vencidos" arriba, con link a la gestión.
- [ ] Bandeja (`/api/inbox/threads`): agregar al hilo `estado_gestion_activa`. Los hilos cuya gestión está cerrada (`concretada`, `no_concretada`, `resuelta`, `fusionada`) van a un filtro **"Cerradas"** y no aparecen en "Todos los estados", salvo que entre un mensaje nuevo después de `cerrada_en`. En ese caso aparece con la etiqueta "Nuevo mensaje en gestión cerrada" y el botón "Reabrir" o "Nueva gestión".

**Aceptación:** test que crea N gestiones concretadas (fichas y legacy) y verifica que `report_data()['indicadores']['concretadas']` sea igual a la cantidad que devuelve el endpoint de Finalizados. Otro test: un seguimiento vencido aparece tanto en Reportes como en `/api/calendar/events`.

---

### 1.4 Un único pipeline de estados

**Síntoma:** conviven tres juegos de estados:
- `oportunidades.estado`: `nueva / contactada / cotizada / negociacion / ganada / perdida`, que es lo que muestra el filtro de Ficha de contactos;
- `fichas_consulta.estado_gestion`: `sin_atender / en_gestion / concretada / no_concretada / resuelta`, que es lo que muestran las tarjetas;
- `bandeja_consultas.estado`: `nueva / en_gestion / resuelta`.

**Cambios:**
- [ ] El estado comercial vive en **la gestión** (`fichas_consulta.estado_gestion`), con este pipeline:
  `sin_atender → calificada → cotizada → muestra_piloto → concretada | no_concretada`
  (más `resuelta` para las consultas no comerciales, y `fusionada`).
- [ ] `no_concretada` exige `motivo_cierre` de una lista: *Precio, Volumen bajo el mínimo, Plazo, Sin respuesta del cliente, Eligió otro proveedor, Otro*.
- [ ] Migración aditiva: `en_gestion` → `calificada`. `oportunidades.estado` queda solo como dato histórico y se deja de mostrar en filtros.
- [ ] El estado del **mensaje** (`bandeja_consultas.estado`) pasa a significar solo atención: leído, respondido o pendiente. No se usa más en Reportes como estado comercial.
- [ ] Frontend: un solo `ESTADOS_GESTION` en `frontend/src/lib/api.ts`, usado por el filtro, las tarjetas, el tablero (columnas) y Reportes.

**Aceptación:** los mismos estados se ven en Bandeja, Ficha de contactos (lista y tablero), Finalizados y Reportes. Los tests existentes se actualizan para el nuevo enum.

---

## Bloque 2 — Específico del negocio de Pasmanter

### 2.1 Tipo de servicio visible y obligatorio
- [ ] Agregar `exportacion` y `no_comercial` al `Literal` de `tipo_consulta` (`ai.py`, `FichaEdit`, frontend).
- [ ] La IA lo sugiere y el vendedor lo confirma (badge "Sugerido por IA" hasta que se edite).
- [ ] `no_comercial` (CV, proveedor, consumidor final): botón **"Archivar como no comercial"**. Queda en `resuelta` y no cuenta en los KPIs de ventas.

### 2.2 Ficha de calificación
Agregar a `fichas_consulta` (migración aditiva):
- [ ] `formula`: `propia | desarrollo_pasmanter | sin_especificar`
- [ ] `marca_registrada`: `si | no | sin_especificar`
- [ ] `registro_anmat`: `si | no | en_tramite | sin_especificar`
- [ ] `destino`: `local | exportacion` + `pais_destino`
- [ ] `plazo_deseado` (texto corto)
- [ ] `localidad` (la carga el formulario web)

**Datos a confirmar** se calcula de los campos vacíos de la ficha (función pura, testeable). La IA puede sumar matices, pero la lista base sale de los datos.

### 2.3 Regla de lote mínimo
- [ ] Constante configurable `LOTE_MINIMO_TERCEROS = 10000` (en Administración o `.env`).
- [ ] Si `tipo_consulta ∈ {fabricacion_terceros, elaboracion_envasado}` y `cantidad < mínimo`, mostrar el badge **"Bajo mínimo"** en bandeja y ficha.
- [ ] La IA **no** debe rechazar al cliente. El borrador puede mencionar que el lote mínimo es de 10.000 unidades solo si el vendedor activa "Informar lote mínimo" (para no prometer ni cerrar puertas sin revisión humana).

### 2.4 Bandeja priorizable
En cada tarjeta de `frontend/src/app/consultas/page.tsx`:
- [ ] Mostrar tipo de servicio, cantidad, responsable, estado de la gestión y **tiempo sin respuesta** ("hace 5 h sin responder", calculado desde el último mensaje entrante sin respuesta registrada).
- [ ] Orden **"Prioridad"** además de "Más reciente": primero lo que lleva más tiempo sin responder, luego mayor volumen. Las de "Bajo mínimo" y "No comercial" van al final.
- [ ] Filtros por **responsable** ("Mis consultas") y por **tipo de servicio**.

### 2.5 Responsable asignado
- [ ] `fichas_consulta.responsable` (username), con botón **"Asignarme"** y selector para administración.
- [ ] El rol `ventas` ve por defecto "Mis consultas" + "Sin asignar".

### 2.6 Respuesta registrada mientras no haya integración de envío
Hoy el borrador dice *"Envío pendiente de integración"* y la respuesta se pierde del historial.
- [ ] Botón **"Copiar y marcar como respondida"**: copia el texto al portapapeles e inserta en `bandeja_consultas` un mensaje **saliente** (columna nueva `direccion='saliente'`), con canal, hora y usuario.
- [ ] El hilo muestra los mensajes salientes alineados a la derecha.
- [ ] El tiempo de primera respuesta (Bloque 3) se calcula con estos registros.

### 2.7 Cotización
- [ ] Al pasar a `cotizada`, pedir `monto`, `moneda` (ARS/USD), `fecha_cotizacion` y `validez_dias`. Guardarlos en la ficha.
- [ ] Mostrarlos en la ficha y en la tarjeta del tablero.

---

## Bloque 3 — Reportes para gerencia

Todos salen de `metrics.py` (Bloque 1.3):
- [ ] **Tiempo medio de primera respuesta**, por canal y por vendedor (desde el primer mensaje entrante hasta el primer saliente).
- [ ] **Embudo** por estado: cantidad y monto cotizado.
- [ ] **Conversión** por tipo de servicio y por canal de origen.
- [ ] **Motivos de no concretadas** (conteo por motivo).
- [ ] **Alerta**: consultas con más de 24 h sin respuesta.
- [ ] El asistente de reportes (`/api/reports/chat`) recibe solo estos datos. Si le preguntan algo que no está, debe responder que ese dato no existe en Impulso, sin estimarlo.

---

## Bloque 4 — Detalles de interfaz y demo

- [ ] Agenda: *"Noviembre De 2026"* → *"Noviembre de 2026"*. Capitalizar solo la primera letra del string completo, no cada palabra, al formatear con `es-AR`.
- [ ] Logo: el isotipo actual es el ícono de "colapsar sidebar" y parece un botón. Reemplazarlo por un isotipo propio simple (por ejemplo, una "I" o una flecha ascendente en el azul petróleo de la marca) en `shell.tsx` y en el login.
- [ ] Botón **"Informe"** del detalle de consulta: al hacer clic no hay feedback visible. Agregar estado de carga y hacer scroll hasta el panel del informe.
- [ ] Datos demo (`seed_demo_v3`): hoy 1 de cada 5 mensajes tiene faltas de ortografía ("ola qeria…"). Mantener uno o dos, para probar la IA, y sumar casos realistas del rubro:
  - una cadena de farmacias que pide condiciones mayoristas de Dermogreen;
  - una startup que quiere 2.000 unidades de sérum (cae en "Bajo mínimo");
  - un distribuidor de Paraguay que consulta por exportación de fragancias Acqua Di Fiore;
  - un CV enviado por el formulario de contacto (no comercial);
  - un proveedor de envases ofreciendo frascos (no comercial).
- [ ] Actualizar `frontend/public/guia-de-uso.pdf` con el pipeline nuevo, la fusión y la priorización.

---

## Migraciones y seguridad de datos

- **Backup de SQLite antes de desplegar** (local y Railway), como en versiones anteriores. Ejemplo: `backups/impulso_pre_v4_AAAAMMDD.sqlite3`.
- Todas las migraciones son **aditivas** (`ALTER TABLE … ADD COLUMN` si falta, `CREATE TABLE IF NOT EXISTS`). No se borran mensajes, fichas, oportunidades ni usuarios.
- La fusión de gestiones y la migración de estados son **idempotentes**: correrlas dos veces no cambia nada.
- No modificar `.env`, `.env.local`, variables de Railway/Vercel ni las credenciales.

## Tests nuevos (`backend/tests/test_v4.py`)

- [ ] Contexto de IA con todos los mensajes de la gestión y los datos de la ficha.
- [ ] Extracción determinística del formulario web (producto, cantidad, localidad).
- [ ] Post-validación: `datos_faltantes` no incluye campos ya cargados.
- [ ] Fusión de gestiones (mensajes, actividades, checklists, claves de remitente).
- [ ] Concretadas de Reportes = Finalizados, con fichas y legacy.
- [ ] Seguimiento vencido visible en Reportes y en Agenda.
- [ ] Mapeo de estados viejos al pipeline nuevo.
- [ ] Badge "Bajo mínimo" según tipo y cantidad.
- [ ] Respuesta saliente registrada y tiempo de primera respuesta.

## Verificación local (Windows PowerShell)

```powershell
cd C:\Users\yesica.cherubino\Downloads\impulso\backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001 --env-file .env

cd ..\frontend
npm run typecheck
npm run build
npm run dev -- -p 3001
```

Probar en `http://localhost:3001/consultas`, en escritorio y en móvil (375 × 812):
1. Abrir Botánica Studio → Informe → debe decir **5000 unidades** y el borrador no debe preguntar la cantidad.
2. Fusionar los duplicados demo → cada empresa aparece una sola vez.
3. Comparar Reportes con Finalizados y Agenda → los números coinciden.
4. Ordenar la bandeja por Prioridad y filtrar "Mis consultas".
5. "Copiar y marcar como respondida" → el mensaje saliente aparece en el hilo.

Recién después, el commit y push habituales:

```powershell
cd ..
git status --short
git add backend/app backend/tests backend/scripts frontend/src frontend/public/guia-de-uso.pdf MEJORAS_V4_PASMANTER.md
git diff --cached --stat
git commit -m "Impulso V4: IA con contexto completo, fusión de gestiones, métricas unificadas y pipeline Pasmanter"
git push origin main
```

## Fuera de alcance de esta versión

- Integración real de envío y recepción con WhatsApp Business, Gmail y el formulario del sitio.
- Usuarios con permisos finos por línea de negocio.
- Integración con Tango (ERP) para precios y stock.
