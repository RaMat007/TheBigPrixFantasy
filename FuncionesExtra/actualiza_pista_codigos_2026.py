# Script para actualizar la columna 'pista' en la tabla carreras
# usando el round y el código geojson personalizado para 2026

import sqlite3
from pathlib import Path

# Mapea round a tu código geojson personalizado (ajusta aquí tus códigos)
ROUND_TO_CODE = {
    1: "QAT",   # Ejemplo: Qatar
    2: "SAU",   # Arabia Saudita
    3: "AUS",   # Australia
    4: "JPN",   # Japón
    5: "CHN",   # China
    6: "MIA",   # Miami
    7: "ITA",   # Imola
    8: "MON",   # Monaco
    9: "ESP",   # España
    10: "CAN",  # Canadá
    11: "AUT",  # Austria
    12: "GBR",  # Gran Bretaña
    13: "HUN",  # Hungría
    14: "BEL",  # Bélgica
    15: "NED",  # Países Bajos
    16: "ITA2", # Monza
    17: "AZE",  # Azerbaiyán
    18: "SIN",  # Singapur
    19: "USA",  # Austin
    20: "MEX",  # México
    21: "BRA",  # Brasil
    22: "LVG",  # Las Vegas
    23: "ABU"   # Abu Dhabi
}

DB_PATH = Path(__file__).parent / "quiniela.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

for rnd, code in ROUND_TO_CODE.items():
    cur.execute("""
        UPDATE carreras
        SET pista = ?
        WHERE round = ?
    """, (code, rnd))
    print(f"Actualizado round {rnd} -> pista '{code}'")

conn.commit()
conn.close()
print("Sincronización de columna 'pista' terminada.")
