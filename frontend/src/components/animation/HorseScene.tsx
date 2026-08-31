import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import styles from '@/pages/AnimationPage.module.css';

export const ADULT_HORSE_ASSET_URL = '/models/horse-adult.glb';

export type SceneStatus = 'loading' | 'ready' | 'playing' | 'complete' | 'unsupported' | 'error';
export type TimelinePhase =
  | 'opening'
  | 'gathering'
  | 'transforming'
  | 'burst'
  | 'pause'
  | 'gallop'
  | 'pullback'
  | 'complete';

interface HorseSceneProps {
  playToken: number;
  reducedMotion: boolean;
  onStatusChange: (status: SceneStatus) => void;
  onPhaseChange: (phase: TimelinePhase) => void;
}

interface HorseRig {
  root: THREE.Group;
  update: (growth: number, stride: number, gallop: boolean) => void;
}

interface EffectRig {
  root: THREE.Group;
  water: THREE.Mesh;
  rings: THREE.Mesh[];
  swirl: THREE.Group;
  burst: THREE.Group;
  droplets: THREE.Mesh[];
  mist: THREE.Points;
  initialMistPositions: Float32Array;
}

type LoadedAsset = {
  scene: THREE.Object3D;
  animations: THREE.AnimationClip[];
};

const TIMELINE_SECONDS = 20;
const FALLBACK_DURATION_MS = 5200;
const GLB_PONY_SCALE = 0.0105;
const GLB_ADULT_SCALE = 0.015;

/**
 * The only asset-loading boundary in the experience. A production-quality
 * horse can be dropped at /models/horse-adult.glb without changing the
 * timeline or water choreography. The procedural rig remains the intentional
 * offline fallback until that file is supplied.
 */
function loadAdultHorseAsset(loader: GLTFLoader): Promise<LoadedAsset> {
  return new Promise((resolve, reject) => {
    loader.load(ADULT_HORSE_ASSET_URL, resolve, undefined, reject);
  });
}

function hasWebGL(canvas: HTMLCanvasElement): boolean {
  try {
    return Boolean(
      canvas.getContext('webgl2') ||
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl')
    );
  } catch {
    return false;
  }
}

function materialSetOpacity(material: THREE.Material, opacity: number) {
  material.transparent = opacity < 1;
  material.opacity = opacity;
}

function makeMesh(
  geometry: THREE.BufferGeometry,
  material: THREE.Material,
  parent: THREE.Object3D,
  position?: THREE.Vector3
): THREE.Mesh {
  const mesh = new THREE.Mesh(geometry, material);
  if (position) mesh.position.copy(position);
  parent.add(mesh);
  return mesh;
}

