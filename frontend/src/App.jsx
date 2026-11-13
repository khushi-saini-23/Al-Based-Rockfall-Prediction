import { useCallback, useEffect, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowRight, BarChart3, Bell,
  Check, CheckCircle2, CircleHelp, CloudRain, Database,
  FileText, Gauge, Image as ImageIcon, LayoutDashboard, MapPinned,
  Menu, Mountain, Pause, Play, Radio, Settings, ShieldAlert,
  SlidersHorizontal, UploadCloud, Waves, X,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { get, patch, post, upload } from './api'
import MineRiskMap from './MineRiskMap.jsx'
import DemoMineMap from './DemoMineMap.jsx'

const sidebarItems = [
  ['Dashboard', LayoutDashboard], ['Live Map', MapPinned], ['Alerts', Bell],
  ['Risk Analysis', BarChart3], ['Sensor Data', Activity], ['Image Detection', ImageIcon],
  ['Reports', FileText], ['Settings', Settings],
]
const zoneNames = { north_wall: 'North Wall', east_bench: 'East Bench', south_ramp: 'South Ramp' }
const chartFields = [
  ['rainfall', 'Rainfall', 'mm/h', '#a3704b'],
  ['soil_moisture', 'Soil moisture', '%', '#698e89'],
  ['ground_vibration', 'Ground vibration', 'mm/s', '#ad896b'],
  ['displacement', 'Displacement', 'mm', '#a9513b'],
]
const riskColors = { LOW: '#658873', MEDIUM: '#d6a063', HIGH: '#b95f43' }
const pageFromHash = () => sidebarItems.map(([name]) => name).find(name => `#${name.toLowerCase().replaceAll(' ', '-')}` === window.location.hash) || 'Dashboard'
const formatTime = value => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'
const formatDate = value => value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—'
const pretty = value => String(value || '').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase())

function Logo({ onClick }) {
  return <button className="logo" onClick={onClick} aria-label="GeoGuards dashboard"><span className="logo-icon"><Mountain size={25} strokeWidth={1.55}/></span><span>GeoGuards</span></button>
}

function Badge({ level, children }) {
  return <span className={`badge ${(level || 'no-data').toLowerCase().replace(' ', '-')}`}>{children || pretty(level)}</span>
}

function Empty({ icon: Icon = Radio, title, detail }) {
  return <div className="empty-state"><Icon size={27} strokeWidth={1.4}/><strong>{title}</strong>{detail && <span>{detail}</span>}</div>
}

function Card({ title, subtitle, action, children, className = '' }) {
  return <section className={`card ${className}`}><div className="card-head"><div><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div>{action}</div>{children}</section>
}

function Stat({ icon: Icon, value, label, tone = 'sand' }) {
  return <div className={`stat ${tone}`}><span className="stat-icon"><Icon size={21} strokeWidth={1.7}/></span><div><strong>{value}</strong><span>{label}</span></div></div>
}

