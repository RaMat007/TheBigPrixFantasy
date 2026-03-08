"""
fix_r1_r2_autopick.py
- R1: limpia auto_piloto_id (lo pone NULL → sin resaltado)
- R2: elige un piloto nuevo que nadie haya elegido manualmente en R2,
       excluye también pilotos ya usados en otras carreras de la temp.
       Luego reasigna los picks auto-asignados (todos los que no sean
       el pick manual de Emigal Racing: LEC) al nuevo piloto.
"""

import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import psycopg2
import psycopg2.extras
from db import get_connection

TEMPORADA_NUM = 1  # temporada activa
R1_ROUND = 1
R2_ROUND = 2

conn = get_connection()
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ── Obtener temporada activa ──────────────────────────────────────────────────
cur.execute("SELECT id FROM temporadas WHERE activa = 1 LIMIT 1")
temp = cur.fetchone()
if not temp:
    print("❌ No hay temporada activa.")
    conn.close()
    sys.exit(1)
temporada_id = temp["id"]
print(f"✅ Temporada activa: {temporada_id}")

# ── Obtener IDs de R1 y R2 ────────────────────────────────────────────────────
cur.execute(
    "SELECT id, round FROM carreras WHERE temporada_id = %s AND round IN (%s, %s)",
    (temporada_id, R1_ROUND, R2_ROUND),
)
carreras_map = {r["round"]: r["id"] for r in cur.fetchall()}
r1_id = carreras_map.get(R1_ROUND)
r2_id = carreras_map.get(R2_ROUND)

if not r1_id:
    print(f"❌ No se encontró carrera R{R1_ROUND}")
    conn.close()
    sys.exit(1)
if not r2_id:
    print(f"❌ No se encontró carrera R{R2_ROUND}")
    conn.close()
    sys.exit(1)

print(f"✅ R1 id={r1_id}, R2 id={r2_id}")

# ═══════════════════════════════════════════════════════════════════════════════
# 1. LIMPIAR R1 → auto_piloto_id = NULL
# ═══════════════════════════════════════════════════════════════════════════════
cur.execute("UPDATE carreras SET auto_piloto_id = NULL WHERE id = %s", (r1_id,))
print(f"✅ R1 auto_piloto_id → NULL (sin alerta)")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. ELEGIR NUEVO PILOTO PARA R2
#    Excluir:
#      a) pilotos ya usados como auto_piloto_id en otras carreras (R1=NULL ahora, OK)
#      b) pilotos ya elegidos manualmente en R2 (= LEC por Emigal Racing)
# ═══════════════════════════════════════════════════════════════════════════════
# a) Pilotos ya usados en otras carreras de la temporada (sin R2)
cur.execute(
    "SELECT auto_piloto_id FROM carreras WHERE temporada_id = %s AND id != %s AND auto_piloto_id IS NOT NULL",
    (temporada_id, r2_id),
)
usados_otras = {r["auto_piloto_id"] for r in cur.fetchall()}

# b) Todos los picks actuales en R2 (incluyendo el de Emigal que eligió manualmente)
#    Necesitamos saber cuál es el pick "manual" (anterior al auto-assign).
#    Emigal Racing fue el único que eligió; los 12 reasignados también tienen LEC ahora.
#    Para saber el piloto del pick manual, buscamos el escudería "Emigal Racing".
cur.execute(
    """
    SELECT u.nombre, p.piloto_id, pl.codigo
    FROM picks p
    JOIN usuarios u ON u.id = p.usuario_id
    JOIN pilotos pl ON pl.id = p.piloto_id
    WHERE p.carrera_id = %s
    ORDER BY u.nombre
    """,
    (r2_id,),
)
picks_r2 = cur.fetchall()
print(f"\nPicks actuales en R2:")
for pk in picks_r2:
    print(f"  {pk['nombre']}: {pk['codigo']}")

# Emigal Racing es el pick manual; todos los demás son auto-asignados (LEC ahora)
# Los picks manuales son los que NO queremos sobreescribir.
# El piloto a excluir del auto-pick es el de Emigal (LEC).
cur.execute(
    """
    SELECT p.piloto_id, pl.codigo
    FROM picks p
    JOIN usuarios u ON u.id = p.usuario_id
    JOIN pilotos pl ON pl.id = p.piloto_id
    WHERE p.carrera_id = %s AND LOWER(u.nombre) LIKE '%%emigal%%'
    """,
    (r2_id,),
)
emigal_pick = cur.fetchone()
manual_picks_ids = set()
if emigal_pick:
    manual_picks_ids.add(emigal_pick["piloto_id"])
    print(f"\n✅ Emigal Racing tiene pick manual: {emigal_pick['codigo']} (id={emigal_pick['piloto_id']})")

excluidos = usados_otras | manual_picks_ids

# Todos los pilotos disponibles
cur.execute("SELECT id, codigo FROM pilotos ORDER BY id")
todos = cur.fetchall()
disponibles = [p for p in todos if p["id"] not in excluidos]
if not disponibles:
    disponibles = [p for p in todos if p["id"] not in usados_otras]

random.seed(42)  # reproducible
nuevo_piloto = random.choice(disponibles)
print(f"\n✅ Nuevo auto-pick para R2: {nuevo_piloto['codigo']} (id={nuevo_piloto['id']})")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. GUARDAR auto_piloto_id en R2
# ═══════════════════════════════════════════════════════════════════════════════
cur.execute(
    "UPDATE carreras SET auto_piloto_id = %s WHERE id = %s",
    (nuevo_piloto["id"], r2_id),
)
print(f"✅ carreras.auto_piloto_id actualizado para R2 → {nuevo_piloto['codigo']}")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. REASIGNAR picks en R2 (todos excepto Emigal Racing) al nuevo piloto
# ═══════════════════════════════════════════════════════════════════════════════
cur.execute(
    """
    SELECT u.id, u.nombre
    FROM usuarios u
    WHERE u.is_admin = 0
      AND u.id NOT IN (
          SELECT u2.id FROM usuarios u2 WHERE LOWER(u2.nombre) LIKE '%%emigal%%'
      )
    """,
)
todos_usuarios = cur.fetchall()
reasignados = []
for u in todos_usuarios:
    cur.execute(
        "SELECT id FROM picks WHERE usuario_id = %s AND carrera_id = %s",
        (u["id"], r2_id),
    )
    existing = cur.fetchone()
    if existing:
        cur.execute(
            "UPDATE picks SET piloto_id = %s WHERE id = %s",
            (nuevo_piloto["id"], existing["id"]),
        )
        reasignados.append(u["nombre"])

print(f"\n✅ Teams reasignados a {nuevo_piloto['codigo']} ({len(reasignados)}):")
for n in reasignados:
    print(f"  → {n}")

conn.commit()
conn.close()
print(f"\n🏁 Listo. R1 sin auto-pick. R2 auto-pick = {nuevo_piloto['codigo']}. Emigal Racing conserva su pick.")
