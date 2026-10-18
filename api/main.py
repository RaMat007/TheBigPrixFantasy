"""API de lectura inicial para BigPrix React 2.0.

No ejecuta init_db ni modifica tablas. La administración y los picks
permanecen exclusivamente en la aplicación actual hasta migrar su autenticación.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor

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
