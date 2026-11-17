// Trustfall - WebXR front end (three.js). Hands-first for Meta Quest Browser; desktop mouse is a DEV stand-in only.
import * as THREE from 'three';
import { VRButton } from 'three/addons/webxr/VRButton.js';
import { XRHandModelFactory } from 'three/addons/webxr/XRHandModelFactory.js';
import { Panel, C, STATUS_COLOR, wrap, badge, rr, labelSprite, setSpriteText, glowTexture, windowTexture } from './ui.js';

const Engine = window.TrustfallEngine;
const params = new URLSearchParams(location.search);
if (params.get('shot')) document.body.classList.add('shot');

const HEALTH_COLOR = { healthy: 0x2fe38a, degraded: 0xf5a524, failed: 0xff3b4e };
const KIND_COLOR = { agent: 0x22d3ee, change: 0xf5a524, event: 0xff3b4e, service: 0xff3b4e, policy: 0xa78bfa, verification: 0x2fe38a, recovery: 0x2fe38a };
const BUILDINGS = {
  'config-store':   { x: -0.30, z: 0.18,  h: 0.16, w: 0.11 },
  'auth-service':   { x: -0.36, z: -0.20, h: 0.20, w: 0.10 },
  'payments-api':   { x: -0.02, z: 0.08,  h: 0.26, w: 0.14 },
  'orders-service': { x: 0.32,  z: 0.16,  h: 0.19, w: 0.11 },
  'edge-gateway':   { x: 0.14,  z: -0.42, h: 0.30, w: 0.12 },
  'analytics':      { x: 0.36,  z: -0.22, h: 0.14, w: 0.10 }
};
const TL_NODE = { T1: 'agent', T2: 'agent', T3: 'change', T4: 'policy', T5: 'service', T6: 'event', T7: null };
const GRAPH_POS = { agent: [-0.42, 0.14, 0.04], change: [-0.16, 0.0, 0.0], policy: [-0.14, 0.30, -0.06],
  event: [0.12, 0.0, 0.05], service: [0.38, 0.10, 0.0], verify: [-0.30, -0.22, 0.10], recovery: [0.18, -0.24, -0.04] };

let engine, scene, camera, renderer, S;
const panels = {}; const pickables = []; const bld = {}; const gnodes = {}; const gedges = []; const links = []; const pulses = [];
let agentMarker, cityGroup, graphGroup, glowTex, particles, hoverCursor;
const raycaster = new THREE.Raycaster();
let audioCtx;

function beep(freq = 880, dur = 0.07, vol = 0.05) {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const o = audioCtx.createOscillator(), g = audioCtx.createGain(); o.frequency.value = freq; o.type = 'sine';
    g.gain.value = vol; g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + dur);
    o.connect(g).connect(audioCtx.destination); o.start(); o.stop(audioCtx.currentTime + dur);
  } catch (e) { /* audio is optional */ }
}

async function boot() {
  let data;
  try { data = await (await fetch('data/scenario.json')).json(); }
  catch (e) { const el = document.getElementById('err'); el.style.display = 'flex'; el.textContent = 'Could not load data/scenario.json - serve this folder over HTTP(S) (see README). ' + e.message; return; }
  engine = new Engine(data);
  S = { ltab: params.get('ltab') || 'AGENT', rtab: params.get('rtab') || 'EVIDENCE', selNode: null, selSvc: null, traceI: -1,
        onboard: params.get('onboard') !== '0', tamper: null, verMsg: '', inputMode: 'Desktop mouse (dev stand-in, NOT hand tracking)', lastResult: null };
  initScene(); buildCity(); buildGraph(); buildPanels();
  engine.onChange(() => { refreshWorld(); redrawAll(); });
  if (params.get('sel')) { selectNode(params.get('sel'), true); S.rtab = params.get('rtab') || 'EVIDENCE'; S.ltab = params.get('ltab') || S.ltab; }
  if (params.get('recover')) engine.recover(params.get('recover'));
  if (params.get('verify')) await runVerify();
  if (params.get('tamper')) await runTamper();
  refreshWorld(); redrawAll();
  renderer.setAnimationLoop(tick);
  window.__tf = { engine, S, select: selectNode, THREE, camera, renderer, bld, gnodes, panels, xr, pickables };
}

function initScene() {
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: !!params.get('shot') });
  renderer.setPixelRatio(1); renderer.setSize(innerWidth, innerHeight); renderer.xr.enabled = true;
  try { renderer.xr.setFoveation(1); } catch (e) { /* optional */ }
  document.body.appendChild(renderer.domElement);
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x060b16); scene.fog = new THREE.Fog(0x060b16, 3.5, 9);
  camera = new THREE.PerspectiveCamera(68, innerWidth / innerHeight, 0.05, 30); camera.position.set(0, 1.5, 0.75); camera.lookAt(0, 1.5, -1);
  scene.add(new THREE.HemisphereLight(0x6fa8ff, 0x0a0f1a, 0.9));
  const d = new THREE.DirectionalLight(0x9fd8ff, 0.7); d.position.set(1, 3, 1); scene.add(d);
  glowTex = glowTexture();

  // floor grid + ring
  const grid = new THREE.GridHelper(14, 56, 0x0f3b52, 0x0b1a2c); grid.position.y = 0; scene.add(grid);
  const ring = new THREE.Mesh(new THREE.RingGeometry(1.7, 1.73, 96), new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.45, side: THREE.DoubleSide }));
  ring.rotation.x = -Math.PI / 2; ring.position.set(0, 0.01, -1); scene.add(ring);

  // particles
  const n = 260, pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { pos[i * 3] = (Math.random() - 0.5) * 4; pos[i * 3 + 1] = 0.6 + Math.random() * 2.2; pos[i * 3 + 2] = -1 + (Math.random() - 0.5) * 3.5; }
  const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  particles = new THREE.Points(pg, new THREE.PointsMaterial({ color: 0x22d3ee, size: 0.01, transparent: true, opacity: 0.55, depthWrite: false }));
  scene.add(particles);

  // VR entry + hands
  const vrBtn = VRButton.createButton(renderer, { optionalFeatures: ['hand-tracking', 'local-floor'] });
  document.body.appendChild(vrBtn);
  setupXRInput();
  renderer.xr.addEventListener('sessionstart', () => { beep(440, 0.2, 0.06); document.getElementById('mode').textContent = 'In VR: detecting input...'; });

  addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
  // DEV-ONLY desktop pointer (clearly not hand tracking)
  const ndc = new THREE.Vector2();
  renderer.domElement.addEventListener('pointermove', (e) => {
    if (renderer.xr.isPresenting) return;
    ndc.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1); raycaster.setFromCamera(ndc, camera); hoverFrom(raycaster, 'desktop');
  });
  renderer.domElement.addEventListener('pointerdown', (e) => {
    if (renderer.xr.isPresenting) return;
    ndc.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1); raycaster.setFromCamera(ndc, camera); activateFrom(raycaster);
  });
  hoverCursor = new THREE.Mesh(new THREE.SphereGeometry(0.008, 12, 12), new THREE.MeshBasicMaterial({ color: 0xffffff })); hoverCursor.visible = false; scene.add(hoverCursor);
}

