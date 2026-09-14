# auth.py
from db import get_connection
import base64
import hashlib
import hmac
import json
import os
import time
import psycopg2.extras
import streamlit as st


SESSION_TOKEN_MAX_AGE = 12 * 60 * 60
SESSION_TOKEN_SALT = "thebigprixfantasy-browser-session-v1"


def _session_secret() -> str:
    """Obtiene una llave privada estable sin exponerla al navegador."""
    configured = os.environ.get("AUTH_COOKIE_SECRET", "")
    database_url = os.environ.get("DATABASE_URL", "")

    try:
        if "AUTH_COOKIE_SECRET" in st.secrets:
            configured = str(st.secrets["AUTH_COOKIE_SECRET"])
        if "DATABASE_URL" in st.secrets:
            database_url = str(st.secrets["DATABASE_URL"])
    except Exception:
        pass

    if configured:
        return configured

    if not database_url:
        raise RuntimeError("No hay una llave disponible para firmar la sesión.")

    return hashlib.sha256(
        f"{SESSION_TOKEN_SALT}:{database_url}".encode("utf-8")
    ).hexdigest()


def _fingerprint_cliente(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:20]


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def crear_token_sesion(user_id: int, cliente: str = "", *_, **__) -> str:
    """Crea un token HMAC firmado válido durante 12 horas."""
    payload = {
        "uid": int(user_id),
        "fp": _fingerprint_cliente(cliente),
        "exp": int(time.time()) + SESSION_TOKEN_MAX_AGE,
    }

    payload_b64 = _b64_encode(
        json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )

    firma = hmac.new(
        _session_secret().encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    return f"{payload_b64}.{firma}"


def validar_token_sesion(token: str, cliente: str = "", *_, **__):
    """Valida firma, expiración y navegador del token recordado."""
    if not token:
        return None

    try:
        payload_b64, firma_recibida = token.split(".", 1)

        firma_esperada = hmac.new(
            _session_secret().encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(firma_recibida, firma_esperada):
            return None

        payload = json.loads(_b64_decode(payload_b64).decode("utf-8"))

        if int(payload["exp"]) < int(time.time()):
            return None

        if payload.get("fp") != _fingerprint_cliente(cliente):
            return None

        user_id = int(payload["uid"])

    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
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
