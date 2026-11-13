import { useState } from 'react'
import { MapContainer, Polygon, TileLayer, Tooltip, ZoomControl } from 'react-leaflet'
import { AlertTriangle, MapPinned } from 'lucide-react'

// Bingham Canyon Mine is a real open-pit mine. The red polygon is an arbitrary
// visual demonstration and has no relationship to measured conditions there.
const mineCenter = [40.529166667, -112.15388889]
const sampleRedArea = [
  [40.5318, -112.1598], [40.5344, -112.1555], [40.5338, -112.1498],
  [40.5308, -112.1455], [40.5273, -112.1474], [40.5254, -112.1525],
  [40.5270, -112.1580],
]

export default function DemoMineMap() {
  const [useOsm, setUseOsm] = useState(false)

  return <div className="terrain-wrap"><div className="vector-map-shell demo-mine-shell">
    <MapContainer className="vector-map" center={mineCenter} zoom={14} minZoom={12} maxZoom={17} zoomControl={false} scrollWheelZoom={false} attributionControl>
      {useOsm ? <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19} attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'/> : <TileLayer url="https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}" maxNativeZoom={15} maxZoom={17} attribution='<a href="https://apps.nationalmap.gov/services/">USGS The National Map</a>' eventHandlers={{ tileerror: () => setUseOsm(true) }}/>}
      <Polygon positions={sampleRedArea} pathOptions={{ color: '#f5b199', weight: 3, fillColor: '#d63d2c', fillOpacity: 0.52, dashArray: '8 5' }}><Tooltip direction="top">Sample red area — no measured risk</Tooltip></Polygon>
      <ZoomControl position="bottomright"/>
    </MapContainer>
    <div className="terrain-label"><MapPinned size={14}/> BINGHAM CANYON MINE · MAP DEMO</div>
    <div className="risk-map-label"><AlertTriangle size={13}/> SAMPLE RED AREA</div>
  </div><div className="terrain-caption"><span>Real mine basemap; red area is illustrative, not measured risk or linked to simulated readings.</span><span>{useOsm ? 'Map data: OpenStreetMap' : 'Imagery: USGS The National Map'}</span></div></div>
}
