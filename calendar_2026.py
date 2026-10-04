"""Calendario F1 oficial verificado el 03/10/2026; horas en UTC.

Fuente: https://www.formula1.com/en/racing/2026 y cada ficha de carrera.
Las claves identifican el GP, nunca su posición mutable en el calendario.
"""
import unicodedata
import math

# key, legacy round, official round, name, UTC start, km, laps, circuit, aliases
_ROWS = [
    ('australia',1,1,'Melbourne, AUS','2026-03-08T04:00:00',5.278,58,'Albert Park Circuit',('melbourne','australia','albert park')),
    ('china',2,2,'Shanghai, CHN','2026-03-15T07:00:00',5.451,56,'Shanghai International Circuit',('shanghai','china')),
    ('japan',3,3,'Suzuka, JPN','2026-03-29T05:00:00',5.807,53,'Suzuka International Racing Course',('suzuka','japan','japon')),
    ('miami',6,4,'Miami, USA','2026-05-03T17:00:00',5.412,57,'Miami International Autodrome',('miami',)),
    ('canada',7,5,'Montreal, CAN','2026-05-24T20:00:00',4.361,70,'Circuit Gilles-Villeneuve',('montreal','canada','gilles')),
    ('monaco',8,6,'Monaco, MON','2026-06-07T13:00:00',3.337,78,'Circuit de Monaco',('monaco',)),
    ('barcelona',9,7,'Barcelona, ESP','2026-06-14T13:00:00',4.657,66,'Circuit de Barcelona-Catalunya',('barcelona','catalunya')),
    ('austria',10,8,'Spielberg, AUT','2026-06-28T13:00:00',4.326,71,'Red Bull Ring',('spielberg','austria','red bull ring')),
    ('britain',11,9,'Silverstone, GBR','2026-07-05T14:00:00',5.891,52,'Silverstone Circuit',('silverstone','great britain','gran bretana')),
    ('belgium',12,10,'Spa, BEL','2026-07-19T13:00:00',7.004,44,'Circuit de Spa-Francorchamps',('spa,','spa-','spa franc','belgium','belgica')),
    ('hungary',13,11,'Hungaroring, HUN','2026-07-26T13:00:00',4.381,70,'Hungaroring',('hungaroring','hungary','hungria')),
    ('netherlands',14,12,'Zandvoort, NED','2026-08-23T13:00:00',4.259,72,'Circuit Zandvoort',('zandvoort','netherlands','paises bajos')),
    ('italy',15,13,'Monza, ITA','2026-09-06T13:00:00',5.793,53,'Autodromo Nazionale Monza',('monza','italy','italia')),
    ('spain',16,14,'Madrid, ESP','2026-09-13T13:00:00',5.414,57,'Madring',('madrid','madring')),
    ('azerbaijan',17,15,'Baku, AZE','2026-09-26T11:00:00',6.003,51,'Baku City Circuit',('baku','azerbaijan','azerbaiyan')),
    ('bahrain',4,16,'Bahréin en Malasia, MYS','2026-10-04T07:00:00',5.543,56,'Sepang International Circuit',('bahrein','bahrain','sepang','malasia','malaysia')),
    ('singapore',18,17,'Singapore, SGP','2026-10-11T12:00:00',4.927,62,'Marina Bay Street Circuit',('singapore','singapur','marina bay')),
    ('usa',19,18,'Austin, USA','2026-10-25T20:00:00',5.513,56,'Circuit of The Americas',('austin','americas','united states')),
    ('mexico',20,19,'Mexico City, MEX','2026-11-01T20:00:00',4.304,71,'Autódromo Hermanos Rodríguez',('mexico','hermanos rodriguez')),
    ('brazil',21,20,'Sao Paulo, BRA','2026-11-08T17:00:00',4.309,71,'Autódromo José Carlos Pace',('sao paulo','brazil','brasil','interlagos','jose carlos')),
    ('las-vegas',22,21,'Las Vegas, USA','2026-11-22T04:00:00',6.201,50,'Las Vegas Strip Circuit',('las vegas',)),
    ('qatar',23,22,'Lusail, QAT','2026-11-29T16:00:00',5.419,57,'Lusail International Circuit',('lusail','lusaail','losail','qatar')),
    ('abu-dhabi',24,23,'Abu Dhabi, UAE','2026-12-06T13:00:00',5.281,58,'Yas Marina Circuit',('abu dhabi','yas marina')),
]
CALENDAR = {r[0]: dict(key=r[0], legacy_round=r[1], round=r[2], nombre=r[3], inicio=r[4], kms=r[5], vueltas=r[6], pista=r[7], aliases=r[8], cancelada=False) for r in _ROWS}
CALENDAR['saudi-arabia'] = dict(key='saudi-arabia', legacy_round=5, round=0, nombre='Jeddah, SAU (cancelada)', inicio='2026-04-19T17:00:00', kms=6.174, vueltas=50, pista='Jeddah Corniche Circuit', aliases=('jeddah','saudi','arabia saudita'), cancelada=True)

