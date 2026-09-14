# auth.py
from db import get_connection
import hashlib
import os
import psycopg2.extras
import streamlit as st
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


SESSION_TOKEN_MAX_AGE = 12 * 60 * 60
SESSION_TOKEN_SALT = "thebigprixfantasy-browser-session-v1"


def _session_secret() -> str:
    """Obtiene una llave privada estable sin exponerla al navegador."""
    configured = os.environ.get("AUTH_COOKIE_SECRET", "")
    database_url = os.environ.get("DATABASE_URL", "")
    try:
        configured = str(st.secrets.get("AUTH_COOKIE_SECRET", configured) or configured)
        database_url = str(st.secrets.get("DATABASE_URL", database_url) or database_url)
    except Exception:
        pass

    if configured:
        return configured
    if not database_url:
        raise RuntimeError("No hay una llave disponible para firmar la sesión.")
    return hashlib.sha256(f"tbpf:{database_url}".encode()).hexdigest()


def _session_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_session_secret(), salt=SESSION_TOKEN_SALT)


def crear_token_sesion(user_id: int) -> str:
    """Crea un token firmado; nunca guarda usuario o contraseña en texto plano."""
    return _session_serializer().dumps({"uid": int(user_id)})


def validar_token_sesion(token: str):
    """Valida el token recordado y vuelve a consultar al usuario en la base."""
    if not token:
        return None
    try:
        payload = _session_serializer().loads(token, max_age=SESSION_TOKEN_MAX_AGE)
        user_id = int(payload["uid"])
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None
    return get_usuario_by_id(user_id)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, stored_hash: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == stored_hash

def validar_login(username: str, password: str):
    """
    Returns {'id','username','is_admin'} on success, else None.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # determine stored column name if legacy
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'usuarios'
    """)
    cols = [c["column_name"] for c in cur.fetchall()]
    colname = "password_hash" if "password_hash" in cols else ("password" if "password" in cols else None)
    if colname is None:
        conn.close()
        return None

    cur.execute(f"SELECT id, username, {colname} as pw, is_admin, escuderia, foto_perfil FROM usuarios WHERE username=%s", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    stored = row["pw"]
    if stored is None:
        return None
    if verify_password(password, stored):
        return {
            "id": row["id"],
            "username": row["username"],
            "is_admin": bool(row["is_admin"]),
            "escuderia": row.get("escuderia") or "",
            "foto_perfil": row.get("foto_perfil") or "",
        }
    return None


def verificar_correo(correo: str, escuderia: str):
    """
    Devuelve el id del usuario si el correo Y la escudería coinciden, si no None.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT id FROM usuarios WHERE LOWER(TRIM(COALESCE(correo,'')))=LOWER(TRIM(%s)) AND correo IS NOT NULL AND correo <> '' AND LOWER(TRIM(COALESCE(escuderia,'')))=LOWER(TRIM(%s))",
        (correo.strip(), escuderia.strip()),
    )
    row = cur.fetchone()
    conn.close()
    return row["id"] if row else None


def get_usuario_by_id(user_id: int):
    """Devuelve dict con datos del usuario por id, o None si no existe."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT id, username, is_admin, escuderia, foto_perfil FROM usuarios WHERE id=%s",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "escuderia": row.get("escuderia") or "",
        "foto_perfil": row.get("foto_perfil") or "",
    }


def actualizar_password(user_id: int, nueva_password: str):
    """Actualiza el hash de contraseña para el usuario dado."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE usuarios SET password_hash=%s WHERE id=%s",
        (hash_password(nueva_password), user_id),
    )
    conn.commit()
    conn.close()
