import sqlite3

from db import DB_PATH
import crud


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # IDs de admin
    cur.execute("SELECT id FROM usuarios WHERE is_admin = 1")
    admin_ids = [row[0] for row in cur.fetchall()]

    if admin_ids:
        q_marks = ",".join(["?"] * len(admin_ids))
        cur.execute(f"DELETE FROM picks WHERE usuario_id IN ({q_marks})", admin_ids)
        cur.execute(f"DELETE FROM puntos WHERE usuario_id IN ({q_marks})", admin_ids)
        print("Eliminados picks y puntos de admin:", admin_ids)

    # Asegurar pick de Speedy González en carrera 1
    cur.execute(
        "SELECT id FROM usuarios WHERE username = ? AND is_admin = 0",
        ("Speedy González",),
    )
    row = cur.fetchone()
    if not row:
        print("No se encontró usuario 'Speedy González' no-admin")
        con.commit()
        con.close()
        return

    speedy_id = row[0]

    # Usar piloto_id 1 por defecto (por simplicidad)
    piloto_id = 1

    cur.execute(
        "INSERT OR REPLACE INTO picks (usuario_id, carrera_id, piloto_id, timestamp) VALUES (?,?,?,datetime('now'))",
        (speedy_id, 1, piloto_id),
    )
    print(f"Pick creado/actualizado para Speedy en carrera 1: piloto_id={piloto_id}")

    con.commit()
    con.close()

    # Recalcular puntos de la carrera 1
    crud.recalcular_puntos_carrera(1)
    print("Puntos recalculados para carrera 1.")


if __name__ == "__main__":
    main()
