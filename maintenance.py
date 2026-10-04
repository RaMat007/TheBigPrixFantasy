"""Worker de GitHub Actions: no necesita que Streamlit esté abierto."""
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
import psycopg2
from db import init_db
from operations import cursor, ensure_schema, maintain, sync_results, create_backup


def connect():
    return psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require', connect_timeout=10)


def main():
    if not os.environ.get('DATABASE_URL'):
        raise SystemExit('Configura el secret DATABASE_URL en GitHub Actions para activar el worker.')
    if not os.environ.get('BACKUP_ENCRYPTION_KEY'):
        raise SystemExit('Configura BACKUP_ENCRYPTION_KEY para proteger la copia externa de respaldo.')
    # Inicializa tablas y trazabilidad también si el worker corre antes del redeploy de Streamlit.
    init_db()
    conn = connect()
    try:
        ensure_schema(conn)
        create_backup(conn, 'Diario', daily=True)
        cur = cursor(conn)
        cur.execute('SELECT id FROM temporadas WHERE activa=1 ORDER BY id')
        seasons = cur.fetchall()
        messages = [maintain(conn, row['id']) for row in seasons]
        cur.execute("SELECT id,payload FROM app_backups WHERE reason='Diario' AND (created_at AT TIME ZONE 'UTC')::date=(now() AT TIME ZONE 'UTC')::date ORDER BY id DESC LIMIT 1")
        backup = cur.fetchone()
        cur.execute("SELECT value FROM app_settings WHERE key='external_backup_day'")
        exported = cur.fetchone()
        day = datetime.now(timezone.utc).date().isoformat()
        needs_export = not exported or exported['value'] != day
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if backup and needs_export:
        target = pathlib.Path('backup_output')
        target.mkdir(exist_ok=True)
        plain = target / 'snapshot.json'
        encrypted = target / ('bigprix_'+datetime.now(timezone.utc).strftime('%Y%m%d')+'.json.enc')
        plain.write_text(json.dumps(backup['payload'],ensure_ascii=False,default=str))
        plain.chmod(0o600)
        try:
            subprocess.run(['openssl','enc','-aes-256-cbc','-salt','-pbkdf2','-iter','200000','-in',str(plain),'-out',str(encrypted),'-pass','env:BACKUP_ENCRYPTION_KEY'],check=True,capture_output=True)
            (target/'exported_day.txt').write_text(day)
        finally:
            plain.unlink(missing_ok=True)
    reports = sync_results(connect)
    conn = connect()
    try:
        cursor(conn).execute("INSERT INTO app_settings(key,value) VALUES('worker_last_run',%s::jsonb) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (json.dumps(datetime.now(timezone.utc).isoformat()),))
        conn.commit()
    finally:
        conn.close()
    print(json.dumps({'autopicks':messages,'resultados':reports},ensure_ascii=False))


def mark_exported():
    marker = pathlib.Path('backup_output/exported_day.txt')
    if not marker.exists():
        return
    conn = connect()
    try:
        cursor(conn).execute("INSERT INTO app_settings(key,value) VALUES('external_backup_day',%s::jsonb) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (json.dumps(marker.read_text().strip()),))
        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    if '--mark-exported' in sys.argv:
        mark_exported()
    else:
        main()
