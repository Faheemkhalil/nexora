// Three.js 3D Scene — Cybernetic AI Reactor Core

import * as THREE from 'three';

interface AIState {
  state: 'idle' | 'listening' | 'thinking' | 'working' | 'success' | 'error';
  intensity: number; // 0-1
}

// Cyan palette — no whites
const CYAN = {
  deep: 0x004C59,
  mid: 0x008FA3,
  bright: 0x00B8CC,
  primary: 0x00DFFF,
  glow: 0x00D4FF,
  green: 0x00FF88,
  dark: 0x001a22,
  shell: 0x0a1a24,
  metal: 0x0c1e2a,
  metalBright: 0x14303d,
} as const;

export class ThreeScene {
  private container: HTMLElement | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private renderer: THREE.WebGLRenderer | null = null;
  private scene: THREE.Scene | null = null;
  private camera: THREE.PerspectiveCamera | null = null;
  private animationId: number | null = null;
  private clock = new THREE.Clock();

  // Core groups
  private core: THREE.Group | null = null;
  private mechanicalGroup: THREE.Group | null = null;
  private innerEnergy: THREE.Mesh | null = null;
  private outerShell: THREE.Mesh | null = null;
  private coreGlow: THREE.Mesh | null = null;
  private rings: THREE.Mesh[] = [];
  private mechanicalArms: THREE.Mesh[] = [];
  private particles: THREE.Points | null = null;
  private innerParticles: THREE.Points | null = null;
  private pulseWave: THREE.Mesh | null = null;

  // Lights
  private coreLights: THREE.PointLight[] = [];

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
    this.createMechanicalHousing();
    this.createOrbitalRings();
    this.createParticles();
    this.createInnerEnergyParticles();
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

