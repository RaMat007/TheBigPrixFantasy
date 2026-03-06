# Migra temporadas, carreras y pilotos desde quiniela.db (SQLite) a PostgreSQL.
# NO migra usuarios, picks, resultados ni puntos (estan vacios o se generan en produccion).
# Uso: .venv/Scripts/python.exe FuncionesExtra/migrar_sqlite_a_postgres.py

import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "DB-MAX", "quiniela.db")

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres.lkenzuuuytedpqeplnac:BigPrix2026@aws-1-us-east-2.pooler.supabase.com:5432/postgres",
)

from db import get_connection, init_db

def migrar():
    print("→ Iniciando migración SQLite → PostgreSQL (solo estructura)")

    # Asegurar esquema en Postgres
    print("→ Ejecutando init_db()...")
    init_db()
    print("✓ Esquema listo")

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sc = sqlite_conn.cursor()

    pg_conn = get_connection()
    pc = pg_conn.cursor()

    # --- TEMPORADAS ---
    sc.execute("SELECT * FROM temporadas")
    rows = sc.fetchall()
    print(f"→ Migrando {len(rows)} temporadas...")
    for r in rows:
        pc.execute("""
            INSERT INTO temporadas (id, nombre, fecha_inicio, fecha_fin, activa)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                nombre=EXCLUDED.nombre,
                fecha_inicio=EXCLUDED.fecha_inicio,
                fecha_fin=EXCLUDED.fecha_fin,
                activa=EXCLUDED.activa
        """, (r["id"], r["nombre"], r["fecha_inicio"], r["fecha_fin"], r["activa"]))
    # Resetear secuencia
    pc.execute("SELECT setval('temporadas_id_seq', COALESCE((SELECT MAX(id) FROM temporadas), 1))")
    print(f"✓ {len(rows)} temporadas migradas")

    # --- CARRERAS ---
    sc.execute("SELECT * FROM carreras")
    rows = sc.fetchall()
    print(f"→ Migrando {len(rows)} carreras...")
    for r in rows:
        pc.execute("""
            INSERT INTO carreras (id, temporada_id, round, nombre, inicio, kms, vueltas, pista, hora)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                nombre=EXCLUDED.nombre, inicio=EXCLUDED.inicio,
                kms=EXCLUDED.kms, vueltas=EXCLUDED.vueltas,
                pista=EXCLUDED.pista, hora=EXCLUDED.hora
        """, (r["id"], r["temporada_id"], r["round"], r["nombre"], r["inicio"],
              dict(r).get("kms"), dict(r).get("vueltas"), dict(r).get("pista"), dict(r).get("hora")))
    pc.execute("SELECT setval('carreras_id_seq', COALESCE((SELECT MAX(id) FROM carreras), 1))")
    print(f"✓ {len(rows)} carreras migradas")

    # --- PILOTOS ---
    sc.execute("SELECT * FROM pilotos")
    rows = sc.fetchall()
    print(f"→ Migrando {len(rows)} pilotos...")
    for r in rows:
        pc.execute("""
            INSERT INTO pilotos (id, codigo, nombre, escuderia, activo)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                nombre=EXCLUDED.nombre, escuderia=EXCLUDED.escuderia, activo=EXCLUDED.activo
        """, (r["id"], r["codigo"], r["nombre"], r["escuderia"], r["activo"]))
    pc.execute("SELECT setval('pilotos_id_seq', COALESCE((SELECT MAX(id) FROM pilotos), 1))")
    print(f"✓ {len(rows)} pilotos migrados")

    pg_conn.commit()
    pg_conn.close()
    sqlite_conn.close()
    print("\n✅ Migración completada: temporadas, carreras y pilotos importados.")

if __name__ == "__main__":
    migrar()
