// 3D centre of the Live stage: Meena's Soundbox (with Kavach in it) and Paytm's systems as glass tiles.
// Packets fly along a link whenever Kavach calls that system. Pure presentation: state comes from stage.js.
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

const map = document.getElementById("map");
const C = { sky: 0x1fb6f0, leaf: 0x26d49a, haldi: 0xffb020, sindoor: 0xff5b4a, navy: 0x0d2a63, idle: 0x3a5a94 };
const TONE = { "": C.idle, ok: C.leaf, warn: C.haldi, bad: C.sindoor };
const ICONS = {
  switch: "M4 8h15l-3-3M20 16H5l3 3", ledger: "M5 3h11l3 3v15H5zM8 9h8M8 13h8M8 17h5", refund: "M4 12a8 8 0 1 0 3-6M4 4v4h4",
  payout: "M12 3v11M7 9l5 5 5-5M4 17v3h16v-3", policy: "M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z", chat: "M4 5h16v11H9l-5 4z",
};
// same layout as the 2D map, in world units
const LAYOUT = { switch: [-3.3, 2.15, -0.6, "switch"], ledger: [3.3, 2.15, -0.6, "ledger"], policy: [-4.6, -0.15, 0.4, "policy"],
  refund: [4.6, -0.15, 0.4, "refund"], customer: [-2.9, -2.35, 0.9, "chat"], payout: [2.9, -2.35, 0.9, "payout"] };

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
} catch (e) { console.warn("WebGL unavailable; keeping the 2D map", e); }

