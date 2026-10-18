# BigPrix React 2.0 — fase inicial

Rama de desarrollo aislada. **No desplegar sobre la app Streamlit actual.** No se modifican tablas ni picks en esta etapa.

## API

En la raíz del repositorio, crear un entorno Python e instalar `pip install -r api/requirements.txt`. Definir `DATABASE_URL` con credenciales privadas fuera del repositorio. Ejecutar `uvicorn api.main:app --host 127.0.0.1 --port 8090`.

La API inicial solo publica el calendario de la temporada activa y la parrilla de pilotos (datos deportivos públicos). No existe aún acceso a ranking, picks ni perfil: requieren autenticación y autorización propias antes de exponer datos.

## React

`cd frontend && npm install && npm run dev` (Vite: puerto 5173; proxy local hacia FastAPI 8090).

## Próximas etapas

1. Autenticación segura y sesión HTTP-only independiente de Streamlit.
2. Dashboard personalizado, clasificación y picks protegidos por usuario.
3. Selección P5 respetando las funciones y restricciones vigentes, sin cambiar los IDs ni el esquema antes de verificar paridad.
4. Admin, históricos Apertura/Clausura, pruebas de regresión y validación de cierre/auto-picks.
5. Despliegue de prueba aislado, prueba end-to-end y eventual migración productiva expresamente autorizada.

**Nota:** El código inicial todavía no cuenta con build ni pruebas de integración ejecutadas en infraestructura real.
