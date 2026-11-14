import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { AlertTriangle, RotateCcw } from 'lucide-react'

// A fictional open-pit surface in local coordinates. It is not built from the uploaded DEM.
const pitRadius = 42
const rings = [0, 0.19, 0.32, 0.45, 0.58, 0.71, 0.84, 1]
const levels = [1, 1, 5, 10, 15, 20, 25, 30]
const riskColors = { LOW: 0x679e72, MEDIUM: 0xe3a34d, HIGH: 0xd34c36, CRITICAL: 0x9f2d2d, 'NO DATA': 0x857a6d }

function elevation(x, z) {
  const angle = Math.atan2(z, x)
  const distortion = 1 + 0.055 * Math.sin(angle * 5 + 0.4) + 0.025 * Math.cos(angle * 11)
  const radius = Math.hypot(x / 1.16, z / 0.86) / (pitRadius * distortion)
  for (let i = 1; i < rings.length; i++) {
    if (radius < rings[i]) {
      const edge = Math.max(0, Math.min(1, (radius - rings[i] + 0.024) / 0.024))
      const bench = THREE.MathUtils.lerp(levels[i - 1], levels[i], edge * edge * (3 - 2 * edge))
      const rock = (Math.sin(x * 1.7 + z * 0.53) * Math.cos(z * 1.31 - x * 0.28) * 0.31 +
        Math.sin(x * 0.41 - z * 0.67) * 0.46) * Math.min(1, radius * 3)
      return bench + rock
    }
  }
  return 30 + Math.sin(x * 0.18 + z * 0.12) * 0.8 + Math.cos(z * 0.27) * 0.5
}

function makeTerrain() {
  const size = 128
  const steps = 220
  const geometry = new THREE.PlaneGeometry(size, size, steps, steps)
  const positions = geometry.attributes.position
  const colors = []
  for (let i = 0; i < positions.count; i++) {
    const x = positions.getX(i)
    const z = -positions.getY(i)
    const y = elevation(x, z)
    positions.setZ(i, y)
    const warm = Math.max(0, Math.min(1, (28 - x + z * 0.22) / 88))
    const color = new THREE.Color(0x817a70).lerp(new THREE.Color(0xb66c43), warm * 0.77)
    const stratum = Math.sin(y * 1.28 + x * 0.045 + z * 0.08) * 0.075
    const grain = Math.sin(x * 2.9 + z * 4.1) * Math.sin(z * 2.4 - x * 1.7) * 0.065
    color.multiplyScalar(0.91 + stratum + grain + (y < 4 ? -0.09 : 0))
    colors.push(color.r, color.g, color.b)
  }
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
  geometry.computeVertexNormals()
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, side: THREE.DoubleSide, flatShading: true }))
  mesh.rotation.x = -Math.PI / 2
  mesh.receiveShadow = true
  return mesh
}

function makeContour(radius) {
  const points = Array.from({ length: 193 }, (_, i) => {
    const angle = i / 192 * Math.PI * 2
    const distortion = 1 + 0.055 * Math.sin(angle * 5 + 0.4) + 0.025 * Math.cos(angle * 11)
    const x = Math.cos(angle) * radius * pitRadius * 1.16 * distortion
    const z = Math.sin(angle) * radius * pitRadius * 0.86 * distortion
    return new THREE.Vector3(x, elevation(x, z) + 0.22, z)
  })
  return new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color: 0xe1b990, transparent: true, opacity: 0.42 }))
}

