"""Centro administrativo de calendario, automatización y trazabilidad."""
import json
import pandas as pd
import streamlit as st
import crud
import operations as ops
import openf1_integration
from db import get_connection


def render(season_id):
    st.title('Control de temporada')
    calendar, results, backups, history, reviews = st.tabs(['Calendario','Resultados automáticos','Respaldos','Historial','Revisiones'])
    with calendar:
        rows = crud.ops_read('SELECT * FROM carreras WHERE temporada_id=%s ORDER BY cancelada,round', (season_id,))
        st.caption('Las fechas están en UTC. Se conservan los IDs y todos los picks. Las rondas se ordenan por fecha después de aprobar la revisión.')
        if st.button('Consultar propuesta de fechas en OpenF1'):
            try:
                with st.spinner('Consultando sesiones Race…'):
                    proposed = openf1_integration.proponer_calendario(rows)
                st.session_state['calendar_review'] = proposed
                st.success('Propuesta disponible. Revisa cada cambio antes de aplicarlo.')
            except Exception as exc:
                st.error(str(exc))
        source = st.session_state.get('calendar_review', rows)
        view = pd.DataFrame(source)[['id','nombre','inicio','cancelada']]
        edited = st.data_editor(view, disabled=['id'], hide_index=True, width='stretch', key=f'calendar_editor_{season_id}')
        old = {r['id']:r for r in rows}
        changes = []
        for r in edited.to_dict('records'):
            for field in ('nombre','inicio','cancelada'):
                if str(r[field]) != str(old[r['id']][field]):
                    changes.append({'ID':r['id'],'GP':old[r['id']]['nombre'],'Campo':field,'Antes':str(old[r['id']][field]),'Después':str(r[field])})
        if changes:
            st.dataframe(pd.DataFrame(changes), hide_index=True, width='stretch')
        else:
            st.caption('No hay cambios propuestos.')
        note = st.text_input('Motivo y fuente de la revisión', key='calendar_note')
        if st.button('Aplicar revisión y crear respaldo', disabled=not changes):
            try:
                count = crud.ops_write(ops.apply_calendar_review, season_id, edited.to_dict('records'), crud.actor_actual(), note)
                st.session_state.pop('calendar_review', None)
                st.success(f'{count} carreras ajustadas; picks conservados.')
            except Exception as exc:
                st.error(f'No se aplicaron cambios: {exc}')
        if st.button('Auditar calendario, picks y puntos', key='control_audit'):
            st.dataframe(crud.auditar_calendario_temporada(season_id), hide_index=True, width='stretch')
        if st.button('Revisar secuencia temporal', key='control_timeline'):
            summary, detail = crud.revisar_secuencia_temporal_picks()
            st.dataframe(summary, hide_index=True, width='stretch')
            st.download_button('Descargar secuencia CSV', detail.to_csv(index=False).encode('utf-8-sig'), 'secuencia_picks.csv', 'text/csv', key='control_csv')
        gaps = crud.ops_read("""SELECT c.id,c.round,c.nombre,c.inicio, count(p.id) AS picks,
          count(p.id) FILTER(WHERE p.auto_asignado=0) AS manuales,c.auto_piloto_id
          FROM carreras c LEFT JOIN picks p ON p.carrera_id=c.id WHERE c.temporada_id=%s
          AND NOT c.cancelada AND c.inicio::timestamp AT TIME ZONE 'UTC' < now()
          GROUP BY c.id HAVING count(p.id)=0 ORDER BY c.inicio""", (season_id,))
        if gaps:
            st.warning('GP pasados sin picks vinculados. Revisa registros y respaldos antes de recuperar elecciones.')
            st.dataframe(pd.DataFrame(gaps), hide_index=True, width='stretch')
    with results:
        enabled = crud.ops_read("SELECT value FROM app_settings WHERE key='auto_results'")[0]['value']
        choice = st.toggle('Importación automática de resultados', value=bool(enabled))
        if choice != enabled:
            crud.guardar_auto_resultados(choice)
        st.caption('Se consulta Race después del final de sesión y desde tres horas después del inicio del GP. Se exige identidad del GP, Top 5 y todos los participantes. Un cambio posterior queda pendiente de aprobación.')
        worker = crud.ops_read("SELECT value FROM app_settings WHERE key='worker_last_run'")
        if worker:
            st.caption('Última ejecución programada: '+str(worker[0]['value']))
            from datetime import datetime, timezone, timedelta
            if datetime.now(timezone.utc)-ops.utc(worker[0]['value']) > timedelta(hours=2):
                st.warning('El proceso programado no registra una ejecución reciente. Revisa GitHub Actions o consulta resultados ahora.')
        else:
            st.info('El proceso programado aún no ha registrado una ejecución. Usa la consulta manual mientras se configura.')
        if st.button('Consultar resultados ahora'):
            try:
                with st.spinner('Consultando clasificaciones…'):
                    report = ops.sync_results(get_connection, force=True)
                st.cache_data.clear()
                if report:
                    st.dataframe(pd.DataFrame(report), hide_index=True, width='stretch')
                else:
                    st.info('No hay GP terminados en los últimos siete días para consultar.')
            except Exception as exc:
                st.error(str(exc))
        states = crud.ops_read('SELECT c.id,c.nombre,rs.status,rs.checked_at,rs.imported_at,rs.message,rs.session_key FROM result_sync rs JOIN carreras c ON c.id=rs.carrera_id WHERE c.temporada_id=%s ORDER BY c.inicio DESC', (season_id,))
        st.dataframe(pd.DataFrame(states), hide_index=True, width='stretch')
        proposals = crud.ops_read("SELECT rs.*,c.nombre FROM result_sync rs JOIN carreras c ON c.id=rs.carrera_id WHERE c.temporada_id=%s AND rs.status='Revisión' AND rs.proposal IS NOT NULL", (season_id,))
        for proposal in proposals:
            with st.expander('Revisar cambio de clasificación: '+proposal['nombre']):
                st.dataframe(pd.DataFrame(proposal['proposal']['resultados']), hide_index=True, width='stretch')
                current = crud.obtener_resultados_carrera(proposal['carrera_id'])
                st.caption('Clasificación publicada actualmente')
                st.dataframe(pd.DataFrame(current), hide_index=True, width='stretch')
                if st.button('Aprobar cambio y recalcular puntos', key=f"approve_result_{proposal['carrera_id']}"):
                    try:
                        state = crud.ops_write(ops.apply_results, proposal['carrera_id'], proposal['proposal'], crud.actor_actual(), True)
                        st.success(state)
                    except Exception as exc:
                        st.error(str(exc))
    with backups:
        st.caption('Diarios durante el mantenimiento y antes de las modificaciones. Los respaldos diarios se conservan 60 días; los de cambios se conservan. La copia externa programada se cifra.')
        if st.button('Crear respaldo ahora'):
            bid, _ = crud.ops_write(ops.create_backup, 'Manual', crud.actor_actual())
            st.success(f'Respaldo {bid} creado.')
        saved = crud.ops_read('SELECT id,created_at,reason,actor FROM app_backups ORDER BY id DESC LIMIT 100')
        st.dataframe(pd.DataFrame(saved), hide_index=True, width='stretch')
        if saved:
            selected = st.selectbox('Respaldo para comparar o recuperar', [r['id'] for r in saved], format_func=lambda i: next(f"#{r['id']} · {r['created_at']} · {r['reason']}" for r in saved if r['id']==i))
            payload = crud.ops_read('SELECT payload FROM app_backups WHERE id=%s', (selected,))[0]['payload']
            st.download_button('Descargar respaldo JSON', json.dumps(payload,ensure_ascii=False,default=str).encode(), f'bigprix_respaldo_{selected}.json', 'application/json')
            if st.button('Comparar con estado actual'):
                current = {table:crud.ops_read(f'SELECT * FROM {table}') for table in ('carreras','picks','resultados','puntos')}
                st.dataframe(pd.DataFrame(ops.compare_backup(payload,current)), hide_index=True, width='stretch')
            races = {r['id']:r['nombre'] for r in payload.get('carreras',[]) if r['temporada_id']==season_id}
            if races:
                with st.expander('Recuperar picks ausentes de una carrera'):
                    rid = st.selectbox('Carrera del respaldo', list(races), format_func=lambda i: f'ID {i} · {races[i]}')
                    st.dataframe(pd.DataFrame([r for r in payload.get('picks',[]) if r['carrera_id']==rid]), hide_index=True, width='stretch')
                    st.caption('Solo inserta elecciones ausentes del mismo ID de GP. Conserva las actuales y recalcula puntos si hay resultados.')
                    recovery_note = st.text_input('Motivo de recuperación')
                    if st.button('Recuperar picks ausentes y crear respaldo'):
                        try:
                            count = crud.ops_write(ops.recover_missing_picks, selected, rid, crud.actor_actual(), recovery_note)
                            st.success(f'{count} picks recuperados.')
                        except Exception as exc:
                            st.error(f'No se aplicaron cambios: {exc}')
    with history:
        st.caption('Historial desde la activación de esta mejora. BASELINE conserva el estado inicial encontrado; las modificaciones posteriores guardan el antes y el después.')
        table = st.selectbox('Registros', ['picks','carreras','resultados','puntos','pick_reviews'])
        events = crud.ops_read('SELECT id,created_at,actor,note,action,record_id,old_data,new_data FROM app_events WHERE table_name=%s ORDER BY id DESC LIMIT 1000', (table,))
        st.dataframe(pd.DataFrame(events), hide_index=True, width='stretch')
        st.download_button('Descargar historial JSON', json.dumps(events,default=str,ensure_ascii=False).encode(), f'historial_{table}.json', 'application/json')
    with reviews:
        pick_rows = crud.ops_read('SELECT p.id,u.username,c.nombre,pi.codigo,p.timestamp,p.auto_asignado,pr.status,pr.note FROM picks p JOIN usuarios u ON u.id=p.usuario_id JOIN carreras c ON c.id=p.carrera_id JOIN pilotos pi ON pi.id=p.piloto_id LEFT JOIN pick_reviews pr ON pr.pick_id=p.id WHERE c.temporada_id=%s ORDER BY p.timestamp DESC', (season_id,))
        st.dataframe(pd.DataFrame(pick_rows), hide_index=True, width='stretch')
        if pick_rows:
            pick_id = st.selectbox('Pick a revisar', [r['id'] for r in pick_rows], format_func=lambda i: next(f"#{i} · {r['username']} · {r['nombre']} · {r['codigo']}" for r in pick_rows if r['id']==i))
            status = st.selectbox('Estado de revisión', ['Permitido','Revisar'])
            note = st.text_input('Nota de revisión posterior')
            if st.button('Guardar revisión'):
                try:
                    crud.guardar_revision_pick(pick_id,status,note)
                    st.success('Revisión guardada en el historial.')
                except Exception as exc:
                    st.error(str(exc))
