from datetime import datetime
from db import get_connection
import pandas as pd
import hashlib
import psycopg2.extras
import rules
import time
import f1db_integration

from logger import get_logger
log = get_logger()

# =========================
# USUARIOS
# =========================
def crear_usuario(username, password, is_admin=0, nombre=None, apellido=None, correo=None, escuderia=None):
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        INSERT INTO usuarios (username, nombre, apellido, correo, escuderia, password_hash, is_admin, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            username,
            nombre,
            apellido,
            correo,
            escuderia,
            password_hash,
            is_admin,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()

def obtener_usuario(username, password):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM usuarios
        WHERE username = %s AND password = %s
    """, (username, password))
    row = cur.fetchone()
    conn.close()
    return row

def actualizar_foto_perfil(user_id: int, foto_b64: str):
    """Guarda la foto de perfil (base64) en la BD para el usuario dado."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE usuarios SET foto_perfil = %s WHERE id = %s",
        (foto_b64, user_id),
    )
    conn.commit()
    conn.close()

def obtener_foto_perfil(user_id: int) -> str:
    """Devuelve la foto_perfil (base64) del usuario, o cadena vacía."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT foto_perfil FROM usuarios WHERE id = %s", (user_id,))
    row = cur.fetchone()
    conn.close()
    return (row["foto_perfil"] or "") if row else ""

def listar_usuarios():
    conn = None
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM usuarios ORDER BY username", conn)
        log.info("Usuarios listados correctamente.")
        return df
    except Exception as e:
        log.error(f"Error al listar usuarios: {e}")
    finally:
        if conn:
            conn.close()
            log.info("Conexión a la base de datos cerrada.")

def editar_usuario(usuario_id, username, is_admin, new_password=None, nombre=None, apellido=None, correo=None, escuderia=None):
    """Actualiza todos los datos de un usuario.

    Si se pasa new_password, también actualiza el password_hash.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    campos = ["username = %s", "is_admin = %s"]
    params = [username, is_admin]

    if nombre is not None:
        campos.append("nombre = %s")
        params.append(nombre)

    if apellido is not None:
        campos.append("apellido = %s")
        params.append(apellido)

    if correo is not None:
        campos.append("correo = %s")
        params.append(correo)

    if escuderia is not None:
        campos.append("escuderia = %s")
        params.append(escuderia)

    if new_password:
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        campos.append("password_hash = %s")
        params.append(password_hash)

    params.append(usuario_id)

    cur.execute(
        f"UPDATE usuarios SET {', '.join(campos)} WHERE id = %s",
        params,
    )

    conn.commit()
    conn.close()


def eliminar_usuario(usuario_id):
    """Elimina un usuario por su id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
    conn.commit()
    conn.close()

def reset_password(usuario_id, new_password):
    password_hash = hashlib.sha256(new_password.encode()).hexdigest()

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        UPDATE usuarios
        SET password_hash = %s
        WHERE id = %s
    """, (password_hash, usuario_id))

    conn.commit()
    conn.close()


# =========================
# TEMPORADAS
# =========================
def crear_temporada(nombre, fecha_inicio, fecha_fin):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO temporadas (nombre, fecha_inicio, fecha_fin, activa)
        VALUES (%s, %s, %s, 0)
    """, (nombre, fecha_inicio, fecha_fin))
    conn.commit()
    conn.close()

def listar_temporadas():
    conn = None
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM temporadas ORDER BY fecha_inicio DESC", conn)
        log.info("Temporadas listadas correctamente.")
        return df
    except Exception as e:
        log.error(f"Error al listar temporadas: {e}")
    finally:
        if conn:
            conn.close()
            log.info("Conexión a la base de datos cerrada.")

def activar_temporada(temporada_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("UPDATE temporadas SET activa = 0")
    cur.execute("""
        UPDATE temporadas
        SET activa = 1
        WHERE id = %s
    """, (temporada_id,))
    conn.commit()
    conn.close()

def obtener_temporada_activa():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM temporadas
        WHERE activa = 1
        LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()
    return row


# =========================
# CARRERAS
# =========================
def crear_carrera(temporada_id, round_num, nombre, inicio, kms=None, vueltas=None, pista=None, hora=None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO carreras (temporada_id, round, nombre, inicio, kms, vueltas, pista, hora)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (temporada_id, round_num, nombre, inicio, kms, vueltas, pista, hora))
    conn.commit()
    conn.close()

def listar_carreras_temporada(temporada_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT *
        FROM carreras
        WHERE temporada_id = %s
        ORDER BY round
    """, conn, params=(temporada_id,))
    conn.close()
    return df

