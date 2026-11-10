// 3D Visual Effects: Dragon Breath Streams, Shattered Stone Physics Shards, Arcane Sigil Shockwaves, Brazier Flames, Volumetric God Rays & Sanctum Magic Circles
import * as THREE from 'three';

export class VFXManager {
  constructor(scene) {
    this.scene = scene;
    this.shards = [];
    this.shockwaves = [];
    this.sparks = [];
    this.breathParticles = [];
    this.breathLights = [];
    this.torchLights = [];
    this.motes = null;
    this.brazierEmbers = null;
    this.runeCircle = null;
    this.altarRuneCircle = null;
    this.godRays = [];
    this.shockwaveTex = this._buildShockwaveSigilTexture();

    this._initCathedralMotes();
    this._initBrazierFlames();
    this._initSanctumRuneCircle();
    this._initCathedralGodRays();
  }

  _buildShockwaveSigilTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 512;
    const ctx = canvas.getContext('2d');
    const cx = 256;
    const cy = 256;
    ctx.clearRect(0, 0, 512, 512);

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 7;
    ctx.beginPath();
    ctx.arc(cx, cy, 232, 0, Math.PI * 2);
    ctx.stroke();

    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(cx, cy, 208, 0, Math.PI * 2);
    ctx.stroke();

    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * 192, cy + Math.sin(a) * 192);
      ctx.lineTo(cx + Math.cos(a) * 244, cy + Math.sin(a) * 244);
      ctx.stroke();
    }
    return new THREE.CanvasTexture(canvas);
  }

  _initCathedralMotes() {
    const count = 440;
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const phases = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      positions[i * 3 + 0] = (Math.random() - 0.5) * 26;
      positions[i * 3 + 1] = Math.random() * 14 - 1.0;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 30;
      phases[i] = Math.random() * Math.PI * 2;
    }

    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));

    const mat = new THREE.PointsMaterial({
      color: 0xf7d794,
      size: 0.085,
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    this.motes = new THREE.Points(geo, mat);
    this.scene.add(this.motes);
  }

  _initBrazierFlames() {
    // 4 outer Dragon-Head Braziers ringing the Ruined Crag Sanctum Altar at (±5.35, 0.94, ±5.35)
    const corners = [
      [-5.35, 0.94, -5.35],
      [ 5.35, 0.94, -5.35],
      [-5.35, 0.94,  5.35],
      [ 5.35, 0.94,  5.35]
    ];
    const perBrazier = 36;
    const total = corners.length * perBrazier;
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array(total * 3);
    const origins = new Float32Array(total * 3);
    const phases = new Float32Array(total);

    let idx = 0;
    for (const [cx, cy, cz] of corners) {
      for (let i = 0; i < perBrazier; i++) {
        const ox = cx + (Math.random() - 0.5) * 0.46;
        const oz = cz + (Math.random() - 0.5) * 0.46;
        origins[idx * 3 + 0] = ox;
        origins[idx * 3 + 1] = cy;
        origins[idx * 3 + 2] = oz;

        positions[idx * 3 + 0] = ox;
        positions[idx * 3 + 1] = cy + Math.random() * 0.95;
        positions[idx * 3 + 2] = oz;
        phases[idx] = Math.random();
        idx++;
      }
    }

    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('aOrigin', new THREE.BufferAttribute(origins, 3));
    geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));

    const mat = new THREE.PointsMaterial({
      color: 0xff9436,
      size: 0.15,
      transparent: true,
      opacity: 0.88,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    this.brazierEmbers = new THREE.Points(geo, mat);
    this.scene.add(this.brazierEmbers);
  }

  _initSanctumRuneCircle() {
    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 1024;
    const ctx = canvas.getContext('2d');
    const cx = 512;
    const cy = 512;

    ctx.clearRect(0, 0, 1024, 1024);
    ctx.strokeStyle = '#ffffff';
    ctx.fillStyle = '#ffffff';

    // Outer & inner concentric arcane dragon-summoning rings
    const radii = [484, 460, 400, 382, 248];
    radii.forEach((r, idx) => {
      ctx.lineWidth = idx % 2 === 0 ? 5.5 : 2.5;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();
    });

    // 8-pointed Draconic Geomancy Star inside the magic circle
    ctx.lineWidth = 3.0;
    for (let s = 0; s < 2; s++) {
      ctx.beginPath();
      for (let k = 0; k <= 4; k++) {
        const ang = (k * 0.5 + s * 0.25) * Math.PI;
        const px = cx + Math.cos(ang) * 380;
        const py = cy + Math.sin(ang) * 380;
        if (k === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.stroke();
    }

    // 16 Elder Draconic Rune glyphs around circumference
    const glyphs = ['ᚠ', 'ᚢ', 'ᚦ', 'ᚨ', 'ᚱ', 'ᚲ', 'ᚷ', 'ᚹ', 'ᚺ', 'ᚾ', 'ᛁ', 'ᛃ', 'ᛇ', 'ᛈ', 'ᛉ', 'ᛊ'];
    ctx.font = 'bold 36px serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    for (let i = 0; i < 16; i++) {
      const a = (i / 16) * Math.PI * 2;
      const gx = cx + Math.cos(a) * 430;
      const gy = cy + Math.sin(a) * 430;
      ctx.save();
      ctx.translate(gx, gy);
      ctx.rotate(a + Math.PI / 2);
      ctx.fillText(glyphs[i], 0, 0);
      ctx.restore();

      ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * 382, cy + Math.sin(a) * 382);
      ctx.lineTo(cx + Math.cos(a) * 404, cy + Math.sin(a) * 404);
      ctx.stroke();
    }

    const tex = new THREE.CanvasTexture(canvas);

    // Lower Cathedral Crypt Magic Circle
    const cryptGeo = new THREE.PlaneGeometry(15.6, 15.6);
    cryptGeo.rotateX(-Math.PI / 2);
    const cryptMat = new THREE.MeshBasicMaterial({
      map: tex,
      color: 0x4fc3f7,
      transparent: true,
      opacity: 0.30,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide
    });
    this.runeCircle = new THREE.Mesh(cryptGeo, cryptMat);
    this.runeCircle.position.set(0, -3.12, 0);
    this.scene.add(this.runeCircle);

    // Upper Ruined Stone Altar Arcane Summoning Circle (replaces checkered board markings!)
    const altarGeo = new THREE.PlaneGeometry(9.65, 9.65);
    altarGeo.rotateX(-Math.PI / 2);
    const altarMat = new THREE.MeshBasicMaterial({
      map: tex,
      color: 0x4fc3f7,
      transparent: true,
      opacity: 0.22,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide
    });
    this.altarRuneCircle = new THREE.Mesh(altarGeo, altarMat);
    this.altarRuneCircle.position.set(0, 0.008, 0);
    this.scene.add(this.altarRuneCircle);
  }

  _initCathedralGodRays() {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 256;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 256);
    grad.addColorStop(0.0, 'rgba(255, 255, 255, 0.0)');
    grad.addColorStop(0.2, 'rgba(255, 255, 255, 0.22)');
    grad.addColorStop(0.75, 'rgba(255, 255, 255, 0.06)');
    grad.addColorStop(1.0, 'rgba(255, 255, 255, 0.0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 64, 256);

    const rayTex = new THREE.CanvasTexture(canvas);

    const roseRayGeo = new THREE.ConeGeometry(5.2, 22.0, 24, 1, true);
    const roseRayMat = new THREE.MeshBasicMaterial({
      map: rayTex,
      color: 0x82cfff,
      transparent: true,
      opacity: 0.14,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide
    });

    const roseRay = new THREE.Mesh(roseRayGeo, roseRayMat);
    roseRay.position.set(0, 6.2, -12.5);
    roseRay.rotation.x = -Math.PI * 0.34;
    this.scene.add(roseRay);
    this.godRays.push(roseRay);
  }

  setTurnRuneColor(turn, inCheck = false) {
    let hex = 0x4fc3f7;
    if (inCheck) hex = 0xff1744;
    else if (turn !== 'w') hex = 0xff6d3a;

    if (this.runeCircle) this.runeCircle.material.color.setHex(hex);
    if (this.altarRuneCircle) this.altarRuneCircle.material.color.setHex(hex);
  }

  registerTorchLight(light, baseIntensity, pos) {
    this.torchLights.push({
      light,
      baseIntensity,
      seed: Math.random() * 100,
      basePos: pos.clone()
    });
  }

  spawnDragonBreath(attackerPos, targetPos, isWhiteDragon) {
    const start = attackerPos.clone().add(new THREE.Vector3(0, 1.08, 0));
    const end = targetPos.clone().add(new THREE.Vector3(0, 0.72, 0));
    const beamDir = new THREE.Vector3().subVectors(end, start).normalize();
    start.addScaledVector(beamDir, 0.32);

    const coreColor = isWhiteDragon ? 0x7be3ff : 0xff5722;
    const secondaryColor = isWhiteDragon ? 0xfff0b3 : 0xffbe3d;

    // Travelling Dragonfire PointLight
    const breathLight = new THREE.PointLight(coreColor, 6.5, 9.0, 1.5);
    breathLight.position.copy(start);
    this.scene.add(breathLight);
    this.breathLights.push({
      light: breathLight,
      start: start.clone(),
      end: end.clone(),
      age: 0,
      maxAge: 0.48
    });

    // 44 high-velocity swirling dragon-breath flame/soulfire orbs
    for (let i = 0; i < 44; i++) {
      const r = 0.045 + Math.random() * 0.075;
      const geo = new THREE.IcosahedronGeometry(r, 0);
      const mat = new THREE.MeshBasicMaterial({
        color: i % 3 === 0 ? secondaryColor : coreColor,
        transparent: true,
        opacity: 0.92,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      });
      const orb = new THREE.Mesh(geo, mat);
      const delay = (i / 44) * 0.24;
      orb.position.copy(start);
      const spread = new THREE.Vector3(
        (Math.random() - 0.5) * 1.4,
        (Math.random() - 0.5) * 1.1,
        (Math.random() - 0.5) * 1.4
      );
      const speed = 6.2 + Math.random() * 3.8;
      const velocity = beamDir.clone().multiplyScalar(speed).add(spread);

      this.scene.add(orb);
      this.breathParticles.push({
        mesh: orb,
        origin: start.clone(),
        velocity,
        delay,
        age: 0,
        maxAge: 0.36 + Math.random() * 0.18
      });
    }
  }

  spawnShatterExplosion(worldPos, material, isWhitePiece) {
    // 1. Spawn 36 carved 3D angular stone dragon-osteoderm shards with physics
    const shardCount = 36;
    const runeColor = isWhitePiece ? 0x4fc3f7 : 0xff5722;

    for (let i = 0; i < shardCount; i++) {
      const radius = 0.044 + Math.random() * 0.072;
      const baseGeo =
        i % 3 === 0
          ? new THREE.TetrahedronGeometry(radius * 1.28, 0)
          : i % 3 === 1
          ? new THREE.OctahedronGeometry(radius * 1.14, 0)
          : new THREE.DodecahedronGeometry(radius, 0);

      baseGeo.scale(
        0.48 + Math.random() * 0.95,
        0.34 + Math.random() * 0.78,
        0.48 + Math.random() * 0.95
      );
      const geo = baseGeo.index ? baseGeo.toNonIndexed() : baseGeo;
      if (geo !== baseGeo) baseGeo.dispose();
      geo.computeVertexNormals();

      const uvAttr = geo.attributes.uv;
      if (uvAttr) {
        const useScales = i % 5 !== 0;
        const vLo = useScales ? 0.37 : 0.695;
        const vSpan = useScales ? 0.11 : 0.085;
        const uBase = Math.random() * 0.75;
        for (let k = 0; k < uvAttr.count; k++) {
          const uOrig = uvAttr.getX(k);
          const vOrig = uvAttr.getY(k);
          uvAttr.setXY(k, uBase + (uOrig % 1) * 0.18, vLo + (vOrig % 1) * vSpan);
        }
        uvAttr.needsUpdate = true;
        geo.setAttribute('uv1', uvAttr);
      }

      const mesh = new THREE.Mesh(geo, material);
      mesh.castShadow = true;
      mesh.receiveShadow = true;

      const heightOffset = 0.18 + Math.random() * 1.25;
      mesh.position.set(
        worldPos.x + (Math.random() - 0.5) * 0.42,
        worldPos.y + heightOffset,
        worldPos.z + (Math.random() - 0.5) * 0.42
      );

      const angle = Math.random() * Math.PI * 2;
      const speed = 1.8 + Math.random() * 4.5;
      const velocity = new THREE.Vector3(
        Math.cos(angle) * speed,
        2.3 + Math.random() * 4.2,
        Math.sin(angle) * speed
      );

      const angularVelocity = new THREE.Vector3(
        (Math.random() - 0.5) * 14,
        (Math.random() - 0.5) * 14,
        (Math.random() - 0.5) * 14
      );

      this.scene.add(mesh);
      this.shards.push({
        mesh,
        velocity,
        angularVelocity,
        restY: radius * 0.42,
        settled: false,
        age: 0
      });
    }

    // 2. Crisp Engraved Arcane Sigil Shockwave Ring (replaces flat solid disc!)
    const ringGeo = new THREE.PlaneGeometry(0.65, 0.65);
    ringGeo.rotateX(-Math.PI / 2);
    const ringMat = new THREE.MeshBasicMaterial({
      map: this.shockwaveTex,
      color: runeColor,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.position.set(worldPos.x, 0.022, worldPos.z);
    this.scene.add(ringMesh);
    this.shockwaves.push({ mesh: ringMesh, age: 0, maxAge: 0.72 });

    // 3. Fiery/Arcane spark burst
    for (let i = 0; i < 26; i++) {
      const sparkGeo = new THREE.OctahedronGeometry(0.038, 0);
      const sparkMat = new THREE.MeshBasicMaterial({
        color: i % 2 === 0 ? runeColor : 0xffd166,
        transparent: true,
        opacity: 1.0,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      });
      const spark = new THREE.Mesh(sparkGeo, sparkMat);
      spark.position.set(worldPos.x, worldPos.y + 0.68, worldPos.z);
      const a = Math.random() * Math.PI * 2;
      const spd = 2.2 + Math.random() * 5.2;
      this.scene.add(spark);
      this.sparks.push({
        mesh: spark,
        velocity: new THREE.Vector3(Math.cos(a) * spd, 2.6 + Math.random() * 4.6, Math.sin(a) * spd),
        age: 0,
        maxAge: 0.58 + Math.random() * 0.36
      });
    }
  }

  clearRubble() {
    for (const s of this.shards) {
      this.scene.remove(s.mesh);
      s.mesh.geometry.dispose();
    }
    this.shards = [];
  }

  update(dt, elapsed) {
    // 1. Update floating cathedral motes
    if (this.motes) {
      const posAttr = this.motes.geometry.getAttribute('position');
      const phaseAttr = this.motes.geometry.getAttribute('aPhase');
      for (let i = 0; i < posAttr.count; i++) {
        let y = posAttr.getY(i) + dt * 0.18;
        if (y > 13.0) y = -1.0;
        const x = posAttr.getX(i) + Math.sin(elapsed * 0.7 + phaseAttr.getX(i)) * dt * 0.08;
        posAttr.setXY(i, x, y);
      }
      posAttr.needsUpdate = true;
    }

    // 1b. Update rising brazier flames
    if (this.brazierEmbers) {
      const posAttr = this.brazierEmbers.geometry.getAttribute('position');
      const origAttr = this.brazierEmbers.geometry.getAttribute('aOrigin');
      const phaseAttr = this.brazierEmbers.geometry.getAttribute('aPhase');
      for (let i = 0; i < posAttr.count; i++) {
        let p = (phaseAttr.getX(i) + dt * 1.35) % 1.0;
        phaseAttr.setX(i, p);
        const ox = origAttr.getX(i);
        const oy = origAttr.getY(i);
        const oz = origAttr.getZ(i);
        const swirl = Math.sin(elapsed * 8.0 + i) * 0.085 * p;
        posAttr.setXYZ(i, ox + swirl, oy + p * 1.05, oz + swirl);
      }
      posAttr.needsUpdate = true;
    }

    // 1c. Rotate Sanctum Magic Circles
    if (this.runeCircle) {
      this.runeCircle.rotation.y = elapsed * 0.10;
      this.runeCircle.material.opacity = 0.26 + Math.sin(elapsed * 2.2) * 0.07;
    }
    if (this.altarRuneCircle) {
      this.altarRuneCircle.rotation.y = -elapsed * 0.06;
      this.altarRuneCircle.material.opacity = 0.18 + Math.sin(elapsed * 1.8) * 0.05;
    }

    // 2. Flicker torch & brazier lights naturally
    for (const t of this.torchLights) {
      const flicker =
        Math.sin(elapsed * 11.0 + t.seed) * 0.12 +
        Math.sin(elapsed * 23.0 + t.seed * 2.1) * 0.06;
      t.light.intensity = Math.max(0.2, t.baseIntensity * (1.0 + flicker));
    }

    // 2b. Update Dragon Breath Streams & Travelling Breath Lights
    for (let i = this.breathLights.length - 1; i >= 0; i--) {
      const bl = this.breathLights[i];
      bl.age += dt;
      const t = bl.age / bl.maxAge;
      if (t >= 1) {
        this.scene.remove(bl.light);
        this.breathLights.splice(i, 1);
      } else {
        bl.light.position.lerpVectors(bl.start, bl.end, Math.min(1, t * 1.25));
        bl.light.intensity = Math.sin(t * Math.PI) * 8.5;
      }
    }

    for (let i = this.breathParticles.length - 1; i >= 0; i--) {
      const bp = this.breathParticles[i];
      bp.age += dt;
      if (bp.age < bp.delay) {
        bp.mesh.visible = false;
        continue;
      }
      bp.mesh.visible = true;
      const t = (bp.age - bp.delay) / bp.maxAge;
      if (t >= 1) {
        this.scene.remove(bp.mesh);
        bp.mesh.geometry.dispose();
        bp.mesh.material.dispose();
        this.breathParticles.splice(i, 1);
      } else {
        bp.mesh.position.addScaledVector(bp.velocity, dt);
        const s = 0.65 + t * 1.85;
        bp.mesh.scale.set(s, s, s);
        bp.mesh.material.opacity = (1.0 - t) * 0.92;
      }
    }

    // 3. Update physics shards
    const gravity = -15.5;
    for (const s of this.shards) {
      s.age += dt;
      if (s.settled) continue;

      s.velocity.y += gravity * dt;
      s.mesh.position.addScaledVector(s.velocity, dt);

      s.mesh.rotation.x += s.angularVelocity.x * dt;
      s.mesh.rotation.y += s.angularVelocity.y * dt;
      s.mesh.rotation.z += s.angularVelocity.z * dt;

      const onAltar =
        Math.abs(s.mesh.position.x) < 5.05 && Math.abs(s.mesh.position.z) < 5.05;
      const floorY = onAltar ? s.restY : -3.8 + s.restY;

      if (s.mesh.position.y <= floorY) {
        s.mesh.position.y = floorY;
        s.velocity.y = -s.velocity.y * 0.32;
        s.velocity.x *= 0.62;
        s.velocity.z *= 0.62;
        s.angularVelocity.multiplyScalar(0.55);

        if (Math.abs(s.velocity.y) < 0.25 && s.velocity.lengthSq() < 0.08) {
          s.settled = true;
        }
      }
    }

    while (this.shards.length > 140) {
      const oldest = this.shards.shift();
      this.scene.remove(oldest.mesh);
      oldest.mesh.geometry.dispose();
    }

    // 4. Update expanding arcane sigil shockwaves
    for (let i = this.shockwaves.length - 1; i >= 0; i--) {
      const sw = this.shockwaves[i];
      sw.age += dt;
      const t = sw.age / sw.maxAge;
      if (t >= 1) {
        this.scene.remove(sw.mesh);
        sw.mesh.geometry.dispose();
        sw.mesh.material.dispose();
        this.shockwaves.splice(i, 1);
      } else {
        const scale = 1.0 + t * 4.4;
        sw.mesh.scale.set(scale, scale, scale);
        sw.mesh.rotation.z = t * 0.65;
        sw.mesh.material.opacity = (1.0 - t) * 0.92;
      }
    }

    // 5. Update sparks
    for (let i = this.sparks.length - 1; i >= 0; i--) {
      const sp = this.sparks[i];
      sp.age += dt;
      const t = sp.age / sp.maxAge;
      if (t >= 1) {
        this.scene.remove(sp.mesh);
        sp.mesh.geometry.dispose();
        sp.mesh.material.dispose();
        this.sparks.splice(i, 1);
      } else {
        sp.velocity.y -= 9.8 * dt;
        sp.mesh.position.addScaledVector(sp.velocity, dt);
        sp.mesh.material.opacity = 1.0 - t;
      }
    }
  }
}