# Top 5 oficiales: permite detectar resultados cargados al GP equivocado.
OFFICIAL_TOP5 = dict(zip(
    ('australia','china','japan','miami','canada','monaco','barcelona','austria','britain','belgium','hungary','netherlands','italy','spain','azerbaijan'),
    (('RUS','ANT','LEC','HAM','NOR'),('ANT','RUS','HAM','LEC','BEA'),
     ('ANT','PIA','LEC','RUS','NOR'),('ANT','NOR','PIA','RUS','VER'),
     ('ANT','HAM','VER','LEC','HAD'),('ANT','HAM','HAD','PIA','LAW'),
     ('HAM','RUS','NOR','VER','PIA'),('RUS','VER','ANT','PIA','HAM'),
     ('LEC','RUS','HAM','NOR','HAD'),('ANT','LEC','VER','HAM','PIA'),
     ('NOR','VER','ANT','LEC','HAM'),('NOR','ANT','RUS','HAM','LEC'),
     ('ANT','RUS','VER','NOR','PIA'),('ANT','VER','NOR','LEC','RUS'),
     ('RUS','VER','HAD','LEC','ANT'))))

def audit_race(row, picks, results, points):
    """Diagnóstico de solo lectura; no inventa ni reasigna elecciones históricas."""
    from datetime import datetime, timezone, timedelta
    from rules import calcular_puntos
    race = identify_race(row)
    problems = []
    expected = OFFICIAL_TOP5.get(race['key'])
    codes = {r['posicion']: r['codigo'].upper() for r in results}
    if race['cancelada']:
        if picks or results or points:
            problems.append('Registros archivados de GP cancelado; excluidos de puntuación')
    elif expected:
        if not picks:
            problems.append('Sin picks históricos; requiere recuperar registros originales')
        if not results:
            problems.append('Faltan resultados')
        elif tuple(codes.get(i) for i in range(1, 6)) != expected:
            problems.append('Top 5 no coincide con F1; revisar identidad de resultados')
    elif results or any(p['puntos'] for p in points):
        problems.append('GP pendiente con resultados o puntos anticipados')
    results_by_driver = {r['piloto_id']: r['posicion'] for r in results}
    points_by_user = {p['usuario_id']: p['puntos'] for p in points}
    if results and not race['cancelada']:
        expected_points = {p['usuario_id']: calcular_puntos(results_by_driver.get(p['piloto_id'])) for p in picks}
        errors = sum(points_by_user.get(uid) != val for uid,val in expected_points.items())
        errors += sum(uid not in expected_points for uid in points_by_user)
        if errors:
            problems.append(f'{errors} registros de puntos inconsistentes con picks/resultados')
    cutoff = datetime.fromisoformat(race['inicio']).replace(tzinfo=timezone.utc) - timedelta(minutes=15)
    late = 0
    invalid_times = 0
    for pick in picks:
        if pick.get('auto_asignado'):
            continue
        try:
            stamp = datetime.fromisoformat(pick['timestamp'].replace('Z','+00:00'))
            stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
            late += stamp >= cutoff
        except (ValueError, TypeError, AttributeError):
            invalid_times += 1
    if late and not race['cancelada']:
        problems.append(f'{late} picks manuales posteriores al cierre; revisar')
    if invalid_times:
        problems.append(f'{invalid_times} fechas de picks inválidas')
    if race['key']=='bahrain' and any(p.get('auto_asignado') and p['timestamp'][:10] < '2026-07-26' for p in picks):
        problems.append('Respaldos automáticos anteriores a la reprogramación; no son elecciones manuales')
    return {'ID':row['id'], 'Ronda':race['round'] if not race['cancelada'] else 'Cancelada',
        'Carrera':race['nombre'], 'UTC':race['inicio'], 'Picks':len(picks),
        'Manuales':sum(not p.get('auto_asignado') for p in picks), 'Resultados':len(results),
        'Revisión':'; '.join(problems) if problems else 'Sin inconsistencias detectadas'}

