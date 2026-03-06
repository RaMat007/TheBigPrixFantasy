from datetime import datetime

import sqlite3

import crud
from db import DB_PATH, init_db


def main():
    init_db()

    # Crear usuarios de prueba
    nombres = ["test1", "test2", "test3", "test4", "test5"]
    for u in nombres:
        try:
            crud.crear_usuario(u, "test", 0)
            print(f"Usuario creado: {u}/test")
        except Exception as e:
            print(f"Usuario {u} ya existe o error: {e}")

    # Obtener ids de usuarios test
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT id, username FROM usuarios WHERE username LIKE 'test%' ORDER BY id"
    )
    usuarios = cur.fetchall()
    print("USUARIOS:", usuarios)

    # Carrera Melbourne id=1
    carrera_id = 1

    # Elegir algunos pilotos por id para variedad (1-5)
    driver_ids = [1, 2, 3, 4, 5]

    for (uid, uname), pid in zip(usuarios, driver_ids):
        cur.execute(
            "INSERT OR REPLACE INTO picks (usuario_id, carrera_id, piloto_id, timestamp) VALUES (?,?,?,?)",
            (uid, carrera_id, pid, datetime.now().isoformat()),
        )
        print(f"Pick para {uname}: piloto_id={pid} en carrera {carrera_id}")

    con.commit()
    con.close()
    print("Picks creados para Melbourne.")


if __name__ == "__main__":
    main()
