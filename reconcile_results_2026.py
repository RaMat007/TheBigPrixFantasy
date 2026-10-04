"""Reconcilia clasificaciones oficiales, sin crear ni mover picks históricos."""
import json
from pathlib import Path
from datetime import datetime, timezone
from calendar_2026 import identify_race, OFFICIAL_TOP5
from rules import calcular_puntos

def load_results():
    data=json.loads(Path(__file__).with_name('official_results_2026.json').read_text())['races']
    if set(data)!=set(OFFICIAL_TOP5):
        raise ValueError('El conjunto de resultados verificados está incompleto.')
    for key, rows in data.items():
        positions=[r['posicion'] for r in rows if r['posicion'] is not None]
        if len(rows)!=22 or len({r['codigo'] for r in rows})!=22:
            raise ValueError(f'Parrilla incompleta o duplicada: {key}')
        if sorted(positions)!=list(range(1,len(positions)+1)):
            raise ValueError(f'Clasificación incompleta: {key}')
        top=tuple(r['codigo'] for r in sorted((r for r in rows if r['posicion']), key=lambda r:r['posicion'])[:5])
        if top!=OFFICIAL_TOP5[key]:
            raise ValueError(f'Top 5 incompatible: {key}')
    return data

def reconcile(conn, temporada_id):
    """Una transacción, respaldo privado y recalculo sobre elecciones existentes."""
    import psycopg2.extras
    data=load_results()
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)',(2026,int(temporada_id)))
    cur.execute('SELECT * FROM carreras WHERE temporada_id=%s ORDER BY round FOR UPDATE',(temporada_id,))
    races=cur.fetchall()
    selected={identify_race(r)['key']:r for r in races if not r.get('cancelada') and identify_race(r)['key'] in data}
    if set(selected)!=set(data):
        raise ValueError('Faltan carreras de 2026; no se cambian los resultados.')
    now=datetime.now(timezone.utc)
    if any(datetime.fromisoformat(r['inicio']).replace(tzinfo=timezone.utc)>=now for r in selected.values()):
        raise ValueError('El conjunto incluye carreras futuras.')
    cur.execute('SELECT id,codigo FROM pilotos')
    drivers={r['codigo'].strip().upper():r['id'] for r in cur.fetchall()}
    missing=sorted({r['codigo'] for rows in data.values() for r in rows if r['posicion'] is not None}-set(drivers))
    if missing:
        raise ValueError('Faltan pilotos en el catálogo: '+', '.join(missing)+'. Actualiza la alineación antes de reconciliar.')
    ids=[r['id'] for r in selected.values()]
    backup={}
    for table in ('picks','resultados','puntos'):
        cur.execute(f'SELECT * FROM {table} WHERE carrera_id=ANY(%s) ORDER BY id FOR UPDATE',(ids,))
        backup[table]=cur.fetchall()
    cur.execute('''CREATE TABLE IF NOT EXISTS reconciliacion_resultados_backups (
        id BIGSERIAL PRIMARY KEY, temporada_id INTEGER NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), payload JSONB NOT NULL)''')
    cur.execute('ALTER TABLE reconciliacion_resultados_backups ENABLE ROW LEVEL SECURITY')
    cur.execute('INSERT INTO reconciliacion_resultados_backups (temporada_id,payload) VALUES (%s,%s::jsonb) RETURNING id',
        (temporada_id,json.dumps(backup,default=str)))
    backup_id=cur.fetchone()['id']
    report=[]
    for key, race in selected.items():
        rid=race['id']
        # NC/DNS/DSQ no tienen posición clasificada y obtienen cero en este juego.
        classified=[(drivers[r['codigo']],r['posicion']) for r in data[key] if r['posicion'] is not None]
        positions=dict(classified)
        picks=[p for p in backup['picks'] if p['carrera_id']==rid]
        cur.execute('DELETE FROM resultados WHERE carrera_id=%s',(rid,))
        cur.executemany('INSERT INTO resultados (carrera_id,piloto_id,posicion) VALUES (%s,%s,%s)',[(rid,pid,pos) for pid,pos in classified])
        cur.execute('DELETE FROM puntos WHERE carrera_id=%s',(rid,))
        if picks:
            cur.executemany('INSERT INTO puntos (usuario_id,carrera_id,puntos) VALUES (%s,%s,%s)',
                [(p['usuario_id'],rid,calcular_puntos(positions.get(p['piloto_id']))) for p in picks])
        report.append({'ID':rid,'Ronda':race['round'],'Carrera':race['nombre'],'Resultados':len(classified),'Picks conservados':len(picks),'Respaldo':backup_id})
    cur.execute('SELECT * FROM picks WHERE carrera_id=ANY(%s) ORDER BY id',(ids,))
    if cur.fetchall()!=backup['picks']:
        raise ValueError('Los picks cambiaron durante la reconciliación; se revierte la transacción.')
    return report
