import unittest
from streamlit.testing.v1 import AppTest

PREFIX = '''
import sys, types, pandas as pd
import streamlit as st
from datetime import datetime,timezone
from calendar_2026 import CALENDAR
fake=types.ModuleType('crud')
db=types.ModuleType('db')
db.get_connection=lambda:None
sys.modules['db']=db
race=dict(CALENDAR['bahrain'],id=4,temporada_id=1,auto_piloto_id=6)
standings=pd.DataFrame([dict(username='Speedy González',total_puntos=100,escuderia='Speedy')]+[dict(username=f'Team {i}',total_puntos=90-i,escuderia=f'Team {i}') for i in range(12)])
fake.listar_usuarios_con_puntos=lambda sid:standings
fake.obtener_proxima_carrera=lambda sid:race
fake.obtener_pick_usuario=lambda uid,rid:dict(piloto_id=6,auto_asignado=1)
fake.obtener_piloto=lambda pid:dict(codigo='SAI',nombre='Carlos Sainz')
fake.listar_pilotos=lambda:pd.DataFrame([dict(id=6,codigo='SAI',nombre='Carlos Sainz'),dict(id=7,codigo='NOR',nombre='Lando Norris')])
fake.progreso_pilotos_temporada=lambda sid:pd.DataFrame([dict(username='Speedy González',round=1,puntos=20)])
fake.actor_actual=lambda:'Administrador'
fake.obtener_resultados_carrera=lambda rid:[]
def read(sql,params=()):
 if sql.startswith('SELECT value FROM app_settings'):return [dict(value=True)] if 'auto_results' in sql else []
 if sql.startswith('SELECT created_at FROM app_backups'):return [dict(created_at=datetime.now(timezone.utc))]
 if sql.startswith('SELECT count(*) AS n'):return [dict(n=3)]
 if sql.startswith('SELECT * FROM carreras'):return [race]
 if sql.startswith('SELECT id,created_at,reason,actor'):return [dict(id=1,created_at=datetime.now(timezone.utc),reason='Inicial',actor='Sistema')]
 if sql.startswith('SELECT payload'):return [dict(payload=dict(carreras=[race],picks=[]))]
 return []
fake.ops_read=read
sys.modules['crud']=fake
st.session_state.username='Speedy González'
st.session_state.user_id=2
st.session_state.escuderia='Speedy'
'''


class UITests(unittest.TestCase):
    def dashboard(self, admin):
        script=PREFIX+f"\nst.session_state.is_admin={admin}\nfrom dashboard_compact import render\nrender(dict(id=1,nombre='Apertura 2026'))\n"
        app=AppTest.from_string(script).run()
        self.assertFalse(app.exception,[(e.message,e.stack_trace) for e in app.exception])
        self.assertEqual(len(app.metric),3)
        self.assertEqual(len(app.dataframe),1)
        return app
    def test_user_dashboard_has_pick_control(self):
        app=self.dashboard(False)
        self.assertTrue(any(b.label=='Guardar pick' for b in app.button))
    def test_admin_dashboard_has_no_personal_pick_control(self):
        app=self.dashboard(True)
        self.assertFalse(any(b.label=='Guardar pick' for b in app.button))
    def test_admin_control_renders_calendar_backups_and_history(self):
        app=AppTest.from_string(PREFIX+"\nst.session_state.is_admin=True\nfrom operations_ui import render\nrender(1)\n").run()
        self.assertFalse(app.exception,[(e.message,e.stack_trace) for e in app.exception])
        self.assertEqual([t.label for t in app.tabs],['Calendario','Resultados automáticos','Respaldos','Historial','Revisiones'])


if __name__=='__main__':unittest.main()
