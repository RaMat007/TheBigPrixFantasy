"""API de lectura inicial para BigPrix React 2.0.

No ejecuta init_db ni modifica tablas. La administración y los picks
permanecen exclusivamente en la aplicación actual hasta migrar su autenticación.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from itsdangerous import URLSafeTimedSerializer, BadSignature
import hashlib
import hmac

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import get_connection

app = FastAPI(title="The Big Prix Fantasy API", version="0.1.0")
allowed_origins = [item.strip() for item in os.getenv("BIGPRIX_CORS_ORIGINS", "http://localhost:5173").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=False, allow_methods=["GET"], allow_headers=["Content-Type"])


@contextmanager
def cursor():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
    finally:
        conn.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "read-only"}


@app.get("/api/season")
def season():
    try:
        with cursor() as cur:
            cur.execute("SELECT id, nombre, fecha_inicio, fecha_fin FROM temporadas WHERE activa = 1 LIMIT 1")
            active = cur.fetchone()
            if not active:
                return {"season": None, "races": []}
            cur.execute("""
                SELECT id, round, nombre, inicio, kms, vueltas, pista, hora
                FROM carreras WHERE temporada_id = %s AND NOT cancelada ORDER BY round
            """, (active["id"],))
            races = [dict(row) for row in cur.fetchall()]
            return {"season": dict(active), "races": races}
    except Exception:
        raise HTTPException(503, detail="No se pudo consultar el calendario")


@app.get("/api/drivers")
def drivers():
    try:
        with cursor() as cur:
            cur.execute("""
                SELECT id, codigo, nombre, escuderia, foto_url, color_escuderia
                FROM pilotos WHERE activo = 1 ORDER BY escuderia, nombre
            """)
            return {"drivers": [dict(row) for row in cur.fetchall()]}
    except Exception:
        raise HTTPException(503, detail="No se pudieron consultar los pilotos")

# En esta fase: sesiones firmadas independientes; nunca se envían tokens en URL.
SESSION_NAME = "bigprix_auth"
SESSION_SECONDS = 12 * 60 * 60
def signer():
    secret = os.getenv("BIGPRIX_SESSION_SECRET")
    if not secret or len(secret) < 32:
        raise HTTPException(503, detail="Sesiones no configuradas")
    return URLSafeTimedSerializer(secret, salt="bigprix-react-v2")

class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)

def current_user(request: Request):
    token = request.cookies.get(SESSION_NAME)
    if not token:
        raise HTTPException(401, detail="Inicia sesión")
    try:
        uid = int(signer().loads(token, max_age=SESSION_SECONDS))
    except (BadSignature, ValueError, TypeError):
        raise HTTPException(401, detail="Sesión inválida")
    with cursor() as cur:
        cur.execute("SELECT id, username, nombre, escuderia, is_admin FROM usuarios WHERE id=%s", (uid,))
        user = cur.fetchone()
    if not user:
        raise HTTPException(401, detail="Usuario no encontrado")
    return dict(user)

@app.post("/api/auth/login")
def login(body: Credentials, response: Response, request: Request):
    with cursor() as cur:
        cur.execute("SELECT id, username, nombre, escuderia, is_admin, password_hash FROM usuarios WHERE username=%s", (body.username,))
        row = cur.fetchone()
    digest = hashlib.sha256(body.password.encode()).hexdigest()
    if not row or not hmac.compare_digest(digest, row["password_hash"] or ""):
        raise HTTPException(401, detail="Credenciales incorrectas")
    secure = os.getenv("BIGPRIX_COOKIE_SECURE", "true").lower() == "true"
    response.set_cookie(SESSION_NAME, signer().dumps(str(row["id"])), max_age=SESSION_SECONDS,
        httponly=True, secure=secure, samesite="lax", path="/api")
    return {"user": {k: row[k] for k in ("id", "username", "nombre", "escuderia", "is_admin")}}

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_NAME, path="/api")
    return {"ok": True}

@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return {"user": user}

@app.get("/api/me/picks")
def my_picks(user=Depends(current_user)):
    with cursor() as cur:
        cur.execute("""
          SELECT p.id, p.carrera_id, c.round, c.nombre AS carrera,
                 d.codigo, d.nombre AS piloto, p.auto_asignado,
                 pt.puntos
          FROM picks p
          JOIN carreras c ON c.id=p.carrera_id
          JOIN pilotos d ON d.id=p.piloto_id
          LEFT JOIN puntos pt ON pt.carrera_id=p.carrera_id AND pt.usuario_id=p.usuario_id
          WHERE p.usuario_id=%s
          ORDER BY c.inicio DESC
        """, (user["id"],))
        return {"picks": [dict(r) for r in cur.fetchall()]}

@app.get("/api/leaderboard")
def leaderboard(user=Depends(current_user)):
    with cursor() as cur:
        cur.execute("SELECT id FROM temporadas WHERE activa=1 LIMIT 1")
        season=cur.fetchone()
        if not season:
            return {"ranking": []}
        cur.execute("""
          SELECT u.id, COALESCE(NULLIF(u.escuderia,''),u.username) AS escuderia,
                 COALESCE(SUM(pt.puntos),0)::integer AS puntos
          FROM usuarios u
          LEFT JOIN puntos pt ON pt.usuario_id=u.id
          LEFT JOIN carreras c ON c.id=pt.carrera_id AND c.temporada_id=%s
          GROUP BY u.id, u.username, u.escuderia
          ORDER BY puntos DESC, escuderia ASC
        """, (season["id"],))
        return {"ranking": [dict(r) for r in cur.fetchall()]}
