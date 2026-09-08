/**
 * pointsField — owns the Three.js particle scene for the welcome splash.
 *
 * Builds two `THREE.Points` clouds:
 *  - the main glyph ("YKM" + cat head) sampled by `sampleGlyphs` and extruded
 *    into a volumetric relief, which spirals in and assembles once (~2.5 s),
 *    then idles with a gentle sway and per-particle shimmer; it reacts to the
 *    cursor (hover makes particles flow, then spring home) and can be dragged
 *    to rotate for a full 360° inspection, springing back face-on on release;
 *  - a sparse ambient "cosmos" field of dim particles drifting slowly behind
 *    the glyph (GPU-side drift, never assembled, never displaced by the mouse).
 *
 * Rendering uses a custom additive glow shader + `UnrealBloomPass`. The caller
 * (ParticleCanvas) drives `requestAnimationFrame` and calls `render(dt, t)`;
 * all simulation logic lives here. `dispose()` releases every GPU resource.
 */

import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { sampleGlyphs } from "./sampleGlyphs";
import { clamp, stepToward, wrapAngle } from "./dragRotation";

/** World-space box the glyph is fit into (kept in sync with sampleGlyphs). */
const GLYPH_WIDTH = 20;
const GLYPH_HEIGHT = 7;
/** Extra framing margin so the glyph never touches the viewport edges. */
const FRAME_MARGIN = 1.32;
const CAMERA_FOV = 45;

const ASSEMBLE_DURATION = 1.4; // travel time of a single particle
const ASSEMBLE_STAGGER = 1.1; // spread of per-particle start delays (→ ~2.5 s total)

const MOUSE_RADIUS = 3.6; // world units of cursor influence
const MOUSE_FOLLOW = 3.2; // coupling of pointer velocity into particle velocity
const MOUSE_PUSH = 9.0; // slight outward "parting" impulse near the cursor
const SPRING = 24.0; // spring stiffness pulling particles home
const DAMPING = 5.5; // velocity damping coefficient (per second)
const MAX_POINTER_SPEED = 260; // clamp for pointer velocity spikes

// Drag-to-rotate: the glyph is extruded into a volumetric relief so it can be
// inspected from any angle; releasing the pointer springs it back face-on.
const EXTRUDE_LAYERS = 3; // depth layers per sampled ink point
const EXTRUDE_DEPTH = 0.8; // total world-space depth of the relief
const YAW_SPEED = 0.005; // radians of yaw per pixel of horizontal drag
const PITCH_SPEED = 0.004; // radians of pitch per pixel of vertical drag
const PITCH_LIMIT = 1.2; // clamp so the mark never tumbles fully over
const DRAG_RATE = 20; // how tightly rotation follows the pointer while dragging
const HOME_RATE = 6; // how quickly rotation springs home after release

const AMBIENT_COUNT = 340;
const ICE_WHITE = new THREE.Color("#eaf4ff");
const PALE_BLUE = new THREE.Color("#9fc6ff");

export interface PointsFieldHandle {
  /** Advance the simulation by `dt` seconds at absolute time `t`, then draw. */
  render(dt: number, t: number): void;
  /** Resize renderer, camera framing and composer to a CSS-pixel size. */
  resize(width: number, height: number): void;
  /** Release geometry, materials, composer and renderer. */
  dispose(): void;
}

const GLYPH_VERTEX = /* glsl */ `
  attribute float aScale;
  uniform float uTime;
  uniform float uSize;
  uniform float uPixelRatio;
  varying float vShimmer;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    float shimmer = 0.72 + 0.28 * sin(uTime * 2.4 + position.x * 1.7 + position.y * 2.1);
    vShimmer = shimmer;
    gl_PointSize = uSize * aScale * uPixelRatio * shimmer * (300.0 / max(0.001, -mv.z));
  }
`;

const GLYPH_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  varying float vShimmer;
  void main() {
    vec2 uv = gl_PointCoord - vec2(0.5);
    float d = length(uv);
    float alpha = pow(smoothstep(0.5, 0.0, d), 1.7);
    if (alpha < 0.01) discard;
    vec3 col = uColor * (0.65 + 0.55 * vShimmer);
    gl_FragColor = vec4(col, alpha * (0.5 + 0.5 * vShimmer) * uOpacity);
  }