function makeHorseRig(): HorseRig {
  const root = new THREE.Group();
  root.name = 'procedural-equine-fallback';
  const coat = new THREE.MeshStandardMaterial({
    color: 0x5a3521,
    roughness: 0.72,
    metalness: 0.03,
  });
  const darkCoat = new THREE.MeshStandardMaterial({
    color: 0x2d1a12,
    roughness: 0.85,
  });
  const black = new THREE.MeshStandardMaterial({ color: 0x110b08, roughness: 0.45 });
  const hoof = new THREE.MeshStandardMaterial({ color: 0x171310, roughness: 0.4, metalness: 0.12 });

  const body = makeMesh(new THREE.SphereGeometry(1, 28, 18), coat, root);
  body.name = 'full-chest-and-barrel';
  body.scale.set(1.48, 0.88, 0.68);
  body.position.set(-0.05, 2.05, 0);

  const shoulder = makeMesh(new THREE.SphereGeometry(0.78, 24, 16), coat, root);
  shoulder.scale.set(0.9, 1.12, 0.84);
  shoulder.position.set(0.63, 2.07, 0);

  const rump = makeMesh(new THREE.SphereGeometry(0.82, 24, 16), coat, root);
  rump.scale.set(0.95, 1.04, 0.86);
  rump.position.set(-0.91, 2.08, 0);

  const neck = makeMesh(new THREE.CylinderGeometry(0.38, 0.6, 1.9, 20), coat, root);
  neck.name = 'long-arched-neck';
  neck.position.set(0.78, 2.98, 0);
  neck.rotation.z = -0.2;

  const throat = makeMesh(new THREE.SphereGeometry(0.48, 20, 14), coat, root);
  throat.scale.set(0.7, 1.3, 0.75);
  throat.position.set(1.02, 3.32, 0);

  const head = makeMesh(new THREE.SphereGeometry(0.5, 24, 16), coat, root);
  head.name = 'equine-head';
  head.scale.set(1.08, 0.9, 0.72);
  head.position.set(1.23, 3.72, 0);
  head.rotation.z = -0.12;

  const muzzle = makeMesh(new THREE.SphereGeometry(0.32, 20, 14), coat, root);
  muzzle.name = 'muzzle-with-nostrils';
  muzzle.scale.set(1.25, 0.7, 0.82);
  muzzle.position.set(1.63, 3.57, 0);

  for (const z of [-0.19, 0.19]) {
    const nostril = makeMesh(new THREE.SphereGeometry(0.052, 10, 8), black, root);
    nostril.position.set(1.83, 3.62, z);
    nostril.scale.set(0.8, 0.7, 1);
  }

  for (const z of [-0.31, 0.31]) {
    const eye = makeMesh(new THREE.SphereGeometry(0.075, 12, 10), black, root);
    eye.position.set(1.47, 3.86, z);
    const eyeCatch = makeMesh(
      new THREE.SphereGeometry(0.018, 8, 6),
      new THREE.MeshBasicMaterial({ color: 0xfff3d0 }),
      root
    );
    eyeCatch.position.set(1.515, 3.89, z - (z > 0 ? 0.05 : -0.05));
  }

  for (const z of [-0.24, 0.24]) {
    const ear = makeMesh(new THREE.ConeGeometry(0.16, 0.5, 12), darkCoat, root);
    ear.position.set(1.02, 4.18, z);
    ear.rotation.z = z > 0 ? -0.18 : 0.18;
  }

  const maneMaterial = new THREE.MeshStandardMaterial({
    color: 0x160e0b,
    roughness: 0.96,
    side: THREE.DoubleSide,
  });
  for (let index = 0; index < 6; index += 1) {
    const mane = makeMesh(new THREE.CapsuleGeometry(0.08, 0.78, 5, 10), maneMaterial, root);
    mane.position.set(0.51 - index * 0.18, 3.25 - index * 0.08, -0.31);
    mane.rotation.z = -0.55;
    mane.rotation.x = 0.2;
    mane.scale.set(1, 1 + index * 0.08, 0.6);
  }

  const tailCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-1.46, 2.35, 0),
    new THREE.Vector3(-1.85, 2.1, 0),
    new THREE.Vector3(-2.05, 1.55, 0.08),
    new THREE.Vector3(-1.92, 1.05, 0.12),
  ]);
  const tail = makeMesh(new THREE.TubeGeometry(tailCurve, 16, 0.15, 10, false), maneMaterial, root);
  tail.name = 'flowing-tail';

  const legs: Array<{ group: THREE.Group; lower: THREE.Mesh; shoe: THREE.Mesh }> = [];
  const legPositions = [
    { x: 0.65, z: 0.36, phase: 0 },
    { x: 0.65, z: -0.36, phase: Math.PI },
    { x: -0.72, z: 0.36, phase: Math.PI },
    { x: -0.72, z: -0.36, phase: 0 },
  ];
  for (const legPosition of legPositions) {
    const leg = new THREE.Group();
    leg.name = 'muscular-leg';
    leg.position.set(legPosition.x, 1.68, legPosition.z);
    const upper = makeMesh(new THREE.CapsuleGeometry(0.17, 0.72, 8, 12), coat, leg);
    upper.position.y = -0.42;
    upper.rotation.z = legPosition.x > 0 ? -0.04 : 0.04;
    const lower = makeMesh(new THREE.CapsuleGeometry(0.115, 0.69, 8, 12), darkCoat, leg);
    lower.position.y = -1.08;
    const shoe = makeMesh(new THREE.BoxGeometry(0.27, 0.15, 0.34), hoof, leg);
    shoe.name = 'defined-hoof';
    shoe.position.set(0.04, -1.64, 0);
    shoe.rotation.z = -0.08;
    root.add(leg);
    legs.push({ group: leg, lower, shoe });
    (leg.userData as { phase: number }).phase = legPosition.phase;
  }

  return {
    root,
    update(growth, stride, gallop) {
      const size = 0.73 + growth * 0.27;
      root.scale.setScalar(size);
      body.scale.y = 0.7 + growth * 0.18;
      body.scale.x = 1.25 + growth * 0.23;
      shoulder.scale.y = 0.9 + growth * 0.22;
      rump.scale.y = 0.9 + growth * 0.2;
      neck.scale.y = 0.7 + growth * 0.3;
      head.scale.set(0.9 + growth * 0.18, 0.78 + growth * 0.14, 0.68 + growth * 0.08);
      for (const { group, lower, shoe } of legs) {
        const phase = (group.userData as { phase: number }).phase;
        const swing = Math.sin(phase + stride);
        group.scale.y = 0.66 + growth * 0.34;
        group.position.y = 1.68 + growth * 0.12;
        group.rotation.z = swing * (gallop ? 0.34 : 0.14);
        lower.rotation.z = Math.max(0, -swing) * (gallop ? 0.42 : 0.15);
        shoe.rotation.z = -0.08 - Math.max(0, swing) * 0.16;
      }
      root.position.y = Math.abs(Math.sin(stride * 2)) * (gallop ? 0.07 : 0.025);
      tail.rotation.z = Math.sin(stride * 0.7) * (gallop ? 0.14 : 0.05);
    },
  };
}

