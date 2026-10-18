import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Flag, Trophy, CalendarDays, Users, ChevronRight, RefreshCw } from 'lucide-react'
import './style.css'

type Race = { id:number; round:number; nombre:string; inicio:string; pista:string|null; vueltas:number|null }
type Driver = { id:number; codigo:string; nombre:string; escuderia:string|null; foto_url:string|null; color_escuderia:string|null }
type Season = { id:number; nombre:string } | null
type Page = 'dashboard' | 'calendar' | 'drivers' | 'ranking'
const menu: {id:Page; name:string; icon:typeof Flag}[] = [
  {id:'dashboard',name:'Inicio',icon:Flag},
  {id:'calendar',name:'Carreras',icon:CalendarDays},
  {id:'drivers',name:'Pilotos',icon:Users},
  {id:'ranking',name:'Ranking',icon:Trophy},
]
function App() {
 const [page,setPage]=useState<Page>('dashboard')
 const [season,setSeason]=useState<Season>(null)
 const [races,setRaces]=useState<Race[]>([])
 const [drivers,setDrivers]=useState<Driver[]>([])
 const [error,setError]=useState('')
 const [loading,setLoading]=useState(true)
 useEffect(()=>{
  Promise.all([
    fetch('/api/season').then(r=>{if(!r.ok)throw Error('Calendario no disponible');return r.json()}),
    fetch('/api/drivers').then(r=>{if(!r.ok)throw Error('Pilotos no disponibles');return r.json()})
  ]).then(([s,d])=>{setSeason(s.season);setRaces(s.races);setDrivers(d.drivers)})
    .catch(e=>setError(e.message)).finally(()=>setLoading(false))
 },[])
 const upcoming=races.find(r=>new Date(r.inicio).getTime()>Date.now())
 const nav=(id:Page)=>setPage(id)
 return <div className="shell">
   <aside className="side"><div className="logo"><span className="mark">B<span>P</span></span><div>THE BIG PRIX<small>FANTASY RACING</small></div></div>
    <p className="side-label">COMPETICIÓN</p><nav>{menu.map(m=><button key={m.id} onClick={()=>nav(m.id)} className={page===m.id?'selected':''}><m.icon size={18}/>{m.name}<ChevronRight size={14} className="arrow"/></button>)}</nav>
    <div className="side-foot">TEMPORADA ACTIVA<strong>{season?.nombre||'No configurada'}</strong><small>React 2.0 · Vista preliminar</small></div></aside>
   <main><header><div><span className="eyebrow">THE BIG PRIX FANTASY / 2026</span><h1>{menu.find(m=>m.id===page)?.name}</h1></div><div className="mode"><span className="pulse"/> VISTA PRELIMINAR</div></header>
    {error&&<div className="error">{error}. Comprueba que FastAPI esté activo en el puerto 8090.</div>}
    {loading?<div className="empty"><RefreshCw className="spin"/> Cargando datos reales...</div>:<>
     {page==='dashboard'&&<><section className="hero"><div><span className="eyebrow">PRÓXIMO GRAN PREMIO</span><h2>{upcoming?.nombre||'Temporada sin carreras pendientes'}</h2><p>{upcoming?.pista||'Consulta el calendario oficial de la liga'}</p><button className="cta" onClick={()=>nav('calendar')}>EXPLORAR CALENDARIO <ChevronRight size={17}/></button></div><div className="round">{upcoming?'R'+String(upcoming.round).padStart(2,'0'):'F1'}</div></section>
       <section className="stats"><article><span>CARRERAS REGISTRADAS</span><strong>{races.length}</strong><small>Calendario en base de datos</small></article><article><span>PILOTOS ACTIVOS</span><strong>{drivers.length}</strong><small>Parrilla registrada</small></article><article><span>TEMPORADA</span><strong className="season-stat">{season?.nombre||'—'}</strong><small>Configuración actual</small></article></section>
       <div className="section-head"><h2>Calendario</h2><button onClick={()=>nav('calendar')}>VER TODO <ChevronRight size={15}/></button></div><div className="race-grid">{races.slice(0,4).map(r=><RaceCard key={r.id} race={r}/>)}</div>
     </>}
     {page==='calendar'&&<><p className="intro">Las carreras están sincronizadas con la temporada activa de BigPrix.</p><div className="race-grid">{races.map(r=><RaceCard key={r.id} race={r}/>)}</div></>}
     {page==='drivers'&&<><p className="intro">Pilotos activos en la base de datos. Las selecciones de P5 se habilitarán cuando esté lista la autenticación.</p><div className="driver-grid">{drivers.map(d=><article key={d.id} className="driver"><span className="driver-code" style={{color:'#'+(d.color_escuderia||'E63946').replace('#','')}}>{d.codigo}</span><div className="driver-info"><strong>{d.nombre}</strong><small>{d.escuderia||'Escudería pendiente'}</small></div>{d.foto_url&&<img src={d.foto_url} alt={d.nombre} loading="lazy"/>}</article>)}</div></>}
     {page==='ranking'&&<div className="empty"><Trophy size={32}/><h2>Ranking próximamente</h2><p>Se conectará tras implementar la autenticación y autorización, sin exponer información privada.</p></div>}
    </>}
   </main><div className="mobile-nav">{menu.map(m=><button key={m.id} className={page===m.id?'selected':''} onClick={()=>nav(m.id)}><m.icon size={20}/><span>{m.name}</span></button>)}</div>
 </div>
}
function RaceCard({race}:{race:Race}) {return <article className="race"><span className="race-top">ROUND {String(race.round).padStart(2,'0')} <Flag size={17}/></span><h3>{race.nombre}</h3><p>{race.pista||'Circuito por confirmar'}</p><div className="race-bottom"><span>{new Date(race.inicio).toLocaleDateString('es-MX',{day:'2-digit',month:'short',year:'numeric'})}</span><span>{race.vueltas?race.vueltas+' VUELTAS':'GRAND PRIX'}</span></div></article>}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
