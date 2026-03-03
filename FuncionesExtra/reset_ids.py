import shutil
import sqlite3
from pathlib import Path

from db import DB_PATH


def backup_db() -> Path:
    backup_path = DB_PATH.with_name(DB_PATH.stem + "_backup_ids.db")
    shutil.copy(DB_PATH, backup_path)
    print(f"Backup creado en: {backup_path}")
    return backup_path


def renumerar_ids():
    backup_db()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # Desactivar FKs para poder manipular tablas y claves
        cur.execute("PRAGMA foreign_keys = OFF;")
        conn.execute("BEGIN TRANSACTION;")

        # ==========================
        # PILOTOS
        # ==========================
        cur.execute("SELECT id, codigo, nombre, escuderia, activo FROM pilotos ORDER BY id")
        pilotos_rows = cur.fetchall()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pilotos_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                escuderia TEXT,
                activo INTEGER DEFAULT 1
            )
            """
        )

        mapa_pilotos = {}
        nuevo_id = 1
        for row in pilotos_rows:
            # Saltar filas "basura" sin código o nombre
            if not row["codigo"] or not row["nombre"]:
                continue

            old_id = row["id"]
            cur.execute(
                "INSERT INTO pilotos_new (id, codigo, nombre, escuderia, activo) VALUES (?, ?, ?, ?, ?)",
                (nuevo_id, row["codigo"], row["nombre"], row["escuderia"], row["activo"]),
            )
            mapa_pilotos[old_id] = nuevo_id
            nuevo_id += 1

        # Reemplazar tabla pilotos
        cur.execute("DROP TABLE pilotos")
        cur.execute("ALTER TABLE pilotos_new RENAME TO pilotos")

        # ==========================
        # CARRERAS
        # ==========================
        cur.execute("SELECT id, temporada_id, round, nombre, inicio FROM carreras ORDER BY id")
        carreras_rows = cur.fetchall()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS carreras_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temporada_id INTEGER NOT NULL,
                round INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                inicio DATETIME NOT NULL,
                UNIQUE(temporada_id, round)
            )
            """
        )

        mapa_carreras = {}
        nuevo_id = 1
        for row in carreras_rows:
            old_id = row["id"]
            cur.execute(
                "INSERT INTO carreras_new (id, temporada_id, round, nombre, inicio) VALUES (?, ?, ?, ?, ?)",
                (nuevo_id, row["temporada_id"], row["round"], row["nombre"], row["inicio"]),
            )
            mapa_carreras[old_id] = nuevo_id
            nuevo_id += 1

        # Reemplazar tabla carreras
        cur.execute("DROP TABLE carreras")
        cur.execute("ALTER TABLE carreras_new RENAME TO carreras")

        # ==========================
        # ACTUALIZAR FKs EN PICKS
        # ==========================
        cur.execute("SELECT id, carrera_id, piloto_id FROM picks")
        for row in cur.fetchall():
            old_carrera = row["carrera_id"]
            old_piloto = row["piloto_id"]
            new_carrera = mapa_carreras.get(old_carrera)
            new_piloto = mapa_pilotos.get(old_piloto)
            if new_carrera is None or new_piloto is None:
                # Si el piloto/carrera ya no existe en el mapa, eliminamos el pick huérfano
                cur.execute("DELETE FROM picks WHERE id = ?", (row["id"],))
                continue
            cur.execute(
                "UPDATE picks SET carrera_id = ?, piloto_id = ? WHERE id = ?",
                (new_carrera, new_piloto, row["id"]),
            )

        # ==========================
        # ACTUALIZAR FKs EN RESULTADOS
        # ==========================
        cur.execute("SELECT id, carrera_id, piloto_id FROM resultados")
        for row in cur.fetchall():
            old_carrera = row["carrera_id"]
            old_piloto = row["piloto_id"]
            new_carrera = mapa_carreras.get(old_carrera)
            new_piloto = mapa_pilotos.get(old_piloto)
            if new_carrera is None or new_piloto is None:
                # Eliminar resultados huérfanos
                cur.execute("DELETE FROM resultados WHERE id = ?", (row["id"],))
                continue
            cur.execute(
                "UPDATE resultados SET carrera_id = ?, piloto_id = ? WHERE id = ?",
                (new_carrera, new_piloto, row["id"]),
            )

        # ==========================
        # ACTUALIZAR FKs EN PUNTOS
        # ==========================
        cur.execute("SELECT id, carrera_id FROM puntos")
        for row in cur.fetchall():
            old_carrera = row["carrera_id"]
            new_carrera = mapa_carreras.get(old_carrera)
            if new_carrera is None:
                continue
            cur.execute(
                "UPDATE puntos SET carrera_id = ? WHERE id = ?",
                (new_carrera, row["id"]),
            )

        # Resetear sqlite_sequence para que próximos inserts sigan la secuencia
        cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('pilotos', 'carreras')")

        conn.commit()
        print("IDs de pilotos y carreras renumerados correctamente.")

    except Exception as e:
        conn.rollback()
        print("ERROR, se hizo rollback:", e)
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    renumerar_ids()
