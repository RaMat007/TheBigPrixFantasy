# db.py
import os
import psycopg2
import psycopg2.extras
from datetime import datetime
import hashlib
from logger import get_logger

log = get_logger()


def _get_database_url():
    """Obtiene DATABASE_URL desde st.secrets (Streamlit Cloud) o variables de entorno."""
    try:
        import streamlit as st
        return st.secrets["DATABASE_URL"]
    except Exception:
        return os.environ.get("DATABASE_URL", "")


def get_connection():
    try:
        url = _get_database_url()
        # Asegurar sslmode=require en la URL si no está ya incluido
        if "sslmode" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode=require"
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
        log.info("Conexión a la base de datos establecida.")
        return conn
    except Exception as e:
        log.error(f"Error al conectar a la base de datos: {e}")
        raise


def _column_exists(cur, table, column):
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return cur.fetchone() is not None


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        nombre TEXT,
        apellido TEXT,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    # Migración en caliente: asegurar columnas extendidas en usuarios
    if not _column_exists(cur, "usuarios", "nombre"):
        cur.execute("ALTER TABLE usuarios ADD COLUMN nombre TEXT")
    if not _column_exists(cur, "usuarios", "apellido"):
        cur.execute("ALTER TABLE usuarios ADD COLUMN apellido TEXT")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS temporadas (
        id SERIAL PRIMARY KEY,
        nombre TEXT NOT NULL,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT NOT NULL,
        activa INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS carreras (
        id SERIAL PRIMARY KEY,
        temporada_id INTEGER NOT NULL,
        round INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        inicio TEXT NOT NULL,
        kms REAL,
        vueltas INTEGER,
        pista TEXT,
        hora TEXT,
        UNIQUE(temporada_id, round),
        FOREIGN KEY (temporada_id) REFERENCES temporadas(id)
    )
    """)

    # Migración en caliente: asegurar columnas extendidas en carreras
    if not _column_exists(cur, "carreras", "kms"):
        cur.execute("ALTER TABLE carreras ADD COLUMN kms REAL")
    if not _column_exists(cur, "carreras", "vueltas"):
        cur.execute("ALTER TABLE carreras ADD COLUMN vueltas INTEGER")
    if not _column_exists(cur, "carreras", "pista"):
        cur.execute("ALTER TABLE carreras ADD COLUMN pista TEXT")
    if not _column_exists(cur, "carreras", "hora"):
        cur.execute("ALTER TABLE carreras ADD COLUMN hora TEXT")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS pilotos (
        id SERIAL PRIMARY KEY,
        codigo TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        escuderia TEXT,
        activo INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS picks (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        carrera_id INTEGER NOT NULL,
        piloto_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        UNIQUE(usuario_id, carrera_id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
        FOREIGN KEY (carrera_id) REFERENCES carreras(id),
        FOREIGN KEY (piloto_id) REFERENCES pilotos(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS picks_temporada (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        temporada_id INTEGER NOT NULL,
        piloto_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        UNIQUE(usuario_id, temporada_id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
        FOREIGN KEY (temporada_id) REFERENCES temporadas(id),
        FOREIGN KEY (piloto_id) REFERENCES pilotos(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS resultados (
        id SERIAL PRIMARY KEY,
        carrera_id INTEGER NOT NULL,
        piloto_id INTEGER NOT NULL,
        posicion INTEGER NOT NULL,
        UNIQUE(carrera_id, posicion),
        FOREIGN KEY (carrera_id) REFERENCES carreras(id),
        FOREIGN KEY (piloto_id) REFERENCES pilotos(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS puntos (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        carrera_id INTEGER NOT NULL,
        puntos INTEGER NOT NULL,
        UNIQUE(usuario_id, carrera_id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
        FOREIGN KEY (carrera_id) REFERENCES carreras(id)
    )
    """)

    _seed_admin(cur)

    conn.commit()
    conn.close()


def _seed_admin(cur):
    """
    user: admin
    pass: admin
    """
    cur.execute("SELECT id FROM usuarios WHERE username = 'admin'")
    if cur.fetchone():
        return

    password_hash = hashlib.sha256("admin".encode()).hexdigest()

    cur.execute("""
        INSERT INTO usuarios (username, password_hash, is_admin, created_at)
        VALUES (%s, %s, %s, %s)
    """, (
        "admin",
        password_hash,
        1,
        datetime.now().isoformat()
    ))
