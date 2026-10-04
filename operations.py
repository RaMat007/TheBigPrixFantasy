"""Mantenimiento independiente de Streamlit, respaldos y trazabilidad."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone, timedelta
import psycopg2.extras
from rules import calcular_puntos


def utc(value):
    value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def context(conn, actor, note=''):
    cur = cursor(conn)
    cur.execute("SELECT set_config('app.actor', %s, true), set_config('app.note', %s, true)", (str(actor), note))


def ensure_schema(conn):
    cur = cursor(conn)
    cur.execute('SELECT pg_advisory_xact_lock(2026, 70001)')
    cur.execute('CREATE TABLE IF NOT EXISTS app_migrations (version TEXT PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now())')
    cur.execute("SELECT version FROM app_migrations WHERE version='operations_v1'")
    if cur.fetchone():
        return
    cur.execute('''
      CREATE TABLE IF NOT EXISTS app_backups (
        id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        reason TEXT NOT NULL, actor TEXT NOT NULL, payload JSONB NOT NULL);
      CREATE TABLE IF NOT EXISTS app_events (
        id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        actor TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', table_name TEXT NOT NULL,
        action TEXT NOT NULL, record_id INTEGER, old_data JSONB, new_data JSONB);
      CREATE TABLE IF NOT EXISTS pick_reviews (
        pick_id INTEGER PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('Permitido','Revisar')),
        note TEXT NOT NULL, actor TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
      CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value JSONB NOT NULL);
      CREATE TABLE IF NOT EXISTS result_sync (
        carrera_id INTEGER PRIMARY KEY, checked_at TIMESTAMPTZ, imported_at TIMESTAMPTZ,
        status TEXT NOT NULL DEFAULT 'Pendiente', message TEXT NOT NULL DEFAULT '',
        source TEXT, session_key BIGINT, fingerprint TEXT, proposal JSONB);
      ALTER TABLE app_backups ENABLE ROW LEVEL SECURITY;
      ALTER TABLE app_events ENABLE ROW LEVEL SECURITY;
      ALTER TABLE pick_reviews ENABLE ROW LEVEL SECURITY;
      ALTER TABLE app_settings ENABLE ROW LEVEL SECURITY;
      ALTER TABLE result_sync ENABLE ROW LEVEL SECURITY;
      ALTER TABLE app_migrations ENABLE ROW LEVEL SECURITY;
      INSERT INTO app_settings VALUES ('auto_results','true'::jsonb) ON CONFLICT DO NOTHING;
    ''')
    cur.execute('''
      CREATE OR REPLACE FUNCTION record_app_event() RETURNS trigger AS $$
      DECLARE before_row JSONB; after_row JSONB;
      BEGIN
        IF TG_OP <> 'INSERT' THEN before_row := to_jsonb(OLD); END IF;
        IF TG_OP <> 'DELETE' THEN after_row := to_jsonb(NEW); END IF;
        IF TG_OP='UPDATE' AND before_row=after_row THEN RETURN NEW; END IF;
        INSERT INTO app_events(actor,note,table_name,action,record_id,old_data,new_data)
        VALUES (COALESCE(NULLIF(current_setting('app.actor',true),''),session_user),
          COALESCE(current_setting('app.note',true),''),TG_TABLE_NAME,TG_OP,
          COALESCE((after_row->>'id')::integer,(before_row->>'id')::integer),before_row,after_row);
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END; $$ LANGUAGE plpgsql;
      CREATE OR REPLACE FUNCTION guard_pick_deadline() RETURNS trigger AS $$
      DECLARE race_start TIMESTAMPTZ; cancelled BOOLEAN;
      BEGIN
        IF COALESCE(current_setting('app.pick_override',true),'') <> '' THEN RETURN NEW; END IF;
        SELECT (inicio::timestamp AT TIME ZONE 'UTC'),cancelada INTO race_start,cancelled
          FROM carreras WHERE id=NEW.carrera_id FOR SHARE;
        IF race_start IS NULL OR cancelled THEN RAISE EXCEPTION 'GP inexistente o cancelado'; END IF;
        IF clock_timestamp() >= race_start - INTERVAL '15 minutes' THEN
          RAISE EXCEPTION 'El plazo para guardar picks ya cerró (15 minutos antes del GP)';
        END IF;
        RETURN NEW;
      END; $$ LANGUAGE plpgsql;
      DROP TRIGGER IF EXISTS guard_pick_deadline ON picks;
      CREATE TRIGGER guard_pick_deadline BEFORE INSERT OR UPDATE ON picks
        FOR EACH ROW EXECUTE FUNCTION guard_pick_deadline();
    ''')
    for table in ('picks', 'carreras', 'resultados', 'puntos', 'pick_reviews'):
        cur.execute(f'DROP TRIGGER IF EXISTS app_history ON {table}')
        cur.execute(f'CREATE TRIGGER app_history AFTER INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION record_app_event()')
    cur.execute("""INSERT INTO app_events(actor,note,table_name,action,record_id,new_data)
        SELECT 'Migración','Estado encontrado al activar el historial; no es la fecha original de elección',
               'picks','BASELINE',p.id,to_jsonb(p) FROM picks p""")
    # Excepción concreta revisada por el administrador. No permite nuevos picks tardíos.
    cur.execute("""INSERT INTO pick_reviews(pick_id,status,note,actor)
        SELECT p.id,'Permitido','Revisión posterior: permitido por el administrador pese al cierre corregido de Miami',
               'Administrador' FROM picks p JOIN carreras c ON c.id=p.carrera_id
        WHERE p.id=128 AND c.calendario_key='miami'
          AND p.timestamp='2026-05-03T17:00:46.261154'
        ON CONFLICT DO NOTHING""")
    cur.execute("INSERT INTO app_migrations(version) VALUES ('operations_v1')")
    create_backup(conn, 'Estado inicial al activar respaldos e historial', 'Migración')


def create_backup(conn, reason, actor='Sistema', daily=False):
    cur = cursor(conn)
    cur.execute('SELECT pg_advisory_xact_lock(2026, 70002)')
    if daily:
        cur.execute("SELECT id FROM app_backups WHERE reason='Diario' AND (created_at AT TIME ZONE 'UTC')::date=(now() AT TIME ZONE 'UTC')::date ORDER BY id LIMIT 1")
        found = cur.fetchone()
        if found:
            return found['id'], False
    # Una única sentencia SELECT toma una instantánea consistente de todas las tablas.
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    excluded = {'app_backups', 'reconciliacion_resultados_backups', 'app_migrations'}
    tables = [r['tablename'] for r in cur.fetchall() if r['tablename'] not in excluded]
    parts = []
    for name in tables:
        safe_name = '"' + name.replace('"', '""') + '"'
        literal = "'" + name.replace("'", "''") + "'"
        parts.append(f"{literal}, (SELECT COALESCE(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM public.{safe_name} t)")
    cur.execute('SELECT jsonb_build_object(' + ','.join(parts) + ') AS data')
    payload = cur.fetchone()['data']
    cur.execute('INSERT INTO app_backups(reason,actor,payload) VALUES(%s,%s,%s::jsonb) RETURNING id', (reason, str(actor), json.dumps(payload, default=str)))
    bid = cur.fetchone()['id']
    # Retención de diarios; los respaldos previos a modificaciones se conservan.
    cur.execute("DELETE FROM app_backups WHERE reason='Diario' AND created_at < now()-interval '60 days'")
    return bid, True


def ensure_autopicks(conn, season_id, now=None):
    """Prepara antes del cierre el GP siguiente, sin inventar picks históricos."""
    now = now or datetime.now(timezone.utc)
    cur = cursor(conn)
    cur.execute('SELECT pg_advisory_xact_lock(2026,70002)')
    cur.execute('SELECT pg_advisory_xact_lock(2026,%s)', (int(season_id),))
    cur.execute("""SELECT * FROM carreras WHERE temporada_id=%s AND NOT cancelada
        AND inicio::timestamp AT TIME ZONE 'UTC' > %s ORDER BY inicio::timestamp LIMIT 1 FOR UPDATE""", (season_id, now))
    race = cur.fetchone()
    if not race:
        return 'Sin próximos GP'
    if now >= utc(race['inicio']) - timedelta(minutes=15):
        return f"R{race['round']}: plazo cerrado; no se generan elecciones retroactivas"
    context(conn, 'Sistema', 'Respaldo automático preparado antes del cierre')
    new_default = not race['auto_piloto_id']
    if new_default:
        cur.execute("SELECT id FROM pilotos WHERE activo=1 ORDER BY id")
        drivers = [r['id'] for r in cur.fetchall()]
        if not drivers:
            return 'No hay pilotos activos para respaldos'
        cur.execute('SELECT auto_piloto_id FROM carreras WHERE temporada_id=%s AND NOT cancelada AND inicio::timestamp < %s::timestamp AND auto_piloto_id IS NOT NULL', (season_id, race['inicio']))
        used = {r['auto_piloto_id'] for r in cur.fetchall()}
        available = [d for d in drivers if d not in used] or drivers
        seed = int(hashlib.sha256(f"{season_id}:{race['id']}".encode()).hexdigest(), 16)
        race['auto_piloto_id'] = available[seed % len(available)]
        create_backup(conn, f"Antes de preparar autopicks del GP {race['id']}")
        cur.execute('UPDATE carreras SET auto_piloto_id=%s WHERE id=%s', (race['auto_piloto_id'], race['id']))
    if not new_default:
        cur.execute('SELECT id FROM usuarios u WHERE is_admin=0 AND NOT EXISTS(SELECT 1 FROM picks p WHERE p.usuario_id=u.id AND p.carrera_id=%s) LIMIT 1', (race['id'],))
        if cur.fetchone():
            create_backup(conn, f"Antes de completar autopicks del GP {race['id']}")
    cur.execute("""INSERT INTO picks(usuario_id,carrera_id,piloto_id,timestamp,auto_asignado)
        SELECT u.id,%s,%s,%s,1 FROM usuarios u WHERE u.is_admin=0
        AND NOT EXISTS(SELECT 1 FROM picks p WHERE p.usuario_id=u.id AND p.carrera_id=%s)
        ON CONFLICT(usuario_id,carrera_id) DO NOTHING""", (race['id'], race['auto_piloto_id'], now.replace(tzinfo=None).isoformat(), race['id']))
    return f"R{race['round']}: {cur.rowcount} respaldos nuevos; elecciones existentes conservadas"


def maintain(conn, season_id):
    create_backup(conn, 'Diario', daily=True)
    return ensure_autopicks(conn, season_id)


def validate_calendar_changes(original, edited):
    if {int(r['id']) for r in original} != {int(r['id']) for r in edited} or len(original) != len(edited):
        raise ValueError('La revisión debe conservar todos los IDs de carrera, sin añadir ni eliminar filas.')
    for row in edited:
        if not str(row['nombre']).strip():
            raise ValueError('Cada GP necesita nombre.')
        row['inicio'] = utc(row['inicio']).replace(tzinfo=None).isoformat()
        row['cancelada'] = bool(row['cancelada'])
    active = sorted([r for r in edited if not r['cancelada']], key=lambda r: (r['inicio'], int(r['id'])))
    if len({r['inicio'] for r in active}) != len(active):
        raise ValueError('Dos GP activos no pueden tener el mismo inicio.')
    for i, row in enumerate(active, 1):
        row['round'] = i
    cancelled = sorted([r for r in edited if r['cancelada']], key=lambda r: int(r['id']))
    for i, row in enumerate(cancelled):
        row['round'] = -i
    return edited


def apply_calendar_review(conn, season_id, edited, actor, note):
    if not note.strip():
        raise ValueError('Indica el motivo y la fuente del cambio de calendario.')
    cur = cursor(conn)
    cur.execute('SELECT pg_advisory_xact_lock(2026,70002)')
    cur.execute('SELECT pg_advisory_xact_lock(2026,%s)', (int(season_id),))
    cur.execute('SELECT * FROM carreras WHERE temporada_id=%s ORDER BY id FOR UPDATE', (season_id,))
    original = cur.fetchall()
    edited = validate_calendar_changes(original, edited)
    old = {int(r['id']): r for r in original}
    changed = [r for r in edited if any(str(r[k]) != str(old[int(r['id'])][k]) for k in ('round','nombre','inicio','cancelada'))]
    if not changed:
        return 0
    create_backup(conn, 'Antes de revisar calendario: '+note, actor)
    context(conn, actor, note)
    offset = max(abs(int(r['round'])) for r in original) + len(original) + 100
    for i, row in enumerate(edited):
        cur.execute('UPDATE carreras SET round=%s WHERE id=%s AND temporada_id=%s', (offset+i, int(row['id']), season_id))
    for row in edited:
        cur.execute('UPDATE carreras SET round=%s,nombre=%s,inicio=%s,hora=%s,cancelada=%s WHERE id=%s AND temporada_id=%s', (row['round'], row['nombre'], row['inicio'], row['inicio'][11:16], row['cancelada'], int(row['id']), season_id))
    return len(changed)


def fingerprint(rows):
    pairs = sorted((r['codigo'], r['posicion']) for r in rows if r['posicion'] is not None)
    return hashlib.sha256(json.dumps(pairs).encode()).hexdigest()


def repair_points(conn, race_id, actor):
    cur = cursor(conn)
    cur.execute('SELECT p.usuario_id,r.posicion FROM picks p LEFT JOIN resultados r ON r.carrera_id=p.carrera_id AND r.piloto_id=p.piloto_id WHERE p.carrera_id=%s', (race_id,))
    expected = {r['usuario_id']:calcular_puntos(r['posicion']) for r in cur.fetchall()}
    cur.execute('SELECT usuario_id,puntos FROM puntos WHERE carrera_id=%s', (race_id,))
    actual = {r['usuario_id']:r['puntos'] for r in cur.fetchall()}
    if actual != expected:
        create_backup(conn, f'Antes de reparar puntos del GP {race_id}', actor)
        context(conn, actor, 'Puntos reconciliados con la clasificación verificada')
        cur.execute('DELETE FROM puntos WHERE carrera_id=%s', (race_id,))
        if expected:
            cur.executemany('INSERT INTO puntos(usuario_id,carrera_id,puntos) VALUES(%s,%s,%s)', [(uid,race_id,score) for uid,score in expected.items()])


def apply_results(conn, race_id, data, actor='Sistema', approve_change=False):
    """Solo una clasificación validada; conserva picks y recalcula sus puntos."""
    cur = cursor(conn)
    cur.execute('SELECT pg_advisory_xact_lock(2026,70002)')
    cur.execute('SELECT * FROM carreras WHERE id=%s FOR UPDATE', (race_id,))
    race = cur.fetchone()
    if not race or race['cancelada']:
        raise ValueError('GP cancelado o inexistente.')
    rows = data['resultados']
    classified = [r for r in rows if r['posicion'] is not None and not r.get('dsq') and not r.get('dns')]
    codes = [r['codigo'] for r in classified]
    positions = [r['posicion'] for r in classified]
    if len(codes) != len(set(codes)) or len(positions) != len(set(positions)) or any(not isinstance(p,int) or p<1 for p in positions) or not {1,2,3,4,5}.issubset(positions):
        raise ValueError('Clasificación incompleta o duplicada; queda pendiente.')
    cur.execute('SELECT pi.codigo,r.posicion FROM resultados r JOIN pilotos pi ON pi.id=r.piloto_id WHERE r.carrera_id=%s', (race_id,))
    existing = cur.fetchall()
    fprint = fingerprint(classified)
    if existing and fingerprint(existing) != fprint and not approve_change:
        cur.execute("""INSERT INTO result_sync(carrera_id,checked_at,status,message,source,session_key,proposal)
            VALUES(%s,now(),'Revisión','La fuente cambió una clasificación publicada; requiere aprobación','OpenF1',%s,%s::jsonb)
            ON CONFLICT(carrera_id) DO UPDATE SET checked_at=now(),status=EXCLUDED.status,message=EXCLUDED.message,proposal=EXCLUDED.proposal,session_key=EXCLUDED.session_key""", (race_id, data['session_key'], json.dumps(data)))
        return 'Revisión'
    if existing and fingerprint(existing) == fprint:
        repair_points(conn, race_id, actor)
        cur.execute("""INSERT INTO result_sync(carrera_id,checked_at,status,message,source,session_key,fingerprint)
            VALUES(%s,now(),'Verificado','Coincide con la clasificación publicada','OpenF1',%s,%s)
            ON CONFLICT(carrera_id) DO UPDATE SET checked_at=now(),status=EXCLUDED.status,message=EXCLUDED.message,proposal=NULL""", (race_id, data['session_key'], fprint))
        return 'Verificado'
    create_backup(conn, f'Antes de importar resultados del GP {race_id}', actor)
    context(conn, actor, f"Resultados OpenF1; sesión {data['session_key']}")
    cur.execute('SELECT id,codigo FROM pilotos')
    drivers = {r['codigo']:r['id'] for r in cur.fetchall()}
    for row in classified:
        if row['codigo'] not in drivers:
            cur.execute('INSERT INTO pilotos(codigo,nombre,activo) VALUES(%s,%s,0) ON CONFLICT(codigo) DO UPDATE SET codigo=EXCLUDED.codigo RETURNING id', (row['codigo'],row.get('nombre') or row['codigo']))
            drivers[row['codigo']] = cur.fetchone()['id']
    cur.execute('DELETE FROM resultados WHERE carrera_id=%s', (race_id,))
    cur.executemany('INSERT INTO resultados(carrera_id,piloto_id,posicion) VALUES(%s,%s,%s)', [(race_id,drivers[r['codigo']],r['posicion']) for r in classified])
    cur.execute('SELECT usuario_id,piloto_id FROM picks WHERE carrera_id=%s', (race_id,))
    picks = cur.fetchall()
    position_by_id = {drivers[r['codigo']]:r['posicion'] for r in classified}
    cur.execute('DELETE FROM puntos WHERE carrera_id=%s', (race_id,))
    if picks:
        cur.executemany('INSERT INTO puntos(usuario_id,carrera_id,puntos) VALUES(%s,%s,%s)', [(p['usuario_id'],race_id,calcular_puntos(position_by_id.get(p['piloto_id']))) for p in picks])
    cur.execute("""INSERT INTO result_sync(carrera_id,checked_at,imported_at,status,message,source,session_key,fingerprint)
        VALUES(%s,now(),now(),'Importado','Resultados y puntos actualizados','OpenF1',%s,%s)
        ON CONFLICT(carrera_id) DO UPDATE SET checked_at=now(),imported_at=now(),status=EXCLUDED.status,message=EXCLUDED.message,source=EXCLUDED.source,session_key=EXCLUDED.session_key,fingerprint=EXCLUDED.fingerprint,proposal=NULL""", (race_id,data['session_key'],fprint))
    return 'Importado'


def sync_results(connection_factory, force=False):
    from openf1_integration import obtener_clasificacion, OpenF1Error
    conn = connection_factory()
    try:
        cur = cursor(conn)
        cur.execute("SELECT value FROM app_settings WHERE key='auto_results'")
        enabled = cur.fetchone()
        if enabled and not enabled['value'] and not force:
            return []
        cur.execute("""SELECT c.* FROM carreras c JOIN temporadas t ON t.id=c.temporada_id
          LEFT JOIN result_sync rs ON rs.carrera_id=c.id WHERE t.activa=1 AND NOT c.cancelada
          AND c.inicio::timestamp AT TIME ZONE 'UTC' < now()-interval '3 hours'
          AND c.inicio::timestamp AT TIME ZONE 'UTC' > now()-interval '7 days'
          AND (%s OR rs.checked_at IS NULL OR rs.checked_at < now()-interval '20 minutes')
          ORDER BY c.inicio DESC LIMIT 3""", (force,))
        races = cur.fetchall()
    finally:
        conn.close()
    reports = []
    for race in races:
        try:
            data = obtener_clasificacion(race, strict=True)
        except (OpenF1Error, ValueError) as exc:
            conn = connection_factory()
            try:
                cur = cursor(conn)
                cur.execute("""INSERT INTO result_sync(carrera_id,checked_at,status,message,source)
                    VALUES(%s,now(),'Pendiente',%s,'OpenF1') ON CONFLICT(carrera_id) DO UPDATE
                    SET checked_at=now(),status=CASE WHEN result_sync.status='Revisión' THEN 'Revisión' ELSE 'Pendiente' END,message=EXCLUDED.message""", (race['id'], str(exc)))
                conn.commit()
            finally:
                conn.close()
            reports.append({'Carrera':race['nombre'],'Estado':'Pendiente','Detalle':str(exc)})
            continue
        conn = connection_factory()
        try:
            cur = cursor(conn)
            cur.execute('SELECT pg_advisory_xact_lock(2026,70002)')
            cur.execute('SELECT pg_advisory_xact_lock(2026,%s)', (int(race['temporada_id']),))
            state = apply_results(conn, race['id'], data)
            conn.commit()
            reports.append({'Carrera':race['nombre'],'Estado':state})
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return reports


def compare_backup(payload, current):
    report = []
    for table in ('carreras','picks','resultados','puntos'):
        before = {str(r['id']):r for r in payload.get(table, [])}
        after = {str(r['id']):r for r in current.get(table, [])}
        report.append({'Tabla':table,'Respaldo':len(before),'Actual':len(after),
                       'Ausentes ahora':len(before.keys()-after.keys()),
                       'Nuevos ahora':len(after.keys()-before.keys()),
                       'Modificados':sum(before[k] != after[k] for k in before.keys() & after.keys())})
    return report


def recover_missing_picks(conn, backup_id, race_id, actor, note):
    if not note.strip():
        raise ValueError('Indica el motivo de recuperación.')
    cur = cursor(conn)
    cur.execute('SELECT pg_advisory_xact_lock(2026,70002)')
    cur.execute('SELECT payload FROM app_backups WHERE id=%s', (backup_id,))
    saved = cur.fetchone()
    if not saved:
        raise ValueError('Respaldo inexistente.')
    picks = [p for p in saved['payload'].get('picks',[]) if p['carrera_id']==race_id]
    if not picks:
        raise ValueError('Este respaldo no contiene picks para ese ID de GP.')
    create_backup(conn, f'Antes de recuperar picks del respaldo {backup_id}', actor)
    context(conn, actor, f'Recuperación del respaldo {backup_id}: {note}')
    cur.execute('LOCK TABLE picks IN SHARE ROW EXCLUSIVE MODE')
    cur.execute("SELECT set_config('app.pick_override', %s, true)", (note,))
    count = 0
    for pick in picks:
        cur.execute('INSERT INTO picks(id,usuario_id,carrera_id,piloto_id,timestamp,auto_asignado) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(usuario_id,carrera_id) DO NOTHING', (pick['id'],pick['usuario_id'],race_id,pick['piloto_id'],pick['timestamp'],pick.get('auto_asignado',0)))
        count += cur.rowcount
    if count:
        cur.execute("SELECT pg_get_serial_sequence('picks','id') AS seq")
        seq = cur.fetchone()['seq']
        if seq:
            cur.execute(f'SELECT last_value FROM {seq}')
            last = cur.fetchone()['last_value']
            cur.execute('SELECT max(id) AS maximum FROM picks')
            maximum = cur.fetchone()['maximum']
            cur.execute('SELECT setval(%s,%s,true)', (seq,max(last,maximum)))
    # Recalcular únicamente el GP recuperado, si ya tiene clasificación.
    cur.execute('SELECT piloto_id,posicion FROM resultados WHERE carrera_id=%s', (race_id,))
    positions = {r['piloto_id']:r['posicion'] for r in cur.fetchall()}
    if positions:
        cur.execute('SELECT usuario_id,piloto_id FROM picks WHERE carrera_id=%s', (race_id,))
        for pick in cur.fetchall():
            cur.execute('INSERT INTO puntos(usuario_id,carrera_id,puntos) VALUES(%s,%s,%s) ON CONFLICT(usuario_id,carrera_id) DO UPDATE SET puntos=EXCLUDED.puntos', (pick['usuario_id'],race_id,calcular_puntos(positions.get(pick['piloto_id']))))
    return count
