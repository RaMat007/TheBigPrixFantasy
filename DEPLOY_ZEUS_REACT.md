# Despliegue de pruebas en ZEUS (sin afectar otros servicios)

**No ejecutar como root ni sustituir servicios existentes.** La rama `feat/react-2` es una versión de desarrollo. El actual sitio Streamlit sigue funcionando por separado.

## 1. Preparación en una carpeta independiente

```bash
cd ~/Projects
git clone --branch feat/react-2 https://github.com/RaMat007/TheBigPrixFantasy.git BIGPRIX_REACT
cd BIGPRIX_REACT
python3 -m venv .venv
.venv/bin/pip install -r api/requirements.txt
cd frontend && npm ci || npm install
npm run build
cd ..
```

Usar una versión Node.js compatible con el Vite del proyecto (Node >=18). Ningún paso cambia ni reinicia SSH, NetworkManager, Tailscale o aplicaciones de ZEUS.

## 2. Credenciales y sesiones

Crear un archivo privado en `~/Projects/BIGPRIX_REACT/.env.zeus` con permisos 600, que contenga:

```dotenv
DATABASE_URL=postgresql://USUARIO:CLAVE@HOST:PUERTO/BASE
BIGPRIX_SESSION_SECRET=GENERAR_SECRETO_ALEATORIO_DE_AL_MENOS_32_CARACTERES
BIGPRIX_COOKIE_SECURE=false
```

Usar inicialmente **una credencial de solo lectura de PostgreSQL** en la base real, sin alterar tablas ni registros. No añadir `.env.zeus` a Git; cargar variables localmente desde la shell. `BIGPRIX_COOKIE_SECURE=false` solo para pruebas HTTP en localhost. Para acceso público HTTPS debe ser `true`.

```bash
cd ~/Projects/BIGPRIX_REACT
set -a; source .env.zeus; set +a
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8090
```

En otra terminal, para desarrollo React: `cd ~/Projects/BIGPRIX_REACT/frontend && npm run dev`. Verificar API: `curl -fsS http://127.0.0.1:8090/api/health`.

## 3. Acceso remoto seguro

Para comprobar desde AIR sin abrir servicios a Internet, iniciar desde **AIR**, por separado:

```bash
ssh -N -L 5173:127.0.0.1:5173 alpha@ZEUS_TAILSCALE_IP
```

Abrir `http://127.0.0.1:5173` en AIR. Este comando solo abre un túnel desde AIR; no altera ni cierra el demonio SSH de ZEUS.

Para producción faltan la configuración del proxy HTTPS, un servicio systemd específico, pruebas de regresión de reglas y la fase de picks autenticados. No migrar DNS ni apagar Streamlit antes de completar esas validaciones.

## Riesgos conocidos

- La aplicación anterior emplea SHA-256 sin salt para contraseñas. Esta compatibilidad es temporal; migrar a Argon2id con rehash al iniciar sesión.
- No habilitar selección de picks hasta verificar las reglas de cierre por zona horaria y sincronización de puntuaciones.
- No reutilizar la base de desarrollo para ejecutar `init_db()` en producción.
- El backend no maneja el estado de conexión a ZEUS ni sustituye configuraciones de Tailscale.