if (renderer) {
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.domElement.className = "gl";
  map.prepend(renderer.domElement);
  map.classList.add("three");

  const scene = new THREE.Scene();
  scene.background = (() => {   // the stage's own night-navy glow, so the canvas blends into the page
    const c = document.createElement("canvas"); c.width = 1024; c.height = 640; const g = c.getContext("2d");
    const r = g.createRadialGradient(512, 290, 20, 512, 320, 620); r.addColorStop(0, "#123a82"); r.addColorStop(0.55, "#0a2257"); r.addColorStop(1, "#06163A");
    g.fillStyle = r; g.fillRect(0, 0, 1024, 640);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  })();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
  camera.position.set(0, 2.4, 13.5);

  scene.add(new THREE.HemisphereLight(0x9cc8ff, 0x061538, 1.1));
  const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(-4, 6, 8); scene.add(key);
  const rim = new THREE.PointLight(C.sky, 30, 14); rim.position.set(3, 2, -3); scene.add(rim);

  // ---------------------------------------------------------------- the Soundbox
  const dev = new THREE.Group(); dev.scale.setScalar(1.3); scene.add(dev);
  const grille = (() => {
    const c = document.createElement("canvas"); c.width = 1024; c.height = 512; const g = c.getContext("2d");
    const grd = g.createLinearGradient(0, 0, 0, 512); grd.addColorStop(0, "#16408a"); grd.addColorStop(1, "#08204f");
    g.fillStyle = grd; g.fillRect(0, 0, 1024, 512);
    g.fillStyle = "rgba(4,14,40,.85)";
    for (let y = 70; y < 440; y += 16) for (let x = 10; x < 1024; x += 16) { g.beginPath(); g.arc(x + ((y / 16) % 2) * 8, y, 4.2, 0, 7); g.fill(); }
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
  })();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(1.25, 1.38, 1.9, 96, 1, false),
    new THREE.MeshPhysicalMaterial({ map: grille, metalness: 0.2, roughness: 0.5, clearcoat: 0.8, clearcoatRoughness: 0.25, emissive: 0x0b2a66, emissiveIntensity: 0.35 }));
  dev.add(body);
  const capMat = new THREE.MeshPhysicalMaterial({ color: 0x0a1f4c, metalness: 0.5, roughness: 0.3, clearcoat: 1 });
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(1.27, 1.25, 0.16, 96), capMat); cap.position.y = 1.03; dev.add(cap);
  const base = new THREE.Mesh(new THREE.CylinderGeometry(1.4, 1.42, 0.12, 96), capMat); base.position.y = -1.0; dev.add(base);
  const ringMat = new THREE.MeshBasicMaterial({ color: C.sky, transparent: true, opacity: 0.9 });
  const ring = new THREE.Mesh(new THREE.TorusGeometry(1.0, 0.045, 16, 128), ringMat); ring.rotation.x = Math.PI / 2; ring.position.y = 1.115; dev.add(ring);
  // the LCD the real device has, on the front
  const lcdC = document.createElement("canvas"); lcdC.width = 512; lcdC.height = 160;
  const lcdT = new THREE.CanvasTexture(lcdC); lcdT.colorSpace = THREE.SRGBColorSpace;
  const lcd = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 0.47), new THREE.MeshBasicMaterial({ map: lcdT, toneMapped: false }));
  lcd.position.set(0, 0.2, 1.36); dev.add(lcd);
  const bezel = new THREE.Mesh(new RoundedBoxGeometry(1.62, 0.58, 0.06, 4, 0.06), new THREE.MeshStandardMaterial({ color: 0x020a1e, roughness: 0.25, metalness: 0.2 }));
  bezel.position.set(0, 0.2, 1.29); dev.add(bezel);
  // light strip round the base, like the device's status glow
  const stripMat = new THREE.MeshBasicMaterial({ color: C.sky, toneMapped: false });
  const strip = new THREE.Mesh(new THREE.TorusGeometry(1.395, 0.03, 12, 160), stripMat); strip.rotation.x = Math.PI / 2; strip.position.y = -0.93; dev.add(strip);
  function drawLcd(text, color = "#FFB020") {
    const g = lcdC.getContext("2d"); g.clearRect(0, 0, 512, 160);
    g.fillStyle = "#020a1e"; g.fillRect(0, 0, 512, 160);
    let size = 80; g.font = `700 ${size}px Anek, system-ui, sans-serif`;
    while (g.measureText(text).width > 440 && size > 30) { size -= 4; g.font = `700 ${size}px Anek, system-ui, sans-serif`; }
    g.textAlign = "center"; g.textBaseline = "middle";
    g.shadowColor = color; g.shadowBlur = 24; g.fillStyle = color; g.fillText(text, 256, 86);
    lcdT.needsUpdate = true;
  }
  drawLcd("ON DUTY");
  document.fonts && document.fonts.ready.then(() => drawLcd(state.lcd || "ON DUTY", state.lcdColor));

  // ripples when it speaks
  const ripples = [0, 1, 2].map((i) => {
    const m = new THREE.Mesh(new THREE.TorusGeometry(1.45, 0.02, 8, 128), new THREE.MeshBasicMaterial({ color: C.sky, transparent: true, opacity: 0 }));
    m.rotation.x = Math.PI / 2; m.position.y = -0.2; m.userData.phase = i / 3; dev.add(m); return m;
  });

  // ---------------------------------------------------------------- the systems
  function iconTexture(d) {
    const c = document.createElement("canvas"); c.width = c.height = 256; const g = c.getContext("2d");
    g.translate(56, 56); g.scale(6, 6); g.strokeStyle = "#ffffff"; g.lineWidth = 1.7; g.lineCap = g.lineJoin = "round";
    g.stroke(new Path2D(d));
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  }
  const nodes = {};
  const linkGroup = new THREE.Group(); scene.add(linkGroup);
  for (const [id, [x, y, z, icon]] of Object.entries(LAYOUT)) {
    const g = new THREE.Group(); g.position.set(x, y, z); scene.add(g);
    const tileMat = new THREE.MeshPhysicalMaterial({ color: 0x123473, metalness: 0.1, roughness: 0.15, transmission: 0, clearcoat: 1, transparent: true, opacity: 0.92,
      emissive: C.idle, emissiveIntensity: 0.15 });
    const tile = new THREE.Mesh(new RoundedBoxGeometry(0.95, 0.95, 0.2, 5, 0.16), tileMat); g.add(tile);
    const face = new THREE.Mesh(new THREE.PlaneGeometry(0.62, 0.62), new THREE.MeshBasicMaterial({ map: iconTexture(ICONS[icon]), transparent: true, color: 0xbfd4ff, toneMapped: false }));
    face.position.z = 0.11; g.add(face);
    const halo = new THREE.Mesh(new THREE.RingGeometry(0.62, 0.68, 64), new THREE.MeshBasicMaterial({ color: C.sky, transparent: true, opacity: 0, side: THREE.DoubleSide }));
    g.add(halo);
    // link: a gentle arc from the device to the tile
    const a = new THREE.Vector3(0, 0.1, 0.4), b = new THREE.Vector3(x, y, z), mid = a.clone().lerp(b, 0.5).add(new THREE.Vector3(0, 0, 1.2));
    const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
    const lineMat = new THREE.MeshBasicMaterial({ color: C.idle, transparent: true, opacity: 0.35 });
    const line = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.012, 6, false), lineMat); linkGroup.add(line);
    nodes[id] = { g, tile, tileMat, face, halo, curve, lineMat, tone: "", active: false, packets: [], seed: Math.random() * 6 };
  }
  const packetGeo = new THREE.SphereGeometry(0.06, 16, 16);
  function sendPackets(id, color = C.sky, n = 4, inbound = true) {
    const nd = nodes[id]; if (!nd) return;
    for (let i = 0; i < n; i++) {
      const m = new THREE.Mesh(packetGeo, new THREE.MeshBasicMaterial({ color, toneMapped: false }));
      m.userData = { t: -i * 0.12, inbound }; scene.add(m); nd.packets.push(m);
    }
  }

  // dust for depth
  const dustGeo = new THREE.BufferGeometry(); const N = 500; const pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) { pos[i * 3] = (Math.random() - 0.5) * 30; pos[i * 3 + 1] = (Math.random() - 0.5) * 16; pos[i * 3 + 2] = -Math.random() * 14 - 2; }
  dustGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({ color: 0x6f9be8, size: 0.04, transparent: true, opacity: 0.55 }));
  scene.add(dust);

  // ---------------------------------------------------------------- post
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.75, 0.6, 0.62);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  // ---------------------------------------------------------------- state from stage.js
  const state = { box: "idle", lcd: "ON DUTY", lcdColor: "#FFB020", speakUntil: 0, flash: 0 };
  const BOXC = { idle: C.sky, thinking: C.sky, speaking: C.sky, listening: C.haldi, fixed: C.leaf, stopped: C.sindoor };
  const PHASE_ZOOM = { idle: 1, detect: 0.86, investigate: 0.95, reconcile: 0.93, fix: 0.9, verify: 0.95, follow: 1, refuse: 0.88 };
  state.phase = "idle"; state.baseZ = 14; state.focus = null; state.sweep = 0;
  const pv = new THREE.Vector3();
  function toScreen(x, y, z) { pv.set(x, y, z).project(camera); return { x: (pv.x * 0.5 + 0.5) * W, y: (-pv.y * 0.5 + 0.5) * H }; }
  window.Scene3D = {
    node(id, tone, active) {
      const nd = nodes[id]; if (!nd) return;
      if (tone != null) nd.tone = tone;
      if (active != null) { if (active && !nd.active) sendPackets(id, C.sky, 5, true); nd.active = active; }
    },
    burst(id, tone) { sendPackets(id, TONE[tone] || C.leaf, 6, false); },
    phase(p) { if (p !== state.phase && (p === "fix" || p === "verify")) state.sweep = 1; state.phase = p; },
    focus(id) { state.focus = id; },
    screen(id) { const nd = nodes[id]; if (!nd) return null; nd.g.getWorldPosition(pv); return toScreen(pv.x, pv.y, pv.z); },
    boxScreen() { return toScreen(0, 0.3 * 1.3, 1.6); },
    box(st, lcd) {
      state.box = st;
      if (lcd != null) { state.lcd = lcd; state.lcdColor = st === "stopped" ? "#FF5B4A" : st === "fixed" ? "#26D49A" : "#FFB020"; drawLcd(lcd, state.lcdColor); }
      if (st === "speaking") state.speakUntil = performance.now() + 3200;
      if (st === "listening") state.speakUntil = performance.now() + 30000;
      if (st === "stopped" || st === "fixed") state.flash = 1;
    },
  };

  // labels: the HTML .node elements follow their tiles
  const v = new THREE.Vector3();
  function placeLabels(w, h) {
    for (const [id, nd] of Object.entries(nodes)) {
      const el = document.getElementById(`n-${id}`); if (!el) continue;
      nd.g.getWorldPosition(v); v.y -= 0.62; v.project(camera);
      el.style.left = `${(v.x * 0.5 + 0.5) * w}px`; el.style.top = `${(-v.y * 0.5 + 0.5) * h}px`;
    }
    const bl = document.getElementById("box3-label");
    if (bl) { v.set(0, -1.6, 1.6).project(camera); bl.style.left = `${(v.x * 0.5 + 0.5) * w}px`; bl.style.top = `${(-v.y * 0.5 + 0.5) * h}px`; }
  }

  let W = 0, H = 0;
  function resize() {
    W = map.clientWidth; H = map.clientHeight;
    if (!W || !H) return;
    renderer.setSize(W, H, false); composer.setSize(W, H); bloom.resolution.set(W, H);
    camera.aspect = W / H;
    // keep the whole constellation in frame whatever the aspect
    const needW = 11.6, needH = 7.2;
    const fov = THREE.MathUtils.degToRad(camera.fov);
    const dH = needH / 2 / Math.tan(fov / 2), dW = needW / 2 / Math.tan(fov / 2) / camera.aspect;
    state.baseZ = Math.max(dH, dW) + 1.2; camera.position.z = state.baseZ;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(map); resize();

  const mouse = { x: 0, y: 0 };
  addEventListener("pointermove", (e) => { mouse.x = e.clientX / innerWidth - 0.5; mouse.y = e.clientY / innerHeight - 0.5; });
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const col = new THREE.Color(), tmp = new THREE.Color();
  const clock = new THREE.Clock();
  const look = new THREE.Vector3();
  const sweepLight = new THREE.PointLight(C.leaf, 0, 9); sweepLight.position.set(-6, 1.5, 3); scene.add(sweepLight);

  function frame() {
    const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime, now = performance.now();
    if (!reduced) {
      dev.rotation.y = Math.sin(t * 0.35) * 0.18 + mouse.x * 0.35;
      dev.position.y = Math.sin(t * 1.1) * 0.06;
      camera.position.x += (mouse.x * 1.2 - camera.position.x) * 0.04;
      camera.position.y += (2.4 - mouse.y * 0.8 - camera.position.y) * 0.04;
      dust.rotation.y = t * 0.01;
    }
    const zt = state.baseZ * (PHASE_ZOOM[state.phase] || 1);
    camera.position.z += (zt - camera.position.z) * 0.03;
    const fz = state.focus && nodes[state.focus] ? nodes[state.focus].g.position : null;
    look.x += ((fz ? fz.x * 0.12 : 0) - look.x) * 0.05; look.y += ((fz ? fz.y * 0.1 : 0) - look.y) * 0.05;
    camera.lookAt(look);
    state.sweep = Math.max(0, state.sweep - dt * 0.6);
    sweepLight.intensity = state.sweep * 60; sweepLight.position.x = -6 + (1 - state.sweep) * 12;
    // device ring
    const boxCol = BOXC[state.box] || C.sky;
    ringMat.color.lerp(tmp.set(boxCol), 0.12); stripMat.color.lerp(tmp.set(boxCol), 0.12);
    ringMat.opacity = state.box === "thinking" ? 0.55 + 0.45 * Math.sin(t * 9) ** 2 : 0.9;
    state.flash = Math.max(0, state.flash - dt * 0.8);
    rim.color.lerp(tmp.set(boxCol), 0.1); rim.intensity = 30 + state.flash * 80;
    const speaking = now < state.speakUntil;
    ripples.forEach((r) => {
      const p = (t * 0.6 + r.userData.phase) % 1;
      const q = state.box === "listening" ? 1 - p : p;
      r.scale.setScalar(1 + q * 1.1); r.material.opacity = speaking ? (state.box === "listening" ? p : 1 - p) * 0.7 : Math.max(0, r.material.opacity - dt);
      r.material.color.set(boxCol);
    });
    // tiles and links
    for (const nd of Object.values(nodes)) {
      const target = nd.active ? C.sky : TONE[nd.tone] ?? C.idle;
      col.set(target);
      nd.tileMat.emissive.lerp(col, 0.1);
      nd.tileMat.emissiveIntensity += ((nd.active ? 1.4 : nd.tone ? 0.8 : 0.15) - nd.tileMat.emissiveIntensity) * 0.1;
      nd.lineMat.color.lerp(col, 0.1);
      nd.lineMat.opacity += ((nd.active ? 0.95 : nd.tone ? 0.6 : 0.3) - nd.lineMat.opacity) * 0.1;
      nd.face.material.color.lerp(tmp.set(nd.tone || nd.active ? 0xffffff : 0xbfd4ff), 0.1);
      nd.halo.material.opacity = nd.active ? 0.5 + 0.4 * Math.sin(t * 8) : Math.max(0, nd.halo.material.opacity - dt * 2);
      nd.halo.scale.setScalar(nd.active ? 1 + 0.08 * Math.sin(t * 8) : 1);
      if (!reduced) { nd.g.position.y += Math.sin(t * 0.9 + nd.seed) * 0.0012; nd.g.rotation.y = Math.sin(t * 0.5 + nd.seed) * 0.25 + mouse.x * 0.3; nd.g.rotation.x = mouse.y * 0.2; }
      nd.packets = nd.packets.filter((m) => {
        m.userData.t += dt * 1.25;
        const tt = m.userData.t; if (tt < 0) { m.visible = false; return true; }
        if (tt > 1) { scene.remove(m); m.material.dispose(); return false; }
        m.visible = true;
        nd.curve.getPoint(m.userData.inbound ? 1 - tt : tt, m.position);
        return true;
      });
      if (nd.active && Math.random() < dt * 3) sendPackets(Object.keys(nodes).find((k) => nodes[k] === nd), C.sky, 1, true);
    }
    composer.render();
    placeLabels(W, H);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