function makeEffectRig(): EffectRig {
  const root = new THREE.Group();
  const waterMaterial = new THREE.MeshPhysicalMaterial({
    color: 0x39717b,
    roughness: 0.16,
    metalness: 0.28,
    transmission: 0.12,
    transparent: true,
    opacity: 0.8,
  });
  const water = makeMesh(new THREE.PlaneGeometry(24, 18, 1, 1), waterMaterial, root);
  water.rotation.x = -Math.PI / 2;
  water.position.y = -0.05;

  const ringMaterial = new THREE.MeshBasicMaterial({
    color: 0x8dd2d0,
    transparent: true,
    opacity: 0.44,
    side: THREE.DoubleSide,
  });
  const rings = [0, 0.7, 1.35, 2.1].map((radius) => {
    const ring = makeMesh(new THREE.RingGeometry(0.48 + radius * 0.13, 0.53 + radius * 0.13, 64), ringMaterial, root);
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(-0.15, 0.012, 0.02);
    ring.scale.setScalar(0.1);
    return ring;
  });

  const swirl = new THREE.Group();
  const swirlMaterial = new THREE.MeshBasicMaterial({
    color: 0xb2eeee,
    transparent: true,
    opacity: 0,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
  });
  for (let index = 0; index < 8; index += 1) {
    const arc = makeMesh(new THREE.TorusGeometry(0.74 + index * 0.1, 0.018, 6, 32, Math.PI * 1.45), swirlMaterial, swirl);
    arc.rotation.set(Math.PI / 2 + index * 0.13, index * 0.25, index * 0.45);
    arc.position.y = 1.12 + index * 0.12;
  }
  root.add(swirl);

  const burst = new THREE.Group();
  const burstMaterial = new THREE.MeshBasicMaterial({
    color: 0xd4ffff,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
  });
  for (let index = 0; index < 24; index += 1) {
    const drop = makeMesh(new THREE.SphereGeometry(0.035 + (index % 3) * 0.018, 8, 6), burstMaterial, burst);
    const angle = (index / 24) * Math.PI * 2;
    drop.userData = { angle, distance: 0.8 + (index % 5) * 0.18, lift: 0.3 + (index % 4) * 0.2 };
  }
  root.add(burst);

  const dropletMaterial = new THREE.MeshBasicMaterial({
    color: 0xafffff,
    transparent: true,
    opacity: 0.75,
  });
  const droplets = [0, 1, 2, 3, 4, 5].map((index) => {
    const drop = makeMesh(new THREE.SphereGeometry(0.028 + (index % 2) * 0.02, 8, 6), dropletMaterial, root);
    drop.position.set(-0.9 + (index % 3) * 0.65, 0.08, -0.55 + Math.floor(index / 3) * 1.1);
    return drop;
  });

  const mistMaterial = new THREE.PointsMaterial({
    color: 0xc4e9e3,
    size: 0.075,
    transparent: true,
    opacity: 0.2,
    depthWrite: false,
  });
  const mistPositions = new Float32Array(18 * 3);
  for (let index = 0; index < 18; index += 1) {
    mistPositions[index * 3] = -7 + (index * 1.7) % 14;
    mistPositions[index * 3 + 1] = 0.12 + (index % 5) * 0.1;
    mistPositions[index * 3 + 2] = -3 + (index * 1.1) % 6;
  }
  const mist = new THREE.Points(new THREE.BufferGeometry(), mistMaterial);
  mist.geometry.setAttribute('position', new THREE.BufferAttribute(mistPositions, 3));
  root.add(mist);

  return {
    root,
    water,
    rings,
    swirl,
    burst,
    droplets,
    mist,
    initialMistPositions: mistPositions.slice(),
  };
}