def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value or '').casefold()) if unicodedata.category(c) != 'Mn')

def identify_race(row):
    key = row.get('calendario_key')
    if key in CALENDAR:
        return CALENDAR[key]
    name = normalize(row.get('nombre'))
    matches = [race for race in CALENDAR.values() if any(alias in name for alias in race['aliases'])]
    if len(matches) != 1:
        raise ValueError(f"No se puede identificar de forma única la carrera ID {row.get('id')}: {row.get('nombre')}")
    return matches[0]

def build_plan(rows):
    plan = [(row, identify_race(row)) for row in rows]
    keys = [race['key'] for _, race in plan]
    if len(keys) != len(set(keys)):
        raise ValueError('Hay carreras duplicadas; no se aplica la renumeración automáticamente.')
    required = {key for key, race in CALENDAR.items() if not race['cancelada']}
    if not required.issubset(keys):
        raise ValueError('Faltan Grandes Premios en la temporada: ' + ', '.join(sorted(required - set(keys))))
    return plan

def apply_calendar(conn, temporada_id):
    """Migración transaccional e idempotente. No escribe picks/resultados/puntos."""
    import psycopg2.extras
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT pg_advisory_xact_lock(%s, %s)', (2026, int(temporada_id)))
    cur.execute('SELECT * FROM carreras WHERE temporada_id=%s FOR UPDATE', (temporada_id,))
    rows = cur.fetchall()
    if not rows:
        return False
    plan = build_plan(rows)
    fields = ('round','nombre','inicio','kms','vueltas','pista','cancelada')
    def differs(row, race, field):
        if field == 'kms' and row.get(field) is not None:
            return not math.isclose(float(row[field]), race[field], abs_tol=0.00001)
        return row.get(field) != race[field]
    changed = any(row.get('calendario_key') != race['key'] or row.get('hora') != race['inicio'][11:16] or any(differs(row, race, f) for f in fields) for row, race in plan)
    if not changed:
        return False
    # Apartar todas las rondas antes de permutarlas respeta UNIQUE(temporada_id, round).
    offset = max(abs(int(row['round'])) for row in rows) + len(rows) + 100
    for index, (row, _) in enumerate(plan):
        cur.execute('UPDATE carreras SET round=%s WHERE id=%s AND temporada_id=%s', (offset + index, row['id'], temporada_id))
    for row, race in plan:
        cur.execute('''UPDATE carreras SET round=%s, nombre=%s, inicio=%s,
            kms=%s, vueltas=%s, pista=%s, hora=%s, calendario_key=%s, cancelada=%s
            WHERE id=%s AND temporada_id=%s''',
            (race['round'], race['nombre'], race['inicio'], race['kms'], race['vueltas'], race['pista'], race['inicio'][11:16], race['key'], race['cancelada'], row['id'], temporada_id))
    return True

def circuit_details():
    return {race['round']: dict(race_date=race['inicio'][:10], race_time=race['inicio'][11:], country=race['nombre'].split(', ')[-1], city=race['nombre'].split(',')[0], laps=race['vueltas'], track_length_km=race['kms'], circuit_name=race['pista']) for race in CALENDAR.values() if not race['cancelada']}
