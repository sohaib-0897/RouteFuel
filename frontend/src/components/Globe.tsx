// Adapted from Aceternity UI's GitHub Globe (Manu Arora).
// https://ui.aceternity.com/components/github-globe
// Retains ThreeGlobe hex polygons, endpoint rings and arcs; replaces the alpha
// React renderer with an explicitly disposed Three.js scene and deterministic motion.
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import ThreeGlobe from 'three-globe'
import gsap from 'gsap'
import type { RoutePlan } from '../types'
export default function Globe({ plan, reduced }: { plan: RoutePlan | null; reduced: boolean }) {
  const host = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    if (!host.current) return
    const mount = host.current
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: 'low-power',
      })
    } catch {
      setFailed(true)
      return
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.setClearColor(0x101210, 0)
    renderer.domElement.setAttribute('aria-hidden', 'true')
    mount.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, 1, 1, 1500)
    const globe = new ThreeGlobe({ animateIn: false })
      .showAtmosphere(false)
      .atmosphereColor('#d2d9d4')
      .atmosphereAltitude(0.055)
      .hexPolygonResolution(3)
      .hexPolygonMargin(0.65)
      .hexPolygonColor(() => '#68808a')
    const material = globe.globeMaterial() as THREE.MeshPhongMaterial
    material.color = new THREE.Color('#e0e0d3')
    material.emissive = new THREE.Color('#e0e0d3')
    material.emissiveIntensity = 0.2
    material.shininess = 2
    scene.add(globe, new THREE.AmbientLight('#ffffff', 1.1))
    const light = new THREE.DirectionalLight('#ffffff', 1.4)
    light.position.set(-200, 350, 250)
    scene.add(light)
    const initial = globe.getCoords(25, -90, 2.15)
    camera.position.set(initial.x, initial.y, initial.z)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableZoom = false
    controls.enablePan = false
    controls.enableDamping = true
    controls.dampingFactor = 0.07
    controls.autoRotate = !reduced && !plan
    controls.autoRotateSpeed = 0.22
    controls.minPolarAngle = 0.35
    controls.maxPolarAngle = 2.5
    const resize = () => {
      const { width, height } = mount.getBoundingClientRect()
      renderer.setSize(width, height)
      camera.aspect = width / Math.max(height, 1)
      camera.updateProjectionMatrix()
    }
    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(mount)
    let disposed = false,
      visible = true,
      raf = 0,
      last = 0,
      dirty = true
    const request = new AbortController()
    fetch(import.meta.env.BASE_URL + 'globe.json', { signal: request.signal })
      .then((r) => {
        if (!r.ok) throw new Error('globe data')
        return r.json()
      })
      .then((data) => {
        if (!disposed) {
          globe.hexPolygonsData(data.features)
          dirty = true
        }
      })
      .catch(() => {
        if (!disposed) setFailed(true)
      })
    const reveal = gsap.timeline()
    if (plan) {
      const target = globe.getCoords(36, -100, 2.05)
      reveal.to(
        camera.position,
        { ...target, duration: reduced ? 0 : 0.6, ease: 'power2.inOut' },
        0,
      )
      const endpoints = [
        { lat: plan.start.latitude, lng: plan.start.longitude },
        { lat: plan.finish.latitude, lng: plan.finish.longitude },
      ]
      globe
        .pointColor(() => '#b74421')
        .pointRadius(0.65)
        .pointAltitude(0.01)
        .pointsMerge(true)
      globe
        .ringColor(() => '#b74421')
        .ringMaxRadius(3)
        .ringPropagationSpeed(2)
        .ringRepeatPeriod(1200)
      reveal.call(
        () => {
          globe.pointsData([endpoints[0]])
          if (!reduced) globe.ringsData([endpoints[0]])
        },
        [],
        reduced ? 0 : 0.25,
      )
      reveal.call(() => globe.pointsData(endpoints), [], reduced ? 0 : 0.5)
      reveal.call(
        () => {
          globe
            .arcsData([
              {
                startLat: plan.start.latitude,
                startLng: plan.start.longitude,
                endLat: plan.finish.latitude,
                endLng: plan.finish.longitude,
              },
            ])
            .arcColor(() => '#b74421')
            .arcAltitude(0.12)
            .arcStroke(0.45)
            .arcDashLength(reduced ? 1 : 0)
            .arcDashGap(2)
            .arcDashInitialGap(0)
            .arcDashAnimateTime(0)
          if (reduced) globe.pauseAnimation()
        },
        [],
        reduced ? 0 : 0.65,
      )
    } else if (reduced) globe.pauseAnimation()
    const invalidate = () => {
      dirty = true
    }
    controls.addEventListener('change', invalidate)
    const arc = { length: 0 }
    if (plan && !reduced)
      reveal.to(
        arc,
        {
          length: 1,
          duration: 0.6,
          ease: 'none',
          onUpdate: () => {
            globe.arcDashLength(arc.length)
          },
        },
        0.65,
      )
    function render(now: number) {
      if (disposed) return
      raf = requestAnimationFrame(render)
      if (!visible || document.hidden || now - last < 33) return
      last = now
      controls.update()
      if (reduced && !dirty) return
      dirty = false
      renderer.render(scene, camera)
    }
    raf = requestAnimationFrame(render)
    const intersection = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting
      if (visible && !reduced) globe.resumeAnimation()
      else globe.pauseAnimation()
    })
    intersection.observe(mount)
    const visibility = () => {
      if (document.hidden) globe.pauseAnimation()
      else if (!reduced && visible) globe.resumeAnimation()
    }
    document.addEventListener('visibilitychange', visibility)
    const lost = (e: Event) => {
      e.preventDefault()
      setFailed(true)
    }
    renderer.domElement.addEventListener('webglcontextlost', lost)
    return () => {
      disposed = true
      request.abort()
      cancelAnimationFrame(raf)
      reveal.kill()
      observer.disconnect()
      intersection.disconnect()
      controls.dispose()
      document.removeEventListener('visibilitychange', visibility)
      renderer.domElement.removeEventListener('webglcontextlost', lost)
      globe.pauseAnimation()
      globe._destructor()
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry?.dispose()
          const materials = Array.isArray(obj.material) ? obj.material : [obj.material]
          materials.forEach((m) => m.dispose())
        }
      })
      renderer.dispose()
      renderer.forceContextLoss()
      renderer.domElement.remove()
    }
  }, [plan, reduced])
  return failed ? (
    <div className="globe-fallback" aria-label="Globe preview unavailable" />
  ) : (
    <div
      className="globe-canvas"
      ref={host}
      role="img"
      aria-label={
        plan
          ? 'Cinematic globe overview of route endpoints; arc is not the driving route'
          : 'Interactive globe overview. Drag to rotate.'
      }
    />
  )
}
