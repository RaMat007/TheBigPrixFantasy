"""
Aplica auto_asignado=1 a todos los picks VER de R2 (auto-asignados),
y restaura LEC a Emmanuel (Emigal Racing, usuario_id=16) con auto_asignado=0.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import get_connection, init_db
import psycopg2.extras

init_db()  # asegura que columna auto_asignado exista

conn = get_connection()
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("SELECT id FROM pilotos WHERE codigo = 'LEC'")
lec_id = cur.fetchone()["id"]
cur.execute("SELECT id FROM pilotos WHERE codigo = 'VER'")
ver_id = cur.fetchone()["id"]
cur.execute("""
    SELECT c.id FROM carreras c
    JOIN temporadas t ON t.id = c.temporada_id
    WHERE t.activa = 1 AND c.round = 2
""")
r2_id = cur.fetchone()["id"]
print(f"R2 id={r2_id}, LEC id={lec_id}, VER id={ver_id}")

# Todos los picks VER en R2 son auto-asignados
cur.execute(
    "UPDATE picks SET auto_asignado = 1 WHERE carrera_id = %s AND piloto_id = %s",
    (r2_id, ver_id),
)
print(f"  auto_asignado=1 en R2 (VER): {cur.rowcount} filas")

# Emmanuel (id=16) eligio LEC manualmente -> restaurar y marcar manual
cur.execute(
    "UPDATE picks SET piloto_id = %s, auto_asignado = 0 WHERE usuario_id = 16 AND carrera_id = %s",
    (lec_id, r2_id),
)
print(f"  Emmanuel -> LEC, auto_asignado=0: {cur.rowcount} filas")

conn.commit()
conn.close()
print("Listo.")
