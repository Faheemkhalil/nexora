// Three.js 3D Scene — Central AI Core

import * as THREE from 'three';

interface AIState {
  state: 'idle' | 'listening' | 'thinking' | 'working' | 'success' | 'error';
  intensity: number; // 0-1
}

export class ThreeScene {
  private container: HTMLElement | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private renderer: THREE.WebGLRenderer | null = null;
  private scene: THREE.Scene | null = null;
  private camera: THREE.PerspectiveCamera | null = null;
  private animationId: number | null = null;
  private clock = new THREE.Clock();

  // Core objects
  private core: THREE.Group | null = null;
  private coreSphere: THREE.Mesh | null = null;
  private rings: THREE.Mesh[] = [];
  private particles: THREE.Points | null = null;
  private pulseWave: THREE.Mesh | null = null;

  // State
  private currentState: AIState = { state: 'idle', intensity: 0 };
  private targetIntensity = 0;
  private reducedMotion = false;

  private ipc: any;

  constructor(ipc: any) {
    this.ipc = ipc;
    this.detectReducedMotion();
    this.createContainer();
    this.initScene();
    this.createCore();
    this.createParticles();
    this.setupEventListeners();
  }

  private detectReducedMotion(): void {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    this.reducedMotion = mediaQuery.matches;
    mediaQuery.addEventListener('change', (e) => {
      this.reducedMotion = e.matches;
    });
  }

  private createContainer(): void {
    this.container = document.querySelector('.canvas-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.className = 'canvas-container';
      document.querySelector('.main')?.appendChild(this.container);
    }

    this.canvas = document.createElement('canvas');
    this.canvas.id = 'three-canvas';
    this.container.appendChild(this.canvas);
  }

  private initScene(): void {
    if (!this.canvas) return;

    // Renderer
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    this.renderer.setSize(this.container!.clientWidth, this.container!.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.2;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0e14);

    // Camera
    this.camera = new THREE.PerspectiveCamera(
      50,
      this.container!.clientWidth / this.container!.clientHeight,
      0.1,
      1000
    );
    this.camera.position.set(0, 0, 5);

    // Lights — restrained to keep the core cyan, not white
    const ambient = new THREE.AmbientLight(0x112233, 0.25);
    this.scene.add(ambient);

    const rimLight = new THREE.DirectionalLight(0x00d4ff, 0.15);
    rimLight.position.set(0, 5, -5);
    this.scene.add(rimLight);

    const coreLight = new THREE.PointLight(0x00d4ff, 1.5, 8);
    coreLight.position.set(0, 0, 0);
    this.scene.add(coreLight);
    this.coreLight = coreLight;
  }

  private coreLight: THREE.PointLight | null = null;