def obtener_carrera(carrera_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM carreras
        WHERE id = %s
    """, (carrera_id,))
    row = cur.fetchone()
    conn.close()
    return row

def obtener_proxima_carrera(temporada_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM carreras
        WHERE temporada_id = %s AND inicio > %s
        ORDER BY inicio ASC
        LIMIT 1
    """, (temporada_id, datetime.now().isoformat()))
    row = cur.fetchone()
    conn.close()
    return row

def editar_carrera(carrera_id, round_num, nombre, inicio, kms=None, vueltas=None, pista=None, hora=None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        UPDATE carreras
        SET round = %s, nombre = %s, inicio = %s, kms = %s, vueltas = %s, pista = %s, hora = %s
        WHERE id = %s
    """, (round_num, nombre, inicio, kms, vueltas, pista, hora, carrera_id))

    conn.commit()
    conn.close()

def eliminar_carrera(carrera_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        DELETE FROM carreras
        WHERE id = %s
    """, (carrera_id,))
    conn.commit()
    conn.close()

def carrera_bloqueada(fecha_carrera):
    return datetime.now() >= datetime.fromisoformat(fecha_carrera)

def countdown(inicio):
    while True:
        now = datetime.now()
        delta = inicio - now
        if delta.total_seconds() <= 0:
            break
        mins, secs = divmod(int(delta.total_seconds()), 60)
        time_str = f"{mins:02}:{secs:02}"
        print(f"Tiempo restante para la carrera: {time_str}", end='\r')
        time.sleep(1)
    print("La carrera ha comenzado!                     ")


def actualizar_carreras_desde_f1db(temporada_id, year):
    """Actualiza kms, vueltas y pista de todas las carreras de una temporada usando F1DB.

    Empareja por número de round entre quiniela.db y f1db.db.
    """
    detalles = f1db_integration.carreras_detalle_por_round(int(year))
    if not detalles:
        log.warning(f"No se encontraron datos de F1DB para el año {year}.")
        return

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        SELECT id, round
        FROM carreras
        WHERE temporada_id = %s
        """,
        (temporada_id,),
    )
    filas = cur.fetchall()

    for row in filas:
        cid = row["id"]
        rnd = row["round"]
        info = detalles.get(int(rnd)) if rnd is not None else None
        if not info:
            continue

        kms = info.get("track_length_km")
        vueltas = info.get("laps")
        pista = info.get("circuit_name")
        race_date = info.get("race_date")
        race_time = info.get("race_time")

        inicio = None
        hora = None
        if race_date:
            # race_time suele venir como HH:MM:SS; lo dejamos tal cual
            if race_time:
                inicio = f"{race_date}T{race_time}"
                hora = race_time[:5]
            else:
                inicio = race_date

        cur.execute(
            """
            UPDATE carreras
            SET kms = COALESCE(%s, kms),
                vueltas = COALESCE(%s, vueltas),
                pista = COALESCE(%s, pista),
                inicio = COALESCE(%s, inicio),
                hora = COALESCE(%s, hora)
            WHERE id = %s
            """,
            (kms, vueltas, pista, inicio, hora, cid),
        )

    conn.commit()
    conn.close()

# =========================
# PILOTOS
# =========================
def crear_piloto(codigo, nombre, escuderia):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO pilotos (codigo, nombre, escuderia, activo)
        VALUES (%s, %s, %s, 1)
    """, (codigo, nombre, escuderia))
    conn.commit()
    conn.close()

def listar_pilotos(activos_only=True):
    conn = None
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM pilotos" + (" WHERE activo = 1" if activos_only else ""), conn)
        log.info("Pilotos listados correctamente.")
        return df
    except Exception as e:
        log.error(f"Error al listar pilotos: {e}")
    finally:
        if conn:
            conn.close()
            log.info("Conexión a la base de datos cerrada.")


