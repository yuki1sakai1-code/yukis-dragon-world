import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/examples/jsm/utils/SkeletonUtils.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { SanctumChess7 as Chess, FILES } from './sanctum-chess.js';

import { SoundEffects } from './sound.js';
import { chooseBestMove, evaluateBoard } from './ai.js';
import { VFXManager } from './vfx.js';

const NODE_SPACING = 1.18;

export const SCENARIOS = {
  standard: null,
  sacrifice: 'rnbkbnr/pp1pppp/2n4/3b3/2B1P2/PPP1PPP/RNBK1NR w - - 0 5',
  immortal: 'r1bk1nr/p2p1p1/n2B3/1p1NP1P/3P1Q1/P1P1K2/q5b w - - 0 22',
  endgame: '1r1k3/4b2/p1np1q1/7/1Q1PN1P/2B4/3K1R1 w - - 0 1'
};

export const DRAGON_STATS = {
  p: { maxHp: 20, atk: 25, def: 10, headHeight: 1.15, title: '幼竜ドレイク' },
  n: { maxHp: 45, atk: 40, def: 18, headHeight: 1.55, title: '双翼ワイバーン' },
  b: { maxHp: 40, atk: 45, def: 15, headHeight: 1.65, title: '双頭の秘術竜ヒドラ' },
  r: { maxHp: 80, atk: 55, def: 35, headHeight: 1.35, title: '要塞重装鎧地竜' },
  q: { maxHp: 90, atk: 70, def: 25, headHeight: 1.85, title: '四翼の飛翔女帝竜' },
  k: { maxHp: 100, atk: 50, def: 40, headHeight: 2.28, title: '聖堂の覇王古竜' }
};

function createHpBarSprite(maxHp, currentHp) {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 28;
  const ctx = canvas.getContext('2d');

  function draw(hp) {
    ctx.clearRect(0, 0, 128, 28);
    // Outer border (Gothic Dark Gold)
    ctx.fillStyle = 'rgba(18, 14, 10, 0.88)';
    ctx.fillRect(2, 2, 124, 24);
    ctx.strokeStyle = '#c5a059';
    ctx.lineWidth = 2.5;
    ctx.strokeRect(2, 2, 124, 24);

    // HP Bar Fill
    const ratio = Math.max(0, Math.min(1, hp / maxHp));
    const barW = Math.floor(116 * ratio);
    if (barW > 0) {
      const grad = ctx.createLinearGradient(6, 0, 122, 0);
      if (ratio > 0.5) {
        grad.addColorStop(0, '#27ae60');
        grad.addColorStop(1, '#2ecc71');
      } else if (ratio > 0.25) {
        grad.addColorStop(0, '#e67e22');
        grad.addColorStop(1, '#f1c40f');
      } else {
        grad.addColorStop(0, '#c0392b');
        grad.addColorStop(1, '#e74c3c');
      }
      ctx.fillStyle = grad;
      ctx.fillRect(6, 6, barW, 16);
    }

    // Text: e.g. "30/30"
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = '#000000';
    ctx.shadowBlur = 4;
    ctx.fillText(`${hp}/${maxHp}`, 64, 14);
  }

  draw(currentHp);
  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
    depthWrite: false
  });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(0.68, 0.15, 1.0);
  sprite.userData = { canvas, ctx, texture, draw };
  return sprite;
}

function createDamageNumberSprite(damage) {
  const canvas = document.createElement('canvas');
  canvas.width = 160;
  canvas.height = 80;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, 160, 80);

  const isBlocked = damage <= 0;
  const text = isBlocked ? 'BLOCK 0' : `-${damage}`;
  ctx.font = 'bold 30px "Cinzel", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  ctx.strokeStyle = '#000000';
  ctx.lineWidth = 6;
  ctx.strokeText(text, 80, 40);

  const grad = ctx.createLinearGradient(0, 15, 0, 65);
  if (isBlocked) {
    grad.addColorStop(0, '#e0e0e0');
    grad.addColorStop(0.5, '#90caf9');
    grad.addColorStop(1, '#1976d2');
  } else {
    grad.addColorStop(0, '#ffcdd2');
    grad.addColorStop(0.5, '#f44336');
    grad.addColorStop(1, '#b71c1c');
  }
  ctx.fillStyle = grad;
  ctx.fillText(text, 80, 40);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
    depthWrite: false
  });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(0.8, 0.4, 1.0);
  return sprite;
}

const PIECE_INFO = {
  p: {
    name: '幼竜ドレイク (Stone Hatchling Drake)',
    shortName: '幼竜ドレイク',
    symbolW: '🦎',
    symbolB: '🦎',
    value: 1,
    lore: '鋭い牙と鉤爪、背ビレの竜鱗石彫を備え、岩場から獲物へ飛び掛かる四足歩行の石造幼竜ドレイク。'
  },
  r: {
    name: '重装鎧地竜 (Armored Behemoth Drake)',
    shortName: '重装鎧地竜',
    symbolW: '🦕',
    symbolB: '🦕',
    value: 5,
    lore: '分厚い玄武岩・石灰岩の骨板甲殻と城鎚のような棍棒尾を持ち、大地を揺るがし突進する重装四足地竜。'
  },
  n: {
    name: '双翼ワイバーン (Winged Sky-Wyvern)',
    shortName: '双翼ワイバーン',
    symbolW: '🦅',
    symbolB: '🦅',
    value: 3,
    lore: '巨大な石彫の飛竜翼を大きく広げ、強靭な後肢の鉤爪と毒針尾で戦列を飛び越え急襲する双翼ワイバーン。'
  },
  b: {
    name: '双頭の秘術竜 (Twin-Headed Hydra-Wyrm)',
    shortName: '双頭の秘術竜',
    symbolW: '🐍',
    symbolB: '🐍',
    value: 3,
    lore: '絡み合う二本の長い竜首と四本の角を持ち、古代ルーンの魔力ブレスを斜線へ放つ双頭の石造ヒドラ古竜。'
  },
  q: {
    name: '四翼の飛翔女帝竜 (Four-Winged Elder Dragon)',
    shortName: '四翼女帝竜',
    symbolW: '👸',
    symbolB: '👸',
    value: 9,
    lore: '上下二対・計四枚の壮麗な石彫竜翼と王冠角、長大な鞭尾を備え、聖域全域を制圧する飛翔女帝古竜。'
  },
  k: {
    name: '大聖堂の覇王古竜 (Sovereign Arch-Dragon)',
    shortName: '覇王古竜',
    symbolW: '👑',
    symbolB: '👑',
    value: 0,
    lore: '後ろ脚で威風堂々と立ち上がり、天を衝く王冠大角と大翼・胸部の古代ルーン炉心を輝かせる大聖堂の覇王古竜。'
  }
};


class WizardsChessApp {
  constructor() {
    this.chess = new Chess();
    this.sfx = new SoundEffects();

    // Game Settings
    this.gameMode = 'pva'; // 'pva' | 'pvp' | 'ava'
    this.aiDepth = 2;
    this.actionCamEnabled = true;
    this.combatCamMode = 'smart'; // 'smart' (俯瞰・離れている時は視点維持) | 'closeup' (常に拡大) | 'free' (常に現在視点維持/拡大なし)
    this.isBusy = false;
    this.selectedSquare = null;
    this.legalMovesForSelected = [];
    this.pendingPromotionMove = null;
    this.lastMove = null;
    this.hintMove = null;

    // Clocks (seconds)
    this.clocks = { w: 600, b: 600 };
    this.lastClockTick = performance.now();

    // Mobile capability detection to constrain WebGL VRAM & post-processing overhead (prevents iOS Safari Jetsam crashes)
    const isCoarsePointer = typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches;
    const isMobileUA = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent || '');
    this.isMobileDevice = window.innerWidth <= 960 || isCoarsePointer || isMobileUA;