// ---------- XR input abstraction: pinch-ray (hand), poke (hand fingertip), controller ray (optional) ----------
const xr = { ctrls: [], hands: [], poke: [{}, {}] };
function setupXRInput() {
  const factory = new XRHandModelFactory();
  for (let i = 0; i < 2; i++) {
    const c = renderer.xr.getController(i); scene.add(c);
    c.userData.kind = 'unknown';
    c.addEventListener('connected', (e) => { c.userData.kind = e.data.hand ? 'hand-pinch' : 'controller'; c.userData.handedness = e.data.handedness; updateInputLabel(); });
    c.addEventListener('disconnected', () => { c.userData.kind = 'unknown'; updateInputLabel(); });
    c.addEventListener('select', () => { const r = rayOf(c); activateFrom(r); });
    const line = new THREE.Mesh(new THREE.CylinderGeometry(0.0015, 0.0015, 1, 6), new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.5 }));
    line.geometry.translate(0, -0.5, 0); line.rotation.x = Math.PI / 2; line.scale.y = 0.6; c.add(line); c.userData.line = line;
    xr.ctrls.push(c);
    const h = renderer.xr.getHand(i); h.add(factory.createHandModel(h, 'spheres')); scene.add(h); xr.hands.push(h);
  }
}
function rayOf(obj) {
  const m = new THREE.Matrix4().extractRotation(obj.matrixWorld);
  const r = new THREE.Raycaster(); r.ray.origin.setFromMatrixPosition(obj.matrixWorld); r.ray.direction.set(0, 0, -1).applyMatrix4(m); return r;
}
function updateInputLabel() {
  const kinds = xr.ctrls.map(c => c.userData.kind);
  const anyHand = kinds.includes('hand-pinch'), anyCtl = kinds.includes('controller');
  S.inputMode = anyHand ? 'Hand tracking (pinch to select, or poke with index finger)' : anyCtl ? 'Controllers (optional)' : 'Waiting for hands...';
  document.getElementById('mode').textContent = 'Input: ' + S.inputMode; redrawAll();
}
function allTargets() { return pickables.filter(o => o.visible !== false && o.parent); }
function hoverFrom(r, src) {
  const hits = r.intersectObjects(allTargets(), false);
  Object.values(panels).forEach(p => p.setHover(null));
  if (!hits.length) { hoverCursor.visible = false; renderer.domElement.style.cursor = 'default'; return null; }
  const h = hits[0]; hoverCursor.visible = true; hoverCursor.position.copy(h.point);
  if (h.object.userData.panel) { const b = h.object.userData.panel.buttonAt(h.uv); h.object.userData.panel.setHover(b ? b.id : null); renderer.domElement.style.cursor = b ? 'pointer' : 'default'; }
  else renderer.domElement.style.cursor = 'pointer';
  return h;
}
function activateFrom(r) {
  const hits = r.intersectObjects(allTargets(), false); if (!hits.length) return;
  activateHit(hits[0]);
}
function activateHit(h) {
  const o = h.object.userData;
  if (o.panel) { const b = o.panel.buttonAt(h.uv); if (b && !b.disabled) { beep(900); onButton(o.panel.name, b.id); } return; }
  if (o.svc) { beep(700); selectService(o.svc); } else if (o.node) { beep(780); selectNode(o.node); } else if (o.agent) { beep(780); selectNode('agent'); }
}