function Trend({ field, label, unit, color, history }) {
  const points = [...history].reverse().map(row => ({ t: formatTime(row.timestamp), value: row[field] }))
  return <Card title={label} subtitle={`Simulated readings · ${unit}`} className="trend-card">
    {points.length ? <ResponsiveContainer width="100%" height={190}><AreaChart data={points} margin={{ top: 12, right: 10, left: -24, bottom: 0 }}><defs><linearGradient id={`area-${field}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={0.33}/><stop offset="100%" stopColor={color} stopOpacity={0.02}/></linearGradient></defs><CartesianGrid vertical={false} stroke="#e9ddd1"/><XAxis dataKey="t" tick={{ fontSize: 10, fill: '#9c8676' }} axisLine={false} tickLine={false} minTickGap={28}/><YAxis tick={{ fontSize: 10, fill: '#9c8676' }} axisLine={false} tickLine={false}/><Tooltip contentStyle={{ background: '#fff9f2', border: '1px solid #e8d9c9', borderRadius: 10 }}/><Area type="monotone" dataKey="value" stroke={color} fill={`url(#area-${field})`} strokeWidth={2.5} dot={false}/></AreaChart></ResponsiveContainer> : <Empty icon={Activity} title="No readings yet" detail="Start the simulator to see this trend."/>}
  </Card>
}

function AlertItem({ alert, onOpen }) {
  return <button className="alert-item" onClick={() => onOpen(alert)}><span className={`alert-symbol ${alert.risk_level.toLowerCase()}`}><AlertTriangle size={18}/></span><span className="alert-copy"><strong>{alert.risk_level === 'HIGH' ? 'Elevated rockfall risk' : 'Conditions require review'}</strong><small>{zoneNames[alert.zone_id] || pretty(alert.zone_id)} · {formatDate(alert.timestamp)}</small></span><Badge level={alert.risk_level}/></button>
}

function SimulatorControls({ running, scenario, busy, action }) {
  return <div className="sim-controls"><div><label htmlFor="scenario">Demonstration scenario</label><select id="scenario" value={scenario || 'normal'} disabled={busy} onChange={e => action(() => post('/api/simulator/scenario', { scenario: e.target.value }))}><option value="normal">Normal conditions</option><option value="heavy_rain">Heavy rainfall</option><option value="slope_movement">Slope movement</option></select></div><button className="brown-button" disabled={busy} onClick={() => action(() => post(running ? '/api/simulator/stop' : '/api/simulator/start'))}>{running ? <Pause size={16}/> : <Play size={16}/>} {running ? 'Pause simulation' : 'Start simulation'}</button><span className={`sim-state ${running ? 'running' : ''}`}><i/>{running ? 'Generating readings every 5 seconds' : 'Simulator paused'}</span></div>
}

export default function App() {
  const [page, setPage] = useState(pageFromHash)
  const [menuOpen, setMenuOpen] = useState(false)
  const [selectedZone, setSelectedZone] = useState('north_wall')
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [showZones, setShowZones] = useState(true)
  const [file, setFile] = useState(null)
  const [uploadResult, setUploadResult] = useState(null)
  const [data, setData] = useState({ summary: null, sensors: [], history: [], predictions: [], alerts: [], detections: [], zones: [], distribution: {} })
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const [summary, sensors, history, predictions, alerts, detections, zones, distribution] = await Promise.all([
        get('/api/dashboard/summary'), get('/api/sensors/latest'), get('/api/sensors/history?limit=90'),
        get('/api/predictions/latest'), get('/api/alerts?limit=30'), get('/api/detections?limit=20'),
        get('/api/zones'), get('/api/dashboard/risk-distribution'),
      ])
      setData({ summary, sensors, history, predictions, alerts, detections, zones, distribution })
      setError('')
    } catch (e) { setError(e.response?.data?.detail || 'Cannot reach the API. Start the FastAPI backend on port 8000.') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh(); const id = setInterval(refresh, 5000); return () => clearInterval(id) }, [refresh])
  useEffect(() => { const onHashChange = () => setPage(pageFromHash()); window.addEventListener('hashchange', onHashChange); return () => window.removeEventListener('hashchange', onHashChange) }, [])
  async function action(fn) { setBusy(true); try { await fn(); await refresh() } catch (e) { setError(e.response?.data?.detail || e.message) } finally { setBusy(false) } }
  function navigate(next) { window.location.hash = next.toLowerCase().replaceAll(' ', '-'); setPage(next); setMenuOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  const currentRisk = data.predictions.find(p => p.zone_id === selectedZone)
  const currentReading = data.sensors.find(r => r.zone_id === selectedZone)
  const zoneHistory = data.history.filter(r => r.zone_id === selectedZone).slice(0, 30)
  const highRiskCount = data.predictions.filter(p => p.risk_level === 'HIGH').length
  const overall = data.summary?.overall_risk || 'NO DATA'
  const running = data.summary?.simulation?.running || false
  const alertCount = data.summary?.active_alerts ?? 0


  return <div className="app-shell"><div className="portal-frame"><div className="portal-body"><aside className={`portal-sidebar ${menuOpen ? 'open' : ''}`}><div className="sidebar-brand"><Logo onClick={() => navigate('Dashboard')}/></div><button className="sidebar-close" onClick={() => setMenuOpen(false)} aria-label="Close menu"><X size={20}/></button><nav>{sidebarItems.map(([name, Icon]) => <button key={name} className={`side-link ${page === name ? 'active' : ''}`} onClick={() => navigate(name)}><Icon size={17} strokeWidth={1.8}/><span>{name}</span>{name === 'Alerts' && alertCount > 0 && <b>{alertCount}</b>}</button>)}</nav><div className="sidebar-foot"><div className="operator-avatar">DO</div><div><strong>Demo Operator</strong><span>Prototype workspace</span></div></div></aside>{menuOpen && <div className="mobile-scrim" onClick={() => setMenuOpen(false)}/>}<main className="portal-content"><div className="page-title"><button className="mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Open sections"><Menu size={21}/></button><div><h1>{page}</h1><p>{page === 'Dashboard' ? 'Mine condition monitoring and alerts' : page === 'Live Map' ? 'Fictional zones, sensors and risk levels' : 'GeoGuards demonstration workspace'}</p></div><span className="demo-mark"><i/> DEMONSTRATION ENVIRONMENT</span></div><div className="prototype-line"><ShieldAlert size={15}/><span>Prototype only: all built-in readings are simulated; risk rules and map positions are unvalidated.</span></div>{error && <div className="error-line"><AlertTriangle size={16}/>{error}</div>}{loading ? <div className="loading">Loading GeoGuards…</div> : <>

    {page === 'Dashboard' && <><div className="stat-grid"><Stat icon={AlertTriangle} value={alertCount} label="Active Alerts" tone="red"/><Stat icon={Mountain} value={highRiskCount.toString().padStart(2, '0')} label="High-Risk Zones" tone="sand"/><Stat icon={MapPinned} value={data.summary?.total_zones ?? 3} label="Monitored Zones" tone="cream"/><Stat icon={Radio} value={`${data.summary?.reporting_zones ?? 0}/${data.summary?.total_zones ?? 3}`} label="Reporting Zones" tone="green"/></div><div className="dashboard-grid"><Card title="Mine zone overview" subtitle="Real mine location with a sample red area" action={<button className="text-action" onClick={() => navigate('Live Map')}>Zone schematic <ArrowRight size={14}/></button>} className="map-card"><DemoMineMap/></Card><Card title="Recent Alerts" subtitle="Dashboard notifications only" action={<button className="text-action" onClick={() => navigate('Alerts')}>View all</button>} className="recent-card">{data.alerts.length ? data.alerts.slice(0, 5).map(a => <AlertItem key={a.id} alert={a} onOpen={alert => { setSelectedAlert(alert); navigate('Alerts') }}/>) : <Empty icon={Bell} title="No alerts yet" detail="Run a scenario or create a test alert."/>}<div className="recent-footer"><span>Overall demo risk</span><Badge level={overall}/></div></Card></div><div className="below-grid"><Card title="Current zone conditions" subtitle={`${zoneNames[selectedZone]} · ${currentReading ? 'simulated' : 'awaiting readings'}`} action={<select value={selectedZone} onChange={e => setSelectedZone(e.target.value)}>{data.zones.map(z => <option value={z.id} key={z.id}>{z.name}</option>)}</select>}><div className="mini-readings"><div><CloudRain size={18}/><span>Rainfall</span><strong>{currentReading?.rainfall ?? '—'} <small>mm/h</small></strong></div><div><Waves size={18}/><span>Moisture</span><strong>{currentReading?.soil_moisture ?? '—'} <small>%</small></strong></div><div><Activity size={18}/><span>Vibration</span><strong>{currentReading?.ground_vibration ?? '—'} <small>mm/s</small></strong></div><div><Gauge size={18}/><span>Displacement</span><strong>{currentReading?.displacement ?? '—'} <small>mm</small></strong></div></div></Card><Card title="Simulation controls" subtitle="Demonstration data source"><SimulatorControls running={running} scenario={data.summary?.simulation?.scenario} busy={busy} action={action}/></Card></div></>}

    {page === 'Live Map' && <><div className="map-intro"><div><span className="section-kicker">MINE ZONE EXPLORER</span><h2>Live Map</h2><p>Illustrative terrain and fictional zone locations. Select a marker for current sensor and rule status.</p></div><button className="outline-button compact" onClick={() => setShowZones(v => !v)}><SlidersHorizontal size={16}/>{showZones ? 'Hide' : 'Show'} zones</button></div><div className="live-map-layout"><Card title="Mine terrain view" subtitle="Generated illustration · not a georeferenced map" className="wide-map-card"><MineRiskMap zones={data.zones} predictions={data.predictions} selectedZone={selectedZone} onSelect={setSelectedZone} large showZones={showZones}/></Card><Card title="Selected zone" subtitle="Current demonstration status" className="zone-detail"><div className="detail-top"><span className="detail-icon"><MapPinned size={23}/></span><Badge level={currentRisk?.risk_level || 'NO DATA'}/></div><h2>{zoneNames[selectedZone]}</h2><p>{currentRisk?.reasons?.join(' · ') || 'No assessment yet. Start the simulator to populate this zone.'}</p><div className="detail-list"><div><span>Data source</span><strong>{currentRisk?.source || '—'}</strong></div><div><span>Updated</span><strong>{formatDate(currentRisk?.timestamp)}</strong></div><div><span>Risk model</span><strong>Provisional rules</strong></div><div><span>DEM layer</span><strong>Unavailable</strong></div></div><button className="brown-button full" onClick={() => navigate('Risk Analysis')}>Review risk analysis <ArrowRight size={16}/></button></Card></div></>}

    {page === 'Alerts' && <><div className="alerts-toolbar"><div><h2>Alert center</h2><p>Test alerts and rule triggers are recorded here. No external notifications are sent.</p></div><button className="brown-button" disabled={busy} onClick={() => action(() => post('/api/alerts/test', { zone_id: selectedZone, risk_level: 'HIGH' }))}><Bell size={16}/> Create test alert</button></div><div className="alerts-layout"><Card title="Recent alerts" subtitle="Newest first · dashboard delivery only" className="alert-list-card">{data.alerts.length ? data.alerts.map(a => <AlertItem key={a.id} alert={a} onOpen={setSelectedAlert}/>) : <Empty icon={Bell} title="No alerts recorded" detail="Start the simulator or create a test alert."/>}</Card><Card title="Alert Details" subtitle="Select an alert to inspect" className="alert-detail-card">{selectedAlert ? <><div className="alert-photo"><img src="/assets/hero-mine.png" alt="Illustrative generated mine landscape"/><span>Illustrative image</span></div><Badge level={selectedAlert.risk_level}/><h2>{selectedAlert.risk_level} demonstration risk</h2><p>{selectedAlert.message}</p><div className="detail-list"><div><span>Zone</span><strong>{zoneNames[selectedAlert.zone_id]}</strong></div><div><span>Time</span><strong>{formatDate(selectedAlert.timestamp)}</strong></div><div><span>Notification</span><strong>No delivery (test mode)</strong></div><div><span>Site alarm</span><strong>{selectedAlert.site_alarm}</strong></div></div>{!selectedAlert.acknowledged ? <button className="brown-button full" onClick={() => action(async () => { await patch(`/api/alerts/${selectedAlert.id}/acknowledge`); setSelectedAlert({ ...selectedAlert, acknowledged: true }) })}><Check size={16}/> Acknowledge alert</button> : <div className="acknowledged"><CheckCircle2 size={17}/> Acknowledged</div>}</> : <Empty icon={CircleHelp} title="Choose an alert" detail="Its details will appear here."/>}</Card></div></>}

    {page === 'Risk Analysis' && <><div className="analysis-note"><Gauge size={21}/><div><strong>Provisional rule-based risk assessment</strong><span>No trained ML model or calibrated event probability is installed. Thresholds are demonstration values.</span></div></div><div className="zone-card-grid">{data.zones.map(z => { const p = data.predictions.find(item => item.zone_id === z.id); return <Card key={z.id} title={z.name} subtitle={p ? `Updated ${formatDate(p.timestamp)}` : 'Awaiting readings'} action={<Badge level={p?.risk_level || 'NO DATA'}/>}><div className="zone-assessment"><span className="overline">RELEVANT CONDITIONS</span>{p ? <ul>{p.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul> : <Empty icon={Gauge} title="No assessment yet" detail="Start the simulator."/>}<div className="assessment-meta"><span>Source: {p?.source || '—'}</span><span>Probability: unavailable</span></div></div></Card> })}</div></>}

    {page === 'Sensor Data' && <><Card title="Sensor simulation" subtitle="Correlated, time-dependent scenarios across three fictional mine zones"><SimulatorControls running={running} scenario={data.summary?.simulation?.scenario} busy={busy} action={action}/></Card><div className="section-heading"><div><h2>Live conditions</h2><p>Every reading below is generated by software.</p></div><select value={selectedZone} onChange={e => setSelectedZone(e.target.value)}>{data.zones.map(z => <option key={z.id} value={z.id}>{z.name}</option>)}</select></div><div className="stat-grid sensor-stats"><Stat icon={CloudRain} value={currentReading?.rainfall ?? '—'} label="Rainfall · mm/h"/><Stat icon={Waves} value={currentReading?.soil_moisture ?? '—'} label="Soil moisture · %" tone="green"/><Stat icon={Activity} value={currentReading?.ground_vibration ?? '—'} label="Vibration · mm/s" tone="cream"/><Stat icon={Gauge} value={currentReading?.displacement ?? '—'} label="Displacement · mm" tone="red"/></div><div className="trend-grid">{chartFields.map(([field, label, unit, color]) => <Trend key={field} field={field} label={label} unit={unit} color={color} history={zoneHistory}/>)}</div></>}

    {page === 'Image Detection' && <><div className="analysis-note"><ImageIcon size={21}/><div><strong>Geological image model unavailable</strong><span>No trained YOLO weights are included. Uploads are recorded; no detections are fabricated.</span></div></div><div className="two-column"><Card title="Upload slope image" subtitle="JPEG, PNG or WebP · maximum 5 MB"><div className="upload-area"><UploadCloud size={35}/><strong>{file?.name || 'Select a mine slope image'}</strong><span>Image analysis remains unavailable until validated geological weights are installed.</span><input type="file" accept="image/jpeg,image/png,image/webp" onChange={e => setFile(e.target.files?.[0] || null)}/></div><div className="upload-actions"><select value={selectedZone} onChange={e => setSelectedZone(e.target.value)}>{data.zones.map(z => <option key={z.id} value={z.id}>{z.name}</option>)}</select><button className="brown-button" disabled={!file || busy} onClick={() => action(async () => setUploadResult(await upload('/api/detect', file, selectedZone)))}>Record upload</button></div>{uploadResult && <div className="upload-message">{uploadResult.message}</div>}</Card><Card title="Upload history" subtitle="No geological detections claimed">{data.detections.length ? data.detections.map(d => <div className="upload-row" key={d.id}><ImageIcon size={18}/><div><strong>{d.filename}</strong><span>{zoneNames[d.zone_id]} · {formatDate(d.timestamp)}</span></div><Badge level="UNAVAILABLE"/></div>) : <Empty icon={ImageIcon} title="No images uploaded"/>}</Card></div></>}

    {page === 'Reports' && <><div className="report-stats"><Stat icon={Bell} value={data.alerts.length} label="Recent Alerts" tone="red"/><Stat icon={Database} value={data.history.length} label="Readings in View"/><Stat icon={Gauge} value={data.predictions.length} label="Current Assessments" tone="cream"/><Stat icon={MapPinned} value={data.zones.length} label="Demo Zones" tone="green"/></div><div className="reports-grid"><Card title="Rainfall trend" subtitle="Latest simulated observations"><ReportBar history={data.history}/></Card><Card title="Risk distribution" subtitle="Current zone-level classifications"><RiskDonut distribution={data.distribution}/></Card></div><Card title="Reading history" subtitle="Recent simulated records across all zones"><div className="table-scroll"><table><thead><tr><th>Time</th><th>Zone</th><th>Rainfall</th><th>Moisture</th><th>Displacement</th><th>Source</th></tr></thead><tbody>{data.history.slice(0, 50).map((r, i) => <tr key={`${r.timestamp}-${r.zone_id}-${i}`}><td>{formatDate(r.timestamp)}</td><td>{zoneNames[r.zone_id]}</td><td>{r.rainfall} mm/h</td><td>{r.soil_moisture}%</td><td>{r.displacement} mm</td><td><Badge level="SIMULATED"/></td></tr>)}</tbody></table>{!data.history.length && <Empty icon={Database} title="No history yet"/>}</div></Card></>}

    {page === 'Settings' && <><div className="two-column"><Card title="System status" subtitle="Current prototype configuration"><div className="settings-list"><div><span>Data storage</span><strong>{data.summary?.storage === 'mongodb' ? 'MongoDB' : 'Volatile memory'}</strong></div><div><span>Risk engine</span><strong>Provisional rules</strong></div><div><span>Image detection</span><strong>Unavailable</strong></div><div><span>External notifications</span><strong>Disabled</strong></div><div><span>Physical hardware</span><strong>Not connected</strong></div></div></Card><Card title="Data provenance & safety" subtitle="Read before demonstration"><div className="safety-copy"><p>Built-in readings are generated by software. Zone positions and terrain art are fictional and have no survey coordinates.</p><p>Risk thresholds have not been validated by a geotechnical engineer. No event probability or time-to-failure forecast is provided.</p><p>Dashboard indicators do not activate a physical siren, lights, or public-address system.</p></div></Card></div><Card title="Simulation controls" subtitle="Start, pause or switch a scenario"><SimulatorControls running={running} scenario={data.summary?.simulation?.scenario} busy={busy} action={action}/></Card></>}

  </>}</main></div></div></div>
}

function ReportBar({ history }) {
  const points = [...history].slice(0, 22).reverse().map((r, i) => ({ n: i + 1, value: r.rainfall }))
  return points.length ? <div className="report-chart"><ResponsiveContainer width="100%" height={215}><BarChart data={points} margin={{ top: 8, right: 10, left: -25, bottom: 0 }}><CartesianGrid vertical={false} stroke="#eee2d6"/><XAxis dataKey="n" tick={{ fontSize: 10, fill: '#9f8877' }} axisLine={false} tickLine={false} minTickGap={18}/><YAxis tick={{ fontSize: 10, fill: '#9f8877' }} axisLine={false} tickLine={false}/><Tooltip contentStyle={{ border: '1px solid #e5d8ca', borderRadius: 8 }}/><Bar dataKey="value" fill="#be8b65" radius={[4, 4, 0, 0]}/></BarChart></ResponsiveContainer></div> : <Empty icon={BarChart3} title="No trend data yet" detail="Start the simulator."/>
}

function RiskDonut({ distribution }) {
  const points = ['LOW', 'MEDIUM', 'HIGH'].map(name => ({ name, value: distribution[name] || 0 }))
  const total = points.reduce((sum, p) => sum + p.value, 0)
  return total ? <div className="donut-layout"><div className="donut-chart"><ResponsiveContainer width="100%" height={215}><PieChart><Pie data={points} dataKey="value" innerRadius={65} outerRadius={91} paddingAngle={2} stroke="none">{points.map(p => <Cell key={p.name} fill={riskColors[p.name]}/>)}</Pie></PieChart></ResponsiveContainer><div className="donut-center"><strong>{total}</strong><span>Zones</span></div></div><div className="donut-legend">{points.map(p => <div key={p.name}><span><i style={{ background: riskColors[p.name] }}/>{pretty(p.name)} risk</span><strong>{Math.round(p.value / total * 100)}%</strong></div>)}</div></div> : <Empty icon={BarChart3} title="No risk distribution" detail="Start the simulator."/>
}
