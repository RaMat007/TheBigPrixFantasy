# auth.py
from db import get_connection
import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, stored_hash: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == stored_hash

def validar_login(username: str, password: str):
    """
    Returns {'id','username','is_admin'} on success, else None.
    """
    conn = get_connection()
    cur = conn.cursor()

    # determine stored column name if legacy
    cur.execute("PRAGMA table_info(usuarios)")
    cols = [c["name"] for c in cur.fetchall()]
    colname = "password_hash" if "password_hash" in cols else ("password" if "password" in cols else None)
    if colname is None:
        conn.close()
        return None

    cur.execute(f"SELECT id, username, {colname} as pw, is_admin FROM usuarios WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    stored = row["pw"]
    if stored is None:
        return None
    if verify_password(password, stored):
        return {"id": row["id"], "username": row["username"], "is_admin": bool(row["is_admin"])}
    return None