// ---------- City ----------
function buildCity() {
  cityGroup = new THREE.Group(); cityGroup.position.set(0, 0.8, -1.0); cityGroup.scale.setScalar(1.25); scene.add(cityGroup);
  const ped = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.2, 0.8, 24), new THREE.MeshStandardMaterial({ color: 0x0d1830, metalness: 0.6, roughness: 0.4 }));
  ped.position.y = -0.42; cityGroup.add(ped);
  const table = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.03, 64), new THREE.MeshStandardMaterial({ color: 0x0b1426, metalness: 0.7, roughness: 0.35 }));
  cityGroup.add(table);
  const rim = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.004, 8, 96), new THREE.MeshBasicMaterial({ color: 0x22d3ee }));
  rim.rotation.x = Math.PI / 2; rim.position.y = 0.016; cityGroup.add(rim);
  const wt = windowTexture();
  for (const [id, b] of Object.entries(BUILDINGS)) {
    const g = new THREE.Group(); g.position.set(b.x, 0.015, b.z);
    const mat = new THREE.MeshStandardMaterial({ color: 0x0c1628, emissive: 0x2fe38a, emissiveMap: wt, emissiveIntensity: 0.9, roughness: 0.45, metalness: 0.5 });
    const body = new THREE.Mesh(new THREE.BoxGeometry(b.w, b.h, b.w), mat); body.position.y = b.h / 2; g.add(body);
    const cap = new THREE.Mesh(new THREE.BoxGeometry(b.w * 0.7, 0.012, b.w * 0.7), new THREE.MeshBasicMaterial({ color: 0x2fe38a })); cap.position.y = b.h + 0.006; g.add(cap);
    const base = new THREE.Mesh(new THREE.TorusGeometry(b.w * 0.85, 0.004, 8, 40), new THREE.MeshBasicMaterial({ color: 0x2fe38a })); base.rotation.x = Math.PI / 2; base.position.y = 0.004; g.add(base);
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0x2fe38a, transparent: true, opacity: 0.5, depthWrite: false, blending: THREE.AdditiveBlending }));
    glow.scale.set(b.w * 3.2, b.w * 3.2, 1); glow.position.y = 0.02; g.add(glow);
    const lbl = labelSprite(engine.data.services[id].label, '#dcecff', 0.3); lbl.position.y = b.h + 0.07; g.add(lbl);
    body.userData.svc = id; pickables.push(body);
    cityGroup.add(g); bld[id] = { g, body, mat, cap, base, glow, lbl, b };
  }
  // failure beacon over payments-api
  const beacon = new THREE.Mesh(new THREE.ConeGeometry(0.03, 0.12, 16, 1, true), new THREE.MeshBasicMaterial({ color: 0xff3b4e, transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false }));
  beacon.position.y = BUILDINGS['payments-api'].h + 0.16; beacon.rotation.x = Math.PI; bld['payments-api'].g.add(beacon); bld['payments-api'].beacon = beacon;
  // dependency links with animated pulses
  for (const [id, s] of Object.entries(engine.data.services)) for (const dep of s.depends_on) {
    const a = bld[id], d = bld[dep]; if (!a || !d) continue;
    const p0 = new THREE.Vector3(a.b.x, 0.03, a.b.z), p1 = new THREE.Vector3(d.b.x, 0.03, d.b.z);
    const mid = p0.clone().add(p1).multiplyScalar(0.5); mid.y = 0.11;
    const curve = new THREE.QuadraticBezierCurve3(p0, mid, p1);
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(24)), new THREE.LineBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.55 }));
    cityGroup.add(line);
    const pulse = new THREE.Mesh(new THREE.SphereGeometry(0.008, 8, 8), new THREE.MeshBasicMaterial({ color: 0x22d3ee })); cityGroup.add(pulse);
    links.push({ from: id, to: dep, curve, line, pulse, off: Math.random() });
  }
  // agent marker near config-store
  agentMarker = new THREE.Group();
  const oct = new THREE.Mesh(new THREE.OctahedronGeometry(0.035), new THREE.MeshStandardMaterial({ color: 0x0c1628, emissive: 0x22d3ee, emissiveIntensity: 1.2 }));
  const orbit = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.002, 8, 48), new THREE.MeshBasicMaterial({ color: 0x22d3ee })); orbit.rotation.x = Math.PI / 2.4;
  const alab = labelSprite('AI AGENT  OpsBot-7', '#22d3ee', 0.3); alab.position.y = 0.09;
  agentMarker.add(oct, orbit, alab); agentMarker.userData.orbit = orbit; oct.userData.agent = true; pickables.push(oct);
  agentMarker.position.set(BUILDINGS['config-store'].x, 0.38, BUILDINGS['config-store'].z + 0.02); cityGroup.add(agentMarker);
}

// ---------- Evidence graph ----------
function buildGraph() {
  graphGroup = new THREE.Group(); graphGroup.position.set(0, 1.72, -1.0); scene.add(graphGroup);
  const title = labelSprite('SPATIAL EVIDENCE GRAPH', '#22d3ee', 0.42); title.position.set(0, 0.45, 0); graphGroup.add(title);
  for (const n of engine.data.graph.nodes) {
    const g = new THREE.Group(); g.position.set(...GRAPH_POS[n.id]);
    const mat = new THREE.MeshStandardMaterial({ color: 0x0c1628, emissive: KIND_COLOR[n.kind], emissiveIntensity: 1.1, transparent: true });
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.04, 24, 24), mat); m.userData.node = n.id; pickables.push(m); g.add(m);
    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: KIND_COLOR[n.kind], transparent: true, opacity: 0.55, depthWrite: false, blending: THREE.AdditiveBlending })); halo.scale.set(0.16, 0.16, 1); g.add(halo);
    const sel = new THREE.Mesh(new THREE.TorusGeometry(0.062, 0.004, 8, 40), new THREE.MeshBasicMaterial({ color: 0xffffff })); sel.visible = false; g.add(sel);
    const lbl = labelSprite(n.label, '#dcecff', 0.3, 44); lbl.position.y = -0.085; g.add(lbl);
    graphGroup.add(g); gnodes[n.id] = { g, m, mat, halo, sel, lbl, n };
  }
  for (const e of engine.data.graph.edges) {
    const a = new THREE.Vector3(...GRAPH_POS[e.from]), b = new THREE.Vector3(...GRAPH_POS[e.to]);
    const grp = new THREE.Group(), dir = b.clone().sub(a), len = dir.length(), up = new THREE.Vector3(0, 1, 0);
    const q = new THREE.Quaternion().setFromUnitVectors(up, dir.clone().normalize());
    const mats = []; const color = e.kind === 'fact' ? 0x22d3ee : 0xf5a524;
    const segs = e.kind === 'fact' ? 1 : Math.max(4, Math.round(len / 0.035));
    for (let i = 0; i < segs; i++) {
      const t0 = i / segs, t1 = e.kind === 'fact' ? 1 : (i + 0.55) / segs, sl = (t1 - t0) * len;
      const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9 }); mats.push(mat);
      const cyl = new THREE.Mesh(new THREE.CylinderGeometry(0.0035, 0.0035, sl, 6), mat);
      cyl.position.copy(a.clone().lerp(b, (t0 + t1) / 2)); cyl.quaternion.copy(q); grp.add(cyl);
    }
    graphGroup.add(grp); gedges.push({ e, grp, mats });
  }
}

