import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "quiniela.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(carreras);")

print("PRAGMA table_info(carreras):")
for row in cur.fetchall():
    print(row)

conn.close()
