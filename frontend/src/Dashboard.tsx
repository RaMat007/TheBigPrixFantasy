import {useEffect, useState} from 'react'
import {ChevronRight, Flag, Save, Trophy} from 'lucide-react'
import TrackOutline from './TrackOutline'
import './dashboard.css'

type Race = {id:number;round:number;nombre:string;inicio:string;pista:string|null;layout?:number[][]|null}
type Driver = {id:number;codigo:string;nombre:string;escuderia:string|null;foto_url:string|null;color_escuderia:string|null}
type Member = {id:number;username:string;escuderia:string;total:number;position:number;change:number|null;scores:Record<string,number>}
type Summary = {
 next_race:Race|null
 my_pick:{piloto_id:number;auto_asignado:number;nombre:string;codigo:string}|null
 standings:Member[]
 rounds:number[]
 top_fives:{codigo:string;nombre:string;picks:number}[]
 remaining:number
}
const utc=(s:string)=>new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(s)?s:s+'Z').getTime()
const palette=['#ed3645','#ff7882','#c72b3b','#a7acb5','#ffffff','#7e8795','#ffabb1','#636d7b','#dd5664','#b8bec8','#8b2331','#e2e5e9','#6d1823']

export default function Dashboard({user,races,drivers,onCalendar}:{
 user:{id:number;username:string;escuderia:string;is_admin?:number}|null
 races:Race[];drivers:Driver[];onCalendar:()=>void
}) {
 const [data,setData]=useState<Summary|null>(null)
 const [chosen,setChosen]=useState('')
 const [busy,setBusy]=useState(false)
 const [message,setMessage]=useState('')
 const [now,setNow]=useState(Date.now())
 const [showAll,setShowAll]=useState(false)
 useEffect(()=>{const id=window.setInterval(()=>setNow(Date.now()),1000);return()=>window.clearInterval(id)},[])
 useEffect(()=>{
  if(!user){setData(null);setChosen('');return}
  let cancelled=false
  setMessage('')
  fetch('/api/dashboard')
   .then(async r=>{if(!r.ok)throw Error('No se pudo consultar el resumen');return r.json()})
   .then((d:Summary)=>{if(!cancelled){setData(d);setChosen(String(d.my_pick?.piloto_id||drivers[0]?.id||''))}})
   .catch(e=>{if(!cancelled)setMessage(e.message)})
  return()=>{cancelled=true}
 },[user?.id,drivers])
 const next=data?.next_race||races.find(r=>utc(r.inicio)>now)||null
 const saved=data?.my_pick
 const selected=drivers.find(d=>d.id===Number(chosen))
 const locked=!!next && now>=utc(next.inicio)
 const seconds=next?Math.max(0,Math.floor((utc(next.inicio)-now)/1000)):0
 const two=(n:number)=>String(n).padStart(2,'0')
 const countdown=seconds>=86400
  ? `${Math.floor(seconds/86400)}d ${two(Math.floor(seconds%86400/3600))}h ${two(Math.floor(seconds%3600/60))}m`
  : `${two(Math.floor(seconds/3600))}:${two(Math.floor(seconds%3600/60))}:${two(seconds%60)}`
 const standings=data?.standings||[]
 const mine=standings.find(s=>s.id===user?.id)
 const rounds=data?.rounds||[]
 const leader=standings[0]?.total||0
 const maxPts=Math.max(1,...standings.map(s=>s.total))
 const chartX=(i:number)=>50+i*(850/Math.max(1,rounds.length))
 const chartY=(v:number)=>250-v/maxPts*215
 const track=next?races.find(r=>r.id===next.id):null

 async function save(){
  if(!user||!next||!chosen||busy||locked||user.is_admin)return
  setBusy(true);setMessage('')
  try{
   const res=await fetch('/api/me/pick',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({carrera_id:next.id,piloto_id:Number(chosen)})
   })
   const body=await res.json()
   if(!res.ok)throw Error(body.detail||'No se pudo guardar el pick')
   const refreshed=await fetch('/api/dashboard')
   if(!refreshed.ok)throw Error('Pick guardado; no se pudo actualizar el resumen')
   const summary:Summary=await refreshed.json()
   setData(summary);setMessage('Pick guardado correctamente')
  }catch(e){setMessage(e instanceof Error?e.message:'Error al guardar')}
  finally{setBusy(false)}
 }

 return <div className="bpx-dashboard">
  <div className="bpx-top">
   <section className="bpx-next">
    <span className="bpx-kicker"><Flag size={14}/> PRÓXIMO GRAN PREMIO</span>
    <h2>{next?.nombre||'Temporada sin carreras pendientes'}</h2>
    <p>{next?.pista||'Consulta el calendario de la liga'}</p>
    {next&&<>
     <strong className="bpx-clock">{locked?'LIGHTS OUT':countdown}</strong>
     <small>R{two(next.round)} · {new Date(utc(next.inicio)).toLocaleString('es-MX',{
       day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'America/Mexico_City'
     })} (CDMX)</small>
    </>}
    <button className="bpx-link" onClick={onCalendar}>CALENDARIO <ChevronRight size={15}/></button>
    {track?.layout?.length?<div className="bpx-track"><TrackOutline points={track.layout} name={next?.pista||next?.nombre||''}/></div>:null}
   </section>
   <section className="bpx-choice">
    <span className="bpx-kicker">MI PICK · 5° LUGAR</span>
    {!user?<div className="bpx-muted">Inicia sesión para elegir tu piloto.</div>
    :!next?<div className="bpx-muted">No hay carrera pendiente.</div>
    :user.is_admin?<div className="bpx-muted">La cuenta administrativa no participa en los picks.</div>
    :<>
     <select aria-label="Seleccionar piloto" value={chosen} disabled={locked||busy}
       onChange={e=>{setChosen(e.target.value);setMessage('')}}>
      {drivers.map(d=><option key={d.id} value={d.id}>{d.nombre} · {d.escuderia||d.codigo}</option>)}
     </select>
     {selected&&<div className="bpx-driver">
      <div><span style={{color:'#'+(selected.color_escuderia||'00eaff').replace('#','')}}>{selected.codigo}</span>
       <strong>{selected.nombre}</strong><small>{selected.escuderia}</small></div>
      {selected.foto_url&&<img src={selected.foto_url} alt={selected.nombre}/>}
     </div>}
     <div className="bpx-choice-foot">
      {saved?`Guardado: ${saved.codigo} · ${saved.nombre}${saved.auto_asignado?' (auto-pick)':''}`:'Aún no tienes pick guardado'}
     </div>
     <button className="bpx-save" disabled={locked||busy||!chosen} onClick={save}>
      <Save size={16}/>{locked?'LIGHTS OUT':busy?'GUARDANDO...':'GUARDAR PICK'}
     </button>
    </>}
    {message&&<p className="bpx-message" role="status">{message}</p>}
   </section>
  </div>
  <div className="bpx-kpis">
   <article><span>POSICIÓN</span><strong>{mine?'#'+mine.position:'—'}</strong></article>
   <article><span>MIS PUNTOS</span><strong>{mine?.total??'—'}</strong></article>
   <article><span>DISTANCIA AL LÍDER</span><strong>{mine?Math.max(0,leader-mine.total)+' pts':'—'}</strong></article>
   <article><span>CARRERAS RESTANTES</span><strong>{data?.remaining??races.filter(r=>utc(r.inicio)>now).length}</strong></article>
  </div>
  {user&&<>
   <div className="bpx-head"><h2>Clasificación del campeonato</h2><button className="bpx-link" onClick={()=>setShowAll(v=>!v)}>{showAll?"VER TOP 5":"VER TABLA COMPLETA"} <ChevronRight size={15}/></button></div>
   <div className="bpx-table-wrap">
    <table className="bpx-table">
     <thead><tr><th>POS</th><th>CAMBIO</th><th>ESCUDERÍA</th><th>TOTAL</th>{rounds.map(r=><th key={r}>R{r}</th>)}</tr></thead>
     <tbody>{(showAll?standings:standings.slice(0,5)).map((s,i)=><tr key={s.id} className={s.id===user.id?'bpx-self':''}>
      <td>#{s.position}</td>
      <td style={{color:s.change===null?'#aaa':s.change>0?'#40d98f':s.change<0?'#f87171':'#aaa'}}>
       {s.change===null?'—':s.change>0?'▲'+s.change:s.change<0?'▼'+Math.abs(s.change):'●'}
      </td>
      <td><i style={{background:palette[i%palette.length]}}/>{s.escuderia}</td>
      <td className="bpx-total">{s.total}</td>
      {rounds.map(r=><td key={r}>{s.scores[String(r)]??'—'}</td>)}
     </tr>)}</tbody>
    </table>
    {!standings.length&&<p className="bpx-muted">Sin participantes registrados.</p>}
   </div>
   <div className="bpx-lower">
    <section className="bpx-chart-panel"><h2>La batalla por el campeonato</h2>
     {rounds.length?<><svg viewBox="0 0 950 290" role="img" aria-label="Puntos acumulados por ronda">
      {[0,.25,.5,.75,1].map(t=><g key={t}>
       <line x1="45" x2="920" y1={chartY(maxPts*t)} y2={chartY(maxPts*t)} stroke="#35404e" strokeDasharray="3 5"/>
       <text x="38" y={chartY(maxPts*t)+4} fill="#92a0ae" textAnchor="end" fontSize="12">{Math.round(maxPts*t)}</text>
      </g>)}
      {rounds.map((r,i)=><text key={r} x={chartX(i+1)} y="275" fill="#92a0ae" textAnchor="middle" fontSize="12">R{r}</text>)}
      {standings.map((s,i)=>{let accumulated=0;const coords=[`50,${chartY(0)}`,...rounds.map((r,j)=>{
       accumulated+=s.scores[String(r)]||0
       return `${chartX(j+1)},${chartY(accumulated)}`
      })];return <polyline key={s.id} points={coords.join(' ')} fill="none"
       stroke={palette[i%palette.length]} strokeWidth={s.id===user.id?5:2}
       strokeOpacity={s.id===user.id?1:.7}/>})}
     </svg><div className="bpx-legend">{standings.map((s,i)=><span key={s.id}>
      <i style={{background:palette[i%palette.length]}}/>{s.escuderia}
     </span>)}</div></>:<p className="bpx-muted">La gráfica aparecerá cuando se registren puntos.</p>}
    </section>
    <section className="bpx-five"><h2><Trophy size={18}/> Five Fives All Time</h2>
     {data?.top_fives.length?data.top_fives.map((p,i)=><div className="bpx-five-row" key={p.codigo}>
      <span>#{i+1}</span><strong>{p.nombre}</strong><small>{p.picks} picks</small>
     </div>):<p className="bpx-muted">Aún no hay resultados.</p>}
    </section>
   </div>
  </>}
 </div>
}