function refreshWorld() {
  // building colours reflect health
  for (const [id, o] of Object.entries(bld)) {
    const col = HEALTH_COLOR[engine.health[id]];
    o.mat.emissive.setHex(col); o.cap.material.color.setHex(col); o.base.material.color.setHex(col); o.glow.material.color.setHex(col);
    setSpriteText(o.lbl, engine.data.services[id].label + (engine.health[id] === 'healthy' ? '' : '  ' + engine.health[id].toUpperCase()), '#' + col.toString(16).padStart(6, '0'));
    o.lbl.scale.set(0.3, 0.3 * 96 / 512, 1);
  }
  bld['payments-api'].beacon.visible = engine.health['payments-api'] === 'failed';
  for (const l of links) {
    const bad = engine.health[l.to] === 'failed', warn = engine.health[l.from] === 'degraded' || engine.health[l.from] === 'failed';
    const col = bad ? 0xff3b4e : (warn ? 0xf5a524 : 0x22d3ee);
    l.line.material.color.setHex(col); l.pulse.material.color.setHex(col); l.speed = bad ? 0.12 : 0.3;
  }
  gnodes.service.mat.emissive.setHex(HEALTH_COLOR[engine.health['payments-api']]); gnodes.service.halo.material.color.setHex(HEALTH_COLOR[engine.health['payments-api']]);
  gnodes.event.mat.emissive.setHex(engine.status === 'RESOLVED' ? 0xf5a524 : 0xff3b4e);
  applyGraphHighlight();
}

function applyGraphHighlight() {
  const sel = S.selNode, nb = sel ? engine.neighbors(sel) : null;
  for (const [id, o] of Object.entries(gnodes)) {
    const on = !nb || nb.includes(id); o.mat.opacity = on ? 1 : 0.22; o.halo.material.opacity = on ? 0.55 : 0.08; o.sel.visible = id === sel;
    o.g.scale.setScalar(id === sel ? 1.25 : 1);
  }
  for (const ge of gedges) {
    const on = !sel || ge.e.from === sel || ge.e.to === sel; ge.mats.forEach(m => m.opacity = on ? 0.95 : 0.12);
  }
}

// ---------- Selection & actions ----------
function selectNode(id, silent) {
  S.selNode = id; S.selSvc = id === 'service' ? 'payments-api' : (id === 'change' ? 'config-store' : null); S.rtab = 'EVIDENCE';
  if (id === 'agent') S.ltab = 'AGENT';
  applyGraphHighlight(); redrawAll();
}
function selectService(id) {
  S.selSvc = id; S.selNode = id === 'payments-api' ? 'service' : id === 'config-store' ? 'change' : null; S.rtab = 'EVIDENCE';
  if (id === 'payments-api') S.ltab = 'AGENT';
  applyGraphHighlight(); redrawAll();
}
async function runVerify() {
  const r = await engine.verifyAll(); if (r.source.indexOf('precomputed') === 0) { engine.verification = r.results; engine.verificationSource = r.source; }
  S.verMsg = 'Verification complete: ' + r.source; redrawAll();
}
async function runTamper() {
  const t = await engine.tamperDemo(); S.tamper = t; redrawAll();
}
function download(name, text, mime) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: mime })); a.download = name; document.body.appendChild(a); a.click(); a.remove();
}
function onButton(panel, id) {
  if (id === 'begin') { S.onboard = false; panels.onboard.mesh.visible = false; redrawAll(); return; }
  if (id.startsWith('ltab:')) { S.ltab = id.slice(5); }
  else if (id.startsWith('rtab:')) { S.rtab = id.slice(5); }
  else if (id.startsWith('tl:')) { const n = TL_NODE[id.slice(3)]; if (n) { selectNode(n); return; } }
  else if (id === 'trace') {
    const order = engine.traceOrder(); S.traceI = (S.traceI + 1) % order.length; selectNode(order[S.traceI]); S.rtab = 'EVIDENCE'; return;
  }
  else if (id === 'verify') { runVerify(); return; }
  else if (id === 'tamper') { runTamper(); return; }
  else if (id.startsWith('rec:')) { S.lastResult = engine.recover(id.slice(4)); beep(S.lastResult.resolved ? 1200 : 400, 0.25, 0.07); return; }
  else if (id === 'exp-md') { download('trustfall-incident.md', Engine.reportToMarkdown(engine.report()), 'text/markdown'); }
  else if (id === 'exp-json') { download('trustfall-incident.json', JSON.stringify(engine.report(), null, 2), 'application/json'); }
  else if (id === 'restart') { location.reload(); return; }
  redrawAll();
}
function redrawAll() { if (!panels.banner) return; Object.values(panels).forEach(p => p.mesh.visible && p.redraw()); }

// ---------- Panels ----------
function tabBar(ctx, p, prefix, tabs, cur, y = 20) {
  const w = (p.pw - 40) / tabs.length;
  tabs.forEach((t, i) => p.btn(prefix + t, 20 + i * w, y, w - 8, 56, t, { active: cur === t, size: 24 }));
}
function buildPanels() {
  const add = (name, p, pos, rotY) => { p.mesh.position.set(...pos); p.mesh.rotation.y = rotY; scene.add(p.mesh); pickables.push(p.mesh); panels[name] = p; return p; };

  add('banner', new Panel('banner', 1.7, 0.27, 1700, 270, drawBanner), [0, 2.62, -1.45], 0);
  add('left', new Panel('left', 0.95, 0.7125, 1024, 768, drawLeft), [-0.92, 1.4, -0.85], 0.5);
  add('right', new Panel('right', 0.95, 0.7125, 1024, 768, drawRight), [0.92, 1.4, -0.85], -0.5);
  add('onboard', new Panel('onboard', 1.05, 0.74, 1024, 722, drawOnboard), [0, 1.45, -0.55], 0);
  panels.onboard.mesh.visible = S.onboard;
}