    // Three.js Core
    this.container = document.getElementById('canvas-container');
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x09080e);
    this.scene.fog = new THREE.FogExp2(0x0b0a12, 0.0155);

    this.camera = new THREE.PerspectiveCamera(
      44,
      window.innerWidth / window.innerHeight,
      0.1,
      160
    );
    this.camera.position.set(0, 8.2, 11.6);
    this._adjustCameraForViewport();

    this.renderer = new THREE.WebGLRenderer({
      antialias: !this.isMobileDevice,
      powerPreference: this.isMobileDevice ? 'default' : 'high-performance',
      preserveDrawingBuffer: false
    });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.isMobileDevice ? 1.5 : 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = this.isMobileDevice ? 1.22 : 1.15;
    this.container.appendChild(this.renderer.domElement);

    this.renderer.domElement.addEventListener(
      'webglcontextlost',
      (e) => {
        e.preventDefault();
        console.warn('WebGL context lost — awaiting restore');
      },
      false
    );

    if (!this.isMobileDevice) {
      // Post-processing Subtle Bloom (tuned so stone stays crisp & runes/stained-glass glow cleanly)
      this.composer = new EffectComposer(this.renderer);
      this.renderPass = new RenderPass(this.scene, this.camera);
      this.composer.addPass(this.renderPass);

      this.bloomPass = new UnrealBloomPass(
        new THREE.Vector2(window.innerWidth, window.innerHeight),
        0.24, // strength
        0.42, // radius
        0.90  // threshold
      );
      this.composer.addPass(this.bloomPass);
      this.composer.addPass(new OutputPass());
    } else {
      this.composer = null;
      this.renderPass = null;
      this.bloomPass = null;
    }

    // Controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.maxPolarAngle = Math.PI * 0.488;
    this.controls.minDistance = 1.6;
    this.controls.maxDistance = 34.0;
    this.controls.target.set(0, 0.65, 0);

    // Camera transition state
    this.camTransition = null;
    this.savedCameraState = null;

    // Raycasting
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.pointerDownPos = new THREE.Vector2();

    // Asset registries
    this.piecePrototypes = {};
    this.materials = { w: null, b: null, kw: null, kb: null, tileLight: null, tileDark: null };
    this.boardSquares = new Map();
    this.squareOverlays = new Map();
    this.pieceInstances = new Map();
    this.activeMixers = new Set();
    this.pedestalMode = 'no-base';
    this.combatRule = 'classic';
    this.damagePopups = [];
    this._kingSlain = null;
    this.moveActionLog = [];
    this.collapsedSquares = new Set();
    this.cataclysmPhase = 0;
    this.peacefulHalfMoves = 0;
    this.chess.load(SCENARIOS.endgame);

    // VFX & Lighting
    this.vfx = new VFXManager(this.scene, { isMobile: this.isMobileDevice });
    this.lights = {};

    this.clock = new THREE.Clock();

    this._setupLighting();
    this.setLightingPreset('moonlit');
    this._bindUIEvents();
    this.setCombatRule('classic', false);
    this._initAssets();

    // Expose for automated QA inspection
    window.__wizardsChess = this;
  }

  _setupLighting() {
    const hemi = new THREE.HemisphereLight(0xdfd2bc, 0x221d2e, 0.85);
    this.scene.add(hemi);
    this.lights.hemi = hemi;

    // Grazing Sanctum Key Light to sculpt carved dragon-scale stone reliefs & cast sharp shadows
    const dirLight = new THREE.DirectionalLight(0xffe6c2, 2.25);
    dirLight.position.set(7.8, 14.2, 9.4);
    dirLight.castShadow = true;
    const shadowSize = this.isMobileDevice ? 1024 : 2048;
    dirLight.shadow.mapSize.width = shadowSize;
    dirLight.shadow.mapSize.height = shadowSize;
    dirLight.shadow.camera.near = 1.0;
    dirLight.shadow.camera.far = 42.0;
    const d = 10.2;
    dirLight.shadow.camera.left = -d;
    dirLight.shadow.camera.right = d;
    dirLight.shadow.camera.top = d;
    dirLight.shadow.camera.bottom = -d;
    dirLight.shadow.bias = -0.0005;
    this.scene.add(dirLight);
    this.lights.dir = dirLight;

    // Cool Gothic Rose-Window Rim Light from North (-Z) to highlight dark volcanic dragon-stone edges
    const rimLight = new THREE.DirectionalLight(0x98ceff, 2.05);
    rimLight.position.set(-6.5, 10.5, -14.5);
    this.scene.add(rimLight);
    this.lights.rim = rimLight;

    // Subtle Secondary Fill from South-West so White & Black dragon carvings stay crisp from all angles
    const fillLight = new THREE.DirectionalLight(0xe5d6c3, 0.92);
    fillLight.position.set(-8.5, 6.5, 9.5);
    this.scene.add(fillLight);
    this.lights.fill = fillLight;

    // 4 Corner Dragon-Head Brazier Fire PointLights around the Ruined Dragon Sanctum Altar
    const brazierCoords = [
      [-5.35, 1.52, -5.35],
      [5.35, 1.52, -5.35],
      [-5.35, 1.52, 5.35],
      [5.35, 1.52, 5.35]
    ];
    this.lights.braziers = [];
    for (const [bx, by, bz] of brazierCoords) {
      const pt = new THREE.PointLight(0xff8e3c, 3.2, 13.5, 1.7);
      pt.position.set(bx, by, bz);
      this.scene.add(pt);
      this.lights.braziers.push(pt);
      this.vfx.registerTorchLight(pt, 3.2, pt.position);
    }

    // Overhead Chandelier Warm Fill
    const chandelierLight = new THREE.PointLight(0xffd280, 3.2, 28.0, 1.55);
    chandelierLight.position.set(0, 9.8, 0);
    this.scene.add(chandelierLight);
    this.lights.chandelier = chandelierLight;
    this.vfx.registerTorchLight(chandelierLight, 3.2, chandelierLight.position);
  }

  setLightingPreset(preset) {
    const topLight = document.getElementById('lighting-select');
    const mobLight = document.getElementById('mobile-lighting-select');
    if (topLight && topLight.value !== preset) topLight.value = preset;
    if (mobLight && mobLight.value !== preset) mobLight.value = preset;

    if (preset === 'candlelight') {
      this.scene.background.setHex(0x09080e);
      this.scene.fog.color.setHex(0x0b0a12);
      this.lights.hemi.color.setHex(0xdfd2bc);
      this.lights.hemi.intensity = 0.85;
      this.lights.dir.color.setHex(0xffe6c2);
      this.lights.dir.intensity = 2.25;
      this.lights.rim.color.setHex(0x8bc4ff);
      this.lights.rim.intensity = 1.75;
      this.lights.braziers.forEach((l) => l.color.setHex(0xff8e3c));
      if (this.lights.chandelier) this.lights.chandelier.color.setHex(0xffd280);
    } else if (preset === 'moonlit') {
      this.scene.background.setHex(0x050914);
      this.scene.fog.color.setHex(0x070d1c);
      this.lights.hemi.color.setHex(0xb3daff);
      this.lights.hemi.intensity = 0.95;
      this.lights.dir.color.setHex(0xdceeff);
      this.lights.dir.intensity = 2.05;
      this.lights.rim.color.setHex(0x69b8ff);
      this.lights.rim.intensity = 1.85;
      this.lights.braziers.forEach((l) => l.color.setHex(0x4fc3f7));
      if (this.lights.chandelier) this.lights.chandelier.color.setHex(0x8bc4ff);
    } else if (preset === 'bloodmoon') {
      this.scene.background.setHex(0x120508);
      this.scene.fog.color.setHex(0x17060a);
      this.lights.hemi.color.setHex(0xffb59e);
      this.lights.hemi.intensity = 0.82;
      this.lights.dir.color.setHex(0xff7d52);
      this.lights.dir.intensity = 2.15;
      this.lights.rim.color.setHex(0xe53935);
      this.lights.rim.intensity = 1.80;
      this.lights.braziers.forEach((l) => l.color.setHex(0xff3d00));
      if (this.lights.chandelier) this.lights.chandelier.color.setHex(0xff5533);
    }
  }

  _processPedestalGeometry(geometry) {
    if (!geometry || geometry.userData.pedestalProcessed) return;
    geometry.userData.pedestalProcessed = true;

    const posAttr = geometry.attributes.position;
    const skinWeightAttr = geometry.attributes.skinWeight;
    const skinIndexAttr = geometry.attributes.skinIndex;
    const indexAttr = geometry.index;
    if (!posAttr || !indexAttr || !skinWeightAttr || !skinIndexAttr) return;

    const numTris = indexAttr.count / 3;
    const indData = indexAttr.array;
    const posData = posAttr.array;
    const wData = skinWeightAttr.array;
    const jData = skinIndexAttr.array;

    const edgeMap = new Map();
    for (let t = 0; t < numTris; t++) {
      const a = indData[t * 3], b = indData[t * 3 + 1], c = indData[t * 3 + 2];
      const edges = [
        a < b ? `${a}_${b}` : `${b}_${a}`,
        b < c ? `${b}_${c}` : `${c}_${b}`,
        c < a ? `${c}_${a}` : `${a}_${c}`
      ];
      for (const e of edges) {
        let list = edgeMap.get(e);
        if (!list) {
          list = [];
          edgeMap.set(e, list);
        }
        list.push(t);
      }
    }

    const triAdj = Array.from({ length: numTris }, () => []);
    for (const list of edgeMap.values()) {
      if (list.length > 1) {
        for (let i = 0; i < list.length; i++) {
          for (let j = i + 1; j < list.length; j++) {
            triAdj[list[i]].push(list[j]);
            triAdj[list[j]].push(list[i]);
          }
        }
      }
    }

    const visited = new Uint8Array(numTris);
    const shells = [];
    for (let t = 0; t < numTris; t++) {
      if (visited[t]) continue;
      const comp = [];
      const queue = [t];
      visited[t] = 1;
      while (queue.length > 0) {
        const u = queue.pop();
        comp.push(u);
        for (const v of triAdj[u]) {
          if (!visited[v]) {
            visited[v] = 1;
            queue.push(v);
          }
        }
      }
      shells.push(comp);
    }

    const pedTris = [];
    const bodyTris = [];
    let bodyMinY = Infinity;

    for (const shell of shells) {
      let maxY = -Infinity;
      let minRootW = Infinity;
      for (const t of shell) {
        for (let k = 0; k < 3; k++) {
          const v = indData[t * 3 + k];
          const y = posData[v * 3 + 1];
          if (y > maxY) maxY = y;
          let rootW = 0;
          for (let j = 0; j < 4; j++) {
            if (jData[v * 4 + j] === 0) rootW += wData[v * 4 + j];
          }
          if (rootW < minRootW) minRootW = rootW;
        }
      }

      const isPed = (maxY <= 0.235 && minRootW > 0.999);
      if (isPed) {
        for (const t of shell) pedTris.push(t);
      } else {
        for (const t of shell) {
          bodyTris.push(t);
          for (let k = 0; k < 3; k++) {
            const v = indData[t * 3 + k];
            const y = posData[v * 3 + 1];
            if (y < bodyMinY) bodyMinY = y;
          }
        }
      }
    }

    const newIndices = new indData.constructor(indexAttr.count);
    let ptr = 0;
    for (const t of bodyTris) {
      newIndices[ptr++] = indData[t * 3];
      newIndices[ptr++] = indData[t * 3 + 1];
      newIndices[ptr++] = indData[t * 3 + 2];
    }
    const bodyCount = ptr;
    for (const t of pedTris) {
      newIndices[ptr++] = indData[t * 3];
      newIndices[ptr++] = indData[t * 3 + 1];
      newIndices[ptr++] = indData[t * 3 + 2];
    }

    geometry.setIndex(new THREE.BufferAttribute(newIndices, 1));
    geometry.userData.bodyCount = bodyCount;
    geometry.userData.totalCount = indexAttr.count;
    geometry.userData.bodyMinY = Number.isFinite(bodyMinY) ? bodyMinY : 0.128;
  }

  setPedestalMode(mode) {
    this.pedestalMode = mode;
    const hasBase = mode === 'with-base';

    const select = document.getElementById('pedestal-mode-select');
    if (select && select.value !== mode) select.value = mode;

    const btnWith = document.getElementById('btn-pedestal-with');
    const btnNone = document.getElementById('btn-pedestal-none');
    if (btnWith) btnWith.classList.toggle('active', hasBase);
    if (btnNone) btnNone.classList.toggle('active', !hasBase);

    // Update prototypes
    for (const proto of Object.values(this.piecePrototypes)) {
      proto.scene?.traverse((child) => {
        if (child.isSkinnedMesh && child.geometry?.userData?.totalCount) {
          const count = hasBase ? child.geometry.userData.totalCount : child.geometry.userData.bodyCount;
          child.geometry.setDrawRange(0, count);
        }
      });
    }

    // Update all live board pieces
    for (const [sq, instance] of this.pieceInstances) {
      let rawBodyMinY = 0.128;
      const scale = instance.type === 'k' ? 1.10 : 1.0;
      instance.root.traverse((child) => {
        if (child.isSkinnedMesh && child.geometry?.userData?.totalCount) {
          const count = hasBase ? child.geometry.userData.totalCount : child.geometry.userData.bodyCount;
          child.geometry.setDrawRange(0, count);
          if (child.geometry.userData.bodyMinY) {
            rawBodyMinY = child.geometry.userData.bodyMinY;
          }
        }
      });
      const bodyMinY = rawBodyMinY * scale;
      instance.bodyMinY = bodyMinY;
      const basePos = this.squareToWorld(sq);
      const yOffset = hasBase ? 0 : -bodyMinY;
      instance.yOffset = yOffset;
      instance.root.position.y = basePos.y + yOffset;
    }
  }

  setCombatRule(rule, showToast = true) {
    this.combatRule = rule;
    const isTactics = rule === 'tactics';

    // Synchronize both top and side panel select elements
    const selectTop = document.getElementById('combat-rule-select');
    if (selectTop && selectTop.value !== rule) selectTop.value = rule;
    const selectSide = document.getElementById('battle-mode-select');
    if (selectSide && selectSide.value !== rule) selectSide.value = rule;

    // Synchronize toggle buttons
    const btnTactics = document.getElementById('btn-mode-tactics');
    const btnClassic = document.getElementById('btn-mode-classic');
    if (btnTactics) btnTactics.classList.toggle('active', isTactics);
    if (btnClassic) btnClassic.classList.toggle('active', !isTactics);

    // Show or hide 3D HP bar sprites on each piece
    for (const inst of this.pieceInstances.values()) {
      if (inst.hpBarSprite) {
        inst.hpBarSprite.visible = isTactics;
      }
    }

    // Toggle inspector RPG stats section
    const rpgStats = document.getElementById('inspector-rpg-stats');
    if (rpgStats) {
      rpgStats.style.display = isTactics ? 'block' : 'none';
    }

    if (showToast) {
      const toast = document.getElementById('status-toast');
      if (toast) {
        toast.textContent = isTactics
          ? '⚔️ 対戦モード: 竜石タクティクス (HP/攻撃/防御バトル) に切り替えました'
          : '♟️ 対戦モード: ワンショットバトル (一撃必殺・通常ルール) に切り替えました';
      }
    }
  }

  _spawnDamageNumber(worldPos, damage) {
    const sprite = createDamageNumberSprite(damage);
    sprite.position.copy(worldPos);
    sprite.position.y += 1.85;
    this.scene.add(sprite);
    this.damagePopups.push({
      sprite,
      elapsed: 0,
      maxLife: 1.1,
      startPos: sprite.position.clone()
    });
  }

  _isRepetitionForbidden(move) {
    if (!move || !move.from || !move.to) return false;
    const playerHistory = this.moveActionLog.filter((m) => m.color === move.color);
    if (playerHistory.length < 2) return false;

    // パターン1: 同じマスへの突撃・弾かれ後退を繰り返す千日手
    // 直近2回連続で同一の from -> to を実行しており、今回も同じ手を指そうとしたら3回目で禁止
    const last1 = playerHistory[playerHistory.length - 1];
    const last2 = playerHistory[playerHistory.length - 2];
    if (
      last1 && last2 &&
      last1.from === move.from && last1.to === move.to &&
      last2.from === move.from && last2.to === move.to
    ) {
      return true;
    }

    // パターン2: 通常移動で同じ2マス間を行き来する千日手 (A -> B -> A -> B -> A -> B の3回目)
    if (playerHistory.length >= 4) {
      const h1 = playerHistory[playerHistory.length - 1];
      const h2 = playerHistory[playerHistory.length - 2];
      const h3 = playerHistory[playerHistory.length - 3];
      const h4 = playerHistory[playerHistory.length - 4];
      if (
        h1.from === move.to && h1.to === move.from &&
        h2.from === move.from && h2.to === move.to &&
        h3.from === move.to && h3.to === move.from &&
        h4.from === move.from && h4.to === move.to
      ) {
        return true;
      }
    }

    return false;
  }

  async triggerCataclysm(forcePhase = null) {
    if (this.isBusy) return;
    const targetPhase = forcePhase !== null ? forcePhase : this.cataclysmPhase + 1;
    if (targetPhase > 3) {
      const toast = document.getElementById('status-toast');
      if (toast) toast.textContent = '🌋 聖域はすでに十字5マスの最終決戦領域まで崩落しています！';
      return;
    }

    this.isBusy = true;
    this.cataclysmPhase = targetPhase;

    const squaresToCollapse = [];
    if (targetPhase === 1) {
      for (let r = 1; r <= 7; r++) {
        squaresToCollapse.push(`a${r}`, `g${r}`);
      }
      for (const f of ['b', 'c', 'd', 'e', 'f']) {
        squaresToCollapse.push(`${f}1`, `${f}7`);
      }
    } else if (targetPhase === 2) {
      for (let r = 2; r <= 6; r++) {
        squaresToCollapse.push(`b${r}`, `f${r}`);
      }
      for (const f of ['c', 'd', 'e']) {
        squaresToCollapse.push(`${f}2`, `${f}6`);
      }
    } else if (targetPhase === 3) {
      // 3x3の四隅が崩落し、十字5マス (c4, d4, e4, d3, d5) に収縮！
      squaresToCollapse.push('c3', 'c5', 'e3', 'e5');
    }

    const toast = document.getElementById('status-toast');
    if (toast) {
      toast.textContent = `🌋 聖域崩壊 (Cataclysm Phase ${targetPhase}) 発動！ 外周石畳が崩落し足場が奪われます！`;
    }
    this.sfx.playCheckHorn();

    // 1. Flash collapsing squares in red
    for (const sq of squaresToCollapse) {
      this.collapsedSquares.add(sq);
      const ov = this.squareOverlays.get(sq);
      if (ov) {
        ov.material.color.setHex(0xff2200);
        ov.material.opacity = 0.85;
      }
    }

    await this._wait(650);
    this.sfx.playSwordStrikeAndShatter();

    // 2. Any dragons standing on collapsing squares plunge into the void
    for (const sq of squaresToCollapse) {
      const inst = this.pieceInstances.get(sq);
      if (inst) {
        const victimPos = this.squareToWorld(sq);
        this.vfx.spawnShatterExplosion(
          victimPos,
          this._getPieceMaterial(inst.type, inst.color),
          inst.color === 'w'
        );
        this._removePieceInstance(sq);

        const coords = this.chess._squareToCoords(sq);
        this.chess._board[coords.r][coords.c] = null;

        if (inst.type === 'k') {
          this._kingSlain = inst.color;
        }

        const feed = document.getElementById('combat-feed');
        if (feed) {
          const div = document.createElement('div');
          div.className = 'combat-entry';
          div.textContent = `🌋 聖域崩落！ ${inst.color === 'w' ? '白竜石' : '黒曜竜'}の${PIECE_INFO[inst.type]?.shortName || '石造竜'}が足場を失い奈落へ消滅！ (${sq.toUpperCase()})`;
          feed.prepend(div);
        }
      }

      const ov = this.squareOverlays.get(sq);
      if (ov) {
        ov.material.color.setHex(0x150808);
        ov.material.opacity = 0.95;
      }
    }

    this._updateBoardHighlights();
    this.updateHUD();
    this._updateCataclysmHUD();
    this.isBusy = false;

    if (this._kingSlain) {
      const victor = this._kingSlain === 'w' ? '黒曜竜の眷属 (Obsidian Brood)' : '白竜石の聖堂群 (Alabaster Brood)';
      this._showGameOverModal(`聖域崩落により覇王古竜が奈落へ堕ちました！ ${victor} の完全勝利！`);
    }
  }

  _updateCataclysmHUD() {
    const phaseBadge = document.getElementById('cataclysm-phase-badge');
    const turnsText = document.getElementById('cataclysm-turns-text');
    const bar = document.getElementById('cataclysm-progress-bar');

    const peacefulFullMoves = Math.floor((this.peacefulHalfMoves || 0) / 2);
    const turnsRemaining = Math.max(0, 10 - peacefulFullMoves);

    if (phaseBadge) {
      if (this.cataclysmPhase === 0) phaseBadge.textContent = '通常 (7x7)';
      else if (this.cataclysmPhase === 1) phaseBadge.textContent = '第1崩落 (5x5)';
      else if (this.cataclysmPhase === 2) phaseBadge.textContent = '第2崩落 (3x3)';
      else phaseBadge.textContent = '最終決戦 (十字5マス)';
    }

    if (turnsText) {
      if (this.cataclysmPhase >= 3) {
        turnsText.textContent = '最大縮小到達';
        turnsText.style.color = '#ff5533';
      } else {
        turnsText.textContent = `${peacefulFullMoves} / 10 ターン (残り ${turnsRemaining})`;
        turnsText.style.color = turnsRemaining <= 3 ? '#ff3311' : '#ffaa44';
      }
    }

    if (bar) {
      const pct = this.cataclysmPhase >= 3 ? 100 : Math.min(100, (peacefulFullMoves / 10) * 100);
      bar.style.width = `${pct}%`;
    }
  }

  _downscaleTextureForMobile(tex, maxDim = 1024) {
    if (!this.isMobileDevice || !tex?.image) return tex;
    const img = tex.image;
    const w = img.naturalWidth || img.width || 0;
    const h = img.naturalHeight || img.height || 0;
    if (!w || !h || (w <= maxDim && h <= maxDim)) return tex;

    const scale = maxDim / Math.max(w, h);
    const nw = Math.max(1, Math.round(w * scale));
    const nh = Math.max(1, Math.round(h * scale));
    const canvas = document.createElement('canvas');
    canvas.width = nw;
    canvas.height = nh;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(img, 0, 0, nw, nh);
      if (typeof img.close === 'function') {
        try { img.close(); } catch {}
      }
      tex.image = canvas;
      tex.generateMipmaps = true;
      tex.minFilter = THREE.LinearMipmapLinearFilter;
      tex.needsUpdate = true;
    }
    return tex;
  }

  async _initAssets() {
    const statusEl = document.getElementById('loading-status');
    const barEl = document.getElementById('loading-bar-fill');
    const updateProgress = (pct, msg) => {
      if (barEl) barEl.style.width = `${pct}%`;
      if (statusEl) statusEl.textContent = msg;
    };

    const texLoader = new THREE.TextureLoader();
    const gltfLoader = new GLTFLoader();
    const rawMaxAniso = this.renderer.capabilities.getMaxAnisotropy();
    const maxAniso = this.isMobileDevice ? Math.min(2, rawMaxAniso) : Math.min(8, rawMaxAniso);

    const consumeEmbedded = (bucket, url) => {
      const store = window.__EMBEDDED_ASSETS__?.[bucket];
      if (!store) return null;
      const slashUrl = url.replace(/^\.\//, '/');
      const dotUrl = url.startsWith('./') ? url : `./${url.replace(/^\//, '')}`;
      const baseName = url.split('/').pop();
      for (const key of [url, slashUrl, dotUrl, baseName]) {
        if (store[key]) {
          const val = store[key];
          delete store[key];
          return val;
        }
      }
      return null;
    };

    const loadTexSingle = (src, { isColor = true, flipY = true, mobileMaxDim = 1024 } = {}) =>
      new Promise((resolve, reject) => {
        texLoader.load(
          src,
          (tex) => {
            tex.flipY = flipY;
            tex.wrapS = THREE.RepeatWrapping;
            tex.wrapT = THREE.RepeatWrapping;
            if (isColor) tex.colorSpace = THREE.SRGBColorSpace;
            tex.anisotropy = maxAniso;
            this._downscaleTextureForMobile(tex, mobileMaxDim);
            tex.needsUpdate = true;
            resolve(tex);
          },
          undefined,
          reject
        );
      });

    const loadTex = async (url, { isColor = true, flipY = true, mobileMaxDim = 1024 } = {}) => {
      const webpUrl = url.replace(/\.png$/i, '.webp');
      const embedded = consumeEmbedded('textures', webpUrl) || consumeEmbedded('textures', url);
      const candidates = embedded ? [embedded] : (webpUrl !== url ? [webpUrl, url] : [url]);
      for (const src of candidates) {
        try {
          return await loadTexSingle(src, { isColor, flipY, mobileMaxDim });
        } catch {
          // Try next candidate
        }
      }
      return null;
    };

    const loadGLB = async (url, fallbackUrl = null) => {
      const b64 = consumeEmbedded('models', url) || (fallbackUrl ? consumeEmbedded('models', fallbackUrl) : null);
      if (b64) {
        const resp = await fetch(`data:model/gltf-binary;base64,${b64}`);
        const buf = await resp.arrayBuffer();
        return new Promise((resolve, reject) => gltfLoader.parse(buf, '', resolve, reject));
      }
      try {
        return await new Promise((resolve, reject) => gltfLoader.load(url, resolve, undefined, reject));
      } catch (err) {
        if (fallbackUrl) {
          return await new Promise((resolve, reject) => gltfLoader.load(fallbackUrl, resolve, undefined, reject));
        }
        throw err;
      }
    };

    const runBatched = async (tasks, batchSize) => {
      const results = [];
      for (let i = 0; i < tasks.length; i += batchSize) {
        const chunk = tasks.slice(i, i + batchSize).map((fn) => fn());
        results.push(...(await Promise.all(chunk)));
      }
      return results;
    };

    try {
      updateProgress(16, '竜鱗石彫PBRマップ (Albedo / Normal / Roughness / AO / Emission) を展開中...');
      const texSpecs = [
        ['./assets/textures/white_piece_albedo.png', { isColor: true, flipY: false, mobileMaxDim: 1024 }],
        ['./assets/textures/white_piece_normal.png', { isColor: false, flipY: false, mobileMaxDim: 1024 }],
        ['./assets/textures/white_piece_roughness.png', { isColor: false, flipY: false, mobileMaxDim: 512 }],
        ['./assets/textures/white_piece_metallic.png', { isColor: false, flipY: false, mobileMaxDim: 512 }],
        ['./assets/textures/white_piece_ao.png', { isColor: false, flipY: false, mobileMaxDim: 512 }],
        ['./assets/textures/white_piece_emission.png', { isColor: true, flipY: false, mobileMaxDim: 512 }],
        ['./assets/textures/black_piece_albedo.png', { isColor: true, flipY: false, mobileMaxDim: 1024 }],
        ['./assets/textures/black_piece_normal.png', { isColor: false, flipY: false, mobileMaxDim: 1024 }],
        ['./assets/textures/black_piece_roughness.png', { isColor: false, flipY: false, mobileMaxDim: 512 }],
        ['./assets/textures/black_piece_metallic.png', { isColor: false, flipY: false, mobileMaxDim: 512 }],
        ['./assets/textures/black_piece_ao.png', { isColor: false, flipY: false, mobileMaxDim: 512 }],
        ['./assets/textures/black_piece_emission.png', { isColor: true, flipY: false, mobileMaxDim: 512 }],
        ['./assets/textures/board_tiles_albedo.png', { isColor: true, flipY: true, mobileMaxDim: 1024 }],
        ['./assets/textures/board_tiles_normal.png', { isColor: false, flipY: true, mobileMaxDim: 1024 }],
        ['./assets/textures/board_tiles_roughness.png', { isColor: false, flipY: true, mobileMaxDim: 512 }],
        ['./assets/textures/board_tiles_metallic.png', { isColor: false, flipY: true, mobileMaxDim: 512 }],
        ['./assets/textures/board_tiles_ao.png', { isColor: false, flipY: true, mobileMaxDim: 512 }]
      ];
      const texBatchSize = this.isMobileDevice ? 4 : texSpecs.length;
      const [
        wAlbedo, wNormal, wRough, wMetal, wAO, wEmissive,
        bAlbedo, bNormal, bRough, bMetal, bAO, bEmissive,
        tAlbedo, tNormal, tRough, tMetal, tAO
      ] = await runBatched(texSpecs.map(([u, opts]) => () => loadTex(u, opts)), texBatchSize);

      // Construct 2K Carved Dragon-Stonework PBR Materials for White & Black Factions
      this.materials.w = new THREE.MeshStandardMaterial({
        name: 'WhiteDragonStone2KPBR',
        color: 0xf4efe6,
        map: wAlbedo,
        normalMap: wNormal,
        normalScale: new THREE.Vector2(1.55, 1.55),
        roughnessMap: wRough,
        roughness: 0.88,
        metalnessMap: wMetal,
        metalness: 0.56,
        aoMap: wAO,
        aoMapIntensity: 1.15,
        emissiveMap: wEmissive,
        emissive: new THREE.Color(0x58d0ff),
        emissiveIntensity: 0.55
      });

      this.materials.b = new THREE.MeshStandardMaterial({
        name: 'BlackDragonStone2KPBR',
        color: 0xffffff,
        map: bAlbedo,
        normalMap: bNormal,
        normalScale: new THREE.Vector2(1.5, 1.5),
        roughnessMap: bRough,
        roughness: 0.72,
        metalnessMap: bMetal,
        metalness: 0.48,
        aoMap: bAO,
        aoMapIntensity: 0.85,
        emissiveMap: bEmissive,
        emissive: new THREE.Color(0xff5a26),
        emissiveIntensity: 0.82
      });

      // Helper to build tailored black obsidian shader with custom lift tint
      const createBlackPieceMat = (name, color, roughness, metalness, aoIntensity, emissiveColor, emissiveIntensity, tintVec) => {
        const mat = new THREE.MeshStandardMaterial({
          name,
          color,
          map: bAlbedo,
          normalMap: bNormal,
          normalScale: new THREE.Vector2(1.55, 1.55),
          roughnessMap: bRough,
          roughness,
          metalnessMap: bMetal,
          metalness,
          aoMap: bAO,
          aoMapIntensity: aoIntensity,
          emissiveMap: bEmissive,
          emissive: new THREE.Color(emissiveColor),
          emissiveIntensity
        });
        mat.onBeforeCompile = (shader) => {
          shader.fragmentShader = shader.fragmentShader.replace(
            '#include <map_fragment>',
            `
            #include <map_fragment>
            diffuseColor.rgb = diffuseColor.rgb * 1.48 + ${tintVec};
            `
          );
        };
        return mat;
      };

      // --- Per-Piece Tailored Materials (Pawn, Rook, Knight, Bishop, Queen, King) ---
      // 1. Pawn: 幼竜ドレイク (Natural Slate & Earthy Charcoal)
      this.materials.pw = new THREE.MeshStandardMaterial({
        name: 'Pawn_WhiteStone',
        color: 0xf4eee4,
        map: wAlbedo,
        normalMap: wNormal,
        normalScale: new THREE.Vector2(1.5, 1.5),
        roughnessMap: wRough,
        roughness: 0.88,
        metalnessMap: wMetal,
        metalness: 0.42,
        aoMap: wAO,
        aoMapIntensity: 1.15,
        emissiveMap: wEmissive,
        emissive: new THREE.Color(0x4fc3f7),
        emissiveIntensity: 0.45
      });
      this.materials.pb = createBlackPieceMat(
        'Pawn_BlackStone', 0xffffff, 0.76, 0.44, 0.85, 0xff6622, 0.72,
        'vec3(0.075, 0.078, 0.086)' // Natural ash slate
      );

      // 2. Rook: 重装鎧地竜 (Heavy Iron-Granite & Deep Gunmetal Basalt)
      this.materials.rw = new THREE.MeshStandardMaterial({
        name: 'Rook_WhiteStone',
        color: 0xe0e6ee, // 青みがかった硬質花崗岩
        map: wAlbedo,
        normalMap: wNormal,
        normalScale: new THREE.Vector2(1.7, 1.7),
        roughnessMap: wRough,
        roughness: 0.82,
        metalnessMap: wMetal,
        metalness: 0.60,
        aoMap: wAO,
        aoMapIntensity: 1.25,
        emissiveMap: wEmissive,
        emissive: new THREE.Color(0x29b6f6),
        emissiveIntensity: 0.58
      });
      this.materials.rb = createBlackPieceMat(
        'Rook_BlackStone', 0xf0f3f8, 0.70, 0.55, 0.88, 0xff4500, 0.85,
        'vec3(0.065, 0.072, 0.092)' // Cold gunmetal heavy iron
      );

      // 3. Knight: 双翼ワイバーン (Wind-Silver Platinum & Storm Shadow-Silver)
      this.materials.nw = new THREE.MeshStandardMaterial({
        name: 'Knight_WhiteStone',
        color: 0xf6f9fc, // 風を纏う銀白・シルバーホワイト
        map: wAlbedo,
        normalMap: wNormal,
        normalScale: new THREE.Vector2(1.55, 1.55),
        roughnessMap: wRough,
        roughness: 0.62,
        metalnessMap: wMetal,
        metalness: 0.68,
        aoMap: wAO,
        aoMapIntensity: 1.05,
        emissiveMap: wEmissive,
        emissive: new THREE.Color(0x00e5ff),
        emissiveIntensity: 0.66
      });
      this.materials.nb = createBlackPieceMat(
        'Knight_BlackStone', 0xf4f8fa, 0.58, 0.62, 0.80, 0xff7700, 0.88,
        'vec3(0.072, 0.082, 0.096)' // Storm-winged shadow silver
      );

      // 4. Bishop: 双頭の秘術竜 (Mystic Amethyst-Quartz & Dark Void Purple)
      this.materials.bw = new THREE.MeshStandardMaterial({
        name: 'Bishop_WhiteStone',
        color: 0xf4ecf8, // 神秘的な淡い紫水晶ホワイト・アメジスト
        map: wAlbedo,
        normalMap: wNormal,
        normalScale: new THREE.Vector2(1.6, 1.6),
        roughnessMap: wRough,
        roughness: 0.68,
        metalnessMap: wMetal,
        metalness: 0.54,
        aoMap: wAO,
        aoMapIntensity: 1.10,
        emissiveMap: wEmissive,
        emissive: new THREE.Color(0xba68c8), // アルケインバイオレット
        emissiveIntensity: 0.70
      });
      this.materials.bb = createBlackPieceMat(
        'Bishop_BlackStone', 0xf7eef9, 0.64, 0.52, 0.82, 0xec407a, 0.90,
        'vec3(0.088, 0.068, 0.102)' // Deep void arcane amethyst obsidian
      );

      // 5. Queen: 四翼女帝竜 (Celestial Pearl-Platinum & Empress Crimson-Velvet)
      this.materials.qw = new THREE.MeshStandardMaterial({
        name: 'Queen_WhiteStone',
        color: 0xfffcf5, // 最高位の真珠光沢・プラチナホワイト
        map: wAlbedo,
        normalMap: wNormal,
        normalScale: new THREE.Vector2(1.65, 1.65),
        roughnessMap: wRough,
        roughness: 0.46,
        metalnessMap: wMetal,
        metalness: 0.78,
        aoMap: wAO,
        aoMapIntensity: 1.05,
        emissiveMap: wEmissive,
        emissive: new THREE.Color(0xffea00), // 太陽神聖ゴールド
        emissiveIntensity: 0.78
      });
      this.materials.qb = createBlackPieceMat(
        'Queen_BlackStone', 0xfbf2f4, 0.48, 0.70, 0.78, 0xff1744, 0.95,
        'vec3(0.088, 0.072, 0.078)' // Royal crimson-tinted dark velvet pearl
      );

      // Helper to add underbelly pale-white shading + piercing jewel dragon eyes to King dragons
      const applyKingBellyShader = (mat, bellyWhiteVec, eyeCfg = null) => {
        const eyeOuterDiff = eyeCfg?.outerDiff || 'vec3(0.00, 0.08, 0.42)';
        const eyeInnerDiff = eyeCfg?.innerDiff || 'vec3(0.02, 0.36, 0.90)';
        const eyeOuterGlow = eyeCfg?.outerGlow || 'vec3(0.00, 0.14, 0.85)';
        const eyeInnerGlow = eyeCfg?.innerGlow || 'vec3(0.04, 0.56, 1.35)';
        const cacheTag = eyeCfg?.tag || 'default';

        const eyeMaskGlsl = `
            float eyeUvBand = smoothstep(0.095, 0.106, vEyeUv.y) * (1.0 - smoothstep(0.184, 0.195, vEyeUv.y));
            float eyePosX = smoothstep(0.078, 0.085, abs(vBellyPos.x)) * (1.0 - smoothstep(0.144, 0.152, abs(vBellyPos.x)));
            float eyePosY = smoothstep(1.860, 1.868, vBellyPos.y) * (1.0 - smoothstep(1.909, 1.918, vBellyPos.y));
            float eyePosZ = smoothstep(-0.405, -0.396, vBellyPos.z) * (1.0 - smoothstep(-0.313, -0.304, vBellyPos.z));
            float eyeMask = clamp(eyeUvBand * eyePosX * eyePosY * eyePosZ, 0.0, 1.0);
        `;

        // Unique cache key ensures White King (Sapphire) & Black King (Crimson) NEVER reuse the same compiled WebGL shader!
        mat.customProgramCacheKey = () => `king_belly_eye_${cacheTag}_${bellyWhiteVec}_${eyeOuterGlow}`;

        mat.onBeforeCompile = (shader) => {
          shader.vertexShader = `
            varying vec3 vBellyPos;
            varying vec3 vBellyNorm;
            varying vec2 vEyeUv;
            ${shader.vertexShader}
          `.replace(
            '#include <begin_vertex>',
            `
            #include <begin_vertex>
            vBellyPos = position;
            vBellyNorm = normal;
            vEyeUv = uv;
            `
          );

          shader.fragmentShader = `
            varying vec3 vBellyPos;
            varying vec3 vBellyNorm;
            varying vec2 vEyeUv;
            ${shader.fragmentShader}
          `
            .replace(
              '#include <map_fragment>',
              `
              #include <map_fragment>
              // Great Dragon pear-shaped underbelly -> chest -> throat mask
              float yFactor = smoothstep(0.32, 0.48, vBellyPos.y) * (1.0 - smoothstep(1.66, 1.77, vBellyPos.y));
              float bellyHalfW = mix(0.155, 0.068, smoothstep(0.82, 1.72, vBellyPos.y));
              float xFactor = 1.0 - smoothstep(bellyHalfW * 0.56, bellyHalfW, abs(vBellyPos.x));
              float zFactor = 1.0 - smoothstep(-0.04, 0.085, vBellyPos.z);
              float normFactor = smoothstep(0.24, -0.22, vBellyNorm.z);
              float bellyMask = clamp(yFactor * xFactor * zFactor * normFactor, 0.0, 1.0);

              // Blend underside towards dignified pale-white stone base
              vec3 bellyWhite = ${bellyWhiteVec};
              diffuseColor.rgb = mix(diffuseColor.rgb, bellyWhite, bellyMask * 0.90);

              ${eyeMaskGlsl}
              float rawDy = vBellyPos.y - 1.8888;
              float rawDz = vBellyPos.z + 0.3551;
              float eDy = (rawDy * 0.94 - rawDz * 0.34) / 0.0205;
              float eDz = (rawDz * 0.94 + rawDy * 0.34) / 0.0438;
              float irisCore = 1.0 - smoothstep(0.18, 0.92, length(vec2(eDz * 0.95, eDy * 0.85)));
              vec3 eyeDiffCol = mix(${eyeOuterDiff}, ${eyeInnerDiff}, irisCore);
              diffuseColor.rgb = mix(diffuseColor.rgb, eyeDiffCol, eyeMask);
              `
            )
            .replace(
              '#include <roughnessmap_fragment>',
              `
              #include <roughnessmap_fragment>
              {
                ${eyeMaskGlsl}
                roughnessFactor = mix(roughnessFactor, 0.12, eyeMask);
              }
              `
            )
            .replace(
              '#include <metalnessmap_fragment>',
              `
              #include <metalnessmap_fragment>
              {
                ${eyeMaskGlsl}
                metalnessFactor = mix(metalnessFactor, 0.08, eyeMask);
              }
              `
            )
            .replace(
              '#include <emissivemap_fragment>',
              `
              #include <emissivemap_fragment>
              {
                ${eyeMaskGlsl}
                float rawDyG = vBellyPos.y - 1.8888;
                float rawDzG = vBellyPos.z + 0.3551;
                float eDyG = (rawDyG * 0.94 - rawDzG * 0.34) / 0.0205;
                float eDzG = (rawDzG * 0.94 + rawDyG * 0.34) / 0.0438;
                float irisCoreG = 1.0 - smoothstep(0.18, 0.92, length(vec2(eDzG * 0.95, eDyG * 0.85)));
                vec3 eyeGlowCol = mix(${eyeOuterGlow}, ${eyeInnerGlow}, irisCoreG);
                totalEmissiveRadiance = mix(totalEmissiveRadiance, eyeGlowCol, eyeMask);
              }
              `
            );
        };
      };

      // 6. King: 大聖堂の覇王古竜 (Radiant Imperial Gold & Obsidian Bronze Gold with Pale-White Underbelly)
      this.materials.kw = new THREE.MeshStandardMaterial({
        name: 'WhiteKingGoldDragon2KPBR',
        color: 0xf6c855, // 輝く高貴なシャンパンゴールド
        map: wAlbedo,
        normalMap: wNormal,
        normalScale: new THREE.Vector2(1.65, 1.65),
        roughnessMap: wRough,
        roughness: 0.36, // 重厚な金属光沢
        metalnessMap: wMetal,
        metalness: 0.84, // 高い金属度でゴールドの質感
        aoMap: wAO,
        aoMapIntensity: 1.15,
        emissiveMap: wEmissive,
        emissive: new THREE.Color(0xffb733),
        emissiveIntensity: 0.72
      });
      applyKingBellyShader(this.materials.kw, 'vec3(0.86, 0.86, 0.88)', {
        tag: 'kw',
        outerDiff: 'vec3(0.00, 0.08, 0.42)',
        innerDiff: 'vec3(0.02, 0.36, 0.90)',
        outerGlow: 'vec3(0.00, 0.14, 0.85)',
        innerGlow: 'vec3(0.04, 0.56, 1.35)'
      });

      this.materials.kb = new THREE.MeshStandardMaterial({
        name: 'BlackKingGoldDragon2KPBR',
        color: 0xcca03a, // 重厚な燻し金・黒曜アンティークゴールド
        map: bAlbedo,
        normalMap: bNormal,
        normalScale: new THREE.Vector2(1.75, 1.75),
        roughnessMap: bRough,
        roughness: 0.38,
        metalnessMap: bMetal,
        metalness: 0.86,
        aoMap: bAO,
        aoMapIntensity: 1.25,
        emissiveMap: bEmissive,
        emissive: new THREE.Color(0xff6a20),
        emissiveIntensity: 0.85
      });
      applyKingBellyShader(this.materials.kb, 'vec3(0.72, 0.73, 0.76)', {
        tag: 'kb',
        outerDiff: 'vec3(0.45, 0.01, 0.02)',
        innerDiff: 'vec3(0.88, 0.08, 0.02)',
        outerGlow: 'vec3(0.88, 0.01, 0.02)',
        innerGlow: 'vec3(1.40, 0.18, 0.02)'
      });

      this.materials.tileLight = new THREE.MeshStandardMaterial({
        name: 'DragonSanctumStone2KPBR',
        color: 0xf3eee5,
        map: tAlbedo,
        normalMap: tNormal,
        normalScale: new THREE.Vector2(1.25, 1.25),
        roughnessMap: tRough,
        roughness: 0.90,
        metalnessMap: tMetal,
        metalness: 0.25,
        aoMap: tAO,
        aoMapIntensity: 1.05
      });

      this.materials.tileDark = this.materials.tileLight;

      updateProgress(45, '3D ゴシック大聖堂と古代ルーン岩場祭壇を召喚中...');
      try {
        const cathedralGLTF = await loadGLB('./assets/models/gothic_cathedral_webp.glb', './assets/models/gothic_cathedral.glb');
        cathedralGLTF.scene.rotation.y = Math.PI;
        const downscaledTex = new Set();
        cathedralGLTF.scene.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
            if (child.material) {
              const mats = Array.isArray(child.material) ? child.material : [child.material];
              for (const mat of mats) {
                const mName = mat.name || '';
                if (!mName.includes('Glass') && !mName.includes('Ember')) {
                  mat.roughness = Math.max(mat.roughness ?? 0.65, 0.68);
                }
                if (this.isMobileDevice) {
                  for (const [slot, maxDim] of [
                    ['map', 768],
                    ['normalMap', 768],
                    ['roughnessMap', 512],
                    ['metalnessMap', 512],
                    ['aoMap', 512],
                    ['emissiveMap', 512]
                  ]) {
                    const tex = mat[slot];
                    if (tex && !downscaledTex.has(tex)) {
                      downscaledTex.add(tex);
                      tex.anisotropy = Math.min(2, tex.anisotropy || 1);
                      this._downscaleTextureForMobile(tex, maxDim);
                    }
                  }
                }
              }
            }
          }
        });
        this.scene.add(cathedralGLTF.scene);
      } catch (err) {
        console.warn('Fallback cathedral builder triggered:', err);
        this._buildFallbackCathedral();
      }

      updateProgress(68, '崩れた石畳と古代ルーン聖痕フィールドを展開中...');
      this._buildInteractiveBoard();

      updateProgress(82, 'ドラゴンたちを呼び覚まし中...');
      const pieceMap = [
        ['p', './assets/models/pawn.glb'],
        ['r', './assets/models/rook.glb'],
        ['n', './assets/models/knight.glb'],
        ['b', './assets/models/bishop.glb'],
        ['q', './assets/models/queen.glb'],
        ['k', './assets/models/king.glb']
      ];

      await runBatched(
        pieceMap.map(([code, url]) => async () => {
          const gltf = await loadGLB(url);
          gltf.scene.traverse((child) => {
            if ((child.isMesh || child.isSkinnedMesh) && child.geometry) {
              if (child.geometry.attributes.uv && !child.geometry.attributes.uv1) {
                child.geometry.setAttribute('uv1', child.geometry.attributes.uv);
              }
              this._processPedestalGeometry(child.geometry);
            }
          });
          this.piecePrototypes[code] = {
            scene: gltf.scene,
            animations: gltf.animations || []
          };
        }),
        this.isMobileDevice ? 2 : pieceMap.length
      );

      // Release embedded texture & model Base64 caches once parsed into Three.js objects
      if (window.__EMBEDDED_ASSETS__) {
        delete window.__EMBEDDED_ASSETS__.textures;
        delete window.__EMBEDDED_ASSETS__.models;
      }

      updateProgress(96, '双覇王古竜の決戦局面へ召喚中 (土台なし・マス接地)...');
      this.syncBoardFromFEN();
      this.updateHUD();

      updateProgress(100, '竜石の聖域・開戦準備完了');
      setTimeout(() => {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.classList.add('fade-out');
      }, 250);
    } catch (err) {
      console.error('Initialization error:', err);
      if (statusEl) statusEl.textContent = 'フォールバック構成で初期化しました。';
      setTimeout(() => {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.classList.add('fade-out');
      }, 500);
    }

    this._animate();
  }

  _buildFallbackCathedral() {
    const frameGeo = new THREE.CylinderGeometry(5.6, 6.1, 0.42, 12);
    const frame = new THREE.Mesh(frameGeo, this.materials.tileLight || new THREE.MeshStandardMaterial({ color: 0x242029, roughness: 0.85 }));
    frame.position.y = -0.21;
    frame.receiveShadow = true;
    this.scene.add(frame);
  }

  _buildLocusRuneTexture() {
    const size = 256;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    const c = size / 2;
    ctx.clearRect(0, 0, size, size);

    const grad = ctx.createRadialGradient(c, c, size * 0.08, c, c, size * 0.48);
    grad.addColorStop(0.0, 'rgba(255, 255, 255, 0.32)');
    grad.addColorStop(0.62, 'rgba(255, 255, 255, 0.14)');
    grad.addColorStop(1.0, 'rgba(255, 255, 255, 0.0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(c, c, size * 0.48, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)';
    ctx.lineWidth = 4.2;
    ctx.beginPath();
    ctx.arc(c, c, size * 0.42, 0, Math.PI * 2);
    ctx.stroke();

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.72)';
    ctx.lineWidth = 2.2;
    ctx.setLineDash([10, 7]);
    ctx.beginPath();
    ctx.arc(c, c, size * 0.34, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // 8 Dragon-fang compass spikes & inner rune diamond
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.88)';
    ctx.lineWidth = 2.4;
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      const r0 = i % 2 === 0 ? size * 0.22 : size * 0.28;
      const r1 = size * 0.44;
      ctx.beginPath();
      ctx.moveTo(c + Math.cos(a) * r0, c + Math.sin(a) * r0);
      ctx.lineTo(c + Math.cos(a) * r1, c + Math.sin(a) * r1);
      ctx.stroke();
    }

    const tex = new THREE.CanvasTexture(canvas);
    tex.needsUpdate = true;
    return tex;
  }

  _buildInteractiveBoard() {
    const boardGroup = new THREE.Group();
    boardGroup.name = 'DraconicSanctumLoci';

    const hitGeo = new THREE.CylinderGeometry(0.56, 0.56, 0.05, 12);
    const hitMat = new THREE.MeshBasicMaterial({
      transparent: true,
      opacity: 0.0,
      depthWrite: false,
      colorWrite: false
    });

    const locusRuneTex = this._buildLocusRuneTexture();
    const overlayGeo = new THREE.PlaneGeometry(1.10, 1.10);
    overlayGeo.rotateX(-Math.PI / 2);

    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) {
        const rank = 7 - r;
        const file = FILES[c];
        const sq = `${file}${rank}`;
        const pos = this.squareToWorld(sq);

        // Invisible raycast sensor on the continuous ruined stone sanctum floor (NO checkerboard squares!)
        const locusSensor = new THREE.Mesh(hitGeo, hitMat);
        locusSensor.position.set(pos.x, 0.01, pos.z);
        locusSensor.userData = { square: sq };
        boardGroup.add(locusSensor);
        this.boardSquares.set(sq, locusSensor);

        // Circular Arcane Draconic Rune-Sigil Highlight (materializes only when active)
        const ovMat = new THREE.MeshBasicMaterial({
          map: locusRuneTex,
          color: 0x4fc3f7,
          transparent: true,
          opacity: 0.0,
          blending: THREE.AdditiveBlending,
          side: THREE.DoubleSide,
          depthWrite: false
        });
        const ovMesh = new THREE.Mesh(overlayGeo, ovMat);
        ovMesh.position.set(pos.x, 0.016, pos.z);
        ovMesh.rotation.y = ((r * 7 + c * 3) % 8) * (Math.PI / 4);
        boardGroup.add(ovMesh);
        this.squareOverlays.set(sq, ovMesh);
      }
    }

    // Jagged rim crags, rubble & broken Gothic columns are baked into gothic_cathedral.glb (build_dragon_sanctum_altar)
    this.scene.add(boardGroup);
  }

  squareToWorld(square) {
    const fileIndex = FILES.indexOf(square[0]);
    const rank = parseInt(square[1], 10);
    const r = 7 - rank;
    return new THREE.Vector3((fileIndex - 3) * NODE_SPACING, 0.0, (r - 3) * NODE_SPACING);
  }

  _getPieceMaterial(type, color) {
    const key = `${type}${color}`;
    if (this.materials[key]) {
      return this.materials[key];
    }
    return color === 'w' ? this.materials.w : this.materials.b;
  }

  _createPieceInstance(type, color, square) {
    const proto = this.piecePrototypes[type];
    if (!proto) return null;

    const clonedScene = SkeletonUtils.clone(proto.scene);
    const mat = this._getPieceMaterial(type, color);
    let boneCount = 0;
    const hasBase = this.pedestalMode !== 'no-base';
    let bodyMinY = 0.128;

    clonedScene.traverse((child) => {
      if (child.isMesh || child.isSkinnedMesh) {
        child.material = mat;
        child.castShadow = true;
        child.receiveShadow = true;
        child.frustumCulled = false;
        child.userData.square = square;
        if (child.skeleton && child.skeleton.bones) {
          boneCount = Math.max(boneCount, child.skeleton.bones.length);
        }
        if (child.geometry?.userData?.totalCount) {
          const count = hasBase ? child.geometry.userData.totalCount : child.geometry.userData.bodyCount;
          child.geometry.setDrawRange(0, count);
          if (child.geometry.userData.bodyMinY) {
            bodyMinY = child.geometry.userData.bodyMinY;
          }
        }
      }
    });

    const scale = type === 'k' ? 1.10 : 1.0;
    clonedScene.scale.setScalar(scale);

    const pos = this.squareToWorld(square);
    const scaledBodyMinY = bodyMinY * scale;
    const yOffset = hasBase ? 0 : -scaledBodyMinY;
    clonedScene.position.set(pos.x, pos.y + yOffset, pos.z);

    const defaultYaw = color === 'w' ? 0 : Math.PI;
    clonedScene.rotation.set(0, defaultYaw, 0);

    this.scene.add(clonedScene);

    const mixer = new THREE.AnimationMixer(clonedScene);
    const actions = {};
    for (const clip of proto.animations) {
      const act = mixer.clipAction(clip);
      actions[clip.name] = act;
    }

    this.activeMixers.add(mixer);

    // Draconic RPG Stats & Overhead HP Bar Sprite
    const stats = DRAGON_STATS[type] || { maxHp: 50, atk: 25, def: 10, headHeight: 1.5, title: '石造竜' };
    const hpBarSprite = createHpBarSprite(stats.maxHp, stats.maxHp);
    const spriteY = stats.headHeight * scale + (hasBase ? 0.12 : scaledBodyMinY + 0.12);
    hpBarSprite.position.set(0, spriteY, 0);
    hpBarSprite.visible = this.combatRule === 'tactics';
    clonedScene.add(hpBarSprite);

    const instance = {
      type,
      color,
      square,
      boneCount: boneCount || 7,
      root: clonedScene,
      mixer,
      actions,
      currentAnim: 'Idle',
      defaultYaw,
      scale,
      yOffset,
      bodyMinY: scaledBodyMinY,
      maxHp: stats.maxHp,
      hp: stats.maxHp,
      atk: stats.atk,
      def: stats.def,
      headHeight: stats.headHeight,
      hpBarSprite,
      updateHp(newHp) {
        this.hp = Math.max(0, Math.min(this.maxHp, newHp));
        if (this.hpBarSprite && this.hpBarSprite.userData?.draw) {
          this.hpBarSprite.userData.draw(this.hp);
          if (this.hpBarSprite.material.map) {
            this.hpBarSprite.material.map.needsUpdate = true;
          }
        }
      }
    };

    this._playPieceAnimation(instance, 'Idle', true);
    return instance;
  }

  _playPieceAnimation(instance, animName, loop = false) {
    if (!instance || !instance.actions) return;
    let targetAction = instance.actions[animName];
    if (!targetAction) {
      const key = Object.keys(instance.actions).find((k) =>
        k.toLowerCase().includes(animName.toLowerCase())
      );
      if (key) targetAction = instance.actions[key];
    }
    if (!targetAction) return;

    for (const act of Object.values(instance.actions)) {
      if (act !== targetAction) {
        act.fadeOut(0.16);
      }
    }

    targetAction.reset();
    targetAction.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, loop ? Infinity : 1);
    targetAction.clampWhenFinished = !loop;
    targetAction.fadeIn(0.16);
    targetAction.play();
    instance.currentAnim = animName;

    if (this.selectedSquare === instance.square) {
      const pill = document.getElementById('inspector-anim-pill');
      if (pill) pill.textContent = animName.toUpperCase();
    }
  }

  _removePieceInstance(square) {
    const inst = this.pieceInstances.get(square);
    if (!inst) return;
    inst.mixer?.stopAllAction?.();
    this.activeMixers.delete(inst.mixer);
    if (inst.hpBarSprite) {
      inst.hpBarSprite.material?.map?.dispose();
      inst.hpBarSprite.material?.dispose();
    }
    this.scene.remove(inst.root);
    this.pieceInstances.delete(square);
  }

  syncBoardFromFEN() {
    for (const sq of Array.from(this.pieceInstances.keys())) {
      this._removePieceInstance(sq);
    }

    const board = this.chess.board();
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) {
        const cell = board[r][c];
        if (!cell) continue;
        const sq = `${FILES[c]}${7 - r}`;
        const inst = this._createPieceInstance(cell.type, cell.color, sq);
        if (inst) {
          this.pieceInstances.set(sq, inst);
        }
      }
    }

    this._updateBoardHighlights();
  }

  _updateBoardHighlights() {
    for (const [, ov] of this.squareOverlays.entries()) {
      ov.material.opacity = 0.0;
    }

    if (this.lastMove) {
      for (const sq of [this.lastMove.from, this.lastMove.to]) {
        const ov = this.squareOverlays.get(sq);
        if (ov) {
          ov.material.color.setHex(0xe5b95c);
          ov.material.opacity = 0.34;
        }
      }
    }

    if (this.hintMove) {
      for (const sq of [this.hintMove.from, this.hintMove.to]) {
        const ov = this.squareOverlays.get(sq);
        if (ov) {
          ov.material.color.setHex(0xab47bc);
          ov.material.opacity = 0.55;
        }
      }
    }

    if (this.chess.inCheck()) {
      const turn = this.chess.turn();
      for (const [sq, inst] of this.pieceInstances.entries()) {
        if (inst.type === 'k' && inst.color === turn) {
          const ov = this.squareOverlays.get(sq);
          if (ov) {
            ov.material.color.setHex(0xff2a2a);
            ov.material.opacity = 0.68;
          }
        }
      }
    }

    if (this.selectedSquare) {
      const selOv = this.squareOverlays.get(this.selectedSquare);
      if (selOv) {
        selOv.material.color.setHex(0x4fc3f7);
        selOv.material.opacity = 0.55;
      }

      for (const m of this.legalMovesForSelected) {
        const ov = this.squareOverlays.get(m.to);
        if (ov) {
          const isCapture = Boolean(m.captured);
          ov.material.color.setHex(isCapture ? 0xff4d4d : 0x5be382);
          ov.material.opacity = isCapture ? 0.62 : 0.42;
        }
      }
    }
  }

  selectSquare(square) {
    if (this.isBusy) return;

    if (this.selectedSquare) {
      const matchingMoves = this.legalMovesForSelected.filter((m) => m.to === square);
      if (matchingMoves.length > 0) {
        if (matchingMoves.some((m) => m.promotion)) {
          this.pendingPromotionMove = { from: this.selectedSquare, to: square };
          document.getElementById('promotion-modal')?.classList.remove('hidden');
          return;
        }
        this.executeMove(matchingMoves[0]);
        return;
      }

      // Check if this move is blocked due to 3-repetition anti-stalemate rule
      const rawMoves = this.chess.moves({ square: this.selectedSquare, verbose: true });
      const blockedByRepetition = rawMoves.some((m) => m.to === square && this._isRepetitionForbidden(m));
      if (blockedByRepetition) {
        const toast = document.getElementById('status-toast');
        if (toast) {
          toast.textContent = '🚫 聖域禁呪: 同一駒の進退・往復ループ（千日手）は3回以上禁止されています！別の手を指してください。';
        }
        this.sfx.playCheckHorn();
        return;
      }

      if (this.collapsedSquares.has(square)) {
        const toast = document.getElementById('status-toast');
        if (toast) toast.textContent = '🚫 崩落した奈落のマスには侵入できません！';
        return;
      }
    }

    const inst = this.pieceInstances.get(square);
    if (inst) {
      this._updateInspector(inst);
      if (inst.color === this.chess.turn()) {
        this.selectedSquare = square;
        this.legalMovesForSelected = this.chess
          .moves({ square, verbose: true })
          .filter((m) => !this._isRepetitionForbidden(m) && !this.collapsedSquares.has(m.to));
        this.sfx.playSelect();
        this._updateBoardHighlights();
        this._updateInspector(inst);
        return;
      }
    }

    this.selectedSquare = null;
    this.legalMovesForSelected = [];
    this._updateBoardHighlights();
  }

  focusSelectedStatueMacro(squareOverride = null) {
    const sq = squareOverride || this.selectedSquare || 'd1';
    const inst = this.pieceInstances.get(sq) || Array.from(this.pieceInstances.values())[0];
    if (!inst) return;
    if (this.selectedSquare !== inst.square) {
      this._updateInspector(inst);
    }
    const basePos = this.squareToWorld(inst.square);
    const frontSign = inst.color === 'w' ? -1 : 1;
    // Choose lateral offset away from adjacent back-rank dragons so jaws, horns & wings are unobstructed
    const xSign = basePos.x >= 0 ? -1 : 1;
    const isBackRank = inst.square[1] === '1' || inst.square[1] === '7';
    const camPos = new THREE.Vector3(
      basePos.x + xSign * 1.62,
      basePos.y + (isBackRank ? 2.15 : 1.62),
      basePos.z + frontSign * (isBackRank ? 2.35 : 2.02)
    );
    const lookTarget = new THREE.Vector3(basePos.x, basePos.y + 0.92, basePos.z);
    this._tweenCamera(camPos, lookTarget, 0.72);
  }

  setCombatCamMode(mode) {
    if (!['smart', 'closeup', 'free'].includes(mode)) return;
    this.combatCamMode = mode;
    this.actionCamEnabled = mode !== 'free';

    const select = document.getElementById('combat-cam-select');
    if (select) select.value = mode;

    const btnSmart = document.getElementById('btn-cam-smart');
    const btnCloseup = document.getElementById('btn-cam-closeup-mode');
    const btnFree = document.getElementById('btn-cam-free');
    if (btnSmart) btnSmart.classList.toggle('active', mode === 'smart');
    if (btnCloseup) btnCloseup.classList.toggle('active', mode === 'closeup');
    if (btnFree) btnFree.classList.toggle('active', mode === 'free');

    const chk = document.getElementById('chk-action-cam');
    if (chk) chk.checked = mode !== 'free';

    const toast = document.getElementById('status-toast');
    if (toast) {
      if (mode === 'smart') toast.textContent = '🎬 攻撃カメラ: 俯瞰時は視点維持 (引いている時は拡大せずそのままブレス鑑賞)';
      else if (mode === 'closeup') toast.textContent = '🎬 攻撃カメラ: 常に迫力拡大 (激突クローズアップ)';
      else if (mode === 'free') toast.textContent = '🎬 攻撃カメラ: 常に現在視点を維持 (ズーム拡大なし)';
    }
  }

  _isOverviewingCamera() {
    if (!this.camera || !this.controls) return false;
    const target = this.controls.target || new THREE.Vector3(0, 0.65, 0);
    const dist = this.camera.position.distanceTo(target);
    const deltaY = this.camera.position.y - target.y;

    // 1. スクロール等で画面を離している場合 (標準岩座視点の距離は約13.8)
    const isFar = dist >= 14.2;

    // 2. 俯瞰（見下ろし角が高い）場合 (魔法陣祭壇・俯瞰プリセット等)
    const isHighAngle = (dist > 0.1 && deltaY / dist >= 0.58) || deltaY >= 9.5;

    return isFar || isHighAngle;
  }

  _resetInspector() {
    const feed = document.getElementById('combat-feed');
    if (feed) {
      feed.innerHTML = '<div class="combat-entry">崩れた石畳と古代ルーン魔法陣の祭壇で、石造ドラゴン群が覚醒しました…</div>';
    }
    const titleEl = document.getElementById('inspector-title');
    const loreEl = document.getElementById('inspector-lore');
    const sqEl = document.getElementById('inspector-square');
    const movesEl = document.getElementById('inspector-moves');
    const bonesEl = document.getElementById('inspector-bones');
    const pillEl = document.getElementById('inspector-anim-pill');

    if (titleEl) titleEl.textContent = '石造竜未選択';
    if (loreEl) {
      loreEl.textContent =
        '祭壇の石造ドラゴンをクリックすると、竜種の特徴・2K竜鱗石彫PBR・7ボーン骨格・進撃可能なルーン聖痕を確認できます。';
    }
    if (sqEl) sqEl.textContent = '—';
    if (movesEl) movesEl.textContent = '0';
    if (bonesEl) bonesEl.textContent = '7 Bones';
    if (pillEl) pillEl.textContent = 'IDLE';

    const hpText = document.getElementById('inspector-hp-text');
    const hpBar = document.getElementById('inspector-hp-bar');
    const atkVal = document.getElementById('inspector-atk-val');
    const defVal = document.getElementById('inspector-def-val');
    if (hpText) hpText.textContent = '— / —';
    if (hpBar) {
      hpBar.style.width = '100%';
      hpBar.style.background = 'linear-gradient(90deg, #27ae60, #2ecc71)';
    }
    if (atkVal) atkVal.textContent = '—';
    if (defVal) defVal.textContent = '—';
  }

  _updateInspector(inst) {
    const titleEl = document.getElementById('inspector-title');
    const loreEl = document.getElementById('inspector-lore');
    const sqEl = document.getElementById('inspector-square');
    const movesEl = document.getElementById('inspector-moves');
    const bonesEl = document.getElementById('inspector-bones');
    const pillEl = document.getElementById('inspector-anim-pill');

    if (!inst) return;
    const meta = PIECE_INFO[inst.type];
    const faction = inst.color === 'w' ? '白竜石' : '黒曜竜';
    if (titleEl) titleEl.textContent = `${faction} • ${meta.name}`;
    if (loreEl) loreEl.textContent = meta.lore;
    if (sqEl) sqEl.textContent = inst.square.toUpperCase();
    const moves = this.chess.moves({ square: inst.square, verbose: true });
    if (movesEl) movesEl.textContent = `${moves.length}`;
    if (bonesEl) bonesEl.textContent = `${inst.boneCount} Bones`;
    if (pillEl) pillEl.textContent = inst.currentAnim.toUpperCase();

    const hpText = document.getElementById('inspector-hp-text');
    const hpBar = document.getElementById('inspector-hp-bar');
    const atkVal = document.getElementById('inspector-atk-val');
    const defVal = document.getElementById('inspector-def-val');
    if (inst.hp !== undefined && inst.maxHp !== undefined) {
      if (hpText) hpText.textContent = `${inst.hp} / ${inst.maxHp}`;
      if (hpBar) {
        const pct = Math.max(0, Math.min(100, Math.round((inst.hp / inst.maxHp) * 100)));
        hpBar.style.width = `${pct}%`;
        if (pct > 50) {
          hpBar.style.background = 'linear-gradient(90deg, #27ae60, #2ecc71)';
        } else if (pct > 25) {
          hpBar.style.background = 'linear-gradient(90deg, #e67e22, #f1c40f)';
        } else {
          hpBar.style.background = 'linear-gradient(90deg, #c0392b, #e74c3c)';
        }
      }
      if (atkVal) atkVal.textContent = `${inst.atk}`;
      if (defVal) defVal.textContent = `${inst.def}`;
    }
  }

  async executeMove(moveInput) {
    if (this.isBusy) return false;

    let moveObj = null;
    try {
      moveObj = this.chess.move(moveInput);
    } catch {
      return false;
    }
    if (!moveObj) return false;

    // Check anti-stalemate 3-repetition rule
    if (this._isRepetitionForbidden(moveObj)) {
      this.chess.undo();
      const toast = document.getElementById('status-toast');
      if (toast) {
        toast.textContent = '🚫 聖域禁呪: 同一駒の進退・往復ループ（千日手）は3回以上禁止されています！別の手を指してください。';
      }
      this.sfx.playCheckHorn();
      return false;
    }

    // Check collapsed abyss square
    if (this.collapsedSquares.has(moveObj.to)) {
      this.chess.undo();
      const toast = document.getElementById('status-toast');
      if (toast) toast.textContent = '🚫 崩落した奈落のマスには侵入できません！';
      this.sfx.playCheckHorn();
      return false;
    }

    this.isBusy = true;
    this.hintMove = null;
    this.selectedSquare = null;
    this.legalMovesForSelected = [];
    this.lastMove = { from: moveObj.from, to: moveObj.to };
    this._updateBoardHighlights();

    const attacker = this.pieceInstances.get(moveObj.from);
    let capturedSquare = moveObj.to;
    if (moveObj.flags && moveObj.flags.includes('e')) {
      const capRank = moveObj.color === 'w' ? parseInt(moveObj.to[1], 10) - 1 : parseInt(moveObj.to[1], 10) + 1;
      capturedSquare = `${moveObj.to[0]}${capRank}`;
    }
    const defender = moveObj.captured ? this.pieceInstances.get(capturedSquare) : null;

    let combatOutcome = null;

    if (attacker) {
      combatOutcome = await this._animateMoveAndCombat(attacker, defender, moveObj, capturedSquare);
    } else {
      this.syncBoardFromFEN();
    }

    // Castling Rook motion (if ever triggered)
    if (moveObj.flags && (moveObj.flags.includes('k') || moveObj.flags.includes('q'))) {
      const rank = moveObj.color === 'w' ? '1' : '7';
      const rookFrom = moveObj.flags.includes('k') ? `g${rank}` : `a${rank}`;
      const rookTo = moveObj.flags.includes('k') ? `e${rank}` : `c${rank}`;
      const rookInst = this.pieceInstances.get(rookFrom);
      if (rookInst) {
        this.pieceInstances.delete(rookFrom);
        rookInst.square = rookTo;
        const rookPos = this.squareToWorld(rookTo);
        rookPos.y += (rookInst.yOffset || 0);
        rookInst.root.position.copy(rookPos);
        this.pieceInstances.set(rookTo, rookInst);
      }
    }

    // Pawn Promotion transfiguration
    if (moveObj.promotion) {
      this._removePieceInstance(moveObj.to);
      const promoted = this._createPieceInstance(moveObj.promotion, moveObj.color, moveObj.to);
      if (promoted) {
        this.pieceInstances.set(moveObj.to, promoted);
        const promoPos = this.squareToWorld(moveObj.to);
        promoPos.y += (promoted.yOffset || 0);
        this.vfx.spawnShatterExplosion(
          promoPos,
          this._getPieceMaterial(moveObj.promotion, moveObj.color),
          moveObj.color === 'w'
        );
      }
    }

    let bossRaidOutcome = null;
    if (this.chess.inCheck()) {
      this.sfx.playCheckHorn();

      // 【条件4: 覇王古竜（キング）のレイドボス耐久バトル】
      // 竜石タクティクスモード時、王手をかけた瞬間に攻撃側から相手キングへ「王手竜炎ブレス」を着弾させ、キングからも反撃ブレスが放たれる
      if (this.combatRule === 'tactics') {
        bossRaidOutcome = await this._handleCheckBossRaid(moveObj);
      }
    }

    this.moveActionLog.push({
      color: moveObj.color,
      piece: moveObj.piece,
      from: moveObj.from,
      to: moveObj.to
    });

    this._logCombatMove(moveObj, combatOutcome);
    this._updateBoardHighlights();
    this.updateHUD();

    // お互いの戦闘が往復10ターン以上実行されない毎にフィールドを狭くしていって逃げ場を縮小！
    const isCombat = Boolean(combatOutcome?.isCombat || bossRaidOutcome?.isCombat);
    if (isCombat) {
      // 交戦が発生: 聖域崩壊タイマーをリセット
      const wasWarning = this.peacefulHalfMoves >= 14;
      this.peacefulHalfMoves = 0;
      if (wasWarning) {
        const toast = document.getElementById('status-toast');
        if (toast) toast.textContent = '🔥 ドラゴン交戦発生！ 聖域崩落カウントダウンがリセットされました！';
      }
    } else {
      // 交戦なし移動: 半手を加算
      this.peacefulHalfMoves++;
    }

    const peacefulFullMoves = Math.floor(this.peacefulHalfMoves / 2);
    const turnsRemaining = Math.max(0, 10 - peacefulFullMoves);

    // 往復10ターン（20手）交戦なし毎にフィールド崩落を発動
    if (peacefulFullMoves >= 10 && this.cataclysmPhase < 3) {
      this.peacefulHalfMoves = 0; // 次の縮小に向けてリセット
      const nextPhase = this.cataclysmPhase + 1;
      await this.triggerCataclysm(nextPhase);
    } else if (this.cataclysmPhase < 3 && turnsRemaining <= 3 && turnsRemaining > 0 && this.peacefulHalfMoves % 2 === 0) {
      // 残り3ターン以下の警告トースト (毎往復ターン表示)
      const toast = document.getElementById('status-toast');
      if (toast) {
        toast.textContent = `⚠️ 警告: 交戦なし！ 残り ${turnsRemaining} ターンで聖域が崩落し盤面が縮小します！`;
      }
    }

    this._updateCataclysmHUD();

    this.isBusy = false;

    if (this._kingSlain) {
      const victor = this._kingSlain === 'w' ? '黒曜竜の眷属 (Obsidian Brood)' : '白竜石の聖堂群 (Alabaster Brood)';
      this._showGameOverModal(`竜石の聖域にて覇王古竜が討滅されました！ ${victor} の完全勝利！`);
      return true;
    }

    if (this.chess.isGameOver()) {
      this._showGameOverModal();
      return true;
    }

    this._maybeTriggerAITurn();
    return true;
  }

  async _animateMoveAndCombat(attacker, defender, moveObj, capturedSquare) {
    const yOffset = attacker.yOffset || 0;
    const startPos = this.squareToWorld(moveObj.from);
    startPos.y += yOffset;
    const targetPos = this.squareToWorld(moveObj.to);
    targetPos.y += yOffset;
    const delta = new THREE.Vector3().subVectors(targetPos, startPos);
    const distance = delta.length();
    const dir = delta.clone().normalize();

    const moveYaw = Math.atan2(-dir.x, -dir.z);
    attacker.root.rotation.y = moveYaw;

    if (defender) {
      const defYOffset = defender.yOffset || 0;
      const defenderPos = this.squareToWorld(capturedSquare);
      defenderPos.y += defYOffset;
      const stopDist = Math.max(0.18, distance - 0.96);
      const strikePos = startPos.clone().addScaledVector(dir, stopDist);

      // 攻撃演出カメラ: 俯瞰・離れている時は視点維持、または設定に応じたクローズアップ
      let triggerActionCam = false;
      if (this.actionCamEnabled) {
        if (this.combatCamMode === 'closeup') {
          triggerActionCam = true;
        } else if (this.combatCamMode === 'free') {
          triggerActionCam = false;
        } else {
          // 'smart' (デフォルト): スクロールで離している・俯瞰している時はズームせず視点を維持！
          triggerActionCam = !this._isOverviewingCamera();
        }
      }

      if (triggerActionCam) {
        this.savedCameraState = {
          pos: this.camera.position.clone(),
          target: this.controls.target.clone()
        };
        const sidePerp = new THREE.Vector3(-dir.z, 0, dir.x);
        const camPos = defenderPos
          .clone()
          .addScaledVector(sidePerp, 3.6)
          .add(new THREE.Vector3(0, 2.75, 0))
          .addScaledVector(dir, -1.35);
        this._tweenCamera(camPos, defenderPos.clone().add(new THREE.Vector3(0, 0.92, 0)), 0.42);
      } else {
        this.savedCameraState = null;
      }

      this._playPieceAnimation(attacker, 'Move', true);
      this.sfx.playStoneSlide(0.52);
      await this._tweenPosition(attacker.root, startPos, strikePos, 0.52, attacker.type === 'n');

      const toDef = new THREE.Vector3().subVectors(defenderPos, strikePos).normalize();
      attacker.root.rotation.y = Math.atan2(-toDef.x, -toDef.z);
      defender.root.rotation.y = Math.atan2(toDef.x, toDef.z);

      this._playPieceAnimation(attacker, 'Attack', false);
      await this._wait(170);
      this.vfx.spawnDragonBreath(strikePos, defenderPos, attacker.color === 'w');
      await this._wait(250);

      this._playPieceAnimation(defender, 'Hit', false);
      this.sfx.playSwordStrikeAndShatter();

      const isTactics = this.combatRule === 'tactics';
      let finalDamage = defender.maxHp;

      if (isTactics) {
        // 攻撃側の攻撃力と、攻撃を受ける側の防御力で、攻撃力の上回った分だけHPが削られる設計
        const rawDiff = (attacker.atk || 0) - (defender.def || 0);
        finalDamage = Math.max(0, rawDiff);

        const currentHp = defender.hp !== undefined ? defender.hp : defender.maxHp;
        const newHp = Math.max(0, currentHp - finalDamage);
        defender.updateHp(newHp);

        this._spawnDamageNumber(defenderPos, finalDamage);
        if (this.selectedSquare === capturedSquare) {
          this._updateInspector(defender);
        }
      } else {
        defender.updateHp(0);
        this._spawnDamageNumber(defenderPos, defender.maxHp);
      }

      // 相手からの猛反撃ブレス (Counter-Attack)
      let counterInfo = null;
      let attackerDestroyed = false;

      if (isTactics) {
        const counterRaw = (defender.atk || 0) - (attacker.def || 0);
        const counterDmg = Math.max(0, counterRaw);

        defender.root.rotation.y = Math.atan2(toDef.x, toDef.z);
        this._playPieceAnimation(defender, 'Attack', false);
        await this._wait(170);
        this.vfx.spawnDragonBreath(defenderPos, strikePos, defender.color === 'w');
        await this._wait(220);

        this._playPieceAnimation(attacker, 'Hit', false);
        this.sfx.playSwordStrikeAndShatter();

        const curAtkHp = attacker.hp !== undefined ? attacker.hp : attacker.maxHp;
        const newAtkHp = Math.max(0, curAtkHp - counterDmg);
        attacker.updateHp(newAtkHp);
        this._spawnDamageNumber(strikePos, counterDmg);

        attackerDestroyed = newAtkHp <= 0;
        counterInfo = {
          damage: counterDmg,
          defenderAtk: defender.atk,
          attackerDef: attacker.def,
          attackerDestroyed,
          attackerRemainHp: attacker.hp,
          attackerMaxHp: attacker.maxHp
        };

        await this._wait(200);
      }

      // 防御側は粉砕消滅し、そのマスを明け渡す（チェス本来の討滅）
      this.vfx.spawnShatterExplosion(
        defenderPos,
        this._getPieceMaterial(defender.type, defender.color),
        defender.color === 'w'
      );
      await this._wait(260);
      this._removePieceInstance(capturedSquare);

      if (defender.type === 'k') {
        this._kingSlain = defender.color;
      }

      // チェスのように自分のターンに1コマ動かす: 攻撃・防御コマが自動で下がるロジックは一切なし
      if (attackerDestroyed) {
        // 反撃で相打ち粉砕された場合
        this.vfx.spawnShatterExplosion(
          strikePos,
          this._getPieceMaterial(attacker.type, attacker.color),
          attacker.color === 'w'
        );
        await this._wait(260);
        this._removePieceInstance(moveObj.from);

        const toCoords = this.chess._squareToCoords(moveObj.to);
        this.chess._board[toCoords.r][toCoords.c] = null;

        if (attacker.type === 'k') {
          this._kingSlain = attacker.color;
        }
      } else {
        // 攻撃側は必ず目標マス（相手のマス）へ進軍し、そこに留まる（下がることは絶対にない）
        this._playPieceAnimation(attacker, 'Move', true);
        await this._tweenPosition(attacker.root, strikePos, targetPos, 0.28, false);
        attacker.root.rotation.y = attacker.defaultYaw;
        this._playPieceAnimation(attacker, 'Idle', true);

        this.pieceInstances.delete(moveObj.from);
        attacker.square = moveObj.to;
        attacker.root.traverse((c) => {
          if (c.isMesh) c.userData.square = moveObj.to;
        });
        this.pieceInstances.set(moveObj.to, attacker);
      }

      if (this.savedCameraState) {
        await this._wait(250);
        this._tweenCamera(this.savedCameraState.pos, this.savedCameraState.target, 0.55);
        this.savedCameraState = null;
      }

      return {
        isCombat: true,
        destroyed: true,
        damage: finalDamage,
        attackerAtk: attacker.atk,
        defenderDef: defender.def,
        victim: defender.type,
        remainHp: 0,
        maxHp: defender.maxHp,
        counter: counterInfo
      };
    } else {
      const dur = Math.min(0.75, Math.max(0.38, distance * 0.14));
      this._playPieceAnimation(attacker, 'Move', true);
      this.sfx.playStoneSlide(dur);
      await this._tweenPosition(attacker.root, startPos, targetPos, dur, attacker.type === 'n');
      attacker.root.rotation.y = attacker.defaultYaw;
      this._playPieceAnimation(attacker, 'Idle', true);

      this.pieceInstances.delete(moveObj.from);
      attacker.square = moveObj.to;
      attacker.root.traverse((c) => {
        if (c.isMesh) c.userData.square = moveObj.to;
      });
      this.pieceInstances.set(moveObj.to, attacker);

      return { isCombat: false, destroyed: false };
    }
  }

  async _handleCheckBossRaid(moveObj) {
    const enemyColor = this.chess.turn(); // 王手をかけられた側 (相手)
    const attackerColor = enemyColor === 'w' ? 'b' : 'w';

    // 相手キングを検索
    let victimKing = null;
    let victimKingSquare = null;
    for (const [sq, inst] of this.pieceInstances.entries()) {
      if (inst.type === 'k' && inst.color === enemyColor) {
        victimKing = inst;
        victimKingSquare = sq;
        break;
      }
    }
    if (!victimKing) return null;

    // 王手をかけた駒（直前に移動した駒）
    const attackerInst = this.pieceInstances.get(moveObj.to);
    if (!attackerInst) return null;

    const atkPos = this.squareToWorld(moveObj.to);
    const kingPos = this.squareToWorld(victimKingSquare);
    const toKing = new THREE.Vector3().subVectors(kingPos, atkPos).normalize();

    // 攻撃カメラ演出（スマートカメラ判定）
    let triggerActionCam = false;
    if (this.actionCamEnabled) {
      if (this.combatCamMode === 'closeup') {
        triggerActionCam = true;
      } else if (this.combatCamMode === 'free') {
        triggerActionCam = false;
      } else {
        triggerActionCam = !this._isOverviewingCamera();
      }
    }

    let savedCam = null;
    if (triggerActionCam) {
      savedCam = {
        pos: this.camera.position.clone(),
        target: this.controls.target.clone()
      };
      const midPos = new THREE.Vector3().addVectors(atkPos, kingPos).multiplyScalar(0.5);
      const camPos = midPos.clone().add(new THREE.Vector3(0, 3.4, 4.8));
      this._tweenCamera(camPos, midPos, 0.42);
    }

    const actorFaction = attackerColor === 'w' ? '白竜石の聖堂群' : '黒曜竜の眷属';
    const kingFaction = enemyColor === 'w' ? '白竜石の聖堂群' : '黒曜竜の眷属';
    const pieceTitle = PIECE_INFO[attackerInst.type]?.shortName || '石造竜';

    const toast = document.getElementById('status-toast');
    if (toast) {
      toast.textContent = `👑 王手竜炎ブレス！ ${actorFaction}の${pieceTitle}が覇王古竜に急襲ブレス！`;
    }

    // 攻撃側の向きをキングへ
    attackerInst.root.rotation.y = Math.atan2(-toKing.x, -toKing.z);
    this._playPieceAnimation(attackerInst, 'Attack', false);
    await this._wait(180);

    // ブレス発射！
    this.vfx.spawnDragonBreath(atkPos, kingPos, attackerColor === 'w');
    await this._wait(260);

    // キングが被弾
    this._playPieceAnimation(victimKing, 'Hit', false);
    this.sfx.playSwordStrikeAndShatter();

    // ダメージ計算: 攻撃力 - キング防御力40 (最低保証5)
    const rawDiff = (attackerInst.atk || 25) - (victimKing.def || 40);
    const damageToKing = Math.max(5, rawDiff);

    const curKingHp = victimKing.hp !== undefined ? victimKing.hp : victimKing.maxHp;
    const newKingHp = Math.max(0, curKingHp - damageToKing);
    victimKing.updateHp(newKingHp);
    this._spawnDamageNumber(kingPos, damageToKing);

    if (this.selectedSquare === victimKingSquare) {
      this._updateInspector(victimKing);
    }

    await this._wait(240);

    let counterDmg = null;
    let attackerDestroyed = false;

    // キングのHPが 0 に到達した場合
    if (newKingHp <= 0) {
      this.vfx.spawnShatterExplosion(
        kingPos,
        this._getPieceMaterial('k', victimKing.color),
        victimKing.color === 'w'
      );
      this._removePieceInstance(victimKingSquare);
      const kCoords = this.chess._squareToCoords(victimKingSquare);
      if (kCoords && this.chess._board[kCoords.r]) {
        this.chess._board[kCoords.r][kCoords.c] = null;
      }
      this._kingSlain = victimKing.color;

      if (toast) {
        toast.textContent = `💥 覇王古竜討滅！ 聖域の支配者 ${kingFaction} のキングが崩御しました！`;
      }
    } else {
      // キング生存時: 覇王古竜からの猛反撃ブレス！
      const toAtk = new THREE.Vector3().subVectors(atkPos, kingPos).normalize();
      victimKing.root.rotation.y = Math.atan2(-toAtk.x, -toAtk.z);
      this._playPieceAnimation(victimKing, 'Attack', false);
      await this._wait(180);

      this.vfx.spawnDragonBreath(kingPos, atkPos, victimKing.color === 'w');
      await this._wait(240);

      this._playPieceAnimation(attackerInst, 'Hit', false);
      this.sfx.playSwordStrikeAndShatter();

      const counterRaw = (victimKing.atk || 50) - (attackerInst.def || 10);
      counterDmg = Math.max(5, counterRaw);

      const curAtkHp = attackerInst.hp !== undefined ? attackerInst.hp : attackerInst.maxHp;
      const newAtkHp = Math.max(0, curAtkHp - counterDmg);
      attackerInst.updateHp(newAtkHp);
      this._spawnDamageNumber(atkPos, counterDmg);

      if (this.selectedSquare === moveObj.to) {
        this._updateInspector(attackerInst);
      }

      await this._wait(220);

      if (newAtkHp <= 0) {
        // 攻撃側が返り討ち粉砕
        attackerDestroyed = true;
        this.vfx.spawnShatterExplosion(
          atkPos,
          this._getPieceMaterial(attackerInst.type, attackerInst.color),
          attackerInst.color === 'w'
        );
        this._removePieceInstance(moveObj.to);
        const aCoords = this.chess._squareToCoords(moveObj.to);
        if (aCoords && this.chess._board[aCoords.r]) {
          this.chess._board[aCoords.r][aCoords.c] = null;
        }
        if (attackerInst.type === 'k') {
          this._kingSlain = attackerInst.color;
        }
        if (toast) {
          toast.textContent = `💥 覇王古竜の猛反撃！ 王手をかけた${pieceTitle}が返り討ち粉砕されました！`;
        }
        await this._wait(250);
      } else {
        this._playPieceAnimation(attackerInst, 'Idle', true);
        attackerInst.root.rotation.y = attackerInst.defaultYaw;
      }

      this._playPieceAnimation(victimKing, 'Idle', true);
      victimKing.root.rotation.y = victimKing.defaultYaw;
    }

    // カメラ復帰
    if (savedCam) {
      await this._wait(200);
      this._tweenCamera(savedCam.pos, savedCam.target, 0.48);
    }

    // 戦闘ログに王手レイドボス戦の経緯を記録
    this._logBossRaid(moveObj, attackerInst, victimKing, damageToKing, counterDmg, attackerDestroyed);

    return {
      isCombat: true,
      damageToKing,
      counterDmg,
      attackerDestroyed,
      kingDestroyed: newKingHp <= 0
    };
  }

  _logBossRaid(moveObj, attackerInst, victimKing, damageToKing, counterDmg, attackerDestroyed) {
    const feed = document.getElementById('combat-feed');
    if (!feed) return;

    const actorFaction = attackerInst.color === 'w' ? '白竜石' : '黒曜竜';
    const kingFaction = victimKing.color === 'w' ? '白竜石' : '黒曜竜';
    const pieceTitle = PIECE_INFO[attackerInst.type]?.shortName || '石造竜';

    let msg = `👑 王手竜炎！ ${actorFaction}の${pieceTitle}(攻${attackerInst.atk})が覇王古竜(防${victimKing.def})に ${damageToKing} ダメージ！ (キング残HP: ${victimKing.hp}/${victimKing.maxHp})`;
    if (victimKing.hp <= 0) {
      msg += ` 🏆 覇王古竜を完全討滅！`;
    } else if (counterDmg !== null) {
      if (attackerDestroyed) {
        msg += ` 💥 覇王猛反撃！ 古竜(攻${victimKing.atk})が ${pieceTitle}(防${attackerInst.def})に ${counterDmg} 反撃ダメ — 返り討ち粉砕！`;
      } else {
        msg += ` 💥 覇王反撃！ 古竜(攻${victimKing.atk})が ${pieceTitle}(防${attackerInst.def})に ${counterDmg} 反撃ダメ！ (残HP: ${attackerInst.hp}/${attackerInst.maxHp})`;
      }
    }

    const div = document.createElement('div');
    div.className = 'combat-entry check-raid';
    div.style.color = '#ffb300';
    div.style.fontWeight = 'bold';
    div.style.borderLeft = '2px solid #ffb300';
    div.style.paddingLeft = '4px';
    div.textContent = msg;
    feed.prepend(div);
  }

  _tweenPosition(obj, fromPos, toPos, durationSec, isJump = false) {
    return new Promise((resolve) => {
      const start = performance.now();
      const step = (now) => {
        const rawT = Math.min(1, (now - start) / (durationSec * 1000));
        const t = rawT < 0.5 ? 4 * rawT * rawT * rawT : 1 - Math.pow(-2 * rawT + 2, 3) / 2;
        obj.position.lerpVectors(fromPos, toPos, t);
        if (isJump) {
          obj.position.y = toPos.y + Math.sin(rawT * Math.PI) * 1.22;
        }
        if (rawT < 1) {
          requestAnimationFrame(step);
        } else {
          obj.position.copy(toPos);
          resolve();
        }
      };
      requestAnimationFrame(step);
    });
  }

  _tweenCamera(targetPos, targetLookAt, durationSec = 0.65) {
    this.camTransition = {
      fromPos: this.camera.position.clone(),
      toPos: targetPos.clone(),
      fromTarget: this.controls.target.clone(),
      toTarget: targetLookAt.clone(),
      elapsed: 0,
      duration: durationSec
    };
  }

  _wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  _maybeTriggerAITurn() {
    if (this.chess.isGameOver() || this.isBusy) return;
    const turn = this.chess.turn();
    const shouldAIMove =
      this.gameMode === 'ava' || (this.gameMode === 'pva' && turn === 'b');

    if (shouldAIMove) {
      setTimeout(() => {
        if (this.isBusy || this.chess.isGameOver()) return;
        const isForbidden = (m) => this._isRepetitionForbidden(m) || this.collapsedSquares.has(m.to);
        const aiMove = chooseBestMove(this.chess, this.aiDepth, isForbidden);
        if (aiMove) {
          this.executeMove(aiMove);
        }
      }, 360);
    }
  }

  _logCombatMove(moveObj, outcome = null) {
    const feed = document.getElementById('combat-feed');
    if (!feed) return;

    const actorFaction = moveObj.color === 'w' ? '白竜石' : '黒曜竜';
    const pieceTitle = PIECE_INFO[moveObj.piece]?.shortName || '石造竜';
    let msg = '';

    if (outcome && outcome.isCombat) {
      const victimTitle = PIECE_INFO[outcome.victim]?.shortName || '石造竜';
      const atk = outcome.attackerAtk ?? '—';
      const def = outcome.defenderDef ?? '—';
      if (outcome.damage <= 0) {
        msg = `🛡️ ${actorFaction}の${pieceTitle}(攻${atk})は ${moveObj.to.toUpperCase()} の${victimTitle}(防${def})の竜鱗に阻まれた！ (ダメージ: 0)`;
      } else if (outcome.destroyed) {
        msg = `🔥 ${actorFaction}の${pieceTitle}(攻${atk})が ${moveObj.to.toUpperCase()} の${victimTitle}(防${def})に ${outcome.damage} ダメージ！ 粉砕撃破！`;
      } else {
        msg = `⚔️ ${actorFaction}の${pieceTitle}(攻${atk})が ${moveObj.to.toUpperCase()} の${victimTitle}(防${def})に ${outcome.damage} ダメージ！ (耐えた！ 残りHP: ${outcome.remainHp}/${outcome.maxHp})`;
      }

      if (outcome.counter) {
        const c = outcome.counter;
        if (c.attackerDestroyed) {
          msg += ` 💥反撃！ ${victimTitle}(攻${c.defenderAtk})が猛反撃し ${pieceTitle}(防${c.attackerDef})に ${c.damage} ダメージ — 攻撃側を返り討ち粉砕！`;
        } else if (c.damage > 0) {
          msg += ` 💥反撃！ ${victimTitle}(攻${c.defenderAtk})が反撃し ${pieceTitle}(防${c.attackerDef})に ${c.damage} ダメージ！ (残りHP: ${c.attackerRemainHp}/${c.attackerMaxHp})`;
        } else {
          msg += ` 🛡️反撃！ ${victimTitle}(攻${c.defenderAtk})の反撃は ${pieceTitle}(防${c.attackerDef})の装甲に阻まれた！ (ダメージ: 0)`;
        }
      }
    } else if (moveObj.captured) {
      const victimTitle = PIECE_INFO[moveObj.captured]?.shortName || '石造竜';
      msg = `🔥 ${actorFaction}の${pieceTitle}が ${moveObj.to.toUpperCase()} の${victimTitle}を竜炎と牙で粉砕！ (${moveObj.san})`;
    } else if (moveObj.san && moveObj.san.includes('+')) {
      msg = `⚡ ${actorFaction}の${pieceTitle}が ${moveObj.to.toUpperCase()} へ飛来 — 覇王古竜に王手咆哮！`;
    } else {
      msg = `⚔️ ${actorFaction}の${pieceTitle}がルーン聖痕 ${moveObj.to.toUpperCase()} へ進撃 (${moveObj.san || ''})`;
    }

    const div = document.createElement('div');
    div.className = 'combat-entry';
    div.textContent = msg;
    feed.prepend(div);
  }

  updateHUD() {
    const turn = this.chess.turn();
    const inCheck = this.chess.inCheck();
    this.vfx.setTurnRuneColor(turn, inCheck);

    const badge = document.getElementById('turn-badge');
    const turnText = document.getElementById('turn-text');
    if (badge && turnText) {
      badge.className = `turn-faction-badge ${turn === 'w' ? 'white-turn' : 'black-turn'} ${inCheck ? 'in-check' : ''}`;
      if (inCheck) {
        turnText.textContent = `${turn === 'w' ? '白亜の覇王古竜' : '黒曜の覇王古竜'}が危機 — 聖域を防衛せよ！`;
      } else {
        turnText.textContent =
          turn === 'w'
            ? '白竜石の咆哮 — ALABASTER WYRM BROOD'
            : '黒曜竜の咆哮 — OBSIDIAN DRAKE BROOD';
      }
    }

    document.getElementById('card-white')?.classList.toggle('active-turn', turn === 'w');
    document.getElementById('card-black')?.classList.toggle('active-turn', turn === 'b');

    const evalRaw = evaluateBoard(this.chess) / 100;
    const clamped = Math.max(-10, Math.min(10, evalRaw));
    const pct = 50 + (clamped / 10) * 45;
    const evalBar = document.getElementById('eval-bar-white');
    const evalScore = document.getElementById('eval-score');
    if (evalBar) evalBar.style.width = `${pct}%`;
    if (evalScore) evalScore.textContent = `${evalRaw >= 0 ? '+' : ''}${evalRaw.toFixed(1)}`;

    const history = this.chess.history({ verbose: true });
    const capturedByW = [];
    const capturedByB = [];
    let matW = 0;
    let matB = 0;

    for (const m of history) {
      if (m.captured) {
        if (m.color === 'w') {
          capturedByW.push(PIECE_INFO[m.captured].symbolB);
          matW += PIECE_INFO[m.captured].value;
        } else {
          capturedByB.push(PIECE_INFO[m.captured].symbolW);
          matB += PIECE_INFO[m.captured].value;
        }
      }
    }

    const trayW = document.getElementById('captured-by-white');
    const trayB = document.getElementById('captured-by-black');
    if (trayW) trayW.textContent = capturedByW.join(' ');
    if (trayB) trayB.textContent = capturedByB.join(' ');

    const advW = document.getElementById('white-advantage');
    const advB = document.getElementById('black-advantage');
    if (advW) advW.textContent = matW > matB ? `+${matW - matB}` : '';
    if (advB) advB.textContent = matB > matW ? `+${matB - matW}` : '';

    const moveListEl = document.getElementById('move-list');
    const moveCountPill = document.getElementById('move-count-pill');
    if (moveListEl) {
      moveListEl.innerHTML = '';
      for (let i = 0; i < history.length; i += 2) {
        const wMove = history[i];
        const bMove = history[i + 1];
        const row = document.createElement('div');
        row.className = 'move-row';
        row.innerHTML = `
          <span class="move-num">${Math.floor(i / 2) + 1}.</span>
          <span class="move-san ${wMove?.captured ? 'capture' : ''}">${wMove ? wMove.san : ''}</span>
          <span class="move-san ${bMove?.captured ? 'capture' : ''}">${bMove ? bMove.san : ''}</span>
        `;
        moveListEl.appendChild(row);
      }
      moveListEl.scrollTop = moveListEl.scrollHeight;
    }
    if (moveCountPill) {
      moveCountPill.textContent = `第${Math.floor(history.length / 2) + 1}刻`;
    }

    const quickSpellsEl = document.getElementById('quick-spells');
    if (quickSpellsEl) {
      quickSpellsEl.innerHTML = '';
      const legalMoves = this.chess.moves({ verbose: true });
      legalMoves.sort((a, b) => (b.captured ? 1 : 0) - (a.captured ? 1 : 0));
      for (const m of legalMoves.slice(0, 6)) {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'quick-spell-chip';
        chip.textContent = m.captured ? `⚔️ ${m.san}` : m.san;
        chip.addEventListener('click', () => {
          if (window.innerWidth <= 960) this._closeMobileDrawers?.();
          this.executeMove(m);
        });
        quickSpellsEl.appendChild(chip);
      }
    }

    this._updateCataclysmHUD();
  }

  parseAndCastCommand(rawText) {
    const text = rawText.trim();
    if (!text) return false;

    const legal = this.chess.moves({ verbose: true });
    const direct = legal.find(
      (m) =>
        m.san.toLowerCase() === text.toLowerCase() ||
        `${m.from}${m.to}`.toLowerCase() === text.toLowerCase().replace(/\s|-|to|へ|に/g, '')
    );
    if (direct) {
      return this.executeMove(direct);
    }

    const lower = text.toLowerCase();
    const pieceAliases = {
      pawn: 'p', drake: 'p', 'ドレイク': 'p', '幼竜': 'p', 'ポーン': 'p', '歩兵': 'p',
      knight: 'n', wyvern: 'n', 'ワイバーン': 'n', '飛竜': 'n', 'ナイト': 'n', '騎士': 'n',
      bishop: 'b', hydra: 'b', '双頭竜': 'b', 'ヒドラ': 'b', '秘術竜': 'b', 'ビショップ': 'b', '司教': 'b',
      rook: 'r', behemoth: 'r', '地竜': 'r', '鎧竜': 'r', 'ルーク': 'r', '城兵': 'r',
      queen: 'q', empress: 'q', '女帝竜': 'q', '四翼竜': 'q', 'クイーン': 'q', '女王': 'q',
      king: 'k', sovereign: 'k', '覇王竜': 'k', '古竜': 'k', '覇王': 'k', 'キング': 'k', '王': 'k'
    };
    const sqMatch = lower.match(/\b([a-g][1-7])\b/) || lower.match(/([a-g][1-7])/);
    if (sqMatch) {
      const targetSq = sqMatch[1];
      let desiredPiece = null;
      for (const [word, code] of Object.entries(pieceAliases)) {
        if (lower.includes(word)) {
          desiredPiece = code;
          break;
        }
      }
      const match = legal.find(
        (m) => m.to === targetSq && (!desiredPiece || m.piece === desiredPiece)
      );
      if (match) {
        return this.executeMove(match);
      }
    }
    return false;
  }

  async triggerBattleDemo() {
    if (this.isBusy) return;
    const currentCaptures = this.chess.moves({ verbose: true }).filter((m) => m.captured);
    if (currentCaptures.length > 0) {
      await this.executeMove(currentCaptures[0]);
      return;
    }

    this.chess.reset();
    this.chess.move('c4');
    this.chess.move('d5');
    this._resetInspector();
    this.syncBoardFromFEN();
    this.updateHUD();
    await this._wait(180);
    await this.executeMove('cxd5');
  }

  _showGameOverModal(customMessage = null) {
    const modal = document.getElementById('gameover-modal');
    const title = document.getElementById('gameover-title');
    const sub = document.getElementById('gameover-subtitle');
    if (!modal || !title || !sub) return;

    if (customMessage) {
      title.textContent = 'SANCTUM CONQUERED — 覇王古竜討滅';
      sub.textContent = customMessage;
    } else if (this.chess.isCheckmate()) {
      const winner = this.chess.turn() === 'w' ? '黒曜竜の眷属 (Obsidian Brood)' : '白竜石の聖堂群 (Alabaster Brood)';
      title.textContent = 'SANCTUM CONQUERED — 覇王古竜陥落';
      sub.textContent = `竜石の聖域にて ${winner} が勝利の咆哮を上げました！`;
    } else if (this.chess.isStalemate()) {
      const winner = this.chess.turn() === 'w' ? '黒曜竜の眷属 (Obsidian Brood)' : '白竜石の聖堂群 (Alabaster Brood)';
      const loser = this.chess.turn() === 'w' ? '白竜石の聖堂群 (Alabaster Brood)' : '黒曜竜の眷属 (Obsidian Brood)';
      title.textContent = 'SANCTUM SURROUNDED — 聖域包囲殲滅';
      sub.textContent = `四方を完全に包囲され、逃げ場と魔力を絶たれた ${loser} が屈服しました！ ${winner} の完全勝利！`;
    } else {
      title.textContent = 'ARCANE STALEMATE — 竜魔力の均衡';
      sub.textContent = '双竜群の魔力が拮抗し、聖域は静寂に包まれました。';
    }
    modal.classList.remove('hidden');
  }

  _adjustCameraForViewport() {
    if (!this.camera) return;
    const aspect = window.innerWidth / window.innerHeight;
    if (aspect < 1.0) {
      // モバイル縦画面など幅が狭い時は、盤面の左右端が切れないよう垂直FOVを自動拡張
      const baseTanHalfFov = Math.tan(THREE.MathUtils.degToRad(44 / 2));
      const desiredHorizontalFactor = baseTanHalfFov * 1.05;
      const dynamicTan = desiredHorizontalFactor / Math.max(0.42, aspect);
      const dynamicFov = Math.min(83, Math.max(44, THREE.MathUtils.radToDeg(2 * Math.atan(dynamicTan))));
      this.camera.fov = dynamicFov;
    } else {
      this.camera.fov = 44;
    }
    this.camera.aspect = aspect;
    this.camera.updateProjectionMatrix();
  }

  _bindUIEvents() {
    const isMobileView = () => window.innerWidth <= 960;
    const leftPanel = document.getElementById('left-panel');
    const rightPanel = document.getElementById('right-panel');
    const supportMenu = document.getElementById('mobile-support-menu');
    const drawerBackdrop = document.getElementById('mobile-drawer-backdrop');
    const mobileLeftBtn = document.getElementById('btn-mobile-left');
    const mobileSupportBtn = document.getElementById('btn-mobile-support');
    const mobileRightBtn = document.getElementById('btn-mobile-right');

    const closeMobileDrawers = () => {
      leftPanel?.classList.remove('mobile-open');
      rightPanel?.classList.remove('mobile-open');
      supportMenu?.classList.add('hidden');
      drawerBackdrop?.classList.add('hidden');
      mobileLeftBtn?.classList.remove('active');
      mobileSupportBtn?.classList.remove('active');
      mobileRightBtn?.classList.remove('active');
    };
    this._closeMobileDrawers = closeMobileDrawers;

    const toggleMobileDrawer = (side) => {
      const targetPanel = side === 'left' ? leftPanel : rightPanel;
      const otherPanel = side === 'left' ? rightPanel : leftPanel;
      const targetBtn = side === 'left' ? mobileLeftBtn : mobileRightBtn;
      const otherBtn = side === 'left' ? mobileRightBtn : mobileLeftBtn;
      if (!targetPanel) return;

      const willOpen = !targetPanel.classList.contains('mobile-open');
      otherPanel?.classList.remove('mobile-open');
      otherBtn?.classList.remove('active');
      supportMenu?.classList.add('hidden');
      mobileSupportBtn?.classList.remove('active');

      if (willOpen) {
        targetPanel.classList.add('mobile-open');
        targetBtn?.classList.add('active');
        drawerBackdrop?.classList.remove('hidden');
      } else {
        targetPanel.classList.remove('mobile-open');
        targetBtn?.classList.remove('active');
        drawerBackdrop?.classList.add('hidden');
      }
    };

    const toggleMobileSupport = () => {
      if (!supportMenu) return;
      const willOpen = supportMenu.classList.contains('hidden');
      leftPanel?.classList.remove('mobile-open');
      rightPanel?.classList.remove('mobile-open');
      mobileLeftBtn?.classList.remove('active');
      mobileRightBtn?.classList.remove('active');

      if (willOpen) {
        supportMenu.classList.remove('hidden');
        mobileSupportBtn?.classList.add('active');
        drawerBackdrop?.classList.remove('hidden');
      } else {
        supportMenu.classList.add('hidden');
        mobileSupportBtn?.classList.remove('active');
        drawerBackdrop?.classList.add('hidden');
      }
    };

    mobileLeftBtn?.addEventListener('click', () => toggleMobileDrawer('left'));
    mobileSupportBtn?.addEventListener('click', toggleMobileSupport);
    mobileRightBtn?.addEventListener('click', () => toggleMobileDrawer('right'));
    drawerBackdrop?.addEventListener('click', closeMobileDrawers);
    document.getElementById('btn-mobile-support-close')?.addEventListener('click', closeMobileDrawers);
    document.querySelectorAll('[data-close-drawer]').forEach((btn) => {
      btn.addEventListener('click', closeMobileDrawers);
    });

    document.getElementById('btn-mobile-undo')?.addEventListener('click', () => {
      closeMobileDrawers();
      document.getElementById('btn-undo')?.click();
    });
    document.getElementById('btn-mobile-hint')?.addEventListener('click', () => {
      closeMobileDrawers();
      document.getElementById('btn-hint')?.click();
    });

    window.addEventListener('resize', () => {
      this._adjustCameraForViewport();
      if (!isMobileView()) closeMobileDrawers();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
      this.composer?.setSize(window.innerWidth, window.innerHeight);
    });

    const dom = this.renderer.domElement;
    dom.addEventListener('pointerdown', (e) => {
      this.pointerDownPos.set(e.clientX, e.clientY);
    });

    dom.addEventListener('pointerup', (e) => {
      if (e.button !== 0) return;
      const dist = Math.hypot(e.clientX - this.pointerDownPos.x, e.clientY - this.pointerDownPos.y);
      const maxDragDist = e.pointerType === 'touch' ? 14 : 6;
      if (dist > maxDragDist) return;

      const rect = dom.getBoundingClientRect();
      this.pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      this.raycaster.setFromCamera(this.pointer, this.camera);
      const targets = [
        ...Array.from(this.boardSquares.values()),
        ...Array.from(this.pieceInstances.values()).map((p) => p.root)
      ];
      const hits = this.raycaster.intersectObjects(targets, true);
      if (hits.length > 0) {
        let obj = hits[0].object;
        while (obj && !obj.userData?.square) {
          obj = obj.parent;
        }
        if (obj?.userData?.square) {
          this.selectSquare(obj.userData.square);
        }
      }
    });

    const camPresets = {
      white: { pos: new THREE.Vector3(0, 8.2, 11.6), target: new THREE.Vector3(0, 0.65, 0) },
      black: { pos: new THREE.Vector3(0, 8.2, -11.6), target: new THREE.Vector3(0, 0.65, 0) },
      overhead: { pos: new THREE.Vector3(0, 15.2, 0.01), target: new THREE.Vector3(0, 0, 0) },
      cathedral: { pos: new THREE.Vector3(7.2, 3.5, 14.8), target: new THREE.Vector3(0, 4.4, -9.0) }
    };

    document.querySelectorAll('.cam-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.cam-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const camKey = btn.dataset.cam;
        if (camKey === 'closeup') {
          this.focusSelectedStatueMacro();
        } else if (camPresets[camKey]) {
          this._tweenCamera(camPresets[camKey].pos, camPresets[camKey].target, 0.75);
        }
        if (isMobileView()) closeMobileDrawers();
      });
    });

    document.getElementById('chk-action-cam')?.addEventListener('change', (e) => {
      this.setCombatCamMode(e.target.checked ? 'smart' : 'free');
    });

    document.getElementById('combat-cam-select')?.addEventListener('change', (e) => {
      this.setCombatCamMode(e.target.value);
    });

    document.getElementById('btn-cam-smart')?.addEventListener('click', () => {
      this.setCombatCamMode('smart');
    });

    document.getElementById('btn-cam-closeup-mode')?.addEventListener('click', () => {
      this.setCombatCamMode('closeup');
    });

    document.getElementById('btn-cam-free')?.addEventListener('click', () => {
      this.setCombatCamMode('free');
    });

    document.getElementById('combat-rule-select')?.addEventListener('change', (e) => {
      this.setCombatRule(e.target.value);
    });

    document.getElementById('battle-mode-select')?.addEventListener('change', (e) => {
      this.setCombatRule(e.target.value);
    });

    document.getElementById('btn-mode-tactics')?.addEventListener('click', () => {
      this.setCombatRule('tactics');
    });

    document.getElementById('btn-mode-classic')?.addEventListener('click', () => {
      this.setCombatRule('classic');
    });

    const applyGameMode = (modeVal) => {
      this.gameMode = modeVal;
      const topSel = document.getElementById('game-mode-select');
      const mobSel = document.getElementById('mobile-game-mode-select');
      if (topSel && topSel.value !== modeVal) topSel.value = modeVal;
      if (mobSel && mobSel.value !== modeVal) mobSel.value = modeVal;

      const wRole = document.getElementById('white-role-label');
      const bRole = document.getElementById('black-role-label');
      if (this.gameMode === 'pva') {
        if (wRole) wRole.textContent = 'Alabaster Brood • 契約者';
        if (bRole) bRole.textContent = 'Obsidian Brood • AI導師';
      } else if (this.gameMode === 'pvp') {
        if (wRole) wRole.textContent = 'Alabaster Brood • 契約者1';
        if (bRole) bRole.textContent = 'Obsidian Brood • 契約者2';
      } else {
        if (wRole) wRole.textContent = 'Alabaster Brood • AI';
        if (bRole) bRole.textContent = 'Obsidian Brood • AI';
      }
      this._maybeTriggerAITurn();
    };

    document.getElementById('game-mode-select')?.addEventListener('change', (e) => {
      applyGameMode(e.target.value);
    });
    document.getElementById('mobile-game-mode-select')?.addEventListener('change', (e) => {
      applyGameMode(e.target.value);
    });

    const applyAiDepth = (val) => {
      const depth = parseInt(val, 10) || 2;
      this.aiDepth = depth;
      const topSel = document.getElementById('ai-depth-select');
      const mobSel = document.getElementById('mobile-ai-depth-select');
      if (topSel && topSel.value !== String(depth)) topSel.value = String(depth);
      if (mobSel && mobSel.value !== String(depth)) mobSel.value = String(depth);
    };

    document.getElementById('ai-depth-select')?.addEventListener('change', (e) => {
      applyAiDepth(e.target.value);
    });
    document.getElementById('mobile-ai-depth-select')?.addEventListener('change', (e) => {
      applyAiDepth(e.target.value);
    });

    document.getElementById('lighting-select')?.addEventListener('change', (e) => {
      this.setLightingPreset(e.target.value);
    });
    document.getElementById('mobile-lighting-select')?.addEventListener('change', (e) => {
      this.setLightingPreset(e.target.value);
    });

    document.getElementById('pedestal-mode-select')?.addEventListener('change', (e) => {
      this.setPedestalMode(e.target.value);
    });

    document.getElementById('btn-pedestal-with')?.addEventListener('click', () => {
      this.setPedestalMode('with-base');
    });

    document.getElementById('btn-pedestal-none')?.addEventListener('click', () => {
      this.setPedestalMode('no-base');
    });

    const bgmBtn = document.getElementById('btn-bgm-toggle');
    bgmBtn?.addEventListener('click', () => {
      const on = this.sfx.toggleBGM();
      bgmBtn.classList.toggle('active', on);
      bgmBtn.innerHTML = on
        ? '🎵 <span class="btn-label">BGM ON</span>'
        : '🔇 <span class="btn-label">BGM OFF</span>';
    });

    const audioBtn = document.getElementById('btn-audio-toggle');
    audioBtn?.addEventListener('click', () => {
      const on = this.sfx.toggle();
      audioBtn.classList.toggle('active', on);
      audioBtn.innerHTML = on
        ? '🔊 <span class="btn-label">効果音 ON</span>'
        : '🔇 <span class="btn-label">効果音 OFF</span>';
    });

    // Auto-start ambient BGM on first user interaction (pointerdown / keydown)
    const unlockAudio = () => {
      this.sfx.init();
      if (!this.sfx.bgmStarted && this.sfx.bgmEnabled) {
        this.sfx.playBGM();
      }
      window.removeEventListener('pointerdown', unlockAudio);
      window.removeEventListener('keydown', unlockAudio);
    };
    window.addEventListener('pointerdown', unlockAudio, { passive: true });
    window.addEventListener('keydown', unlockAudio, { passive: true });

    const toggleHUD = () => {
      closeMobileDrawers();
      document.getElementById('ui-root')?.classList.toggle('hud-minimized');
    };
    document.getElementById('btn-toggle-ui')?.addEventListener('click', toggleHUD);
    window.addEventListener('keydown', (e) => {
      if (e.key.toLowerCase() === 'h' && document.activeElement?.tagName !== 'INPUT') {
        toggleHUD();
      }
    });

    document.getElementById('spell-form')?.addEventListener('submit', (e) => {
      e.preventDefault();
      const input = document.getElementById('spell-input');
      if (!input) return;
      const ok = this.parseAndCastCommand(input.value);
      const toast = document.getElementById('status-toast');
      if (ok) {
        input.value = '';
        if (toast) toast.textContent = '⚡ 竜語号令成功！石造ドラゴンが進撃します。';
        if (isMobileView()) closeMobileDrawers();
      } else if (toast) {
        toast.textContent = `⚠️ 「${input.value}」は現在の局面で無効な号令です (例: e4, Nf3, ワイバーン f3)`;
      }
    });

    document.getElementById('btn-battle-demo')?.addEventListener('click', () => {
      if (isMobileView()) closeMobileDrawers();
      this.triggerBattleDemo();
    });

    const resetMatch = () => {
      if (this.isBusy) return;
      if (isMobileView()) closeMobileDrawers();
      const scenKey = document.getElementById('scenario-select')?.value || 'endgame';
      const scenFen = SCENARIOS[scenKey];
      if (scenFen) {
        this.chess.load(scenFen);
      } else {
        this.chess.reset();
      }
      this.lastMove = null;
      this.hintMove = null;
      this.selectedSquare = null;
      this.legalMovesForSelected = [];
      this.clocks = { w: 600, b: 600 };
      this._kingSlain = null;
      this.moveActionLog = [];
      this.collapsedSquares.clear();
      this.cataclysmPhase = 0;
      this.peacefulHalfMoves = 0;
      this._updateCataclysmHUD();
      this.vfx.clearRubble();
      this.syncBoardFromFEN();
      this.updateHUD();
      this._resetInspector();
      document.getElementById('gameover-modal')?.classList.add('hidden');
      this._maybeTriggerAITurn();
    };

    document.getElementById('btn-new-game')?.addEventListener('click', resetMatch);
    document.getElementById('btn-modal-rematch')?.addEventListener('click', resetMatch);
    document.getElementById('btn-modal-inspect')?.addEventListener('click', () => {
      document.getElementById('gameover-modal')?.classList.add('hidden');
    });

    document.getElementById('btn-undo')?.addEventListener('click', () => {
      if (this.isBusy) return;
      if (isMobileView()) closeMobileDrawers();
      this.chess.undo();
      this.moveActionLog.pop();
      if (this.gameMode === 'pva' && this.chess.turn() === 'b') {
        this.chess.undo();
        this.moveActionLog.pop();
      }
      this.lastMove = null;
      this.selectedSquare = null;
      this.legalMovesForSelected = [];
      this.syncBoardFromFEN();
      this.updateHUD();
    });

    document.getElementById('btn-hint')?.addEventListener('click', () => {
      if (this.isBusy || this.chess.isGameOver()) return;
      if (isMobileView()) closeMobileDrawers();
      const isForbidden = (m) => this._isRepetitionForbidden(m) || this.collapsedSquares.has(m.to);
      const best = chooseBestMove(this.chess, 2, isForbidden);
      if (best) {
        this.hintMove = best;
        this._updateBoardHighlights();
        const toast = document.getElementById('status-toast');
        if (toast) {
          toast.textContent = `🔮 聖堂の神託: ${PIECE_INFO[best.piece].shortName}を ${best.from.toUpperCase()} から ${best.to.toUpperCase()} へ (${best.san})`;
        }
      }
    });

    document.getElementById('btn-clear-debris')?.addEventListener('click', () => {
      this.vfx.clearRubble();
    });

    document.querySelectorAll('.anim-test-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const animName = btn.dataset.anim || 'Idle';
        const sq = this.selectedSquare || 'g1';
        const inst = this.pieceInstances.get(sq) || Array.from(this.pieceInstances.values())[0];
        if (!inst) return;
        this._updateInspector(inst);
        this._playPieceAnimation(inst, animName, animName === 'Idle');
        if (animName === 'Attack') {
          this.sfx.playSwordStrikeAndShatter();
        } else if (animName === 'Move') {
          this.sfx.playStoneSlide(0.45);
        }
        if (animName !== 'Idle') {
          setTimeout(() => {
            if (!this.isBusy && inst.currentAnim === animName) {
              this._playPieceAnimation(inst, 'Idle', true);
            }
          }, 1600);
        }
      });
    });

    document.getElementById('scenario-select')?.addEventListener('change', (e) => {
      if (this.isBusy) return;
      if (isMobileView()) closeMobileDrawers();
      const key = e.target.value;
      const fen = SCENARIOS[key];
      if (fen) {
        this.chess.load(fen);
      } else {
        this.chess.reset();
      }
      this.lastMove = null;
      this.hintMove = null;
      this.selectedSquare = null;
      this.legalMovesForSelected = [];
      this._kingSlain = null;
      this.moveActionLog = [];
      this.collapsedSquares.clear();
      this.cataclysmPhase = 0;
      this.peacefulHalfMoves = 0;
      this._updateCataclysmHUD();
      this.vfx.clearRubble();
      this.syncBoardFromFEN();
      this.updateHUD();
      this._resetInspector();
      const toast = document.getElementById('status-toast');
      if (toast) {
        toast.textContent = `🏰 聖域決戦シナリオ召喚: ${e.target.options[e.target.selectedIndex].text}`;
      }
    });

    const voiceBtn = document.getElementById('btn-voice-cmd');
    voiceBtn?.addEventListener('click', () => {
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      const toast = document.getElementById('status-toast');
      if (!SpeechRec) {
        if (toast) toast.textContent = '🎙️ お使いのブラウザは音声認識非対応です。テキスト欄に竜語号令を入力してください。';
        return;
      }
      const rec = new SpeechRec();
      rec.lang = 'ja-JP';
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      voiceBtn.classList.add('listening');
      if (toast) toast.textContent = '🎙️ 竜語の号令を唱えてください (例: 「ワイバーン f3」「ドレイク e4」)...';

      rec.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const input = document.getElementById('spell-input');
        if (input) input.value = transcript;
        const ok = this.parseAndCastCommand(transcript);
        if (toast) {
          toast.textContent = ok
            ? `🎙️ 音声号令発動: 「${transcript}」!`
            : `🎙️ 「${transcript}」に対応する合法手が見つかりませんでした。`;
        }
      };
      rec.onerror = () => voiceBtn.classList.remove('listening');
      rec.onend = () => voiceBtn.classList.remove('listening');
      rec.start();
    });

    document.querySelectorAll('.promo-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const promoPiece = btn.dataset.piece || 'q';
        document.getElementById('promotion-modal')?.classList.add('hidden');
        if (this.pendingPromotionMove) {
          const move = { ...this.pendingPromotionMove, promotion: promoPiece };
          this.pendingPromotionMove = null;
          this.executeMove(move);
        }
      });
    });
  }

  _updateClocks(now) {
    const dt = (now - this.lastClockTick) / 1000;
    this.lastClockTick = now;
    if (this.chess.isGameOver()) return;

    const turn = this.chess.turn();
    this.clocks[turn] = Math.max(0, this.clocks[turn] - dt);

    const fmt = (sec) => {
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    };
    const wEl = document.getElementById('clock-white');
    const bEl = document.getElementById('clock-black');
    if (wEl) wEl.textContent = fmt(this.clocks.w);
    if (bEl) bEl.textContent = fmt(this.clocks.b);
  }

  _animate() {
    requestAnimationFrame(() => this._animate());

    const dt = Math.min(0.1, this.clock.getDelta());
    const elapsed = this.clock.elapsedTime;

    for (const mixer of this.activeMixers) {
      mixer.update(dt);
    }

    if (this.camTransition) {
      this.camTransition.elapsed += dt;
      const rawT = Math.min(1, this.camTransition.elapsed / this.camTransition.duration);
      const t = rawT < 0.5 ? 2 * rawT * rawT : 1 - Math.pow(-2 * rawT + 2, 2) / 2;
      this.camera.position.lerpVectors(this.camTransition.fromPos, this.camTransition.toPos, t);
      this.controls.target.lerpVectors(this.camTransition.fromTarget, this.camTransition.toTarget, t);
      if (rawT >= 1) {
        this.camTransition = null;
      }
    }

    this.controls.update();
    this.vfx.update(dt, elapsed);

    for (let i = this.damagePopups.length - 1; i >= 0; i--) {
      const p = this.damagePopups[i];
      p.elapsed += dt;
      const progress = p.elapsed / p.maxLife;
      p.sprite.position.y = p.startPos.y + progress * 0.95;
      p.sprite.material.opacity = Math.max(0, 1 - Math.pow(progress, 2));
      if (progress >= 1) {
        this.scene.remove(p.sprite);
        p.sprite.material.map?.dispose();
        p.sprite.material?.dispose();
        this.damagePopups.splice(i, 1);
      }
    }

    this._updateClocks(performance.now());

    if (this.composer) {
      this.composer.render();
    } else {
      this.renderer.render(this.scene, this.camera);
    }
  }
}

window.addEventListener('DOMContentLoaded', () => {
  new WizardsChessApp();
});
