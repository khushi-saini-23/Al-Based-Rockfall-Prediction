import { useEffect } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, Polygon, Polyline, Tooltip, useMap, ZoomControl } from 'react-leaflet'
import { AlertTriangle, Layers3 } from 'lucide-react'
import 'leaflet/dist/leaflet.css'

// Fictional local coordinates. No latitude, longitude, surveyed mine boundary, or DEM is provided.
const point = ([x, y]) => [100 - y, x * 2]
const shape = points => points.map(point)
const zoneShapes = {
  north_wall: shape([[15, 12], [23, 8], [33, 11], [40, 17], [38, 27], [32, 35], [22, 32], [15, 25], [12, 18]]),
  east_bench: shape([[59, 27], [68, 23], [78, 27], [85, 35], [83, 45], [77, 54], [66, 52], [58, 45], [55, 36]]),
  south_ramp: shape([[31, 62], [40, 57], [50, 60], [57, 68], [55, 79], [46, 88], [36, 86], [29, 77], [27, 69]]),
  sample_area: shape([[42, 31], [49, 27], [56, 30], [61, 37], [59, 45], [53, 51], [46, 49], [41, 42]]),
}
const mineBoundary = shape([[6, 19], [18, 10], [35, 7], [47, 12], [61, 9], [78, 14], [92, 29], [95, 48], [87, 69], [74, 83], [55, 94], [35, 90], [17, 77], [7, 57]])
const ridge = shape([[0, 30], [11, 26], [21, 30], [31, 26], [42, 31], [54, 26], [67, 29], [80, 24], [100, 27]])
const accessRoad = shape([[0, 80], [11, 71], [21, 64], [28, 56], [36, 53], [42, 48], [52, 44], [65, 43], [75, 35], [87, 25], [100, 20]])

function ring(cx, cy, rx, ry, rotation = -0.28) {
  return Array.from({ length: 64 }, (_, i) => {
    const angle = i / 64 * Math.PI * 2
    const irregular = 1 + 0.035 * Math.sin(i * 1.7)
    const x = rx * Math.cos(angle) * irregular
    const y = ry * Math.sin(angle) * irregular
    return point([cx + x * Math.cos(rotation) - y * Math.sin(rotation), cy + x * Math.sin(rotation) + y * Math.cos(rotation)])
  })
}

const benches = [
  { positions: ring(52, 51, 34, 27), color: '#c4b49b' },
  { positions: ring(52, 51, 29, 23), color: '#b6a58b' },
  { positions: ring(52, 51, 23, 19), color: '#a6957c' },
  { positions: ring(52, 51, 17, 14), color: '#94846e' },
  { positions: ring(52, 51, 10, 8), color: '#776d5d' },
]

const colors = {
  HIGH: { color: '#bd4c37', fillColor: '#d6432d', fillOpacity: 0.59, weight: 2.5 },
  MEDIUM: { color: '#cf9348', fillColor: '#e9aa57', fillOpacity: 0.38, weight: 2 },
  LOW: { color: '#5e8b65', fillColor: '#80ad79', fillOpacity: 0.25, weight: 1.8 },
  SAMPLE: { color: '#be4835', fillColor: '#d6432d', fillOpacity: 0.54, weight: 2.5, dashArray: '6 4' },
}

function FitMap() {
  const map = useMap()
  useEffect(() => {
    const container = map.getContainer()
    let frame
    const fit = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        map.invalidateSize({ pan: false, animate: false })
        map.fitBounds([[0, 0], [100, 200]], { padding: [18, 18], animate: false })
      })
    }
    const observer = new ResizeObserver(fit)
    observer.observe(container)
    fit()
    return () => { observer.disconnect(); cancelAnimationFrame(frame) }
  }, [map])
  return null
}

export default function MineRiskMap({ zones, predictions, selectedZone, onSelect, large = false, showZones = true }) {
  const hasHigh = predictions.some(p => p.risk_level === 'HIGH')
  const showSample = !hasHigh
  const areas = showSample ? [{ zone_id: 'sample_area', risk_level: 'SAMPLE' }, ...predictions] : predictions

  return <div className={`terrain-wrap ${large ? 'large' : ''}`}>
    <div className="vector-map-shell">
      <MapContainer className="vector-map" crs={L.CRS.Simple} center={[50, 100]} zoom={2} zoomSnap={0.25} zoomDelta={0.5} minZoom={0.5} maxZoom={5} zoomControl={false} scrollWheelZoom={false} attributionControl={false} maxBounds={[[-20, -20], [120, 220]]} maxBoundsViscosity={1}>
        <FitMap />
        <Polygon positions={mineBoundary} pathOptions={{ color: '#60715e', fillColor: '#c5ceb2', fillOpacity: 0.62, weight: 2 }} interactive={false}/>
        <Polyline positions={ridge} pathOptions={{ color: '#8ba17f', weight: 2, opacity: 0.75, dashArray: '4 5' }} interactive={false}/>
        {benches.map((bench, index) => <Polygon key={index} positions={bench.positions} pathOptions={{ color: '#e6d6ba', fillColor: bench.color, fillOpacity: 0.87, weight: 2.5 }} interactive={false}/>)}
        <Polyline positions={accessRoad} pathOptions={{ color: '#fff2d6', weight: 5, opacity: 0.95 }} interactive={false}/>
        <Polyline positions={accessRoad} pathOptions={{ color: '#92795e', weight: 1, opacity: 0.8, dashArray: '3 5' }} interactive={false}/>
        {showZones && areas.map(area => zoneShapes[area.zone_id] && <Polygon key={area.zone_id} positions={zoneShapes[area.zone_id]} pathOptions={colors[area.risk_level]} interactive={false}/>)}
        {showZones && zones.map(zone => {
          const risk = predictions.find(p => p.zone_id === zone.id)?.risk_level || 'NO DATA'
          return <CircleMarker key={zone.id} center={[100 - zone.y, zone.x * 2]} radius={selectedZone === zone.id ? 11 : 9} pathOptions={{ color: '#fff6e8', weight: 2.5, fillColor: risk === 'HIGH' ? '#bb4d36' : risk === 'MEDIUM' ? '#d99d50' : risk === 'LOW' ? '#5f8c67' : '#81766a', fillOpacity: 1 }} eventHandlers={{ click: () => onSelect(zone.id) }}><Tooltip permanent={selectedZone === zone.id || !zone.id.startsWith('LOC_')} direction="auto" offset={[7, 0]} className="zone-map-tooltip">{zone.name}</Tooltip></CircleMarker>
        })}
        <ZoomControl position="bottomright"/>
      </MapContainer>
      <div className="terrain-label"><Layers3 size={14}/> SCHEMATIC MINE MAP</div>
      {showZones && <div className="risk-map-label"><AlertTriangle size={13}/>{showSample ? 'SAMPLE RED AREA' : 'HIGH RISK · SIMULATED'}</div>}
    </div>
    <div className="terrain-caption"><span>{showSample ? 'Red area is a sample only; it is not a current zone assessment.' : 'Red areas follow provisional HIGH assessments.'} Fictional coordinates; no DEM.</span><div className="map-legend"><span><i className="dot low"/>Low</span><span><i className="dot medium"/>Medium</span><span><i className="dot high"/>High</span><span><i className="dot no-data"/>No data</span></div></div>
  </div>
}