`;

const AMBIENT_VERTEX = /* glsl */ `
  attribute float aSeed;
  uniform float uTime;
  uniform float uSize;
  uniform float uPixelRatio;
  varying float vTwinkle;
  void main() {
    vec3 p = position;
    p.x += sin(uTime * 0.13 + aSeed * 41.0) * 1.1;
    p.y += cos(uTime * 0.11 + aSeed * 27.0) * 1.1;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    float twinkle = 0.35 + 0.65 * (0.5 + 0.5 * sin(uTime * 1.3 + aSeed * 63.0));
    vTwinkle = twinkle;
    gl_PointSize = uSize * uPixelRatio * twinkle * (300.0 / max(0.001, -mv.z));
  }
`;

const AMBIENT_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  varying float vTwinkle;
  void main() {
    vec2 uv = gl_PointCoord - vec2(0.5);
    float d = length(uv);
    float alpha = pow(smoothstep(0.5, 0.0, d), 1.6);
    if (alpha < 0.01) discard;
    gl_FragColor = vec4(uColor, alpha * 0.5 * vTwinkle);
  }
`;

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/**
 * Build the particle field inside `container`. Async because glyph sampling
 * awaits webfont readiness. Throws if a WebGL renderer cannot be created.
 */
export async function createPointsField(container: HTMLElement): Promise<PointsFieldHandle> {
  const flat = await sampleGlyphs({
    targetWidth: GLYPH_WIDTH,
    targetHeight: GLYPH_HEIGHT,
  });
  // Extrude the flat ink into a volumetric relief: each sampled point becomes
  // several particles spread across a depth range (with a little xy jitter),
  // so the mark reads as a solid from any angle, not a paper-thin card.
  const baseCount = Math.floor(flat.length / 3);
  const count = baseCount * EXTRUDE_LAYERS;
  const home = new Float32Array(count * 3);
  for (let b = 0; b < baseCount; b++) {
    for (let l = 0; l < EXTRUDE_LAYERS; l++) {
      const i = b * EXTRUDE_LAYERS + l;
      const z = EXTRUDE_LAYERS > 1 ? (l / (EXTRUDE_LAYERS - 1) - 0.5) * EXTRUDE_DEPTH : 0;
      home[i * 3] = flat[b * 3] + (Math.random() - 0.5) * 0.05;
      home[i * 3 + 1] = flat[b * 3 + 1] + (Math.random() - 0.5) * 0.05;
      home[i * 3 + 2] = z + (Math.random() - 0.5) * 0.03;
    }
  }

  const width = Math.max(1, container.clientWidth);
  const height = Math.max(1, container.clientHeight);
  const pixelRatio = Math.min(typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1, 2);

  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(pixelRatio);
  renderer.setSize(width, height);
  renderer.setClearColor(0x000000, 1);
  renderer.domElement.style.display = "block";
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(CAMERA_FOV, width / height, 0.1, 300);

  // --- Main glyph points -------------------------------------------------
  const spawn = new Float32Array(count * 3);
  const live = new Float32Array(count * 3);
  const velocity = new Float32Array(count * 3);
  const delays = new Float32Array(count);
  const scales = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const frac = count > 1 ? i / (count - 1) : 0;
    const angle = frac * Math.PI * 2 * 7 + i * 0.013;
    const radius = 5 + frac * 20;
    spawn[i * 3] = Math.cos(angle) * radius;
    spawn[i * 3 + 1] = Math.sin(angle) * radius * 0.55;
    spawn[i * 3 + 2] = Math.sin(frac * Math.PI * 5) * 3;
    live[i * 3] = spawn[i * 3];
    live[i * 3 + 1] = spawn[i * 3 + 1];
    live[i * 3 + 2] = spawn[i * 3 + 2];
    delays[i] = frac * ASSEMBLE_STAGGER;
    scales[i] = 0.6 + Math.random() * 0.9;
  }

  const glyphGeometry = new THREE.BufferGeometry();
  const positionAttr = new THREE.BufferAttribute(live, 3);
  positionAttr.setUsage(THREE.DynamicDrawUsage);
  glyphGeometry.setAttribute("position", positionAttr);
  glyphGeometry.setAttribute("aScale", new THREE.BufferAttribute(scales, 1));

  const glyphUniforms = {
    uTime: { value: 0 },
    // The extruded layers stack additively when viewed face-on, so a smaller
    // size + per-particle opacity keep the front view from blowing out.
    uSize: { value: 0.45 },
    uOpacity: { value: 0.45 },
    uPixelRatio: { value: pixelRatio },
    uColor: { value: ICE_WHITE },
  };
  const glyphMaterial = new THREE.ShaderMaterial({
    uniforms: glyphUniforms,
    vertexShader: GLYPH_VERTEX,
    fragmentShader: GLYPH_FRAGMENT,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const glyphPoints = new THREE.Points(glyphGeometry, glyphMaterial);
  const glyphGroup = new THREE.Group();
  glyphGroup.add(glyphPoints);
  scene.add(glyphGroup);

  // --- Ambient cosmos field ---------------------------------------------
  const ambientPos = new Float32Array(AMBIENT_COUNT * 3);
  const ambientSeed = new Float32Array(AMBIENT_COUNT);
  for (let i = 0; i < AMBIENT_COUNT; i++) {
    ambientPos[i * 3] = (Math.random() - 0.5) * 90;
    ambientPos[i * 3 + 1] = (Math.random() - 0.5) * 50;
    ambientPos[i * 3 + 2] = -6 - Math.random() * 34;
    ambientSeed[i] = Math.random();
  }
  const ambientGeometry = new THREE.BufferGeometry();
  ambientGeometry.setAttribute("position", new THREE.BufferAttribute(ambientPos, 3));
  ambientGeometry.setAttribute("aSeed", new THREE.BufferAttribute(ambientSeed, 1));
  const ambientUniforms = {
    uTime: { value: 0 },
    uSize: { value: 0.5 },
    uPixelRatio: { value: pixelRatio },
    uColor: { value: PALE_BLUE },
  };
  const ambientMaterial = new THREE.ShaderMaterial({
    uniforms: ambientUniforms,
    vertexShader: AMBIENT_VERTEX,
    fragmentShader: AMBIENT_FRAGMENT,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const ambientPoints = new THREE.Points(ambientGeometry, ambientMaterial);
  const ambientGroup = new THREE.Group();
  ambientGroup.add(ambientPoints);
  scene.add(ambientGroup);

  // --- Post-processing bloom --------------------------------------------
  const composer = new EffectComposer(renderer);
  composer.setPixelRatio(pixelRatio);
  composer.setSize(width, height);
  composer.addPass(new RenderPass(scene, camera));
  const bloomPass = new UnrealBloomPass(new THREE.Vector2(width, height), 0.9, 0.55, 0.18);
  composer.addPass(bloomPass);

  // --- Pointer tracking --------------------------------------------------
  const ndc = new THREE.Vector2(0, 0);
  const pointerWorld = new THREE.Vector3();
  const pointerLocal = new THREE.Vector3();
  const prevPointerLocal = new THREE.Vector3();
  let hasPointer = false;

  // Drag-to-rotate state.
  let dragging = false;
  let targetYaw = 0;
  let targetPitch = 0;
  let dragYaw = 0;
  let dragPitch = 0;
  let lastPointerX = 0;
  let lastPointerY = 0;

  function setNdc(event: PointerEvent): void {
    const rect = renderer.domElement.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    ndc.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    ndc.y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
    hasPointer = true;
  }

  function onPointerDown(event: PointerEvent): void {
    dragging = true;
    lastPointerX = event.clientX;
    lastPointerY = event.clientY;
    renderer.domElement.setPointerCapture(event.pointerId);
    renderer.domElement.style.cursor = "grabbing";
  }
  function onPointerMove(event: PointerEvent): void {
    setNdc(event);
    if (!dragging) return;
    const dx = event.clientX - lastPointerX;
    const dy = event.clientY - lastPointerY;
    lastPointerX = event.clientX;
    lastPointerY = event.clientY;
    targetYaw += dx * YAW_SPEED; // unbounded — full 360° inspection
    targetPitch = clamp(targetPitch + dy * PITCH_SPEED, -PITCH_LIMIT, PITCH_LIMIT);
  }
  function onPointerUp(event: PointerEvent): void {
    if (!dragging) return;
    dragging = false;
    renderer.domElement.releasePointerCapture(event.pointerId);
    renderer.domElement.style.cursor = "grab";
    // Spring home by the shortest arc: wrap the current yaw, then target zero.
    dragYaw = wrapAngle(dragYaw);
    targetYaw = 0;
    targetPitch = 0;
    // Re-sync the flow pointer so hover-push resumes without a velocity spike.
    setNdc(event);
    updatePointerLocal();
    prevPointerLocal.copy(pointerLocal);
  }
  function onPointerLeave(): void {
    hasPointer = false;
  }
  renderer.domElement.style.cursor = "grab";
  renderer.domElement.style.touchAction = "none";
  renderer.domElement.addEventListener("pointerdown", onPointerDown);
  renderer.domElement.addEventListener("pointermove", onPointerMove);
  renderer.domElement.addEventListener("pointerup", onPointerUp);
  renderer.domElement.addEventListener("pointercancel", onPointerUp);
  renderer.domElement.addEventListener("pointerleave", onPointerLeave);

  function updatePointerLocal(): void {
    // Intersect the camera ray through the NDC with the glyph plane (z = 0),
    // then express it in the glyph group's local space (accounts for sway).
    const v = new THREE.Vector3(ndc.x, ndc.y, 0.5).unproject(camera);
    const dir = v.sub(camera.position); // un-normalised ray direction
    if (Math.abs(dir.z) < 1e-6) return;
    const s = -camera.position.z / dir.z; // ray parameter at which z = 0
    pointerWorld.copy(camera.position).addScaledVector(dir, s);
    glyphGroup.updateMatrixWorld();
    pointerLocal.copy(glyphGroup.worldToLocal(pointerWorld.clone()));
  }

  function framingDistance(aspect: number): number {
    const vFov = (CAMERA_FOV * Math.PI) / 180;
    const halfTan = Math.tan(vFov / 2);
    const distH = (GLYPH_HEIGHT * FRAME_MARGIN) / (2 * halfTan);
    const distW = (GLYPH_WIDTH * FRAME_MARGIN) / (2 * halfTan * aspect);
    return Math.max(distH, distW);
  }

  camera.position.set(0, 0, framingDistance(width / height));
  camera.lookAt(0, 0, 0);

  let elapsed = 0;
  let assembled = count === 0;
  let disposed = false;

  function stepAssemble(): void {
    for (let i = 0; i < count; i++) {
      const local = Math.min(1, Math.max(0, (elapsed - delays[i]) / ASSEMBLE_DURATION));
      const e = easeOutCubic(local);
      const i3 = i * 3;
      live[i3] = spawn[i3] + (home[i3] - spawn[i3]) * e;
      live[i3 + 1] = spawn[i3 + 1] + (home[i3 + 1] - spawn[i3 + 1]) * e;
      live[i3 + 2] = spawn[i3 + 2] + (home[i3 + 2] - spawn[i3 + 2]) * e;
    }
    if (elapsed >= ASSEMBLE_STAGGER + ASSEMBLE_DURATION) {
      // Snap to home and hand over to the idle spring system.
      live.set(home);
      velocity.fill(0);
      assembled = true;
    }
  }

  function stepIdle(dt: number): void {
    let pvx = 0;
    let pvy = 0;
    if (hasPointer) {
      pvx = (pointerLocal.x - prevPointerLocal.x) / dt;
      pvy = (pointerLocal.y - prevPointerLocal.y) / dt;
      const speed = Math.hypot(pvx, pvy);
      if (speed > MAX_POINTER_SPEED) {
        const k = MAX_POINTER_SPEED / speed;
        pvx *= k;
        pvy *= k;
      }
    }
    const damp = Math.exp(-DAMPING * dt);
    const r2 = MOUSE_RADIUS * MOUSE_RADIUS;
    for (let i = 0; i < count; i++) {
      const i3 = i * 3;
      const px = live[i3];
      const py = live[i3 + 1];
      const dx = px - pointerLocal.x;
      const dy = py - pointerLocal.y;
      const d2 = dx * dx + dy * dy;
      if (hasPointer && !dragging && d2 < r2) {
        const d = Math.sqrt(d2) || 1e-4;
        const falloff = 1 - d / MOUSE_RADIUS;
        const impulse = falloff * falloff;
        velocity[i3] += (pvx * MOUSE_FOLLOW + (dx / d) * MOUSE_PUSH) * impulse * dt;
        velocity[i3 + 1] += (pvy * MOUSE_FOLLOW + (dy / d) * MOUSE_PUSH) * impulse * dt;
      }
      // Spring back toward home + damping.
      velocity[i3] += (home[i3] - px) * SPRING * dt;
      velocity[i3 + 1] += (home[i3 + 1] - py) * SPRING * dt;
      velocity[i3 + 2] += (home[i3 + 2] - live[i3 + 2]) * SPRING * dt;
      velocity[i3] *= damp;
      velocity[i3 + 1] *= damp;
      velocity[i3 + 2] *= damp;
      live[i3] += velocity[i3] * dt;
      live[i3 + 1] += velocity[i3 + 1] * dt;
      live[i3 + 2] += velocity[i3 + 2] * dt;
    }
  }

  function render(dt: number, t: number): void {
    if (disposed) return;
    const step = Math.min(0.05, Math.max(0.0001, dt));
    elapsed += step;

    glyphUniforms.uTime.value = t;
    ambientUniforms.uTime.value = t;

    // Ease the drag offset toward its target (tight while dragging, springing
    // home after release), composed over the gentle idle sway.
    const rate = dragging ? DRAG_RATE : HOME_RATE;
    dragYaw = stepToward(dragYaw, targetYaw, step, rate);
    dragPitch = stepToward(dragPitch, targetPitch, step, rate);
    glyphGroup.rotation.y = Math.sin(t * 0.25) * 0.18 + dragYaw;
    glyphGroup.rotation.x = Math.sin(t * 0.18) * 0.06 + dragPitch;
    ambientGroup.rotation.z += step * 0.006;

    if (hasPointer) updatePointerLocal();

    if (!assembled) {
      stepAssemble();
    } else {
      stepIdle(step);
      if (hasPointer && !dragging) prevPointerLocal.copy(pointerLocal);
    }
    positionAttr.needsUpdate = true;

    composer.render(step);
  }

  function resize(w: number, h: number): void {
    if (disposed) return;
    const nw = Math.max(1, w);
    const nh = Math.max(1, h);
    camera.aspect = nw / nh;
    camera.position.z = framingDistance(camera.aspect);
    camera.updateProjectionMatrix();
    renderer.setSize(nw, nh);
    composer.setSize(nw, nh);
    bloomPass.setSize(nw, nh);
  }

  function dispose(): void {
    if (disposed) return;
    disposed = true;
    renderer.domElement.removeEventListener("pointerdown", onPointerDown);
    renderer.domElement.removeEventListener("pointermove", onPointerMove);
    renderer.domElement.removeEventListener("pointerup", onPointerUp);
    renderer.domElement.removeEventListener("pointercancel", onPointerUp);
    renderer.domElement.removeEventListener("pointerleave", onPointerLeave);
    glyphGeometry.dispose();
    glyphMaterial.dispose();
    ambientGeometry.dispose();
    ambientMaterial.dispose();
    bloomPass.dispose();
    composer.dispose();
    renderer.dispose();
    renderer.forceContextLoss?.();
    if (renderer.domElement.parentNode === container) {
      container.removeChild(renderer.domElement);
    }
  }

  return { render, resize, dispose };
}
