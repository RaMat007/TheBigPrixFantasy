import sqlite3
from pathlib import Path
from typing import Dict, Any

# Ruta fija al archivo SQLite de F1DB (mismo que usa f1db_prueba.py)
F1DB_PATH = Path(__file__).parent / "Consultas F1DB" / "f1db.db"


def _get_f1db_connection() -> sqlite3.Connection:
    """Devuelve una conexión de solo lectura a la base F1DB.

    Si el archivo no existe, lanza una excepción para que el caller pueda manejarlo.
    """
    if not F1DB_PATH.exists():
        raise FileNotFoundError(f"No se encontró la base F1DB en {F1DB_PATH}")

    conn = sqlite3.connect(F1DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def carreras_detalle_por_round(year: int) -> Dict[int, Dict[str, Any]]:
    """Devuelve un dict {round: {country, city, laps, track_length_km, circuit_name}}.

    Si no hay datos o falla la conexión, devuelve dict vacío.
    """
    try:
        conn = _get_f1db_connection()
    except FileNotFoundError:
        return {}

    cur = conn.cursor()
    sql = """
        SELECT
            r.round,
            r.date         AS race_date,
            r.time         AS race_time,
            co.name        AS country,
            c.place_name   AS city,
            r.laps         AS laps,
            r.course_length AS track_length_km,
            c.name         AS circuit_name
        FROM race r
        JOIN grand_prix gp ON gp.id = r.grand_prix_id
        JOIN circuit c     ON c.id = r.circuit_id
        JOIN country co    ON co.id = c.country_id
        WHERE r.year = ?
        ORDER BY r.round
    """

    try:
        cur.execute(sql, (year,))
        rows = cur.fetchall()
    finally:
        conn.close()

    detalle: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        rnd = int(row["round"])
        detalle[rnd] = {
            "race_date": row["race_date"],
            "race_time": row["race_time"],
            "country": row["country"],
            "city": row["city"],
            "laps": row["laps"],
            "track_length_km": row["track_length_km"],
            "circuit_name": row["circuit_name"],
        }

    return detalle