function disposeObjectGraph(root: THREE.Object3D) {
  root.traverse((object) => {
    const mesh = object as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    const material = mesh.material;
    if (Array.isArray(material)) {
      material.forEach((item) => item.dispose());
    } else if (material) {
      material.dispose();
    }
  });
}

function disposeScene(scene: THREE.Scene, renderer: THREE.WebGLRenderer) {
  disposeObjectGraph(scene);
  renderer.dispose();
  renderer.forceContextLoss?.();
}

type FallbackStep = 'opening' | 'gathering' | 'transforming' | 'burst' | 'gallop' | 'complete';

const FALLBACK_STEP_COPY: Record<FallbackStep, string> = {
  opening: 'A small step enters the shallows',
  gathering: 'The water gathers around each hoof',
  transforming: 'Strength rises through the current',
  burst: 'A new shape breaks the surface',
  gallop: 'The adult horse finds open ground',
  complete: 'The journey is complete',
};

function getFallbackStep(progress: number): FallbackStep {
  if (progress >= 1) return 'complete';
  if (progress < 0.2) return 'opening';
  if (progress < 0.4) return 'gathering';
  if (progress < 0.65) return 'transforming';
  if (progress < 0.8) return 'burst';
  return 'gallop';
}

function HorseFallback({
  playToken,
  reducedMotion,
  onStatusChange,
  onPhaseChange,
}: HorseSceneProps) {
  const [progress, setProgress] = useState(0);
  const handledPlayTokenRef = useRef(0);

  useEffect(() => {
    onStatusChange('unsupported');
    onPhaseChange('opening');
  }, [onPhaseChange, onStatusChange]);

  useEffect(() => {
    if (playToken <= handledPlayTokenRef.current) return;
    handledPlayTokenRef.current = playToken;
    setProgress(0);
    onPhaseChange('opening');

    if (reducedMotion) {
      setProgress(1);
      onPhaseChange('complete');
      onStatusChange('complete');
      return;
    }

    onStatusChange('playing');
    let frameId = 0;
    const startedAt = performance.now();
    const advance = (now: number) => {
      const nextProgress = Math.min((now - startedAt) / FALLBACK_DURATION_MS, 1);
      setProgress(nextProgress);
      const nextStep = getFallbackStep(nextProgress);
      onPhaseChange(nextStep === 'complete' ? 'complete' : nextStep);
      if (nextProgress >= 1) {
        onStatusChange('complete');
        return;
      }
      frameId = window.requestAnimationFrame(advance);
    };
    frameId = window.requestAnimationFrame(advance);

    return () => window.cancelAnimationFrame(frameId);
  }, [onPhaseChange, onStatusChange, playToken, reducedMotion]);

  const step = getFallbackStep(progress);
  const isComplete = step === 'complete';

  return (
    <div
      className={styles.fallbackScene}
      data-testid="horse-fallback"
      data-step={step}
      data-progress={progress.toFixed(2)}
      role="img"
      aria-label="Poster-based horse transformation fallback"
    >
      <img
        className={styles.fallbackImage}
        src="/horse-panel.jpg"
        alt="A dark horse standing in an open field beneath a wide evening sky"
      />
      <div className={styles.fallbackImageShade} aria-hidden="true" />
      <div
        className={styles.fallbackPony}
        data-visible={step === 'opening' || step === 'gathering' || step === 'transforming'}
        aria-hidden="true"
      />
      <div
        className={styles.fallbackAdult}
        data-visible={step === 'burst' || step === 'gallop' || isComplete}
        aria-hidden="true"
      />
      <div className={styles.fallbackStory} aria-hidden="true">
        <span className={styles.fallbackStoryKicker}>A non-WebGL study</span>
        <span className={styles.fallbackStoryRule} />
        <span>{FALLBACK_STEP_COPY[step]}</span>
      </div>
      <div className={styles.fallbackSteps} aria-hidden="true">
        <span data-active={step === 'opening' || step === 'gathering'}>first steps</span>
        <span data-active={step === 'transforming' || step === 'burst'}>transformation</span>
        <span data-active={step === 'gallop' || isComplete}>open ground</span>
      </div>
    </div>
  );
}