function drawBanner(ctx, p) {
  // logo + wordmark
  ctx.save(); ctx.translate(40, 40); ctx.strokeStyle = C.cyan; ctx.lineWidth = 9; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(100, 0); ctx.lineTo(160, 22); ctx.lineTo(160, 80); ctx.quadraticCurveTo(160, 150, 100, 185); ctx.quadraticCurveTo(40, 150, 40, 80); ctx.lineTo(40, 22); ctx.closePath(); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(100, 40); ctx.lineTo(100, 105); ctx.moveTo(75, 90); ctx.lineTo(100, 120); ctx.lineTo(125, 90); ctx.stroke();
  ctx.fillStyle = C.red; ctx.beginPath(); ctx.arc(100, 150, 8, 0, 7); ctx.fill(); ctx.restore();
  ctx.fillStyle = C.text; ctx.font = '800 84px system-ui, sans-serif'; ctx.fillText('TRUSTFALL', 260, 118);
  ctx.fillStyle = C.cyan; ctx.font = '600 34px system-ui, sans-serif'; ctx.fillText('THE AGENTOPS COMMAND CENTER', 264, 170);
  ctx.fillStyle = C.dim; ctx.font = '500 26px system-ui, sans-serif'; ctx.font = '500 22px system-ui, sans-serif'; ctx.fillText(engine.data.incident.id, 264, 218);
  const resolved = engine.status === 'RESOLVED';
  const col = resolved ? C.green : C.red;
  ctx.fillStyle = col + '22'; rr(ctx, 980, 36, 680, 198, 22); ctx.fill(); ctx.strokeStyle = col; ctx.lineWidth = 4; rr(ctx, 980, 36, 680, 198, 22); ctx.stroke();
  ctx.fillStyle = col; ctx.font = '800 38px system-ui, sans-serif';
  ctx.fillText(resolved ? 'RESOLVED (simulated)' : 'PAYMENTS API FAILED', 1010, 100);
  ctx.fillStyle = C.text; ctx.font = '500 28px system-ui, sans-serif';
  ctx.fillText(resolved ? 'Restored from verified snapshot EV-006' : 'OpsBot-7 wrote to PRODUCTION config', 1010, 150);
  ctx.fillStyle = C.dim; ctx.font = '500 20px system-ui, sans-serif'; ctx.fillText('Input: ' + (S.inputMode.length > 48 ? S.inputMode.slice(0, 46) + '..' : S.inputMode), 1010, 205);
}

function drawLeft(ctx, p) {
  tabBar(ctx, p, 'ltab:', ['AGENT', 'TIMELINE'], S.ltab);
  if (S.ltab === 'AGENT') drawAgent(ctx, p); else drawTimeline(ctx, p);
}
function drawAgent(ctx, p) {
  const a = engine.data.agent, auth = engine.authorization();
  ctx.fillStyle = C.text; ctx.font = '800 38px system-ui, sans-serif'; ctx.fillText('AI AGENT INSPECTOR', 30, 120);
  ctx.font = '500 26px system-ui, sans-serif'; ctx.fillStyle = C.dim;
  ctx.fillText(a.name + '   ID: ' + a.agent_id, 30, 160);
  ctx.fillText('Capabilities: ' + a.capabilities.join(', '), 30, 196);
  ctx.fillText('Granted: ' + a.grants.map(g => g.action + '@' + g.scopes.join('/')).join('; '), 30, 232);
  // the two separate verdicts
  const bx = 30, by = 258, bw = 470, bh = 150;
  const idc = auth.identity_verified ? C.green : C.red, azc = auth.authorized ? C.green : C.red;
  [['IDENTITY', auth.identity_verified ? 'VERIFIED' : 'NOT VERIFIED', idc, bx, 'Signature on EV-002 matches the configured key.'],
   ['ACTION', auth.authorized ? 'AUTHORIZED' : 'NOT AUTHORIZED', azc, bx + bw + 24, 'Policy EV-005: write only on staging; change was production.']].forEach(([k, v, c, x, note]) => {
    ctx.fillStyle = c + '22'; rr(ctx, x, by, bw, bh, 16); ctx.fill(); ctx.strokeStyle = c; ctx.lineWidth = 4; rr(ctx, x, by, bw, bh, 16); ctx.stroke();
    ctx.fillStyle = C.dim; ctx.font = '700 24px system-ui, sans-serif'; ctx.fillText(k, x + 18, by + 34);
    ctx.fillStyle = c; ctx.font = '800 38px system-ui, sans-serif'; ctx.fillText(v, x + 18, by + 80);
    ctx.fillStyle = C.text; ctx.font = '500 21px system-ui, sans-serif'; wrap(ctx, note, x + 18, by + 112, bw - 36, 25);
  });
  ctx.fillStyle = C.amber; ctx.font = '700 26px system-ui, sans-serif'; ctx.fillText('Identity is not authorization.', 30, 450);
  ctx.fillStyle = C.text; ctx.font = '700 28px system-ui, sans-serif'; ctx.fillText('Recorded actions', 30, 500);
  ctx.font = '500 24px system-ui, sans-serif';
  [['EV-001', 'Received task: tune pool in STAGING'], ['EV-002', 'Identity attested'], ['EV-003', 'Wrote max_connections 100 -> 0 in PRODUCTION']].forEach((r, i) => {
    const st = engine.verification[r[0]].status; ctx.fillStyle = C.dim; ctx.fillText(r[0], 30, 540 + i * 40);
    ctx.fillStyle = C.text; ctx.fillText(r[1], 140, 540 + i * 40); ctx.fillStyle = STATUS_COLOR[st]; ctx.fillText(st, 840, 540 + i * 40);
  });
  ctx.fillStyle = C.dim; ctx.font = '500 22px system-ui, sans-serif';
  wrap(ctx, 'A VERIFIED signature proves the record is untampered for the configured key. It does not prove the action was safe or allowed.', 30, 690, 960, 28);
}
function drawTimeline(ctx, p) {
  ctx.fillStyle = C.text; ctx.font = '800 38px system-ui, sans-serif'; ctx.fillText('INCIDENT TIMELINE', 30, 120);
  const rows = engine.log; const rh = Math.min(62, 580 / rows.length);
  rows.forEach((e, i) => {
    const y = 140 + i * rh, tl = engine.data.timeline[i], id = tl ? tl.id : null;
    ctx.fillStyle = (id && TL_NODE[id]) ? '#0f1d33' : '#0b1424'; rr(ctx, 24, y, 976, rh - 8, 10); ctx.fill();
    if (id && TL_NODE[id]) p.buttons.push({ id: 'tl:' + id, x: 24, y, w: 976, h: rh - 8 });
    ctx.fillStyle = e.text.indexOf('Recovery') === 0 ? C.green : (e.text.indexOf('exceeds') > 0 ? C.red : C.cyan); ctx.font = '700 22px system-ui, sans-serif';
    ctx.fillText(e.t.slice(11, 19), 38, y + rh / 2 + 2);
    ctx.fillStyle = C.text; ctx.font = '500 24px system-ui, sans-serif'; ctx.fillText(e.text.length > 62 ? e.text.slice(0, 60) + '...' : e.text, 150, y + rh / 2 + 2);
    ctx.fillStyle = C.dim; ctx.font = '500 20px system-ui, sans-serif'; ctx.fillText(e.evidence.join(' '), 880, y + rh / 2 + 2);
  });
  ctx.fillStyle = C.dim; ctx.font = '500 22px system-ui, sans-serif'; ctx.fillText('Select an event to highlight it in the evidence graph.', 30, 735);
}

