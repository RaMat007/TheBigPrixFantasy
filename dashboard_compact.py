"""Inicio compacto; el detalle completo permanece en su propia pestaña."""
import html
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import altair as alt
import streamlit as st
import crud
from rules import carrera_bloqueada
from operations import utc


def render(season):
    st.markdown('<style>[data-testid=stMainBlockContainer]{padding-top:1.2rem;padding-bottom:1rem}</style>',unsafe_allow_html=True)
    sid = season['id']
    st.markdown(f"### {html.escape(str(season['nombre']))} · {html.escape(str(st.session_state.get('escuderia') or st.session_state.username))}")
    standings = crud.listar_usuarios_con_puntos(sid).reset_index(drop=True)
    if not standings.empty:
        standings.insert(0,'Posición',range(1,len(standings)+1))
    mine = standings[standings['username']==st.session_state.username] if not standings.empty else pd.DataFrame()
    position = int(mine.iloc[0]['Posición']) if not mine.empty else '—'
    points = int(mine.iloc[0]['total_puntos'] or 0) if not mine.empty else 0
    leader = int(standings.iloc[0]['total_puntos'] or 0) if not standings.empty else 0
    race = crud.obtener_proxima_carrera(sid)
    a,b,c = st.columns([1,1,2])
    a.metric('Posición',f'#{position}' if position!='—' else '—')
    b.metric('Puntos',points)
    c.metric('Distancia al líder',f'{max(0,leader-points)} pts')
    left,right = st.columns([1,1.55],gap='medium')
    with left:
        with st.container(border=True):
            if race:
                start = utc(race['inicio'])
                close = start-timedelta(minutes=15)
                local = start.astimezone(ZoneInfo('America/Mexico_City'))
                remaining = max(0,int((close-datetime.now(timezone.utc)).total_seconds()))
                days, seconds = divmod(remaining,86400)
                hours, seconds = divmod(seconds,3600)
                minutes = seconds//60
                st.markdown(f"**R{race['round']} · {race['nombre']}**")
                st.caption(f"Carrera: {local:%d/%m/%y %H:%M} · México | {start:%H:%M} UTC")
                st.markdown(f"**Cierre de picks: {days}d {hours:02}h {minutes:02}m**" if remaining else '**Picks cerrados**')
                st.caption(f"Cierre: {close.astimezone(ZoneInfo('America/Mexico_City')):%d/%m/%y %H:%M} · México")
                pick = crud.obtener_pick_usuario(st.session_state.user_id,race['id'])
                if pick:
                    driver = crud.obtener_piloto(pick['piloto_id'])
                    st.markdown(f"Tu pick: **{driver['codigo']} · {driver['nombre']}**")
                    st.caption('Respaldo automático; puedes sustituirlo antes del cierre.' if pick.get('auto_asignado') else 'Elección manual guardada.')
                if not st.session_state.is_admin:
                    drivers = crud.listar_pilotos()
                    if not drivers.empty:
                        opts = {int(r.id):f'{r.codigo} · {r.nombre}' for r in drivers.itertuples()}
                        ids = list(opts)
                        selected = st.selectbox('Piloto para el 5.º lugar',ids,format_func=opts.get,index=ids.index(pick['piloto_id']) if pick and pick['piloto_id'] in ids else 0,disabled=carrera_bloqueada(race['inicio']),key=f"compact_pick_{race['id']}")
                        if st.button('Guardar pick',disabled=carrera_bloqueada(race['inicio']),width='stretch',key=f"compact_save_{race['id']}"):
                            try:
                                crud.guardar_pick(st.session_state.user_id,race['id'],selected)
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
            else:
                st.info('No hay más GP programados.')
        status = crud.ops_read("SELECT status,count(*) AS cantidad FROM result_sync GROUP BY status")
        pending = sum(r['cantidad'] for r in status if r['status']=='Revisión')
        if pending and st.session_state.is_admin:
            st.warning(f'{pending} clasificación(es) pendiente(s) de revisión en Control de temporada.')
        backup = crud.ops_read('SELECT created_at FROM app_backups ORDER BY id DESC LIMIT 1')
        if st.session_state.is_admin and backup:
            st.caption(f"Último respaldo: {backup[0]['created_at'].astimezone(ZoneInfo('America/Mexico_City')):%d/%m/%y %H:%M}")
        if st.session_state.is_admin:
            gaps = crud.ops_read("SELECT count(*) AS n FROM carreras c WHERE temporada_id=%s AND NOT cancelada AND inicio::timestamp AT TIME ZONE 'UTC'<now() AND NOT EXISTS(SELECT 1 FROM picks p WHERE p.carrera_id=c.id)", (sid,))[0]['n']
            if gaps:
                st.caption(f'{gaps} GP pasados sin picks vinculados · revisar en Control de temporada.')
    with right:
        ranking, evolution = st.tabs(['Clasificación','Evolución'])
        with ranking:
            if standings.empty:
                st.info('Todavía no hay participantes.')
            else:
                cols = ['Posición','username','total_puntos']
                if 'escuderia' in standings:
                    cols.insert(2,'escuderia')
                st.dataframe(standings[cols].rename(columns={'username':'Usuario','escuderia':'Escudería','total_puntos':'Puntos'}),hide_index=True,height=410,width='stretch')
        with evolution:
            progress = crud.progreso_pilotos_temporada(sid)
            if progress.empty:
                st.info('Todavía no hay resultados.')
            else:
                progress = progress.groupby(['username','round'],as_index=False)['puntos'].sum().sort_values(['username','round'])
                progress['Acumulado'] = progress.groupby('username')['puntos'].cumsum()
                chart = alt.Chart(progress).mark_line(point=True).encode(x=alt.X('round:Q',title='Ronda'),y=alt.Y('Acumulado:Q',title='Puntos'),color=alt.Color('username:N',title='Escudería'),tooltip=['username','round','Acumulado']).properties(height=330)
                st.altair_chart(chart,width='stretch')
