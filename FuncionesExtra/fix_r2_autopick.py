"""
Script de un solo uso: arregla el auto-pick de R2.
- Elige un piloto aleatorio != PER para R2
- Guarda ese piloto en carreras.auto_piloto_id para R2
- Sobreescribe los picks de todos los usuarios de R2 EXCEPTO Emigal Racing
  (que ya eligió LEC manualmente)

Ejecutar desde la raíz del proyecto:
  python FuncionesExtra/fix_r2_autopick.py
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2.extras
from db import get_connection
from datetime import datetime

EXCLUIR_ESCUDERIA = "emigal racing"   # <-- escudería que ya eligió manualmente
ROUND_NUM = 2

def main():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 1. Obtener temporada activa
    cur.execute("SELECT id FROM temporadas WHERE activa = 1 ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        # Intentar con activa = true (boolean)
        cur.execute("SELECT id FROM temporadas WHERE activa = true ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
    if not row:
        print("❌ No hay temporada activa")
        conn.close()
        return
    temporada_id = row["id"]
    print(f"✅ Temporada activa: {temporada_id}")

    # 2. Obtener carrera R2 de esa temporada
    cur.execute(
        "SELECT id FROM carreras WHERE temporada_id = %s AND round = %s",
        (temporada_id, ROUND_NUM),
    )
    row = cur.fetchone()
    if not row:
        print(f"❌ No se encontró R{ROUND_NUM}")
        conn.close()
        return
    carrera_id = row["id"]
    print(f"✅ Carrera R{ROUND_NUM} id={carrera_id}")

    # 3. Obtener id de PER
    cur.execute("SELECT id, codigo FROM pilotos WHERE codigo = 'PER'")
    per_row = cur.fetchone()
    per_id = per_row["id"] if per_row else None
    print(f"✅ PER id={per_id}")

    # 4. Elegir piloto aleatorio != PER
    cur.execute("SELECT id, codigo FROM pilotos ORDER BY id")
    todos = [r for r in cur.fetchall()]
    disponibles = [p for p in todos if p["id"] != per_id]
    elegido = random.choice(disponibles)
    print(f"✅ Piloto elegido para auto-pick R{ROUND_NUM}: {elegido['codigo']} (id={elegido['id']})")

    # 5. Guardar auto_piloto_id en la carrera
    cur.execute(
        "UPDATE carreras SET auto_piloto_id = %s WHERE id = %s",
        (elegido["id"], carrera_id),
    )
    print(f"✅ auto_piloto_id actualizado en carrera R{ROUND_NUM}")

    # 6. Obtener usuarios a reasignar (todos excepto la escudería excluida)
    cur.execute(
        """
        SELECT u.id, u.username, u.escuderia
        FROM usuarios u
        WHERE u.is_admin = 0
          AND LOWER(COALESCE(u.escuderia, u.username)) != LOWER(%s)
        ORDER BY u.id
        """,
        (EXCLUIR_ESCUDERIA,),
    )
    usuarios = cur.fetchall()
    print(f"✅ Usuarios a reasignar: {[u['escuderia'] or u['username'] for u in usuarios]}")

    # 7. Sobrescribir pick de esos usuarios en R2
    now = datetime.now().isoformat()
    for u in usuarios:
        cur.execute(
            """
            INSERT INTO picks (usuario_id, carrera_id, piloto_id, timestamp)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (usuario_id, carrera_id) DO UPDATE
                SET piloto_id = EXCLUDED.piloto_id,
                    timestamp = EXCLUDED.timestamp
            """,
            (u["id"], carrera_id, elegido["id"], now),
        )
        print(f"  → {u['escuderia'] or u['username']}: pick = {elegido['codigo']}")

    conn.commit()
    conn.close()
    print(f"\n🏁 Listo. R{ROUND_NUM} auto-pick = {elegido['codigo']}, Emigal Racing conserva LEC.")

if __name__ == "__main__":
    main()
