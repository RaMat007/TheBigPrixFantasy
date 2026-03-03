from datetime import datetime

import sqlite3

import crud
from db import DB_PATH, init_db


def main():
    init_db()

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Usuarios participantes (no admin)
    cur.execute(
        "SELECT id, username FROM usuarios WHERE is_admin = 0 ORDER BY id"
    )
    usuarios = cur.fetchall()
    print("USUARIOS PARTICIPANTES:", usuarios)

    # Pilotos activos
    cur.execute(
        "SELECT id, codigo FROM pilotos WHERE activo = 1 ORDER BY id"
    )
    pilotos = cur.fetchall()
    print("PILOTOS:", pilotos)

    if not usuarios or not pilotos:
        print("No hay usuarios participantes o pilotos activos.")
        con.close()
        return

    carrera_id = 2  # Segunda carrera

    # Asignar pilotos en ciclo
    idx = 0
    for uid, uname in usuarios:
        piloto_id = pilotos[idx % len(pilotos)][0]
        crud.guardar_pick(uid, carrera_id, piloto_id)
        print(f"Pick segunda carrera -> {uname}: piloto_id={piloto_id}")
        idx += 1

    con.close()
    print("Picks creados/actualizados para la segunda carrera.")


if __name__ == "__main__":
    main()
