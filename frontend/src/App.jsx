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
import MineTerrain3D from './MineTerrain3D.jsx'
import MineRiskMap from './MineRiskMap.jsx'

const sidebarItems = [
  ['Dashboard', LayoutDashboard], ['Live Map', MapPinned], ['Alerts', Bell],
  ['Risk Analysis', BarChart3], ['Sensor Data', Activity], ['Terrain Analysis', Mountain], ['Image Detection', ImageIcon],
  ['Reports', FileText], ['Settings', Settings],
]
const zoneNames = { north_wall: 'North Wall', east_bench: 'East Bench', south_ramp: 'South Ramp' }
const zoneName = id => zoneNames[id] || (id?.startsWith('LOC_') ? `Demo ${id}` : pretty(id))
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
  return <Card title={label} subtitle={`Synthetic readings · ${unit}`} className="trend-card">
    {points.length ? <ResponsiveContainer width="100%" height={190}><AreaChart data={points} margin={{ top: 12, right: 10, left: -24, bottom: 0 }}><defs><linearGradient id={`area-${field}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={0.33}/><stop offset="100%" stopColor={color} stopOpacity={0.02}/></linearGradient></defs><CartesianGrid vertical={false} stroke="#e9ddd1"/><XAxis dataKey="t" tick={{ fontSize: 10, fill: '#9c8676' }} axisLine={false} tickLine={false} minTickGap={28}/><YAxis tick={{ fontSize: 10, fill: '#9c8676' }} axisLine={false} tickLine={false}/><Tooltip contentStyle={{ background: '#fff9f2', border: '1px solid #e8d9c9', borderRadius: 10 }}/><Area type="monotone" dataKey="value" stroke={color} fill={`url(#area-${field})`} strokeWidth={2.5} dot={false}/></AreaChart></ResponsiveContainer> : <Empty icon={Activity} title="No readings yet" detail="Start the simulator to see this trend."/>}
  </Card>
}

function AlertItem({ alert, onOpen }) {
  return <button className="alert-item" onClick={() => onOpen(alert)}><span className={`alert-symbol ${alert.risk_level.toLowerCase()}`}><AlertTriangle size={18}/></span><span className="alert-copy"><strong>{alert.risk_level === 'HIGH' ? 'Elevated rockfall risk' : 'Conditions require review'}</strong><small>{zoneName(alert.zone_id)} · {formatDate(alert.timestamp)}</small></span><Badge level={alert.risk_level}/></button>
}

function SimulatorControls({ running, scenario, busy, action }) {
  return <div className="sim-controls"><div><label htmlFor="scenario">Demonstration scenario</label><select id="scenario" value={scenario || 'normal'} disabled={busy} onChange={e => action(() => post('/api/simulator/scenario', { scenario: e.target.value }))}><option value="normal">Normal conditions</option><option value="heavy_rain">Heavy rainfall</option><option value="slope_movement">Slope movement</option></select></div><button className="brown-button" disabled={busy} onClick={() => action(() => post(running ? '/api/simulator/stop' : '/api/simulator/start'))}>{running ? <Pause size={16}/> : <Play size={16}/>} {running ? 'Pause simulation' : 'Start simulation'}</button><span className={`sim-state ${running ? 'running' : ''}`}><i/>{running ? 'Generating readings every 5 seconds' : 'Simulator paused'}</span></div>
}

function DemoDatasetControls({ busy, onImport, result }) {
  return <div className="sim-controls"><button className="brown-button" disabled={busy} onClick={onImport}><Database size={16}/> Load supplied CSV sample</button><span>Synthetic hourly readings from 2023 · 10 fictional locations · provisional rules only.</span>{result && <span>Imported {result.imported} readings; skipped {result.skipped_existing} already loaded. No event labels were imported.</span>}<span>Rainfall and displacement rates use a provisional one-hour mapping. These assessments are not safety forecasts.</span></div>
}

function DetectionPreview({ imageUrl, result }) {
  if (!imageUrl || !result?.image_width || !result?.image_height) return null
  return <div className="detection-preview"><img src={imageUrl} alt="Uploaded image with YOLO detection boxes"/>{result.detections.map((item, index) => { const [x1, y1, x2, y2] = item.box_xyxy; return <span key={index} className="detection-box" style={{ left: `${x1 / result.image_width * 100}%`, top: `${y1 / result.image_height * 100}%`, width: `${(x2 - x1) / result.image_width * 100}%`, height: `${(y2 - y1) / result.image_height * 100}%` }}><b>{item.class_name} {(item.confidence * 100).toFixed(1)}%</b></span> })}</div>
}

function MLStatusPanel({ status, comparison, assessments }) {
  const latest = assessments?.[0]
  const metrics = ['precision', 'recall', 'f1', 'pr_auc', 'false_alarms_per_monitored_zone_day']
  return <Card title="Research ML status" subtitle="Random Forest and XGBoost · research workflow only" className="ml-status-card">
    <div className="detail-list"><div><span>Dashboard assessment source</span><strong>DEMO_RULES</strong></div>
      <div><span>Research model</span><strong>{status?.available ? `${status.model_name} · ${status.model_version}` : 'Unavailable'}</strong></div>
      <div><span>Validation status</span><strong>{status?.validation_status || 'Unavailable'}</strong></div>
      <div><span>Prediction horizon</span><strong>{status?.prediction_horizon_hours ? `${status.prediction_horizon_hours} hours` : 'Not active'}</strong></div>
      <div><span>Latest research assessment</span><strong>{latest ? formatDate(latest.assessment_timestamp) : 'None'}</strong></div>
      <div><span>Input quality</span><strong>{latest?.data_quality || 'No research input'}</strong></div>
      <div><span>Research category</span><strong>{latest?.risk_level || 'Unavailable'}</strong></div>
      <div><span>Individual explanation</span><strong>{latest?.top_contributing_features?.length ? latest.top_contributing_features.map(item => item.feature).join(', ') : 'Unavailable'}</strong></div>
    </div>
    <p className="ml-status-note">{status?.reason || 'No real-data model has been activated.'} Research scores are not calibrated event probabilities or operational alerts.</p>
    {comparison?.available && <div className="table-scroll"><table><thead><tr><th>Held-out test metric</th><th>Random Forest</th><th>XGBoost</th></tr></thead><tbody>{metrics.map(metric => <tr key={metric}><td>{pretty(metric)}</td><td>{comparison.models?.random_forest?.test_metrics?.[metric] ?? 'Unavailable'}</td><td>{comparison.models?.xgboost?.test_metrics?.[metric] ?? 'Unavailable'}</td></tr>)}</tbody></table><p className="ml-status-note">Research evaluation only · no model selected for safety use.</p></div>}
    {assessments?.length > 0 && <div className="table-scroll"><table><thead><tr><th>Assessment time</th><th>Zone</th><th>Model</th><th>Source</th><th>Quality</th></tr></thead><tbody>{assessments.map(item => <tr key={item.id}><td>{formatDate(item.assessment_timestamp)}</td><td>{zoneName(item.zone_id)}</td><td>{item.model_name} · {item.model_version}</td><td>{item.prediction_source}</td><td>{item.data_quality}</td></tr>)}</tbody></table></div>}
  </Card>
}

export default function App() {
  const [page, setPage] = useState(pageFromHash)
  const [menuOpen, setMenuOpen] = useState(false)
  const [selectedZone, setSelectedZone] = useState('north_wall')
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [showZones, setShowZones] = useState(true)
  const [file, setFile] = useState(null)
  const [terrainFile, setTerrainFile] = useState(null)
  const [terrainResult, setTerrainResult] = useState(null)
  const [uploadResult, setUploadResult] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [data, setData] = useState({ summary: null, sensors: [], status: [], history: [], predictions: [], predictionHistory: [], demoEvents: null, alerts: [], detections: [], visionStatus: null, terrainAnalyses: [], zones: [], distribution: {}, mlStatus: null, mlComparison: null, mlAssessments: [] })
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [importResult, setImportResult] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [summary, sensors, status, history, predictions, predictionHistory, demoEvents, alerts, detections, visionStatus, terrainAnalyses, zones, distribution, mlStatus, mlComparison, mlAssessments] = await Promise.all([
        get('/api/dashboard/summary'), get('/api/sensors/latest'), get('/api/sensors/status'), get('/api/sensors/history?limit=500'),
        get('/api/predictions/latest'), get('/api/predictions?limit=100'), get('/api/demo/events'), get('/api/alerts?limit=30'), get('/api/detections?limit=20'), get('/api/detect/status'), get('/api/terrain/analyses?limit=20'),
        get('/api/zones'), get('/api/dashboard/risk-distribution'), get('/api/ml/status'), get('/api/ml/comparison'), get('/api/ml/assessments?limit=20'),
      ])
      setData({ summary, sensors, status, history, predictions, predictionHistory, demoEvents, alerts, detections, visionStatus, terrainAnalyses, zones, distribution, mlStatus, mlComparison, mlAssessments })
      setError('')
    } catch (e) { setError(e.response?.data?.detail || 'Cannot reach the API. Start the FastAPI backend on port 8000.') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh(); const id = setInterval(refresh, 5000); return () => clearInterval(id) }, [refresh])
  useEffect(() => { const onHashChange = () => setPage(pageFromHash()); window.addEventListener('hashchange', onHashChange); return () => window.removeEventListener('hashchange', onHashChange) }, [])
  useEffect(() => {
    if (!menuOpen) return undefined
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previous }
  }, [menuOpen])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])
  async function action(fn) { setBusy(true); try { await fn(); await refresh() } catch (e) { setError(e.response?.data?.detail || e.message) } finally { setBusy(false) } }
  async function loadDemo() { await action(async () => { const result = await post('/api/demo/import?limit_per_location=30'); setImportResult(result); setSelectedZone('LOC_01') }) }
  function navigate(next) { window.location.hash = next.toLowerCase().replaceAll(' ', '-'); setPage(next); setMenuOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  const currentRisk = data.predictions.find(p => p.zone_id === selectedZone)
  const currentReading = data.sensors.find(r => r.zone_id === selectedZone)
  const isCsvZone = selectedZone.startsWith('LOC_')
  const currentStatus = data.status.find(item => item.zone_id === selectedZone)
  const zoneAlert = data.alerts.find(item => item.zone_id === selectedZone)
  const zoneDetection = data.detections.find(item => item.zone_id === selectedZone)
  const zoneTerrain = data.terrainAnalyses.find(item => item.zone_id === selectedZone)
  const zoneHistory = data.history.filter(r => r.zone_id === selectedZone).slice(0, 30)
  const highRiskCount = data.predictions.filter(p => p.risk_level === 'HIGH').length
  const overall = data.summary?.overall_risk || 'NO DATA'
  const running = data.summary?.simulation?.running || false
  const alertCount = data.summary?.active_alerts ?? 0


  return <div className="app-shell"><div className="portal-frame"><div className="portal-body"><aside className={`portal-sidebar ${menuOpen ? 'open' : ''}`}><div className="sidebar-brand"><Logo onClick={() => navigate('Dashboard')}/></div><button className="sidebar-close" onClick={() => setMenuOpen(false)} aria-label="Close menu"><X size={20}/></button><nav>{sidebarItems.map(([name, Icon]) => <button key={name} className={`side-link ${page === name ? 'active' : ''}`} onClick={() => navigate(name)}><Icon size={17} strokeWidth={1.8}/><span>{name}</span>{name === 'Alerts' && alertCount > 0 && <b>{alertCount}</b>}</button>)}</nav><div className="sidebar-foot"><div className="operator-avatar">DO</div><div><strong>Demo Operator</strong><span>Prototype workspace</span></div></div></aside>{menuOpen && <div className="mobile-scrim" onClick={() => setMenuOpen(false)}/>}<main className="portal-content"><div className="page-title"><button className="mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Open sections"><Menu size={21}/></button><div><h1>{page}</h1><p>{page === 'Dashboard' ? 'Mine condition monitoring and alerts' : page === 'Live Map' ? 'Fictional zones, sensors and risk levels' : 'GeoGuards demonstration workspace'}</p></div><span className="demo-mark"><i/> DEMONSTRATION ENVIRONMENT</span></div><div className="prototype-line"><ShieldAlert size={15}/><span>Prototype only: all built-in readings are simulated; risk rules and map positions are unvalidated.</span></div>{error && <div className="error-line"><AlertTriangle size={16}/>{error}</div>}{loading ? <div className="loading">Loading GeoGuards…</div> : <>

    {page === 'Dashboard' && <><div className="stat-grid"><Stat icon={AlertTriangle} value={alertCount} label="Active Alerts" tone="red"/><Stat icon={Mountain} value={highRiskCount.toString().padStart(2, '0')} label="High Demo Risk Results" tone="sand"/><Stat icon={MapPinned} value={data.summary?.total_zones ?? 0} label="Demo Locations" tone="cream"/><Stat icon={Radio} value={`${data.summary?.reporting_zones ?? 0}/${data.summary?.total_zones ?? 0}`} label="Recent Readings" tone="green"/></div><div className="dashboard-grid"><Card title="Mine zone overview" subtitle="Fictional mine schematic with zone risk areas" action={<button className="text-action" onClick={() => navigate('Live Map')}>Open 3D view <ArrowRight size={14}/></button>} className="map-card"><MineRiskMap zones={data.zones} predictions={data.predictions} selectedZone={selectedZone} onSelect={setSelectedZone}/></Card><Card title="Recent Alerts" subtitle="Dashboard notifications only" action={<button className="text-action" onClick={() => navigate('Alerts')}>View all</button>} className="recent-card">{data.alerts.length ? data.alerts.slice(0, 5).map(a => <AlertItem key={a.id} alert={a} onOpen={alert => { setSelectedAlert(alert); navigate('Alerts') }}/>) : <Empty icon={Bell} title="No alerts yet" detail="Run a scenario or create a test alert."/>}<div className="recent-footer"><span>Overall demo risk</span><Badge level={overall}/></div></Card></div><div className="below-grid"><Card title="Latest zone readings" subtitle={`${zoneName(selectedZone)} · ${currentReading?.dataset_provenance ? 'historical synthetic CSV' : currentReading ? 'simulated' : 'awaiting readings'}`} action={<select value={selectedZone} onChange={e => setSelectedZone(e.target.value)}>{data.zones.map(z => <option value={z.id} key={z.id}>{z.name}</option>)}</select>}><div className="mini-readings"><div><CloudRain size={18}/><span>Rainfall</span><strong>{currentReading?.rainfall ?? '—'} <small>mm/h</small></strong></div><div><Waves size={18}/><span>Moisture</span><strong>{currentReading?.soil_moisture ?? '—'} <small>%</small></strong></div><div><Activity size={18}/><span>Vibration</span><strong>{currentReading?.ground_vibration ?? '—'} <small>mm/s</small></strong></div><div><Gauge size={18}/><span>Displacement</span><strong>{currentReading?.displacement ?? '—'} <small>{isCsvZone ? 'mm/h' : 'mm'}</small></strong></div></div></Card><Card title="Simulation controls" subtitle="Demonstration data source"><SimulatorControls running={running} scenario={data.summary?.simulation?.scenario} busy={busy} action={action}/></Card></div></>}

    {page === 'Live Map' && <><div className="map-intro"><div><span className="section-kicker">MINE ZONE EXPLORER</span><h2>Live Map</h2><p>Interactive 3D demonstration terrain and fictional zone locations. Select a marker for current sensor and rule status.</p></div><button className="outline-button compact" onClick={() => setShowZones(v => !v)}><SlidersHorizontal size={16}/>{showZones ? 'Hide' : 'Show'} zones</button></div><div className="live-map-layout"><Card title="Mine terrain view" subtitle="Interactive 3D schematic · not surveyed or georeferenced" className="wide-map-card"><MineTerrain3D zones={data.zones} predictions={data.predictions} selectedZone={selectedZone} onSelect={setSelectedZone} showZones={showZones}/></Card><Card title="Selected zone" subtitle="Latest stored demonstration status" className="zone-detail"><div className="detail-top"><span className="detail-icon"><MapPinned size={23}/></span><Badge level={currentRisk?.risk_level || 'NO DATA'}/></div><h2>{zoneName(selectedZone)}</h2><p>{currentRisk?.reasons?.join(' · ') || 'No assessment yet. Start the simulator to populate this zone.'}</p><div className="detail-list"><div><span>Data source</span><strong>{currentRisk?.dataset_provenance ? 'historical synthetic CSV' : currentRisk?.source || '—'}</strong></div><div><span>Input time</span><strong>{formatDate(currentRisk?.input_timestamp || currentRisk?.timestamp)}</strong></div><div><span>Risk model</span><strong>Provisional rules</strong></div><div><span>CSV slope angle</span><strong>{currentReading?.raw_demo_features?.slope_angle_deg != null ? `${currentReading.raw_demo_features.slope_angle_deg}° · synthetic` : '—'}</strong></div><div><span>CSV elevation</span><strong>{currentReading?.raw_demo_features?.elevation_m != null ? `${currentReading.raw_demo_features.elevation_m} m · synthetic` : '—'}</strong></div><div><span>Uploaded DEM</span><strong>{zoneTerrain ? `${zoneTerrain.filename} · unverified zone tag` : 'Unavailable'}</strong></div><div><span>Latest alert</span><strong>{zoneAlert ? `${zoneAlert.risk_level} · ${formatDate(zoneAlert.timestamp)}` : 'None'}</strong></div><div><span>Image analysis</span><strong>{zoneDetection?.status || 'None'}</strong></div></div><button className="brown-button full" onClick={() => navigate('Risk Analysis')}>Review risk analysis <ArrowRight size={16}/></button></Card></div></>}

    {page === 'Alerts' && <><div className="alerts-toolbar"><div><h2>Alert center</h2><p>Test alerts and rule triggers are recorded here. No external notifications are sent.</p></div><button className="brown-button" disabled={busy} onClick={() => action(() => post('/api/alerts/test', { zone_id: selectedZone, risk_level: 'HIGH' }))}><Bell size={16}/> Create test alert</button></div><div className="alerts-layout"><Card title="Recent alerts" subtitle="Newest first · dashboard delivery only" className="alert-list-card">{data.alerts.length ? data.alerts.map(a => <AlertItem key={a.id} alert={a} onOpen={setSelectedAlert}/>) : <Empty icon={Bell} title="No alerts recorded" detail="Start the simulator or create a test alert."/>}</Card><Card title="Alert Details" subtitle="Select an alert to inspect" className="alert-detail-card">{selectedAlert ? <><div className="alert-photo"><img src="/assets/hero-mine.png" alt="Illustrative generated mine landscape"/><span>Illustrative image</span></div><Badge level={selectedAlert.risk_level}/><h2>{selectedAlert.risk_level} demonstration risk</h2><p>{selectedAlert.message}</p>{selectedAlert.reasons?.length > 0 && <p><strong>Factors:</strong> {selectedAlert.reasons.join(' · ')}</p>}{selectedAlert.recommended_action && <p><strong>Suggested action:</strong> {selectedAlert.recommended_action}</p>}<div className="detail-list"><div><span>Zone</span><strong>{zoneName(selectedAlert.zone_id)}</strong></div><div><span>Time</span><strong>{formatDate(selectedAlert.timestamp)}</strong></div><div><span>Notification</span><strong>No delivery (test mode)</strong></div><div><span>Site alarm</span><strong>{selectedAlert.site_alarm}</strong></div></div>{!selectedAlert.acknowledged ? <button className="brown-button full" onClick={() => action(async () => { await patch(`/api/alerts/${selectedAlert.id}/acknowledge`); setSelectedAlert({ ...selectedAlert, acknowledged: true }) })}><Check size={16}/> Acknowledge alert</button> : <div className="acknowledged"><CheckCircle2 size={17}/> Acknowledged</div>}</> : <Empty icon={CircleHelp} title="Choose an alert" detail="Its details will appear here."/>}</Card></div></>}

    {page === 'Risk Analysis' && <><div className="analysis-note"><Gauge size={21}/><div><strong>Provisional rule-based risk assessment</strong><span>No validated ML model or calibrated event probability is installed. Thresholds are demonstration values.</span></div></div><MLStatusPanel status={data.mlStatus} comparison={data.mlComparison} assessments={data.mlAssessments}/><div className="zone-card-grid">{data.zones.map(z => { const p = data.predictions.find(item => item.zone_id === z.id); return <Card key={z.id} title={z.name} subtitle={p ? `Updated ${formatDate(p.timestamp)}` : 'Awaiting readings'} action={<Badge level={p?.risk_level || 'NO DATA'}/>}><div className="zone-assessment"><span className="overline">RELEVANT CONDITIONS</span>{p ? <ul>{p.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul> : <Empty icon={Gauge} title="No assessment yet" detail="Start the simulator."/>}{p?.recommended_action && <p><strong>Suggested action:</strong> {p.recommended_action}</p>}<div className="assessment-meta"><span>Source: {p?.source || '—'} · {p?.assessment_type || 'DEMO_RULES'}</span><span>Input: {formatDate(p?.input_timestamp || p?.timestamp)}</span><span>Probability: unavailable</span></div></div></Card> })}</div></>}

    {page === 'Sensor Data' && <><Card title="Supplied CSV demonstration data" subtitle="Separate source files aligned by timestamp and location_id"><DemoDatasetControls busy={busy} onImport={loadDemo} result={importResult}/></Card><Card title="Sensor simulation" subtitle="Correlated, time-dependent scenarios across three fictional mine zones"><SimulatorControls running={running} scenario={data.summary?.simulation?.scenario} busy={busy} action={action}/></Card><div className="section-heading"><div><h2>Latest stored conditions</h2><p>Every reading below is synthetic. CSV observations are historical demonstrations, not live sensors.</p></div><select value={selectedZone} onChange={e => setSelectedZone(e.target.value)}>{data.zones.map(z => <option key={z.id} value={z.id}>{z.name}</option>)}</select></div><div className="stat-grid sensor-stats"><Stat icon={CloudRain} value={currentReading?.rainfall ?? '—'} label="Rainfall · mm/h"/><Stat icon={Waves} value={currentReading?.soil_moisture ?? '—'} label="Soil moisture · %" tone="green"/><Stat icon={Activity} value={currentReading?.ground_vibration ?? '—'} label="Vibration · mm/s" tone="cream"/><Stat icon={Gauge} value={currentReading?.displacement ?? '—'} label={`Displacement · ${isCsvZone ? 'mm/h' : 'mm'}`} tone="red"/></div><Card title="Source status" subtitle="Last received reading; hardware connection is unverified"><div className="detail-list"><div><span>Selected location</span><strong>{zoneName(selectedZone)}</strong></div><div><span>Status</span><strong>{pretty(currentStatus?.status || 'no_readings')}</strong></div><div><span>Last observation</span><strong>{formatDate(currentStatus?.last_reading_at)}</strong></div><div><span>Assessment</span><strong>{currentRisk?.assessment_type || 'No assessment'}</strong></div></div>{currentRisk?.reasons?.length > 0 && <p><strong>Rule factors:</strong> {currentRisk.reasons.join(' · ')}</p>}</Card><div className="trend-grid">{chartFields.map(([field, label, unit, color]) => <Trend key={field} field={field} label={label} unit={isCsvZone && field === 'displacement' ? 'mm/h' : unit} color={color} history={zoneHistory}/>)}</div></>}

    {page === 'Terrain Analysis' && <><div className="analysis-note"><Mountain size={21}/><div><strong>Uploaded DEM analysis</strong><span>ESRI ASCII elevation grid only. Results are descriptive; no surveyed mine alignment or hazard validation is claimed.</span></div></div><div className="two-column"><Card title="Analyze elevation grid" subtitle=".asc or .txt · up to 10 MB"><div className="upload-area"><UploadCloud size={35}/><strong>{terrainFile?.name || 'Select an ESRI ASCII DEM'}</strong><span>Slope, aspect, elevation and local roughness are calculated from the uploaded raster.</span><input type="file" accept=".asc,.txt,text/plain" onChange={e => setTerrainFile(e.target.files?.[0] || null)}/></div><div className="upload-actions"><select value={selectedZone} onChange={e => setSelectedZone(e.target.value)}>{data.zones.map(z => <option key={z.id} value={z.id}>{z.name}</option>)}</select><button className="brown-button" disabled={!terrainFile || busy} onClick={() => action(async () => setTerrainResult(await upload('/api/terrain/analyze', terrainFile, selectedZone)))}>Analyze DEM</button></div><p>Selected zone is a user tag only; geographic overlap is not verified.</p></Card><Card title="Latest analysis" subtitle="Descriptive terrain statistics">{(terrainResult || data.terrainAnalyses[0]) ? (() => { const t = terrainResult || data.terrainAnalyses[0]; return <div className="detail-list"><div><span>File</span><strong>{t.filename}</strong></div><div><span>Grid</span><strong>{t.ncols} × {t.nrows} cells</strong></div><div><span>Elevation</span><strong>{t.elevation_min}–{t.elevation_max}</strong></div><div><span>Mean slope</span><strong>{t.slope_mean_deg}°</strong></div><div><span>Maximum slope</span><strong>{t.slope_max_deg}°</strong></div><div><span>Mean aspect</span><strong>{t.aspect_mean_deg == null ? 'Flat' : `${t.aspect_mean_deg}°`}</strong></div><div><span>Mean local relief</span><strong>{t.roughness_mean_elevation_range}</strong></div><div><span>Mine georeferencing</span><strong>Unverified</strong></div></div> })() : <Empty icon={Mountain} title="No DEM analyzed" detail="Upload an ESRI ASCII elevation grid."/>}</Card></div></>}

    {page === 'Image Detection' && <><div className="analysis-note"><ImageIcon size={21}/><div><strong>{data.visionStatus?.available ? (data.visionStatus?.mode === 'general_objects_demo' ? 'General object detection · demo' : 'Configured geological YOLO · unvalidated') : 'Geological image model unavailable'}</strong><span>{data.visionStatus?.reason || 'No trained YOLO weights are included. Uploads are recorded; no detections are fabricated.'}</span></div></div><div className="two-column"><Card title="Upload slope image" subtitle="JPEG, PNG or WebP · maximum 5 MB"><div className="upload-area"><UploadCloud size={35}/><strong>{file?.name || 'Select a mine slope image'}</strong><span>{data.visionStatus?.available ? (data.visionStatus?.mode === 'general_objects_demo' ? 'Detects general object classes only; no rockfall hazard assessment.' : 'Configured weights can detect objects, but cannot predict future rockfall.') : 'Image analysis remains unavailable until geological weights are configured.'}</span><input type="file" accept="image/jpeg,image/png,image/webp" onChange={e => setFile(e.target.files?.[0] || null)}/></div><div className="upload-actions"><select value={selectedZone} onChange={e => setSelectedZone(e.target.value)}>{data.zones.map(z => <option key={z.id} value={z.id}>{z.name}</option>)}</select><button className="brown-button" disabled={!file || busy} onClick={() => action(async () => { const result = await upload('/api/detect', file, selectedZone); setUploadResult(result); setPreviewUrl(URL.createObjectURL(file)) })}>{data.visionStatus?.available ? 'Analyze image' : 'Record upload'}</button></div>{uploadResult && <><DetectionPreview imageUrl={previewUrl} result={uploadResult}/><div className="upload-message">{uploadResult.message}{uploadResult.detections?.map((d, i) => <div key={i}>{d.class_name} · {(d.confidence * 100).toFixed(1)}% · box {d.box_xyxy.join(', ')}</div>)}</div></>}</Card><Card title="Upload history" subtitle="Stored uploads and unvalidated inference status">{data.detections.length ? data.detections.map(d => <div className="upload-row" key={d.id}><ImageIcon size={18}/><div><strong>{d.filename}</strong><span>{zoneName(d.zone_id)} · {formatDate(d.timestamp)}</span></div><Badge level={d.status?.startsWith('analyzed_') ? 'DEMO' : 'UNAVAILABLE'}/></div>) : <Empty icon={ImageIcon} title="No images uploaded"/>}</Card></div></>}

    {page === 'Reports' && <><div className="report-stats"><Stat icon={Bell} value={data.alerts.length} label="Recent Alerts" tone="red"/><Stat icon={Database} value={data.history.length} label="Readings in View"/><Stat icon={Gauge} value={data.predictions.length} label="Current Assessments" tone="cream"/><Stat icon={MapPinned} value={data.zones.length} label="Demo Zones" tone="green"/></div><div className="reports-grid"><Card title="Rainfall trend" subtitle="Latest simulated observations"><ReportBar history={data.history}/></Card><Card title="Risk distribution" subtitle="Current zone-level classifications"><RiskDonut distribution={data.distribution}/></Card></div><Card title="Reading history" subtitle="Recent simulated records across all zones"><div className="table-scroll"><table><thead><tr><th>Time</th><th>Zone</th><th>Rainfall</th><th>Moisture</th><th>Displacement</th><th>Source</th></tr></thead><tbody>{data.history.slice(0, 50).map((r, i) => <tr key={`${r.timestamp}-${r.zone_id}-${i}`}><td>{formatDate(r.timestamp)}</td><td>{zoneName(r.zone_id)}</td><td>{r.rainfall} mm/h</td><td>{r.soil_moisture}%</td><td>{r.displacement} {r.dataset_provenance ? 'mm/h' : 'mm'}</td><td><Badge level="SIMULATED"/></td></tr>)}</tbody></table>{!data.history.length && <Empty icon={Database} title="No history yet"/>}</div></Card><Card title="Supplied synthetic event records" subtitle="Positive rule-generated timestamps only · unlisted periods are unknown"><div className="table-scroll"><table><thead><tr><th>Time</th><th>Location</th><th>Label source</th></tr></thead><tbody>{data.demoEvents?.events?.map((event, i) => <tr key={i}><td>{formatDate(event.timestamp)}</td><td>{zoneName(event.location_id)}</td><td>{event.event_label_source}</td></tr>)}</tbody></table>{!data.demoEvents?.events?.length && <Empty icon={Database} title="No event file available" detail="Check the demo dataset status endpoint."/>}</div><p>These synthetic positives are not used to assess current risk or calculate model accuracy.</p></Card><Card title="Assessment history" subtitle="Stored demonstration rule results; no calibrated probabilities"><div className="table-scroll"><table><thead><tr><th>Input time</th><th>Zone</th><th>Rule level</th><th>Factors</th><th>Source</th></tr></thead><tbody>{data.predictionHistory.slice(0, 50).map((p, i) => <tr key={`${p.timestamp}-${p.zone_id}-${i}`}><td>{formatDate(p.input_timestamp || p.timestamp)}</td><td>{zoneName(p.zone_id)}</td><td><Badge level={p.risk_level}/></td><td>{p.reasons?.join(' · ')}</td><td>{p.assessment_type || 'DEMO_RULES'}</td></tr>)}</tbody></table>{!data.predictionHistory.length && <Empty icon={Gauge} title="No assessments yet"/>}</div></Card></>}

    {page === 'Settings' && <><div className="two-column"><Card title="System status" subtitle="Current prototype configuration"><div className="settings-list"><div><span>Data storage</span><strong>{data.summary?.storage === 'mongodb' ? 'MongoDB' : 'Volatile memory'}</strong></div><div><span>Risk engine</span><strong>Provisional rules</strong></div><div><span>Image detection</span><strong>{data.visionStatus?.available ? (data.visionStatus?.mode === 'general_objects_demo' ? 'General objects · demo' : 'Geological model · unvalidated') : 'Unavailable'}</strong></div><div><span>External notifications</span><strong>Disabled</strong></div><div><span>Physical hardware</span><strong>Not connected</strong></div></div></Card><Card title="Data provenance & safety" subtitle="Read before demonstration"><div className="safety-copy"><p>Built-in readings and supplied CSVs are synthetic. CSV event labels are rule-generated and are not used for risk assessment. Zone positions and terrain art are fictional and have no survey coordinates.</p><p>Risk thresholds have not been validated by a geotechnical engineer. No event probability or time-to-failure forecast is provided.</p><p>Dashboard indicators do not activate a physical siren, lights, or public-address system.</p></div></Card></div><Card title="Simulation controls" subtitle="Start, pause or switch a scenario"><SimulatorControls running={running} scenario={data.summary?.simulation?.scenario} busy={busy} action={action}/></Card></>}

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