function drawRight(ctx, p) {
  tabBar(ctx, p, 'rtab:', ['EVIDENCE', 'VERIFY', 'AI', 'RECOVER', 'REPORT'], S.rtab);
  ({ EVIDENCE: drawEvidence, VERIFY: drawVerify, AI: drawAI, RECOVER: drawRecover, REPORT: drawReport })[S.rtab](ctx, p);
}
function drawEvidence(ctx, p) {
  ctx.fillStyle = C.text; ctx.font = '800 36px system-ui, sans-serif';
  if (!S.selNode) {
    ctx.fillText('EVIDENCE GRAPH', 30, 120); ctx.font = '500 27px system-ui, sans-serif'; ctx.fillStyle = C.dim;
    let y = wrap(ctx, 'Select a node in the floating graph, a building, or a timeline event. Connected nodes stay bright; the rest dim.', 30, 165, 960, 36);
    y += 20; badge(ctx, 30, y, 'FACT', C.cyan); ctx.fillStyle = C.text; ctx.font = '500 26px system-ui, sans-serif'; ctx.fillText('solid cyan line: backed by verified evidence', 150, y + 30);
    y += 70; badge(ctx, 30, y, 'HYPOTHESIS', C.amber); ctx.fillStyle = C.text; ctx.fillText('dashed amber line: plausible, not proven', 250, y + 30);
    p.btn('trace', 30, 560, 460, 80, 'Trace incident sequence', { color: C.cyan, size: 28 });
    return;
  }
  const n = gnodes[S.selNode].n;
  ctx.fillText(n.label.toUpperCase(), 30, 118); ctx.font = '500 25px system-ui, sans-serif'; ctx.fillStyle = C.dim;
  let y = wrap(ctx, n.detail, 30, 156, 960, 32);
  y += 6; ctx.fillStyle = C.text; ctx.font = '700 26px system-ui, sans-serif'; ctx.fillText('Evidence', 30, y); y += 12;
  let x = 30; n.evidence.forEach(ev => { const st = engine.verification[ev].status; x += badge(ctx, x, y, ev + ' ' + st, STATUS_COLOR[st], 21) + 12; });
  y += 72; ctx.fillStyle = C.text; ctx.font = '700 26px system-ui, sans-serif'; ctx.fillText('Why connected', 30, y); y += 14;
  engine.edgesOf(S.selNode).slice(0, 4).forEach(e => {
    const other = e.from === S.selNode ? e.to : e.from, c = e.kind === 'fact' ? C.cyan : C.amber;
    const bw = badge(ctx, 30, y, e.kind === 'fact' ? 'FACT' : 'HYPOTHESIS', c, 18);
    ctx.fillStyle = C.text; ctx.font = '600 22px system-ui, sans-serif'; ctx.fillText(gnodes[other].n.label, 30 + bw + 12, y + 26);
    ctx.fillStyle = C.dim; ctx.font = '500 21px system-ui, sans-serif'; y = wrap(ctx, e.why, 30, y + 62, 960, 26) + 8;
  });
  p.btn('trace', 30, 690, 360, 62, S.traceI >= 0 ? 'Next step (' + (S.traceI + 1) + '/6)' : 'Trace sequence', { color: C.cyan, size: 24 });
}
function drawVerify(ctx, p) {
  ctx.fillStyle = C.text; ctx.font = '800 36px system-ui, sans-serif'; ctx.fillText('EVIDENCE VERIFICATION', 30, 118);
  ctx.font = '500 21px system-ui, sans-serif'; ctx.fillStyle = C.dim; ctx.fillText('Source: ' + engine.verificationSource, 30, 148);
  Object.keys(engine.verification).forEach((id, i) => {
    const v = engine.verification[id], y = 170 + i * 52;
    ctx.fillStyle = '#0f1d33'; rr(ctx, 24, y, 976, 46, 8); ctx.fill();
    ctx.fillStyle = C.text; ctx.font = '700 24px system-ui, sans-serif'; ctx.fillText(id, 38, y + 31);
    ctx.fillStyle = STATUS_COLOR[v.status]; ctx.fillText(v.status, 150, y + 31);
    ctx.fillStyle = C.dim; ctx.font = '500 19px system-ui, sans-serif'; const r = v.reason.length > 58 ? v.reason.slice(0, 56) + '...' : v.reason; ctx.fillText(r, 310, y + 30);
  });
  p.btn('verify', 24, 545, 330, 62, 'Re-run verification', { color: C.green, size: 24 });
  p.btn('tamper', 370, 545, 380, 62, 'Tamper test on EV-003', { color: C.amber, size: 24 });
  if (S.tamper) {
    ctx.fillStyle = C.amber + '22'; rr(ctx, 24, 622, 976, 70, 10); ctx.fill();
    ctx.fillStyle = C.amber; ctx.font = '700 22px system-ui, sans-serif';
    ctx.fillText('EV-003 edited (scope production -> staging): ' + S.tamper.result.status, 38, 652);
    ctx.fillStyle = C.dim; ctx.font = '500 19px system-ui, sans-serif'; ctx.fillText('Source: ' + S.tamper.source, 38, 680);
  }
  ctx.fillStyle = C.dim; ctx.font = '500 21px system-ui, sans-serif'; wrap(ctx, 'VERIFIED = signature matches record and configured key. It is NOT a safety, authorization or causation verdict.', 30, 722, 960, 26);
}
function drawAI(ctx, p) {
  const inv = engine.data.investigation;
  ctx.fillStyle = C.text; ctx.font = '800 34px system-ui, sans-serif'; ctx.fillText('AI INVESTIGATION', 30, 112);
  ctx.fillStyle = C.amber; ctx.font = '600 19px system-ui, sans-serif';
  ctx.fillText(inv.source === 'ai-validated' ? 'Source: AI model, schema- and evidence-validated' : 'Source: deterministic fallback (no AI key configured)', 30, 138);
  ctx.fillStyle = C.text; ctx.font = '600 22px system-ui, sans-serif'; let y = wrap(ctx, inv.suspected_root_cause, 30, 172, 960, 28) + 4;
  inv.findings.forEach(f => {
    const c = f.kind === 'fact' ? C.cyan : C.amber; const bw = badge(ctx, 30, y, f.kind === 'fact' ? 'FACT' : 'HYPOTHESIS', c, 16);
    ctx.fillStyle = C.green; ctx.font = '600 18px system-ui, sans-serif'; ctx.fillText(f.evidence_ids.join(' '), 30 + bw + 12, y + 22);
    ctx.fillStyle = C.text; ctx.font = '500 20px system-ui, sans-serif'; y = wrap(ctx, f.statement, 30, y + 50, 960, 25) + 2;
  });
  y += 8; ctx.fillStyle = C.dim; ctx.font = '600 20px system-ui, sans-serif';
  y = wrap(ctx, 'Confidence ' + inv.confidence.toUpperCase() + ': ' + inv.confidence_explanation, 30, y, 960, 25) + 4;
  ctx.fillStyle = C.amber; ctx.fillText('Unresolved: ' + inv.unresolved_questions[0], 30, y + 4);
}
function drawRecover(ctx, p) {
  ctx.fillStyle = C.text; ctx.font = '800 36px system-ui, sans-serif'; ctx.fillText('RECOVERY DECISION', 30, 118);
  ctx.fillStyle = C.dim; ctx.font = '500 21px system-ui, sans-serif'; ctx.fillText('Simulation only: no real infrastructure is changed.', 30, 148);
  const opts = Object.entries(engine.data.recovery_options), done = engine.status === 'RESOLVED';
  opts.forEach(([id, o], i) => {
    const y = 175 + i * 170;
    ctx.fillStyle = '#0d1830'; rr(ctx, 24, y, 976, 156, 14); ctx.fill();
    ctx.fillStyle = C.text; ctx.font = '500 21px system-ui, sans-serif'; wrap(ctx, o.consequence, 40, y + 100, 640, 26);
    p.btn('rec:' + id, 700, y + 28, 280, 100, o.label.replace('Restore previous configuration', 'Restore config').replace('Isolate the problematic agent', 'Isolate agent').replace('Continue investigation without recovery', 'Keep investigating'),
      { color: id === 'restore_previous_config' ? C.green : C.cyan, disabled: done, size: 24 });
    ctx.fillStyle = C.text; ctx.font = '700 27px system-ui, sans-serif'; ctx.fillText(o.label, 40, y + 44);
  });
  if (S.lastResult) { ctx.fillStyle = S.lastResult.resolved ? C.green : C.amber; ctx.font = '700 24px system-ui, sans-serif'; ctx.fillText('Result: ' + S.lastResult.effect, 30, 735); }
}
function drawReport(ctx, p) {
  const r = engine.report();
  ctx.fillStyle = C.text; ctx.font = '800 36px system-ui, sans-serif'; ctx.fillText('INCIDENT REPORT', 30, 118);
  ctx.font = '500 24px system-ui, sans-serif'; let y = 160;
  const row = (k, v, c) => { ctx.fillStyle = C.dim; ctx.fillText(k, 30, y); ctx.fillStyle = c || C.text; y = wrap(ctx, v, 270, y, 720, 30) + 8; };
  row('Incident', r.incident_id);
  row('Service', r.affected_service.label + ' - ' + r.affected_service.health, r.affected_service.health === 'healthy' ? C.green : C.red);
  row('Agent', r.agent.name + ' (identity verified: ' + r.agent.identity_verified + ')');
  row('Authorized', String(r.permission_findings.authorized), r.permission_findings.authorized ? C.green : C.red);
  const cnt = {}; Object.values(r.evidence_verification).forEach(v => cnt[v.status] = (cnt[v.status] || 0) + 1);
  row('Evidence', Object.keys(cnt).map(k => cnt[k] + ' ' + k).join(', '));
  row('Root cause', r.suspected_root_cause);
  row('Evidence refs', r.supporting_evidence.join(', '));
  row('Recovery', r.recovery_actions.join(', ') || 'none yet');
  row('Status', r.resolution_status, r.resolution_status === 'RESOLVED' ? C.green : C.red);
  p.btn('exp-md', 30, 690, 300, 62, 'Export Markdown', { color: C.cyan, size: 24 });
  p.btn('exp-json', 346, 690, 300, 62, 'Export JSON', { color: C.cyan, size: 24 });
}
function drawOnboard(ctx, p) {
  ctx.fillStyle = C.cyan; ctx.font = '800 54px system-ui, sans-serif'; ctx.fillText('Welcome, investigator', 40, 100);
  ctx.fillStyle = C.text; ctx.font = '500 29px system-ui, sans-serif';
  let y = wrap(ctx, 'An AI agent changed production configuration and Payments API went down. Reconstruct what happened using evidence, not guesses.', 40, 160, 940, 38) + 14;
  [['1', 'Pinch (or poke) the red Payments API building.'], ['2', 'Open the AI agent: identity is verified, but was the action authorized?'],
   ['3', 'Pinch graph nodes to see connected evidence. Cyan = fact, amber = hypothesis.'], ['4', 'Verify evidence, read the AI findings, choose a recovery, export the report.']].forEach(s => {
    ctx.fillStyle = C.cyan + '33'; ctx.beginPath(); ctx.arc(70, y + 4, 24, 0, 7); ctx.fill(); ctx.fillStyle = C.cyan; ctx.font = '800 28px system-ui, sans-serif'; ctx.fillText(s[0], 61, y + 15);
    ctx.fillStyle = C.text; ctx.font = '500 27px system-ui, sans-serif'; y = wrap(ctx, s[1], 115, y + 14, 860, 34) + 18;
  });
  ctx.fillStyle = C.dim; ctx.font = '500 22px system-ui, sans-serif'; wrap(ctx, 'Seated-friendly: everything is within arm reach. Hand tracking must be enabled in Quest settings. Scenario data is fictional; recovery is simulated.', 40, 585, 940, 28);
  p.btn('begin', 330, 630, 360, 70, 'Begin investigation', { color: C.green, size: 30 });
}

