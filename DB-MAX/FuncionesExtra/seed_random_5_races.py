from datetime import datetime
import random
import sqlite3

from db import DB_PATH, init_db
import crud


def main():
    # Opcional: fijar semilla para reproducibilidad
    random.seed(42)

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
    print("PILOTOS ACTIVOS:", pilotos)

    if not usuarios or not pilotos:
        print("No hay usuarios participantes o pilotos activos. Abortando.")
        con.close()
        return

    piloto_ids = [p[0] for p in pilotos]

    # Primeras 5 carreras por round
    cur.execute(
        "SELECT id, round, nombre FROM carreras WHERE round BETWEEN 1 AND 5 ORDER BY round"
    )
    carreras = cur.fetchall()
    print("CARRERAS (1-5):", carreras)

    if not carreras:
        print("No hay carreras con round 1-5. Abortando.")
        con.close()
        return

    for carrera_id, round_num, nombre in carreras:
        print(f"\n=== Carrera {round_num} - {nombre} (id={carrera_id}) ===")

        # Limpiar datos previos de esa carrera
        cur.execute("DELETE FROM picks WHERE carrera_id = ?", (carrera_id,))
        cur.execute("DELETE FROM resultados WHERE carrera_id = ?", (carrera_id,))
        cur.execute("DELETE FROM puntos WHERE carrera_id = ?", (carrera_id,))

        # Picks aleatorios por usuario
        for uid, uname in usuarios:
            piloto_id = random.choice(piloto_ids)
            cur.execute(
                "INSERT OR REPLACE INTO picks (usuario_id, carrera_id, piloto_id, timestamp) VALUES (?,?,?,?)",
                (uid, carrera_id, piloto_id, datetime.now().isoformat()),
            )
            print(f"Pick -> {uname}: piloto_id={piloto_id}")

        # Resultados aleatorios: permutación completa de pilotos activos
        orden = random.sample(piloto_ids, len(piloto_ids))
        for pos, pid in enumerate(orden, start=1):
            cur.execute(
                "INSERT INTO resultados (carrera_id, piloto_id, posicion) VALUES (?,?,?)",
                (carrera_id, pid, pos),
            )
        print("Resultados aleatorios generados.")

        # Confirmar antes de recalcular puntos
        con.commit()

        # Recalcular puntos para esta carrera
        crud.recalcular_puntos_carrera(carrera_id)
        print("Puntos recalculados.")

    con.close()
    print("\nDatos aleatorios generados para las primeras 5 carreras.")


if __name__ == "__main__":
    main()
