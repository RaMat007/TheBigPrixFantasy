from db import get_connection

# =========================
# CONFIG
# =========================
CARRERA_ID = 1   # <-- AJUSTA ESTO

# (codigo_piloto, posicion)
resultados = [
    ("VER", 1),
    ("PER", 2),
    ("NOR", 3),
    ("PIA", 4),
    ("LEC", 5),
    ("SAI", 6),
    ("RUS", 7),
    ("HAM", 8),
    ("BOT", 9),
    ("ALO", 10),
    ("VET", 11),
    ("OCO", 12),
    ("GAS", 13),
    ("TSU", 14),
    ("MAG", 15),
    ("ZHO", 16),
    ("LAT", 17),
    ("RIC", 18),
    ("STR", 19),
    ("MSC", 20),
]

# =========================
# LOGICA
# =========================
conn = get_connection()
cur = conn.cursor()

# Borrar resultados previos
cur.execute(
    "DELETE FROM resultados WHERE carrera_id = ?",
    (CARRERA_ID,)
)

for codigo, posicion in resultados:
    # Obtener piloto_id desde codigo
    cur.execute(
        "SELECT id FROM pilotos WHERE codigo = ? AND activo = 1",
        (codigo,)
    )
    row = cur.fetchone()

    if not row:
        raise Exception(f"❌ Piloto con código '{codigo}' no existe")

    piloto_id = row["id"]

    # Insertar resultado
    cur.execute("""
        INSERT INTO resultados (carrera_id, piloto_id, posicion)
        VALUES (?, ?, ?)
    """, (CARRERA_ID, piloto_id, posicion))

conn.commit()
conn.close()

print("✅ Resultados cargados correctamente")
