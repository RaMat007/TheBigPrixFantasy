import copy
import sys
import types
import unittest
from calendar_2026 import CALENDAR, OFFICIAL_TOP5, apply_calendar, audit_race, build_plan

sys.modules.setdefault('psycopg2', types.SimpleNamespace(extras=types.SimpleNamespace(RealDictCursor=object)))
sys.modules.setdefault('psycopg2.extras', sys.modules['psycopg2'].extras)

class Database:
    def __init__(self):
        self.rows = [dict(id=r['legacy_round'], round=r['legacy_round'], nombre=r['nombre'], inicio='2026-01-01T00:00', kms=None, vueltas=None, pista=None, cancelada=False, calendario_key=None) for r in CALENDAR.values()]
        self.picks = [dict(id=r['id']+100, carrera_id=r['id'], usuario_id=2, piloto_id=6) for r in self.rows]
        self.results = [dict(carrera_id=6, piloto_id=1, posicion=1)]
        self.points = [dict(carrera_id=6, usuario_id=2, puntos=1)]
        self.writes = 0
    def cursor(self, **kwargs): return self
    def fetchall(self): return copy.deepcopy(self.rows)
    def execute(self, sql, args):
        if not sql.startswith('UPDATE'): return
        assert 'UPDATE carreras' in sql
        self.writes += 1
        if len(args)==3:
            rnd, rid, _ = args
            assert all(r['id']==rid or r['round']!=rnd for r in self.rows), 'UNIQUE collision'
            next(r for r in self.rows if r['id']==rid)['round']=rnd
        else:
            rnd,name,start,km,laps,track,hour,key,cancel,rid,_=args
            assert all(r['id']==rid or r['round']!=rnd for r in self.rows), 'UNIQUE collision'
            next(r for r in self.rows if r['id']==rid).update(round=rnd,nombre=name,inicio=start,kms=km,vueltas=laps,pista=track,hora=hour,calendario_key=key,cancelada=cancel)

class CalendarTests(unittest.TestCase):
    def test_migration_preserves_all_links_and_is_idempotent(self):
        db=Database(); links=copy.deepcopy((db.picks,db.results,db.points))
        self.assertTrue(apply_calendar(db,1))
        self.assertEqual((db.picks,db.results,db.points),links)
        by_id={r['id']:r for r in db.rows}
        self.assertEqual(by_id[4]['round'],16)
        self.assertEqual(by_id[4]['inicio'],'2026-10-04T07:00:00')
        self.assertEqual(by_id[6]['round'],4)
        self.assertEqual(by_id[6]['inicio'],'2026-05-03T17:00:00')
        self.assertEqual(by_id[17]['round'],15)
        self.assertEqual(by_id[18]['round'],17)
        self.assertTrue(by_id[5]['cancelada'])
        self.assertEqual(sorted(r['round'] for r in db.rows if not r['cancelada']),list(range(1,24)))
        writes=db.writes
        self.assertFalse(apply_calendar(db,1))
        self.assertEqual(db.writes,writes)
    def test_identity_is_not_inferred_from_round(self):
        db=Database()
        for r in db.rows: r['round']=100-r['round']
        apply_calendar(db,1)
        self.assertEqual(next(r for r in db.rows if r['id']==6)['calendario_key'],'miami')
    def test_postgres_real_rounding_does_not_repeat_migration(self):
        import struct
        db=Database();apply_calendar(db,1)
        for r in db.rows:
            r['kms']=struct.unpack('f',struct.pack('f',r['kms']))[0]
        self.assertFalse(apply_calendar(db,1))
    def test_ambiguous_or_incomplete_season_does_not_write(self):
        db=Database();db.rows[0]['nombre']='Unknown'
        with self.assertRaises(ValueError): apply_calendar(db,1)
        self.assertEqual(db.writes,0)
        db=Database();db.rows.pop(0)
        with self.assertRaises(ValueError): apply_calendar(db,1)
        self.assertEqual(db.writes,0)
    def test_audit_detects_moved_results_and_bad_points(self):
        row=dict(CALENDAR['miami'],id=6,calendario_key='miami')
        picks=[dict(usuario_id=2,piloto_id=5,auto_asignado=0,timestamp='2026-05-02T12:00:00')]
        results=[dict(posicion=i,piloto_id=i,codigo=code) for i,code in enumerate(OFFICIAL_TOP5['miami'],1)]
        report=audit_race(row,picks,results,[dict(usuario_id=2,puntos=20)])
        self.assertEqual(report['Revisión'],'Sin inconsistencias detectadas')
        results[0]['codigo']='LEC'
        report=audit_race(row,picks,results,[dict(usuario_id=2,puntos=1)])
        self.assertIn('Top 5 no coincide',report['Revisión'])
        self.assertIn('puntos inconsistentes',report['Revisión'])
    def test_archived_cancellation_and_old_autopicks_are_identified(self):
        row=dict(CALENDAR['saudi-arabia'],id=5,calendario_key='saudi-arabia')
        pick=dict(usuario_id=2,piloto_id=6,auto_asignado=1,timestamp='2026-03-29T05:53:18')
        self.assertIn('GP cancelado',audit_race(row,[pick],[],[])['Revisión'])
        row=dict(CALENDAR['bahrain'],id=4,calendario_key='bahrain')
        self.assertIn('Respaldos automáticos',audit_race(row,[pick],[],[])['Revisión'])
    def test_miami_late_pick_is_allowed_with_review_note(self):
        row=dict(CALENDAR['miami'],id=6,calendario_key='miami')
        pick=dict(usuario_id=2,piloto_id=6,auto_asignado=0,timestamp='2026-05-03T18:00:00')
        report = audit_race(row,[pick],[],[])['Revisión']
        self.assertIn('Revisión posterior', report)
        self.assertIn('permitido(s) por el administrador', report)
        row=dict(CALENDAR['canada'],id=7,calendario_key='canada')
        pick['timestamp']='2026-05-24T21:00:00'
        self.assertIn('posteriores al cierre',audit_race(row,[pick],[],[])['Revisión'])

if __name__=='__main__': unittest.main()