// ---------- Frame loop ----------
const tmp = new THREE.Vector3();
function tick(time) {
  const t = time / 1000;
  for (const l of links) { const u = (t * l.speed + l.off) % 1; l.pulse.position.copy(l.curve.getPoint(l.to && engine.health[l.to] === 'failed' ? u * 0.85 : u)); }
  const fail = engine.health['payments-api'] === 'failed';
  if (fail) { const k = 0.55 + 0.45 * Math.sin(t * 4); bld['payments-api'].mat.emissiveIntensity = 0.5 + k; bld['payments-api'].glow.material.opacity = 0.3 + 0.4 * k; bld['payments-api'].beacon.material.opacity = 0.15 + 0.3 * k; }
  else { bld['payments-api'].mat.emissiveIntensity = 0.9; bld['payments-api'].glow.material.opacity = 0.5; }
  agentMarker.rotation.y = t * 0.8; agentMarker.position.y = 0.38 + Math.sin(t * 1.6) * 0.01; agentMarker.userData.orbit.rotation.z = t * 1.2;
  particles.rotation.y = t * 0.01;
  graphGroup.children.forEach((c, i) => { if (c.position && c !== graphGroup.children[0]) c.position.y += Math.sin(t * 1.2 + i) * 0.00008; });
  if (renderer.xr.isPresenting) pokeUpdate();
  renderer.render(scene, camera);
  if (renderer.xr.isPresenting) {
    xr.ctrls.forEach(c => { if (c.userData.kind !== 'unknown') { const r = rayOf(c); const h = hoverFromQuiet(r); c.userData.line.scale.y = h ? h.distance : 0.6; } });
  }
}
function hoverFromQuiet(r) { const h = r.intersectObjects(allTargets(), false)[0]; if (h && h.object.userData.panel) { const p = h.object.userData.panel; const b = p.buttonAt(h.uv); p.setHover(b ? b.id : null); hoverCursor.visible = true; hoverCursor.position.copy(h.point); } else if (!h) { hoverCursor.visible = false; } return h; }