def obtener_piloto(piloto_id):
    """Devuelve un piloto por id o None si no existe."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT * FROM pilotos
        WHERE id = %s
        """,
        (piloto_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row

def desactivar_piloto(piloto_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        UPDATE pilotos
        SET activo = 0
        WHERE id = %s
    """, (piloto_id,))
    conn.commit()
    conn.close()

def editar_piloto(piloto_id, codigo, nombre, escuderia, activo):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        UPDATE pilotos
        SET codigo = %s, nombre = %s, escuderia = %s, activo = %s
        WHERE id = %s
    """, (codigo, nombre, escuderia, activo, piloto_id))

    conn.commit()
    conn.close()


# =========================
# PICKS
# =========================
def guardar_pick(usuario_id, carrera_id, piloto_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO picks
        (usuario_id, carrera_id, piloto_id, timestamp)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (usuario_id, carrera_id)
        DO UPDATE SET piloto_id = EXCLUDED.piloto_id, timestamp = EXCLUDED.timestamp
    """, (usuario_id, carrera_id, piloto_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def obtener_pick_usuario(usuario_id, carrera_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM picks
        WHERE usuario_id = %s AND carrera_id = %s
    """, (usuario_id, carrera_id))
    row = cur.fetchone()
    conn.close()
    return row

def listar_picks_carrera(carrera_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT p.*, u.username, pl.nombre AS piloto
        FROM picks p
        JOIN usuarios u ON u.id = p.usuario_id
        JOIN pilotos pl ON pl.id = p.piloto_id
        WHERE p.carrera_id = %s
    """, (carrera_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def pick_designado(carrera_id, piloto_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT COUNT(*) AS cnt FROM picks
        WHERE carrera_id = %s AND piloto_id = %s
    """, (carrera_id, piloto_id))
    count = cur.fetchone()["cnt"]
    conn.close()
    return count > 0

def top_picks_global(temporada_id, limit=10):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT
            pl.codigo AS piloto_codigo,
            pl.nombre AS piloto_nombre,
            COALESCE(COUNT(p.id), 0) AS pick_count
        FROM pilotos pl
        LEFT JOIN picks p 
            ON p.piloto_id = pl.id
        LEFT JOIN carreras c
            ON c.id = p.carrera_id
            AND c.temporada_id = %s
        GROUP BY pl.id
        ORDER BY pick_count DESC, pl.nombre ASC
        LIMIT %s
    """, conn, params=(temporada_id, limit))
    conn.close()
    return df


def _ensure_picks_temporada_table(cur):
    """Crea la tabla picks_temporada si aún no existe (migración en caliente)."""
    cur.execute(
        """
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
        """
    )


def guardar_pick_temporada(usuario_id, temporada_id, piloto_id):
    """Guarda o actualiza la selección de 5° lugar para toda la temporada."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    _ensure_picks_temporada_table(cur)
    cur.execute(
        """
        INSERT INTO picks_temporada
        (usuario_id, temporada_id, piloto_id, timestamp)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (usuario_id, temporada_id)
        DO UPDATE SET piloto_id = EXCLUDED.piloto_id, timestamp = EXCLUDED.timestamp
        """,
        (usuario_id, temporada_id, piloto_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def obtener_pick_temporada(usuario_id, temporada_id):
    """Devuelve el pick de temporada (si existe) para un usuario."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    _ensure_picks_temporada_table(cur)
    cur.execute(
        """
        SELECT * FROM picks_temporada
        WHERE usuario_id = %s AND temporada_id = %s
        """,
        (usuario_id, temporada_id),
    )
    row = cur.fetchone()
    conn.close()
    return row


def historial_picks_usuario(usuario_id, temporada_id):
    """Historial de picks por carrera para un usuario en una temporada."""
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            c.round,
            c.nombre AS carrera,
            c.inicio,
            pl.codigo AS piloto_codigo,
            pl.nombre AS piloto_nombre,
            r.posicion AS posicion_real,
            COALESCE(pt.puntos, 0) AS puntos
        FROM picks p
        JOIN carreras c ON c.id = p.carrera_id
        JOIN pilotos pl ON pl.id = p.piloto_id
        LEFT JOIN resultados r
            ON r.carrera_id = p.carrera_id
           AND r.piloto_id = p.piloto_id
        LEFT JOIN puntos pt
            ON pt.carrera_id = p.carrera_id
           AND pt.usuario_id = p.usuario_id
        WHERE p.usuario_id = %s
          AND c.temporada_id = %s
        ORDER BY c.round ASC
        """,
        conn,
        params=(usuario_id, temporada_id),
    )
    conn.close()
    return df


def historial_picks_temporada(temporada_id):
    """Historial de picks por carrera para todos los usuarios (no-admin) en una temporada."""
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            c.round,
            c.nombre AS carrera,
            c.inicio,
            u.username,
            pl.codigo AS piloto_codigo,
            pl.nombre AS piloto_nombre,
            r.posicion AS posicion_real,
            COALESCE(pt.puntos, 0) AS puntos
        FROM picks p
        JOIN usuarios u ON u.id = p.usuario_id AND u.is_admin = 0
        JOIN carreras c ON c.id = p.carrera_id
        JOIN pilotos pl ON pl.id = p.piloto_id
        LEFT JOIN resultados r
            ON r.carrera_id = p.carrera_id
           AND r.piloto_id = p.piloto_id
        LEFT JOIN puntos pt
            ON pt.carrera_id = p.carrera_id
           AND pt.usuario_id = p.usuario_id
        WHERE c.temporada_id = %s
        ORDER BY c.round ASC, u.username ASC
        """,
        conn,
        params=(temporada_id,),
    )
    conn.close()
    return df

# =========================
# RESULTADOS
# =========================
def borrar_resultados_carrera(carrera_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        DELETE FROM resultados
        WHERE carrera_id = %s
    """, (carrera_id,))
    conn.commit()
    conn.close()

def guardar_resultado(carrera_id, piloto_id, posicion):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO resultados (carrera_id, piloto_id, posicion)
        VALUES (%s, %s, %s)
    """, (carrera_id, piloto_id, posicion))
    conn.commit()
    conn.close()

def obtener_resultados_carrera(carrera_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""



































                        SELECT r.piloto_id, r.posicion, p.codigo, p.nombre
        FROM resultados r
        JOIN pilotos p ON p.id = r.piloto_id
        WHERE r.carrera_id = %s
        ORDER BY r.posicion
    """, (carrera_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def recalcular_puntos_carrera(carrera_id):
    """Recalcula y guarda los puntos de una carrera en base a picks y resultados.

    Regla actual (juego 5º lugar):
    - Se toma la posición real del piloto pickeado.
    - Se pasan esos datos a rules.calcular_puntos(posicion_real).
    - Si no hay resultado para ese piloto, otorga 0 puntos.
    """

    # Obtener todos los picks de la carrera con su posición real (si existe)
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT p.usuario_id, r.posicion
        FROM picks p
        LEFT JOIN resultados r
            ON r.carrera_id = p.carrera_id
           AND r.piloto_id = p.piloto_id
        WHERE p.carrera_id = %s
        """,
        (carrera_id,),
    )
    rows = cur.fetchall()
    conn.close()

    # Borrar puntos previos de esa carrera
    borrar_puntos_carrera(carrera_id)

    # Calcular y guardar puntos por usuario
    for row in rows:
        usuario_id = row["usuario_id"]
        posicion_real = row["posicion"]

        if posicion_real is None:
            puntos = 0
        else:
            puntos = rules.calcular_puntos(posicion_real)

        guardar_puntos(usuario_id, carrera_id, puntos)

def leaderboard_temporada(temporada_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT 
            u.username,
            p.usuario_id,
            r.posicion AS real_pos,
            5 AS pick_pos
        FROM picks p
        JOIN usuarios u ON u.id = p.usuario_id
        JOIN carreras c ON c.id = p.carrera_id
        JOIN resultados r 
            ON r.carrera_id = p.carrera_id
           AND r.piloto_id = p.piloto_id
        WHERE c.temporada_id = %s
    """, conn, params=(temporada_id,))
    conn.close()

    if df.empty:
        return df

    df["puntos"] = df.apply(
        lambda x: rules.calcular_puntos(x["pick_pos"], x["real_pos"]),
        axis=1
    )

    leaderboard = (
        df.groupby("username", as_index=False)["puntos"]
        .sum()
        .sort_values("puntos", ascending=False)
    )

    return leaderboard


# =========================
# PUNTOS / STANDINGS
# =========================
def borrar_puntos_carrera(carrera_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        DELETE FROM puntos
        WHERE carrera_id = %s
    """, (carrera_id,))
    conn.commit()
    conn.close()

def guardar_puntos(usuario_id, carrera_id, puntos):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO puntos
        (usuario_id, carrera_id, puntos)
        VALUES (%s, %s, %s)
        ON CONFLICT (usuario_id, carrera_id)
        DO UPDATE SET puntos = EXCLUDED.puntos
    """, (usuario_id, carrera_id, puntos))
    conn.commit()
    conn.close()

def leaderboard_temporada(temporada_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT u.username, SUM(pt.puntos) AS total_puntos
        FROM puntos pt
        JOIN usuarios u ON u.id = pt.usuario_id
        JOIN carreras c ON c.id = pt.carrera_id
        WHERE c.temporada_id = %s
          AND u.is_admin = 0
        GROUP BY u.id
        ORDER BY total_puntos DESC
    """, (temporada_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def progreso_pilotos_temporada(temporada_id):
    """Devuelve la progresión de puntos por carrera para cada usuario.

    Usa la tabla puntos (ya calculada por carrera) y construye un
    acumulado por usuario ordenado por round.
    """
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            u.username,
            c.round,
            c.nombre AS carrera,
            pt.puntos
                FROM puntos pt
                JOIN usuarios u ON u.id = pt.usuario_id
                JOIN carreras c ON c.id = pt.carrera_id
                WHERE c.temporada_id = %s
                    AND u.is_admin = 0
        ORDER BY c.round, u.username
        """,
        conn,
        params=(temporada_id,),
    )
    conn.close()

    if df.empty:
        return df

    df = df.sort_values(["username", "round"])
    df["puntos_acum"] = df.groupby("username")["puntos"].cumsum()
    return df


def detalle_carrera(temporada_id, carrera_id):
    """Detalle de una carrera: picks, posición real y puntos por usuario."""
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            u.username,
            pl.codigo AS piloto_codigo,
            pl.nombre AS piloto_nombre,
            r.posicion AS posicion_real,
            COALESCE(pt.puntos, 0) AS puntos
        FROM picks p
        JOIN usuarios u ON u.id = p.usuario_id AND u.is_admin = 0
        JOIN pilotos pl ON pl.id = p.piloto_id
        JOIN carreras c ON c.id = p.carrera_id
        LEFT JOIN resultados r
            ON r.carrera_id = p.carrera_id
           AND r.piloto_id = p.piloto_id
        LEFT JOIN puntos pt
            ON pt.carrera_id = p.carrera_id
           AND pt.usuario_id = p.usuario_id
        WHERE p.carrera_id = %s
          AND c.temporada_id = %s
        ORDER BY puntos DESC, u.username ASC
        """,
        conn,
        params=(carrera_id, temporada_id),
    )
    conn.close()
    return df


def listar_picks_temporada(temporada_id):
    """Devuelve todos los picks de 5° de temporada (no-admins)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    _ensure_picks_temporada_table(cur)
    df = pd.read_sql_query(
        """
        SELECT
            u.username,
            pl.codigo AS piloto_codigo,
            pl.nombre AS piloto_nombre
        FROM picks_temporada pt
        JOIN usuarios u ON u.id = pt.usuario_id AND u.is_admin = 0
        JOIN pilotos pl ON pl.id = pt.piloto_id
        WHERE pt.temporada_id = %s
        ORDER BY u.username
        """,
        conn,
        params=(temporada_id,),
    )
    conn.close()
    return df


def mejores_carreras_temporada(temporada_id, limit=10):
    """Top desempeños individuales por carrera en la temporada."""
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            u.username,
            c.round,
            c.nombre AS carrera,
            pt.puntos
        FROM puntos pt
        JOIN usuarios u ON u.id = pt.usuario_id AND u.is_admin = 0
        JOIN carreras c ON c.id = pt.carrera_id
        WHERE c.temporada_id = %s
        ORDER BY pt.puntos DESC, c.round ASC
        LIMIT %s
        """,
        conn,
        params=(temporada_id, limit),
    )
    conn.close()
    return df
