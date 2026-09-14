import psycopg2.extras

from db import get_connection


def get_usuario_by_email(email: str):
    """Busca el usuario interno asociado al correo autenticado por Google."""
    correo = str(email or "").strip().lower()
    if not correo:
        return None

    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id, username, is_admin, escuderia, foto_perfil
            FROM usuarios
            WHERE LOWER(TRIM(COALESCE(correo, ''))) = %s
            LIMIT 1
            """,
            (correo,),
        )
        row = cur.fetchone()
    finally:
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