export function HorseScene({ playToken, reducedMotion, onStatusChange, onPhaseChange }: HorseSceneProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const startSequenceRef = useRef<(() => void) | null>(null);
  const handledPlayTokenRef = useRef(0);
  const [renderMode, setRenderMode] = useState<'webgl' | 'fallback'>('webgl');

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (!hasWebGL(canvas)) {
      setRenderMode('fallback');
      onStatusChange('unsupported');
      return;
    }

    let disposed = false;
    let frameId = 0;
    let startedAt = 0;
    let elapsedBeforePlay = 0;
    let isPlaying = false;
    let timelineComplete = false;
    const clock = new THREE.Clock();
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x102a35);
    scene.fog = new THREE.FogExp2(0x193b43, 0.045);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 80);
    camera.position.set(6.5, 3.7, 8.8);
    camera.lookAt(0, 1.8, 0);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        powerPreference: 'high-performance',
      });
    } catch {
      setRenderMode('fallback');
      onStatusChange('unsupported');
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.65));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const ambient = new THREE.HemisphereLight(0xc8eee9, 0x183239, 1.9);
    scene.add(ambient);
    const key = new THREE.DirectionalLight(0xffe6be, 4.4);
    key.position.set(-4, 8, 5);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.left = -7;
    key.shadow.camera.right = 7;
    key.shadow.camera.top = 7;
    key.shadow.camera.bottom = -3;
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x73d2d0, 2.6);
    rim.position.set(4, 4, -6);
    scene.add(rim);

    const horse = makeHorseRig();
    horse.root.traverse((object) => {
      const mesh = object as THREE.Mesh;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
    });
    scene.add(horse.root);
    const effects = makeEffectRig();
    scene.add(effects.root);
    const loader = new GLTFLoader();
    let externalAsset: THREE.Object3D | undefined;
    let mixer: THREE.AnimationMixer | undefined;
    let assetAction: THREE.AnimationAction | undefined;

    const resize = () => {
      const width = Math.max(canvas.clientWidth, 320);
      const height = Math.max(canvas.clientHeight, 240);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    resize();

    const render = () => {
      if (disposed) return;
      const delta = Math.min(clock.getDelta(), 0.05);
      if (isPlaying) {
        const now = performance.now();
        elapsedBeforePlay = (now - startedAt) / 1000;
      }
      const progress = Math.min(elapsedBeforePlay / (reducedMotion ? 1.1 : TIMELINE_SECONDS), 1);
      const time = progress * TIMELINE_SECONDS;
      const growth = time < 6 ? 0 : Math.min((time - 6) / 4, 1);
      const phase: TimelinePhase =
        time < 3 ? 'opening' :
        time < 6 ? 'gathering' :
        time < 10 ? 'transforming' :
        time < 11.8 ? 'burst' :
        time < 13.6 ? 'pause' :
        time < 17.5 ? 'gallop' :
        time < TIMELINE_SECONDS ? 'pullback' : 'complete';
      const poseTime = phase === 'pause' ? 11.8 : time;
      const stride = poseTime * (poseTime > 13 ? 3.8 : 2.2);
      horse.update(growth, stride, time > 13.6);
      const travel =
        time < 6 ? -1.5 + time * 0.2 :
        time < 13.6 ? -0.3 :
        -0.3 + Math.min((time - 13.6) / 6.4, 1) * 3.2;
      horse.root.position.x = travel;
      if (externalAsset) {
        externalAsset.scale.setScalar(GLB_PONY_SCALE + growth * (GLB_ADULT_SCALE - GLB_PONY_SCALE));
        externalAsset.position.y = Math.abs(Math.sin(stride * 2)) * (time > 13.6 ? 0.07 : 0.025);
        externalAsset.position.x = travel;
        externalAsset.visible = growth > 0.72;
        horse.root.visible = growth < 0.92;
      }
      const swirlOpacity = time >= 3 && time < 10.8 ? Math.sin(Math.min((time - 3) / 7.8, 1) * Math.PI) * 0.72 : 0;
      const swirlMaterial = effects.swirl.children[0] as THREE.Mesh;
      if (!Array.isArray(swirlMaterial.material)) {
        materialSetOpacity(swirlMaterial.material, swirlOpacity);
      }
      effects.swirl.rotation.y += delta * 0.8;
      effects.swirl.visible = swirlOpacity > 0;

      effects.rings.forEach((ring, index) => {
        const rippleProgress = Math.max(0, Math.min(1, (time - index * 0.45) / 3.4));
        ring.scale.setScalar(0.1 + rippleProgress * (1.25 + index * 0.22));
        materialSetOpacity(ring.material as THREE.Material, Math.max(0, 0.44 * (1 - rippleProgress)));
        ring.position.x = travel + (index % 2 ? 0.6 : -0.6);
      });
      const burstProgress = time >= 9.6 && time < 13 ? Math.min((time - 9.6) / 2.1, 1) : 0;
      effects.burst.children.forEach((child) => {
        const drop = child as THREE.Mesh;
        const data = drop.userData as { angle: number; distance: number; lift: number };
        drop.position.set(
          Math.cos(data.angle) * data.distance * burstProgress,
          0.45 + data.lift * burstProgress - burstProgress * burstProgress * 0.38,
          Math.sin(data.angle) * data.distance * burstProgress
        );
      });
      materialSetOpacity((effects.burst.children[0] as THREE.Mesh).material as THREE.Material, burstProgress > 0 ? 0.86 * (1 - burstProgress * 0.38) : 0);
      effects.droplets.forEach((drop, index) => {
        drop.position.x = travel - 0.75 + (index % 3) * 0.65;
        drop.position.y = 0.06 + Math.abs(Math.sin(stride + index)) * (burstProgress > 0 ? 0.6 : 0.12);
      });
      const mistPositions = effects.mist.geometry.getAttribute('position') as THREE.BufferAttribute;
      for (let index = 0; index < mistPositions.count; index += 1) {
        mistPositions.setY(index, mistPositions.getY(index) + delta * (0.018 + (index % 3) * 0.008));
        if (mistPositions.getY(index) > 0.9) mistPositions.setY(index, 0.08);
      }
      mistPositions.needsUpdate = true;

      const pullback = time < 13.6 ? 0 : Math.min((time - 13.6) / 6.4, 1);
      camera.position.x = 6.5 + Math.sin(time * 0.13) * 0.28 + pullback * 2.2;
      camera.position.y = 3.7 + Math.sin(time * 0.21) * 0.08 + pullback * 0.8;
      camera.position.z = 8.8 + pullback * 4;
      camera.lookAt(travel * 0.48, 1.8, 0);
      if (mixer && isPlaying && phase !== 'pause') mixer.update(delta);
      renderer.render(scene, camera);

      if (isPlaying && progress >= 1) {
        isPlaying = false;
        timelineComplete = true;
        elapsedBeforePlay = reducedMotion ? 1.1 : TIMELINE_SECONDS;
        onPhaseChange('complete');
        onStatusChange('complete');
      } else {
        onPhaseChange(phase);
      }
      frameId = window.requestAnimationFrame(render);
    };

    void loadAdultHorseAsset(loader).then((asset) => {
      if (disposed) return;
      externalAsset = asset.scene;
      externalAsset.name = 'replaceable-adult-horse-asset';
      externalAsset.scale.setScalar(timelineComplete ? GLB_ADULT_SCALE : GLB_PONY_SCALE);
      externalAsset.position.set(timelineComplete ? 2.9 : -1.5, 0.03, 0);
      externalAsset.rotation.y = -Math.PI / 2;
      externalAsset.visible = timelineComplete;
      externalAsset.traverse((object) => {
        const mesh = object as THREE.Mesh;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
      });
      scene.add(externalAsset);
      if (asset.animations.length > 0) {
        mixer = new THREE.AnimationMixer(externalAsset);
        const authoredGallop =
          asset.animations.find((clip) => /gallop|run/i.test(clip.name)) ??
          asset.animations.find((clip) => /walk|trot/i.test(clip.name)) ??
          asset.animations[0];
        assetAction = mixer.clipAction(authoredGallop);
        if (isPlaying) {
          assetAction.reset().play();
          mixer.setTime(elapsedBeforePlay);
        }
      }
    }).catch(() => {
      // The procedural equine is deliberately retained when the optional
      // local GLB has not been supplied or cannot be decoded.
    }).finally(() => {
      if (!disposed && !timelineComplete) onStatusChange(isPlaying ? 'playing' : 'ready');
    });

    horse.update(0, 0, false);
    onStatusChange('loading');
    startSequenceRef.current = () => {
      elapsedBeforePlay = reducedMotion ? TIMELINE_SECONDS : 0;
      startedAt = performance.now();
      isPlaying = !reducedMotion;
      timelineComplete = reducedMotion;
      horse.update(0, 0, false);
      horse.root.visible = true;
      horse.root.position.x = -1.5;
      effects.swirl.rotation.set(0, 0, 0);
      effects.rings.forEach((ring) => ring.scale.setScalar(0.1));
      const mistPositions = effects.mist.geometry.getAttribute('position') as THREE.BufferAttribute;
      mistPositions.array.set(effects.initialMistPositions);
      mistPositions.needsUpdate = true;
      mixer?.stopAllAction();
      mixer?.setTime(0);
      assetAction?.reset().play();
      if (externalAsset) {
        externalAsset.scale.setScalar(reducedMotion ? GLB_ADULT_SCALE : GLB_PONY_SCALE);
        externalAsset.position.set(reducedMotion ? 2.9 : -1.5, 0.03, 0);
        externalAsset.visible = reducedMotion;
      }
      onPhaseChange(reducedMotion ? 'complete' : 'opening');
      onStatusChange(reducedMotion ? 'complete' : 'playing');
    };
    frameId = window.requestAnimationFrame(render);

    return () => {
      disposed = true;
      startSequenceRef.current = null;
      window.cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      mixer?.stopAllAction();
      if (externalAsset) disposeObjectGraph(horse.root);
      disposeScene(scene, renderer);
    };
  }, [onPhaseChange, onStatusChange, reducedMotion]);

  useEffect(() => {
    if (playToken <= handledPlayTokenRef.current) return;
    handledPlayTokenRef.current = playToken;
    startSequenceRef.current?.();
  }, [playToken]);

  if (renderMode === 'fallback') {
    return (
      <HorseFallback
        playToken={playToken}
        reducedMotion={reducedMotion}
        onStatusChange={onStatusChange}
        onPhaseChange={onPhaseChange}
      />
    );
  }

  return <canvas ref={canvasRef} className="horse-scene-canvas" role="img" aria-label="Cinematic horse transformation scene" />;
}