// Fingertip "poke": index-finger-tip crossing a panel's surface or touching a building/graph node.
function pokeUpdate() {
  xr.hands.forEach((hand, i) => {
    const tip = hand.joints && hand.joints['index-finger-tip']; if (!tip || !tip.visible && !tip.position) return;
    tip.getWorldPosition(tmp); const st = xr.poke[i];
    for (const mesh of pickables) {
      if (!mesh.visible) continue;
      if (mesh.userData.panel) {
        const p = mesh.userData.panel, local = mesh.worldToLocal(tmp.clone());
        const inside = Math.abs(local.x) < p.wM / 2 && Math.abs(local.y) < p.hM / 2;
        const key = p.name, prev = st[key] === undefined ? 1 : st[key]; st[key] = inside ? local.z : 1;
        if (inside && prev > 0.02 && local.z <= 0.012 && local.z > -0.06) {
          activateHit({ object: mesh, uv: new THREE.Vector2(local.x / p.wM + 0.5, local.y / p.hM + 0.5) });
        }
      } else {
        mesh.getWorldPosition(tip.userData.tmp = tip.userData.tmp || new THREE.Vector3());
        const r = (mesh.geometry.boundingSphere || (mesh.geometry.computeBoundingSphere(), mesh.geometry.boundingSphere)).radius;
        const near = tmp.distanceTo(tip.userData.tmp) < Math.max(r, 0.05) * 1.1; const key = 'o' + mesh.id, was = st[key]; st[key] = near;
        if (near && !was) activateHit({ object: mesh });
      }
    }
  });
}

boot();
