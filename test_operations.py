import copy
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from calendar_2026 import CALENDAR
import operations as ops
import openf1_integration as api


class ResultsDB:
    def __init__(self, existing=False):
        self.race = dict(CALENDAR['miami'],id=6,temporada_id=1)
        self.drivers = [dict(id=i,codigo=f'D{i}') for i in range(1,6)]
        self.results = [dict(codigo='D5',posicion=1)] if existing else []
        self.picks = [dict(usuario_id=2,piloto_id=5)]
        self.points = [dict(usuario_id=2,carrera_id=6,puntos=1)]
        self.saved=[]
        self.output=[]
    def cursor(self, **kwargs): return self
    def execute(self, query, args=None):
        if query.startswith('SELECT * FROM carreras'): self.output=[self.race]
        elif query.startswith('SELECT pi.codigo'): self.output=self.results
        elif query=='SELECT id,codigo FROM pilotos': self.output=self.drivers
        elif query.startswith('SELECT usuario_id,piloto_id FROM picks'): self.output=self.picks
        elif query.startswith('SELECT p.usuario_id,r.posicion'): self.output=[dict(usuario_id=p['usuario_id'],posicion=next((r['posicion'] for r in self.results if r.get('codigo')==f"D{p['piloto_id']}"),None)) for p in self.picks]
        elif query.startswith('SELECT usuario_id,puntos FROM puntos'): self.output=self.points
        elif query.startswith('DELETE FROM resultados'): self.results=[]
        elif query.startswith('DELETE FROM puntos'): self.points=[]
        self.saved.append((query,args))
    def fetchall(self): return copy.deepcopy(self.output)
    def fetchone(self): return copy.deepcopy(self.output[0]) if self.output else None
    def executemany(self,query,args):
        self.saved.append((query,args))
        if query.startswith('INSERT INTO resultados'):
            self.results=[dict(carrera_id=rid,piloto_id=pid,posicion=pos) for rid,pid,pos in args]
        elif query.startswith('INSERT INTO puntos'):
            self.points=[dict(usuario_id=uid,carrera_id=rid,puntos=score) for uid,rid,score in args]