function makeHaulRoad() {
  const group = new THREE.Group()
  for (let band = 1; band < rings.length - 1; band++) {
    const radius = (rings[band] + rings[band + 1]) / 2
    const vertices = []
    const indices = []
    const count = 155
    const start = band % 2 ? -0.2 : 0.25
    const sweep = Math.PI * 1.72
    for (let i = 0; i <= count; i++) {
      const angle = start + i / count * sweep
      const distortion = 1 + 0.055 * Math.sin(angle * 5 + 0.4) + 0.025 * Math.cos(angle * 11)
      const x = Math.cos(angle) * radius * pitRadius * 1.16 * distortion
      const z = Math.sin(angle) * radius * pitRadius * 0.86 * distortion
      const tangentX = -Math.sin(angle) * 1.16
      const tangentZ = Math.cos(angle) * 0.86
      const length = Math.hypot(tangentX, tangentZ)
      const sideX = -tangentZ / length * 1.25
      const sideZ = tangentX / length * 1.25
      for (const sign of [1, -1]) {
        const px = x + sideX * sign
        const pz = z + sideZ * sign
        vertices.push(px, elevation(px, pz) + 0.34, pz)
      }
      if (i < count) {
        const n = i * 2
        indices.push(n, n + 1, n + 2, n + 1, n + 3, n + 2)
      }
    }
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3))
    geometry.setIndex(indices)
    geometry.computeVertexNormals()
    group.add(new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: 0x8c765f, roughness: 1, side: THREE.DoubleSide })))
  }
  return group
}

function box(parent, width, height, depth, color, x, y, z) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), new THREE.MeshStandardMaterial({ color, roughness: 0.88 }))
  mesh.position.set(x, y, z)
  mesh.castShadow = true
  parent.add(mesh)
  return mesh
}

function makeTruck(x, z, rotation = 0, scale = 1) {
  const truck = new THREE.Group()
  truck.position.set(x, elevation(x, z) + 0.75, z)
  truck.rotation.y = rotation
  truck.scale.setScalar(scale)
  box(truck, 3.7, 0.7, 1.8, 0x4d473d, 0, 0.45, 0)
  box(truck, 2.1, 1.0, 1.75, 0xc4973f, -0.65, 1.1, 0)
  box(truck, 1.05, 1.25, 1.8, 0xd5a740, 1.25, 1.15, 0)
  box(truck, 0.08, 0.55, 1.45, 0x303b40, 1.79, 1.36, 0)
  for (const px of [-1.25, 1.22]) for (const pz of [-1, 1]) {
    const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.48, 0.48, 0.29, 12), new THREE.MeshStandardMaterial({ color: 0x252522, roughness: 1 }))
    wheel.rotation.x = Math.PI / 2
    wheel.position.set(px, 0.12, pz)
    wheel.castShadow = true
    truck.add(wheel)
  }
  return truck
}

function beam(parent, start, end, radius, color) {
  const direction = new THREE.Vector3().subVectors(end, start)
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.75, radius, direction.length(), 8), new THREE.MeshStandardMaterial({ color, roughness: 0.85 }))
  mesh.position.copy(start).add(end).multiplyScalar(0.5)
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize())
  mesh.castShadow = true
  parent.add(mesh)
}

function makeExcavator(x, z, rotation = 0) {
  const excavator = new THREE.Group()
  excavator.position.set(x, elevation(x, z) + 0.3, z)
  excavator.rotation.y = rotation
  box(excavator, 2.8, 0.55, 1.75, 0x3a3832, 0, 0.4, 0)
  box(excavator, 2.1, 1.05, 1.6, 0xd1a33c, -0.35, 1.2, 0)
  box(excavator, 0.9, 0.7, 0.07, 0x3c4747, -0.05, 1.4, 0.82)
  beam(excavator, new THREE.Vector3(0.35, 1.45, 0), new THREE.Vector3(2.9, 3.75, 0), 0.28, 0xd1a33c)
  beam(excavator, new THREE.Vector3(2.9, 3.75, 0), new THREE.Vector3(4.4, 1.7, 0), 0.2, 0xd1a33c)
  box(excavator, 0.8, 0.55, 1.1, 0x4d4235, 4.55, 1.5, 0)
  return excavator
}

function makeRockScatter() {
  const count = 280
  const geometry = new THREE.DodecahedronGeometry(1, 0)
  const material = new THREE.MeshStandardMaterial({ roughness: 1, flatShading: true })
  const rocks = new THREE.InstancedMesh(geometry, material, count)
  const item = new THREE.Object3D()
  for (let i = 0; i < count; i++) {
    const a = i * 2.39996
    const r = 5 + Math.sqrt((i * 73) % count / count) * 56
    const x = Math.cos(a) * r
    const z = Math.sin(a) * r * 0.87
    const size = 0.23 + ((i * 37) % 19) / 22
    item.position.set(x, elevation(x, z) + size * 0.28, z)
    item.rotation.set(i * 0.7, i * 1.31, i * 0.41)
    item.scale.set(size * 1.6, size * 0.65, size)
    item.updateMatrix()
    rocks.setMatrixAt(i, item.matrix)
    rocks.setColorAt(i, new THREE.Color(i % 3 === 0 ? 0x8e6855 : i % 3 === 1 ? 0x766e63 : 0xb18362))
  }
  rocks.castShadow = true
  return rocks
}

