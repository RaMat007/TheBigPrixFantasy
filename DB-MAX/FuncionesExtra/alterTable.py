import sqlite3
import shutil
from pathlib import Path

DB_PATH = Path(__file__).parent / "quiniela.db"

# --- Backup ----
backup = DB_PATH.with_name("quiniela_backup.db")
shutil.copy(DB_PATH, backup)
print("Backup creado:", backup)

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

cur.execute("""UPDATE carreras
            SET inicio = inicio || ' 12:00:00'
            WHERE LENGTH(inicio) = 10""")

con.commit()
con.close()
print("Tabla carreras actualizada correctamente.")