class OpsTests(unittest.TestCase):
    def data(self):
        return dict(session_key=42,resultados=[dict(codigo=f'D{i}',posicion=i) for i in range(1,6)])
    def test_new_results_backup_and_score_without_changing_picks(self):
        db=ResultsDB(); before=copy.deepcopy(db.picks)
        with patch('operations.create_backup',return_value=(1,True)) as backup:
            self.assertEqual(ops.apply_results(db,6,self.data()),'Importado')
        backup.assert_called_once()
        self.assertEqual(db.picks,before)
        self.assertEqual(db.points,[dict(usuario_id=2,carrera_id=6,puntos=20)])
        self.assertFalse(any('INSERT INTO picks' in sql or 'UPDATE picks' in sql for sql,_ in db.saved))
    def test_changed_published_results_require_review(self):
        db=ResultsDB(existing=True); before=copy.deepcopy((db.results,db.picks,db.points))
        with patch('operations.create_backup') as backup:
            self.assertEqual(ops.apply_results(db,6,self.data()),'Revisión')
        backup.assert_not_called()
        self.assertEqual((db.results,db.picks,db.points),before)
        self.assertFalse(any(sql.startswith('DELETE') for sql,_ in db.saved))
    def test_matching_results_repair_missing_or_inconsistent_points(self):
        db=ResultsDB();db.results=self.data()['resultados']
        before=copy.deepcopy(db.picks)
        with patch('operations.create_backup',return_value=(1,True)):
            self.assertEqual(ops.apply_results(db,6,self.data()),'Verificado')
        self.assertEqual(db.points[0]['puntos'],20)
        self.assertEqual(db.picks,before)
    def test_admin_can_approve_changed_results(self):
        db=ResultsDB(existing=True)
        with patch('operations.create_backup',return_value=(1,True)):
            self.assertEqual(ops.apply_results(db,6,self.data(),approve_change=True),'Importado')
        self.assertEqual(db.points[0]['puntos'],20)
    def test_partial_and_duplicate_classifications_do_not_write(self):
        for rows in [self.data()['resultados'][:4],self.data()['resultados']+[dict(codigo='D1',posicion=6)]]:
            db=ResultsDB()
            with self.assertRaises(ValueError):ops.apply_results(db,6,dict(session_key=42,resultados=rows))
            self.assertFalse(any(sql.startswith('DELETE') for sql,_ in db.saved))
    def test_calendar_reorders_preserving_ids_and_archives_cancellation(self):
        old=[dict(id=4,nombre='Bahréin',inicio='2026-04-12T15:00',cancelada=False),dict(id=5,nombre='Jeddah',inicio='2026-04-19T17:00',cancelada=False),dict(id=6,nombre='Miami',inicio='2026-05-03T17:00',cancelada=False)]
        edited=copy.deepcopy(old);edited[0]['inicio']='2026-10-04T07:00';edited[1]['cancelada']=True
        result=ops.validate_calendar_changes(old,edited)
        self.assertEqual({r['id']:r['round'] for r in result},{4:2,5:0,6:1})
        self.assertEqual({r['id'] for r in result},{4,5,6})
    def test_calendar_missing_ids_and_duplicate_dates_are_rejected(self):
        rows=[dict(id=1,nombre='A',inicio='2026-03-08T04:00',cancelada=False),dict(id=2,nombre='B',inicio='2026-03-15T07:00',cancelada=False)]
        with self.assertRaises(ValueError):ops.validate_calendar_changes(rows,rows[:1])
        edited=copy.deepcopy(rows);edited[1]['inicio']=edited[0]['inicio']
        with self.assertRaises(ValueError):ops.validate_calendar_changes(rows,edited)
    def test_backup_comparison_identifies_missing_and_changed_picks(self):
        before={'picks':[dict(id=1,piloto_id=2),dict(id=2,piloto_id=3)]}
        after={'picks':[dict(id=1,piloto_id=4),dict(id=3,piloto_id=2)]}
        result=next(r for r in ops.compare_backup(before,after) if r['Tabla']=='picks')
        self.assertEqual((result['Ausentes ahora'],result['Nuevos ahora'],result['Modificados']),(1,1,1))
    def fixture(self):
        session=dict(session_key=42,meeting_key=1,session_name='Race',location='Miami',country_name='United States',circuit_short_name='Miami',date_start='2026-05-03T17:00:00+00:00',date_end='2026-05-03T19:00:00+00:00')
        drivers=[dict(driver_number=i,name_acronym=f'D{i}',full_name=f'Driver {i}') for i in range(1,23)]
        results=[dict(driver_number=i,position=i,dnf=False,dns=False,dsq=False) for i in range(1,23)]
        def get(endpoint,**kwargs):return {'sessions':[session],'drivers':drivers,'session_result':results}[endpoint]
        return session,drivers,results,get
    def test_strict_api_import_requires_full_session_and_preserves_classified_dnf(self):
        _,_,results,get=self.fixture();results[-1]['dnf']=True
        with patch.object(api,'_get_json',side_effect=get):
            data=api.obtener_clasificacion(CALENDAR['miami'],strict=True)
        self.assertEqual(len(data['resultados']),22)
        self.assertEqual(data['resultados'][-1]['posicion'],22)
    def test_strict_api_rejects_wrong_gp_unfinished_and_partial_data(self):
        for kind in ('wrong_gp','unfinished','partial'):
            session,_,results,get=self.fixture()
            if kind=='wrong_gp':session.update(location='Monza',country_name='Italy',circuit_short_name='Monza')
            if kind=='unfinished':session['date_end']='2099-05-03T19:00:00+00:00'
            if kind=='partial':results.pop()
            with patch.object(api,'_get_json',side_effect=get):
                with self.assertRaises(api.OpenF1Error):api.obtener_clasificacion(CALENDAR['miami'],strict=True)
    def test_disqualified_driver_has_no_scoring_position(self):
        _,_,results,get=self.fixture();results[-1]['dsq']=True
        with patch.object(api,'_get_json',side_effect=get):
            data=api.obtener_clasificacion(CALENDAR['miami'],strict=True)
        self.assertIsNone(data['resultados'][-1]['posicion'])
    def test_utc_values_preserve_timezone(self):
        self.assertEqual(ops.utc('2026-10-03T20:00:00-06:00'),datetime(2026,10,4,2,tzinfo=timezone.utc))


if __name__=='__main__':unittest.main()