function disposeGroup(group) {
  group.traverse(object => {
    object.geometry?.dispose()
    if (Array.isArray(object.material)) object.material.forEach(material => material.dispose())
    else object.material?.dispose()
  })
}

export default function MineTerrain3D({ zones, predictions, selectedZone, onSelect, showZones = true }) {
  const host = useRef(null)
  const model = useRef(null)
  const onSelectRef = useRef(onSelect)
  const [available, setAvailable] = useState(true)
  const hasHigh = predictions.some(p => ['HIGH', 'CRITICAL'].includes(p.risk_level))
  onSelectRef.current = onSelect

  useEffect(() => {
    const container = host.current
    let renderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    } catch {
      setAvailable(false)
      return undefined
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 0.95
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFShadowMap
    container.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xbfc3c1)
    scene.fog = new THREE.Fog(0xbfc3c1, 175, 275)
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 400)
    const home = new THREE.Vector3(89, 108, 111)
    camera.position.copy(home)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(0, 10, 0)
    controls.enableDamping = true
    controls.minDistance = 55
    controls.maxDistance = 220
    controls.maxPolarAngle = Math.PI * 0.49
    controls.update()
    scene.add(new THREE.HemisphereLight(0xe2e7e9, 0x51483f, 1.2))
    const sun = new THREE.DirectionalLight(0xffe3b9, 1.8)
    sun.position.set(-54, 96, 56)
    sun.castShadow = true
    sun.shadow.mapSize.set(2048, 2048)
    sun.shadow.camera.left = -82
    sun.shadow.camera.right = 82
    sun.shadow.camera.top = 82
    sun.shadow.camera.bottom = -82
    sun.shadow.bias = -0.00025
    scene.add(sun)
    const scenery = new THREE.Group()
    scenery.add(makeTerrain())
    for (const radius of rings.slice(1, -1)) scenery.add(makeContour(radius))
    scenery.add(makeHaulRoad())
    scenery.add(makeRockScatter())
    scenery.add(makeTruck(-25, 23, 1.1, 1.15))
    scenery.add(makeTruck(30, 12, -0.65, 0.95))
    scenery.add(makeTruck(9, -12, 2.3, 0.75))
    scenery.add(makeExcavator(-13, -9, -0.55))
    scenery.add(makeExcavator(11, 5, 2.6))
    scene.add(scenery)
    const dynamic = new THREE.Group()
    scene.add(dynamic)
    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    let down = null
    const onPointerDown = event => { down = [event.clientX, event.clientY] }
    const onPointerUp = event => {
      if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 6) return
      const rect = renderer.domElement.getBoundingClientRect()
      pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1)
      raycaster.setFromCamera(pointer, camera)
      const hit = raycaster.intersectObjects(dynamic.children, true).find(item => item.object.userData.zoneId)
      if (hit) onSelectRef.current(hit.object.userData.zoneId)
    }
    renderer.domElement.addEventListener('pointerdown', onPointerDown)
    renderer.domElement.addEventListener('pointerup', onPointerUp)
    const resize = () => {
      const width = container.clientWidth
      const height = container.clientHeight
      if (!width || !height) return
      camera.aspect = width / height
      const distanceScale = Math.max(1, 1.1 / camera.aspect)
      home.set(89 * distanceScale, 108 * distanceScale, 111 * distanceScale)
      camera.position.copy(home)
      controls.maxDistance = Math.max(220, home.length() * 1.6)
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    }
    const observer = new ResizeObserver(resize)
    observer.observe(container)
    resize()
    let frame
    const draw = () => { frame = requestAnimationFrame(draw); controls.update(); renderer.render(scene, camera) }
    draw()
    model.current = { scene, camera, controls, home, dynamic }
    return () => {
      model.current = null
      cancelAnimationFrame(frame)
      observer.disconnect()
      renderer.domElement.removeEventListener('pointerdown', onPointerDown)
      renderer.domElement.removeEventListener('pointerup', onPointerUp)
      controls.dispose()
      disposeGroup(dynamic)
      disposeGroup(scenery)
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])

  useEffect(() => {
    const current = model.current
    if (!current) return
    const { dynamic } = current
    disposeGroup(dynamic)
    dynamic.clear()
    if (!showZones) return
    if (!hasHigh) {
      const sample = new THREE.Mesh(new THREE.CircleGeometry(10, 48), new THREE.MeshBasicMaterial({ color: 0xd74732, transparent: true, opacity: 0.5, depthWrite: false, side: THREE.DoubleSide }))
      sample.rotation.x = -Math.PI / 2
      sample.position.set(-7, elevation(-7, -3) + 0.3, -3)
      dynamic.add(sample)
    }
    for (const zone of zones) {
      const x = (Number(zone.x) - 50) * 1.02
      const z = (Number(zone.y) - 50) * 1.02
      if (!Number.isFinite(x) || !Number.isFinite(z)) continue
      const risk = predictions.find(item => item.zone_id === zone.id)?.risk_level || 'NO DATA'
      const y = elevation(x, z)
      if (risk !== 'NO DATA') {
        const area = new THREE.Mesh(new THREE.CircleGeometry(zone.id.startsWith('LOC_') ? 3.2 : 6, 32), new THREE.MeshBasicMaterial({ color: riskColors[risk] || riskColors['NO DATA'], transparent: true, opacity: 0.38, depthWrite: false, side: THREE.DoubleSide }))
        area.rotation.x = -Math.PI / 2
        area.position.set(x, y + 0.38, z)
        dynamic.add(area)
      }
      const selected = selectedZone === zone.id
      const marker = new THREE.Mesh(new THREE.SphereGeometry(selected ? 1.45 : 1, 16, 12), new THREE.MeshStandardMaterial({ color: riskColors[risk] || riskColors['NO DATA'], emissive: selected ? 0x5b3020 : 0x000000, roughness: 0.55 }))
      marker.position.set(x, y + 2.45, z)
      marker.userData.zoneId = zone.id
      dynamic.add(marker)
      const stem = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x, y + 0.4, z), new THREE.Vector3(x, y + 2.45, z)]), new THREE.LineBasicMaterial({ color: 0xfff7e8 }))
      dynamic.add(stem)
    }
  }, [zones, predictions, selectedZone, showZones, hasHigh])

  const resetView = () => {
    if (!model.current) return
    model.current.camera.position.copy(model.current.home)
    model.current.controls.target.set(0, 10, 0)
    model.current.controls.update()
  }

  return <div className="terrain-wrap large"><div className="terrain-3d-shell">
    <div ref={host} className="terrain-3d-canvas" role="img" aria-label="Interactive fictional three-dimensional open-pit mine model with selectable risk zone markers"/>
    {!available && <div className="terrain-3d-unavailable">3D graphics are unavailable in this browser.</div>}
    <div className="terrain-label">3D SCHEMATIC MINE MODEL</div>
    {showZones && <div className="risk-map-label"><AlertTriangle size={13}/>{hasHigh ? 'HIGH RISK · DEMO RULES' : 'SAMPLE RED AREA'}</div>}
    <button className="terrain-reset" onClick={resetView} aria-label="Reset 3D view"><RotateCcw size={16}/> Reset view</button>
    <span className="terrain-3d-hint"><span className="desktop-hint">Drag to rotate · scroll to zoom · click a marker</span><span className="mobile-hint">Drag to rotate · pinch to zoom · tap a marker</span></span>
  </div><div className="terrain-caption"><span>{hasHigh ? 'Colored areas follow provisional assessments.' : 'Red area is an illustrative sample, not a current assessment.'} Fictional terrain and coordinates; no DEM is used for this model.</span><div className="map-legend"><span><i className="dot low"/>Low</span><span><i className="dot medium"/>Medium</span><span><i className="dot high"/>High</span><span><i className="dot no-data"/>No data</span></div></div></div>
}