  private createCore(): void {
    if (!this.scene) return;

    this.core = new THREE.Group();
    this.scene.add(this.core);

    // Central sphere — dark glass with cyan translucency, not white
    const geometry = new THREE.IcosahedronGeometry(1, 16);
    const material = new THREE.MeshPhysicalMaterial({
      color: 0x001822,
      metalness: 0.2,
      roughness: 0.15,
      transmission: 0.5,
      thickness: 0.3,
      clearcoat: 0.8,
      clearcoatRoughness: 0.15,
      ior: 1.3,
      transparent: true,
      opacity: 0.85,
      emissive: new THREE.Color(0x003355),
      emissiveIntensity: 0.3,
    });
    this.coreSphere = new THREE.Mesh(geometry, material);
    this.core.add(this.coreSphere);

    // Inner glow sphere
    const innerGeo = new THREE.SphereGeometry(0.7, 32, 32);
    const innerMat = new THREE.MeshBasicMaterial({
      color: 0x00d4ff,
      transparent: true,
      opacity: 0.15,
      side: THREE.BackSide,
    });
    const inner = new THREE.Mesh(innerGeo, innerMat);
    this.core.add(inner);
    this.innerGlow = inner;

    // Rings
    const ringCount = 3;
    for (let i = 0; i < ringCount; i++) {
      const ringGeo = new THREE.RingGeometry(1.5 + i * 0.5, 1.6 + i * 0.5, 64);
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0x00d4ff,
        transparent: true,
        opacity: 0.3 - i * 0.08,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = -Math.PI / 2 + (i * 0.3);
      ring.rotation.z = i * 0.5;
      this.core.add(ring);
      this.rings.push(ring);
    }

    // Pulse wave
    const waveGeo = new THREE.RingGeometry(1, 1.1, 64);
    const waveMat = new THREE.MeshBasicMaterial({
      color: 0x00d4ff,
      transparent: true,
      opacity: 0,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    this.pulseWave = new THREE.Mesh(waveGeo, waveMat);
    this.pulseWave.rotation.x = -Math.PI / 2;
    this.core.add(this.pulseWave);
  }

  private innerGlow: THREE.Mesh | null = null;

  private createParticles(): void {
    if (!this.scene) return;

    const count = this.reducedMotion ? 500 : 2000;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    const colors = new Float32Array(count * 3);
    const velocities = new Float32Array(count * 3);

    const color1 = new THREE.Color(0x00d4ff);
    const color2 = new THREE.Color(0x00ff88);

    for (let i = 0; i < count; i++) {
      const radius = 2 + Math.random() * 4;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);

      sizes[i] = Math.random() * 2 + 0.5;

      const t = Math.random();
      const c = color1.clone().lerp(color2, t);
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;

      velocities[i * 3] = (Math.random() - 0.5) * 0.002;
      velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.002;
      velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.002;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('velocity', new THREE.BufferAttribute(velocities, 3));

    const material = new THREE.PointsMaterial({
      size: 1,
      vertexColors: true,
      transparent: true,
      opacity: 0.6,
      sizeAttenuation: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    this.particles = new THREE.Points(geometry, material);
    this.scene.add(this.particles);
  }

  private setupEventListeners(): void {
    window.addEventListener('resize', () => this.onResize());

    // Listen for state changes from backend
    this.ipc.on('voice_state', (_: string, data: any) => {
      this.setState(data.state || 'idle', data.intensity || 0);
    });

    this.ipc.on('chat_chunk_start', () => this.setState('thinking', 0.6));
    this.ipc.on('chat_chunk_end', () => this.setState('success', 0.3));
    this.ipc.on('event', (event: string) => {
      if (event.startsWith('tool_')) {
        this.setState('working', 0.7);
      }
    });
  }

  public setState(state: AIState['state'], intensity: number): void {
    this.currentState = { state, intensity };
    this.targetIntensity = intensity;
    this.updateCoreAppearance();
  }

  private updateCoreAppearance(): void {
    if (!this.coreSphere || !this.innerGlow || !this.coreLight) return;

    const colors: Record<AIState['state'], { core: number; glow: number; light: number }> = {
      idle: { core: 0x001122, glow: 0x00d4ff, light: 0x00d4ff },
      listening: { core: 0x002211, glow: 0x00ff88, light: 0x00ff88 },
      thinking: { core: 0x222200, glow: 0xffaa00, light: 0xffaa00 },
      working: { core: 0x220022, glow: 0xff66cc, light: 0xff66cc },
      success: { core: 0x002200, glow: 0x00ff88, light: 0x00ff88 },
      error: { core: 0x220000, glow: 0xff3366, light: 0xff3366 },
    };

    const c = colors[this.currentState.state] || colors.idle;
    const intensity = this.currentState.intensity;

    // Core material color
    (this.coreSphere.material as THREE.MeshPhysicalMaterial).color.setHex(c.core);
    (this.coreSphere.material as THREE.MeshPhysicalMaterial).emissive = new THREE.Color(c.core);
    (this.coreSphere.material as THREE.MeshPhysicalMaterial).emissiveIntensity = intensity * 0.3;

    // Inner glow
    (this.innerGlow.material as THREE.MeshBasicMaterial).color.setHex(c.glow);
    (this.innerGlow.material as THREE.MeshBasicMaterial).opacity = 0.15 + intensity * 0.3;

    // Core light
    this.coreLight.color.setHex(c.light);
    this.coreLight.intensity = intensity * 2;
  }

  public start(): void {
    this.animate();
  }

  private animate = (): void => {
    this.animationId = requestAnimationFrame(this.animate);

    const delta = this.clock.getDelta();
    const time = this.clock.getElapsedTime();

    if (!this.reducedMotion) {
      // Rotate core slowly
      if (this.core) {
        this.core.rotation.y += delta * 0.05;
        this.core.rotation.x = Math.sin(time * 0.2) * 0.1;
      }

      // Rotate rings
      this.rings.forEach((ring, i) => {
        ring.rotation.z += delta * 0.1 * (i + 1) * 0.5;
        ring.rotation.y += delta * 0.02 * (i + 1);
      });

      // Animate particles
      if (this.particles) {
        this.particles.rotation.y += delta * 0.01;
        const pos = this.particles.geometry.attributes.position.array as Float32Array;
        const vel = this.particles.geometry.attributes.velocity.array as Float32Array;
        for (let i = 0; i < pos.length; i += 3) {
          pos[i] += vel[i] * 60;
          pos[i + 1] += vel[i + 1] * 60;
          pos[i + 2] += vel[i + 2] * 60;

          // Wrap around
          const dist = Math.sqrt(pos[i] ** 2 + pos[i + 1] ** 2 + pos[i + 2] ** 2);
          if (dist > 6) {
            pos[i] *= 0.3;
            pos[i + 1] *= 0.3;
            pos[i + 2] *= 0.3;
          }
        }
        this.particles.geometry.attributes.position.needsUpdate = true;
      }

      // Pulse wave
      if (this.pulseWave && this.currentState.intensity > 0.3) {
        const scale = 1 + (Math.sin(time * 3) * 0.5 + 0.5) * this.currentState.intensity * 2;
        this.pulseWave.scale.setScalar(scale);
        (this.pulseWave.material as THREE.MeshBasicMaterial).opacity =
          (1 - (scale - 1) / 2) * this.currentState.intensity * 0.5;
      }
    }

    // Smooth intensity transitions
    const currentIntensity = this.currentState.intensity;
    if (Math.abs(currentIntensity - this.targetIntensity) > 0.01) {
      this.currentState.intensity += (this.targetIntensity - currentIntensity) * 0.1;
      this.updateCoreAppearance();
    }

    // Render
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  };

  private onResize(): void {
    if (!this.container || !this.renderer || !this.camera) return;

    const width = this.container.clientWidth;
    const height = this.container.clientHeight;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  public dispose(): void {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }

    if (this.renderer) {
      this.renderer.dispose();
      this.renderer = null;
    }

    if (this.scene) {
      this.scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose();
          if (Array.isArray(obj.material)) {
            obj.material.forEach((m) => m.dispose());
          } else {
            obj.material.dispose();
          }
        } else if (obj instanceof THREE.Points) {
          obj.geometry.dispose();
          (obj.material as THREE.Material).dispose();
        }
      });
      this.scene = null;
    }

    if (this.canvas && this.canvas.parentNode) {
      this.canvas.parentNode.removeChild(this.canvas);
      this.canvas = null;
    }
  }
}