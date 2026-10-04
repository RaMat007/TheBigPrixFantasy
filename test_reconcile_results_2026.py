import copy
import unittest
from test_calendar_2026 import Database
from calendar_2026 import CALENDAR
from reconcile_results_2026 import load_results, reconcile

class DB:
    def __init__(self):
        data=load_results()
        self.races=[dict(CALENDAR[k],id=CALENDAR[k]['legacy_round'],calendario_key=k) for k in data]
        codes=sorted({r['codigo'] for rows in data.values() for r in rows})
        self.drivers=[dict(id=i,codigo=c) for i,c in enumerate(codes,1)]
        pid=next(r['id'] for r in self.drivers if r['codigo']=='NOR')
        self.picks=[dict(id=101,usuario_id=2,carrera_id=1,piloto_id=pid,timestamp='2026-03-07T10:00',auto_asignado=0)]
        self.results=[dict(id=1,carrera_id=1,piloto_id=pid,posicion=1)]
        self.points=[dict(id=1,usuario_id=2,carrera_id=1,puntos=1)]
        self.output=[];self.backup=None;self.writes=0
    def cursor(self, **kwargs): return self
    def fetchall(self): return copy.deepcopy(self.output)
    def fetchone(self): return copy.deepcopy(self.output[0])
    def execute(self, sql, args=None):
        if sql.startswith('SELECT * FROM carreras'): self.output=self.races
        elif sql=='SELECT id,codigo FROM pilotos': self.output=self.drivers
        elif sql.startswith('SELECT * FROM '):
            table={'resultados':'results','puntos':'points'}.get(sql.split()[3],sql.split()[3]);self.output=getattr(self,table)
        elif sql.startswith('INSERT INTO reconciliacion'):
            import json
            self.backup=json.loads(args[1]);self.output=[dict(id=1)];self.writes+=1
        elif sql.startswith('DELETE FROM '):
            table={'resultados':'results','puntos':'points'}.get(sql.split()[2],sql.split()[2]);setattr(self,table,[r for r in getattr(self,table) if r['carrera_id']!=args[0]]);self.writes+=1
    def executemany(self, sql, values):
        self.writes+=1
        if 'INSERT INTO resultados' in sql:
            self.results.extend(dict(carrera_id=rid,piloto_id=pid,posicion=pos) for rid,pid,pos in values)
        elif 'INSERT INTO puntos' in sql:
            self.points.extend(dict(usuario_id=uid,carrera_id=rid,puntos=pts) for uid,rid,pts in values)
        else: raise AssertionError(sql)

class ReconcileTests(unittest.TestCase):
    def test_complete_official_snapshot(self):
        data=load_results()
        self.assertEqual(len(data),15)
        self.assertTrue(all(len(rows)==22 for rows in data.values()))
    def test_preserve_picks_backup_and_recalculate(self):
        db=DB();before=copy.deepcopy(db.picks)
        report=reconcile(db,1)
        self.assertEqual(db.picks,before)
        self.assertEqual(db.backup['picks'],before)
        self.assertEqual(db.backup['puntos'][0]['puntos'],1)
        self.assertEqual(db.points[0]['puntos'],20)
        self.assertEqual(len(db.points),1)
        self.assertEqual(len(report),15)
        self.assertEqual(next(r for r in report if r['ID']==17)['Picks conservados'],0)
    def test_missing_driver_fails_before_any_write(self):
        db=DB();db.drivers=[]
        with self.assertRaisesRegex(ValueError,'Faltan pilotos'): reconcile(db,1)
        self.assertEqual(db.writes,0)

if __name__=='__main__': unittest.main()