    // Renderer — alpha:false for opaque canvas, scene.background fills background
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance',
    });
    this.renderer.setSize(this.container!.clientWidth, this.container!.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.85;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    // Scene with dark background
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0e14);

    // Camera
    this.camera = new THREE.PerspectiveCamera(
      45,
      this.container!.clientWidth / this.container!.clientHeight,
      0.1,
      100
    );
    this.camera.position.set(0, 0.3, 6);
    this.camera.lookAt(0, 0, 0);

    // Lighting — very restrained, dark ambient
    const ambient = new THREE.AmbientLight(0x051018, 0.4);
    this.scene.add(ambient);

    // Top rim light — subtle
    const topLight = new THREE.DirectionalLight(0x004455, 0.3);
    topLight.position.set(0, 5, 3);
    this.scene.add(topLight);

    // Bottom fill — very dim
    const bottomLight = new THREE.DirectionalLight(0x002233, 0.15);
    bottomLight.position.set(0, -3, 2);
    this.scene.add(bottomLight);

    // Core point lights — cyan, controlled intensity
    const lightPositions: [number, number, number][] = [
      [0, 0, 0],
      [1.2, 0.8, 0.5],
      [-1.2, -0.8, 0.5],
      [0, 1.2, -0.5],
    ];

    lightPositions.forEach((pos) => {
      const light = new THREE.PointLight(CYAN.glow, 0.8, 5, 2);
      light.position.set(...pos);
      this.scene!.add(light);
      this.coreLights.push(light);
    });

    // Ambient glow at center
    const centerLight = new THREE.PointLight(CYAN.bright, 0.6, 3, 1.5);
    centerLight.position.set(0, 0, 0);
    this.scene!.add(centerLight);
    this.coreLights.push(centerLight);
  }

  // ─── CORE ─────────────────────────────────────────────────────────
  private createCore(): void {
    if (!this.scene) return;

    this.core = new THREE.Group();
    this.scene.add(this.core);

    // 1) Inner energy sphere — bright cyan core, small, emissive
    const innerGeo = new THREE.IcosahedronGeometry(0.55, 3);
    const innerMat = new THREE.MeshStandardMaterial({
      color: CYAN.mid,
      emissive: new THREE.Color(CYAN.bright),
      emissiveIntensity: 0.9,
      roughness: 0.3,
      metalness: 0.1,
      transparent: true,
      opacity: 0.85,
    });
    this.innerEnergy = new THREE.Mesh(innerGeo, innerMat);
    this.core.add(this.innerEnergy);

    // 2) Core glow sphere — additive halo around inner energy
    const glowGeo = new THREE.SphereGeometry(0.65, 24, 24);
    const glowMat = new THREE.MeshBasicMaterial({
      color: CYAN.primary,
      transparent: true,
      opacity: 0.12,
      side: THREE.BackSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.coreGlow = new THREE.Mesh(glowGeo, glowMat);
    this.core.add(this.coreGlow);

    // 3) Outer translucent shell — glass-like containment
    const shellGeo = new THREE.IcosahedronGeometry(1.0, 2);
    const shellMat = new THREE.MeshPhysicalMaterial({
      color: CYAN.dark,
      emissive: new THREE.Color(CYAN.deep),
      emissiveIntensity: 0.15,
      metalness: 0.4,
      roughness: 0.2,
      transmission: 0.6,
      thickness: 0.4,
      clearcoat: 1.0,
      clearcoatRoughness: 0.1,
      ior: 1.4,
      transparent: true,
      opacity: 0.6,
      side: THREE.DoubleSide,
    });
    this.outerShell = new THREE.Mesh(shellGeo, shellMat);
    this.core.add(this.outerShell);
  }

  // ─── MECHANICAL HOUSING ───────────────────────────────────────────
  private createMechanicalHousing(): void {
    if (!this.core) return;

    this.mechanicalGroup = new THREE.Group();
    this.core.add(this.mechanicalGroup);

    const metalMat = new THREE.MeshStandardMaterial({
      color: CYAN.metal,
      emissive: new THREE.Color(CYAN.deep),
      emissiveIntensity: 0.08,
      metalness: 0.85,
      roughness: 0.35,
    });

    const metalBrightMat = new THREE.MeshStandardMaterial({
      color: CYAN.metalBright,
      emissive: new THREE.Color(CYAN.mid),
      emissiveIntensity: 0.12,
      metalness: 0.8,
      roughness: 0.3,
    });

    // Radial mechanical arms — 6 arms extending outward
    const armCount = 6;
    for (let i = 0; i < armCount; i++) {
      const angle = (i / armCount) * Math.PI * 2;
      const armGroup = new THREE.Group();

      // Main arm — elongated box
      const armGeo = new THREE.BoxGeometry(0.08, 0.12, 1.8);
      const arm = new THREE.Mesh(armGeo, metalMat);
      arm.position.set(0, 0, 1.6);
      armGroup.add(arm);

      // Arm connector ring segment — thicker near core
      const connGeo = new THREE.CylinderGeometry(0.06, 0.08, 0.3, 8);
      const conn = new THREE.Mesh(connGeo, metalBrightMat);
      conn.rotation.x = Math.PI / 2;
      conn.position.set(0, 0, 0.65);
      armGroup.add(conn);

      // Small cyan accent light on each arm tip
      const tipGeo = new THREE.SphereGeometry(0.03, 8, 8);
      const tipMat = new THREE.MeshBasicMaterial({
        color: CYAN.primary,
        transparent: true,
        opacity: 0.7,
      });
      const tip = new THREE.Mesh(tipGeo, tipMat);
      tip.position.set(0, 0, 2.5);
      armGroup.add(tip);

      armGroup.rotation.y = angle;
      armGroup.rotation.x = (Math.random() - 0.5) * 0.15;
      this.mechanicalGroup.add(armGroup);
      this.mechanicalArms.push(arm);
    }

    // Conduit rings — 2 thin rings near the shell
    for (let i = 0; i < 2; i++) {
      const r = 1.15 + i * 0.15;
      const conduitGeo = new THREE.TorusGeometry(r, 0.02, 8, 48);
      const conduitMat = new THREE.MeshStandardMaterial({
        color: CYAN.metalBright,
        emissive: new THREE.Color(CYAN.mid),
        emissiveIntensity: 0.2,
        metalness: 0.9,
        roughness: 0.2,
      });
      const conduit = new THREE.Mesh(conduitGeo, conduitMat);
      conduit.rotation.x = Math.PI / 2 + i * 0.2;
      this.mechanicalGroup.add(conduit);
    }

    // Vertical support struts — 4 around the core
    for (let i = 0; i < 4; i++) {
      const angle = (i / 4) * Math.PI * 2 + Math.PI / 4;
      const strutGeo = new THREE.CylinderGeometry(0.025, 0.035, 2.2, 6);
      const strut = new THREE.Mesh(strutGeo, metalMat);
      const dist = 1.3;
      strut.position.set(
        Math.cos(angle) * dist,
        0,
        Math.sin(angle) * dist
      );
      strut.rotation.z = (Math.random() - 0.5) * 0.1;
      this.mechanicalGroup.add(strut);
    }
  }

  // ─── ORBITAL RINGS ────────────────────────────────────────────────
  private createOrbitalRings(): void {
    if (!this.core) return;

    const ringConfigs = [
      { radius: 1.6, tube: 0.015, color: CYAN.primary, opacity: 0.5, rotX: -0.3, rotZ: 0.1 },
      { radius: 2.0, tube: 0.012, color: CYAN.bright, opacity: 0.35, rotX: -0.5, rotZ: 0.4 },
      { radius: 2.4, tube: 0.010, color: CYAN.mid, opacity: 0.25, rotX: -0.7, rotZ: 0.7 },
      { radius: 2.8, tube: 0.008, color: CYAN.deep, opacity: 0.18, rotX: -0.9, rotZ: 1.0 },
    ];

    ringConfigs.forEach((cfg) => {
      const ringGeo = new THREE.TorusGeometry(cfg.radius, cfg.tube, 16, 96);
      const ringMat = new THREE.MeshBasicMaterial({
        color: cfg.color,
        transparent: true,
        opacity: cfg.opacity,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = cfg.rotX;
      ring.rotation.z = cfg.rotZ;
      this.core!.add(ring);
      this.rings.push(ring);
    });

    // Pulse wave — thin ring that expands on activity
    const waveGeo = new THREE.TorusGeometry(1.0, 0.01, 8, 64);
    const waveMat = new THREE.MeshBasicMaterial({
      color: CYAN.primary,
      transparent: true,
      opacity: 0,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.pulseWave = new THREE.Mesh(waveGeo, waveMat);
    this.pulseWave.rotation.x = -Math.PI / 2;
    this.core!.add(this.pulseWave);
  }

  // ─── OUTER PARTICLES ──────────────────────────────────────────────
  private createParticles(): void {
    if (!this.scene) return;

    const count = this.reducedMotion ? 400 : 1200;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    const colors = new Float32Array(count * 3);
    const velocities = new Float32Array(count * 3);

    const cyanColor = new THREE.Color(CYAN.bright);
    const greenColor = new THREE.Color(CYAN.green);

    for (let i = 0; i < count; i++) {
      const radius = 2.5 + Math.random() * 4;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);

      sizes[i] = Math.random() * 1.5 + 0.3;

      const t = Math.random();
      const c = cyanColor.clone().lerp(greenColor, t * 0.3);
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;

      velocities[i * 3] = (Math.random() - 0.5) * 0.001;
      velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.001;
      velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.001;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('velocity', new THREE.BufferAttribute(velocities, 3));

    const material = new THREE.PointsMaterial({
      size: 0.8,
      vertexColors: true,
      transparent: true,
      opacity: 0.5,
      sizeAttenuation: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    this.particles = new THREE.Points(geometry, material);
    this.scene.add(this.particles);
  }

  // ─── INNER ENERGY PARTICLES ───────────────────────────────────────
  private createInnerEnergyParticles(): void {
    if (!this.scene) return;

    const count = this.reducedMotion ? 100 : 300;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      const r = Math.random() * 0.8;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);

      sizes[i] = Math.random() * 0.8 + 0.2;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    const material = new THREE.PointsMaterial({
      size: 0.4,
      color: CYAN.primary,
      transparent: true,
      opacity: 0.6,
      sizeAttenuation: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    this.innerParticles = new THREE.Points(geometry, material);
    this.core!.add(this.innerParticles);
  }

  // ─── EVENT LISTENERS ──────────────────────────────────────────────
  private setupEventListeners(): void {
    window.addEventListener('resize', () => this.onResize());

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

  // ─── STATE MANAGEMENT ─────────────────────────────────────────────
  public setState(state: AIState['state'], intensity: number): void {
    this.currentState = { state, intensity };
    this.targetIntensity = intensity;
    this.updateCoreAppearance();
  }

  private updateCoreAppearance(): void {
    if (!this.innerEnergy || !this.coreGlow) return;

    const colors: Record<string, { energy: number; glow: number; light: number }> = {
      idle:      { energy: CYAN.mid,    glow: CYAN.primary, light: CYAN.glow },
      listening: { energy: CYAN.green,  glow: CYAN.green,   light: CYAN.green },
      thinking:  { energy: 0xccaa00,    glow: 0xffaa00,     light: 0xffaa00 },
      speaking:  { energy: 0x00cccc,    glow: 0x00ffff,     light: 0x00ffff },
      working:   { energy: 0xcc66cc,    glow: 0xff66cc,     light: 0xff66cc },
      success:   { energy: CYAN.green,  glow: CYAN.green,   light: CYAN.green },
      error:     { energy: 0xcc3333,    glow: 0xff3366,     light: 0xff3366 },
    };

    const c = colors[this.currentState.state] || colors.idle;
    const intensity = this.currentState.intensity;

    // Inner energy color and emissive
    const energyMat = this.innerEnergy.material as THREE.MeshStandardMaterial;
    energyMat.color.setHex(c.energy);
    energyMat.emissive.setHex(c.glow);
    energyMat.emissiveIntensity = 0.5 + intensity * 0.5;

    // Core glow
    const glowMat = this.coreGlow.material as THREE.MeshBasicMaterial;
    glowMat.color.setHex(c.glow);
    glowMat.opacity = 0.08 + intensity * 0.15;

    // Core lights
    this.coreLights.forEach((light, i) => {
      light.color.setHex(c.light);
      light.intensity = 0.4 + intensity * (i === this.coreLights.length - 1 ? 1.2 : 0.6);
    });
  }

  // ─── ANIMATION LOOP ──────────────────────────────────────────────
  public start(): void {
    this.animate();
  }

  private animate = (): void => {
    this.animationId = requestAnimationFrame(this.animate);

    const delta = this.clock.getDelta();
    const time = this.clock.getElapsedTime();

    if (!this.reducedMotion) {
      // Core group — very slow rotation
      if (this.core) {
        this.core.rotation.y += delta * 0.04;
        this.core.rotation.x = Math.sin(time * 0.15) * 0.05;
      }

      // Inner energy — slow independent rotation
      if (this.innerEnergy) {
        this.innerEnergy.rotation.y += delta * 0.08;
        this.innerEnergy.rotation.x = Math.sin(time * 0.3) * 0.06;

        // Subtle breathing scale
        const breathe = 1.0 + Math.sin(time * 0.8) * 0.03;
        this.innerEnergy.scale.setScalar(breathe);
      }

      // Outer shell — very slight rotation opposite direction
      if (this.outerShell) {
        this.outerShell.rotation.y -= delta * 0.02;
        this.outerShell.rotation.z = Math.sin(time * 0.2) * 0.03;
      }

      // Core glow pulse
      if (this.coreGlow) {
        const glowPulse = 0.08 + Math.sin(time * 0.6) * 0.04;
        (this.coreGlow.material as THREE.MeshBasicMaterial).opacity = glowPulse + this.currentState.intensity * 0.1;
      }

      // Mechanical housing — very subtle rotation
      if (this.mechanicalGroup) {
        this.mechanicalGroup.rotation.y += delta * 0.01;
      }

      // Orbital rings — each at different speed
      this.rings.forEach((ring, i) => {
        const speed = 0.05 + i * 0.02;
        ring.rotation.z += delta * speed;
        ring.rotation.y += delta * speed * 0.3;
      });

      // Outer particles
      if (this.particles) {
        this.particles.rotation.y += delta * 0.005;
        const pos = this.particles.geometry.attributes.position.array as Float32Array;
        const vel = this.particles.geometry.attributes.velocity.array as Float32Array;
        for (let i = 0; i < pos.length; i += 3) {
          pos[i] += vel[i] * 60;
          pos[i + 1] += vel[i + 1] * 60;
          pos[i + 2] += vel[i + 2] * 60;

          const dist = Math.sqrt(pos[i] ** 2 + pos[i + 1] ** 2 + pos[i + 2] ** 2);
          if (dist > 6.5) {
            pos[i] *= 0.2;
            pos[i + 1] *= 0.2;
            pos[i + 2] *= 0.2;
          }
        }
        this.particles.geometry.attributes.position.needsUpdate = true;
      }

      // Inner energy particles — faster, orbiting inside core
      if (this.innerParticles) {
        this.innerParticles.rotation.y += delta * 0.3;
        this.innerParticles.rotation.x += delta * 0.1;
      }

      // Pulse wave on activity
      if (this.pulseWave && this.currentState.intensity > 0.3) {
        const scale = 1 + (Math.sin(time * 2) * 0.5 + 0.5) * this.currentState.intensity * 1.5;
        this.pulseWave.scale.setScalar(scale);
        (this.pulseWave.material as THREE.MeshBasicMaterial).opacity =
          Math.max(0, (1 - (scale - 1) / 1.5)) * this.currentState.intensity * 0.35;
      } else if (this.pulseWave) {
        (this.pulseWave.material as THREE.MeshBasicMaterial).opacity = 0;
      }
    }

    // Smooth intensity transitions
    if (Math.abs(this.currentState.intensity - this.targetIntensity) > 0.01) {
      this.currentState.intensity += (this.targetIntensity - this.currentState.intensity) * 0.08;
      this.updateCoreAppearance();
    }

    // Render
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  };

  // ─── RESIZE ──────────────────────────────────────────────────────
  private onResize(): void {
    if (!this.container || !this.renderer || !this.camera) return;

    const width = this.container.clientWidth;
    const height = this.container.clientHeight;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  // ─── CLEANUP ─────────────────────────────────────────────────────
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
