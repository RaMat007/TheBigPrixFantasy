# db.py
import sqlite3
from pathlib import Path
from datetime import datetime
import hashlib
from logger import get_logger

log = get_logger()

DB_PATH = Path(__file__).parent / "quiniela.db"


def get_connection():
    try:
        conn = sqlite3.connect(
            DB_PATH,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        log.info("Conexión a la base de datos establecida.")
        return conn
    except Exception as e:
        log.error(f"Error al conectar a la base de datos: {e}")
        raise


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        nombre TEXT,
        apellido TEXT,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    # Migración en caliente: asegurar columnas extendidas en usuarios
    cur.execute("PRAGMA table_info(usuarios)")
    cols_usuarios = [row[1] for row in cur.fetchall()]
    if "nombre" not in cols_usuarios:
        cur.execute("ALTER TABLE usuarios ADD COLUMN nombre TEXT")
    if "apellido" not in cols_usuarios:
        cur.execute("ALTER TABLE usuarios ADD COLUMN apellido TEXT")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS temporadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT NOT NULL,
        activa INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS carreras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        temporada_id INTEGER NOT NULL,
        round INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        inicio DATETIME NOT NULL,
        kms REAL,
        vueltas INTEGER,
        pista TEXT,
        hora TEXT,
        UNIQUE(temporada_id, round),
        FOREIGN KEY (temporada_id) REFERENCES temporadas(id)
    )
    """)

    # Migración en caliente: asegurar columnas extendidas en carreras
    cur.execute("PRAGMA table_info(carreras)")
    cols = [row[1] for row in cur.fetchall()]

    if "kms" not in cols:
        cur.execute("ALTER TABLE carreras ADD COLUMN kms REAL")
    if "vueltas" not in cols:
        cur.execute("ALTER TABLE carreras ADD COLUMN vueltas INTEGER")
    if "pista" not in cols:
        cur.execute("ALTER TABLE carreras ADD COLUMN pista TEXT")
    if "hora" not in cols:
        cur.execute("ALTER TABLE carreras ADD COLUMN hora TEXT")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS pilotos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        escuderia TEXT,
        activo INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS picks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        VALUES (?, ?, ?, ?)
    """, (
        "admin",
        password_hash,
        1,
        datetime.now().isoformat()
    ))
