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
    symbolW: '🐉',
    symbolB: '🐉',
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
    this.isBusy = false;
    this.selectedSquare = null;
    this.legalMovesForSelected = [];
    this.pendingPromotionMove = null;
    this.lastMove = null;
    this.hintMove = null;

    // Clocks (seconds)
    this.clocks = { w: 600, b: 600 };
    this.lastClockTick = performance.now();

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

    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: true
    });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.container.appendChild(this.renderer.domElement);

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
    this.chess.load(SCENARIOS.endgame);

    // VFX & Lighting
    this.vfx = new VFXManager(this.scene);
    this.lights = {};

    this.clock = new THREE.Clock();

    this._setupLighting();
    this.setLightingPreset('moonlit');
    this._bindUIEvents();
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
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
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
      [ 5.35, 1.52, -5.35],
      [-5.35, 1.52,  5.35],
      [ 5.35, 1.52,  5.35]
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

  async _initAssets() {
    const statusEl = document.getElementById('loading-status');
    const barEl = document.getElementById('loading-bar-fill');
    const updateProgress = (pct, msg) => {
      if (barEl) barEl.style.width = `${pct}%`;
      if (statusEl) statusEl.textContent = msg;
    };

    const texLoader = new THREE.TextureLoader();
    const gltfLoader = new GLTFLoader();
    const maxAniso = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());

    const loadTex = (url, { isColor = true, flipY = true } = {}) =>
      new Promise((resolve) => {
        const src = window.__EMBEDDED_ASSETS__?.textures?.[url] || url;
        texLoader.load(
          src,
          (tex) => {
            tex.flipY = flipY;
            tex.wrapS = THREE.RepeatWrapping;
            tex.wrapT = THREE.RepeatWrapping;
            if (isColor) tex.colorSpace = THREE.SRGBColorSpace;
            tex.anisotropy = maxAniso;
            tex.needsUpdate = true;
            resolve(tex);
          },
          undefined,
          () => resolve(null)
        );
      });

    const loadGLB = (url) =>
      new Promise((resolve, reject) => {
        const b64 = window.__EMBEDDED_ASSETS__?.models?.[url];
        if (b64) {
          const binStr = atob(b64);
          const len = binStr.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binStr.charCodeAt(i);
          }
          gltfLoader.parse(bytes.buffer, '', resolve, reject);
        } else {
          gltfLoader.load(url, resolve, undefined, reject);
        }
      });

    try {
      updateProgress(16, '2K (2048x2048) 竜鱗石彫PBRマップ (Albedo / Normal / Roughness / AO / Emission) を展開中...');
      const [
        wAlbedo, wNormal, wRough, wMetal, wAO, wEmissive,
        bAlbedo, bNormal, bRough, bMetal, bAO, bEmissive,
        tAlbedo, tNormal, tRough, tMetal, tAO
      ] = await Promise.all([
        loadTex('/assets/textures/white_piece_albedo.png',    { isColor: true,  flipY: false }),
        loadTex('/assets/textures/white_piece_normal.png',    { isColor: false, flipY: false }),
        loadTex('/assets/textures/white_piece_roughness.png', { isColor: false, flipY: false }),
        loadTex('/assets/textures/white_piece_metallic.png',  { isColor: false, flipY: false }),
        loadTex('/assets/textures/white_piece_ao.png',        { isColor: false, flipY: false }),
        loadTex('/assets/textures/white_piece_emission.png',  { isColor: true,  flipY: false }),
        loadTex('/assets/textures/black_piece_albedo.png',    { isColor: true,  flipY: false }),
        loadTex('/assets/textures/black_piece_normal.png',    { isColor: false, flipY: false }),
        loadTex('/assets/textures/black_piece_roughness.png', { isColor: false, flipY: false }),
        loadTex('/assets/textures/black_piece_metallic.png',  { isColor: false, flipY: false }),
        loadTex('/assets/textures/black_piece_ao.png',        { isColor: false, flipY: false }),
        loadTex('/assets/textures/black_piece_emission.png',  { isColor: true,  flipY: false }),
        loadTex('/assets/textures/board_tiles_albedo.png',    { isColor: true,  flipY: true }),
        loadTex('/assets/textures/board_tiles_normal.png',    { isColor: false, flipY: true }),
        loadTex('/assets/textures/board_tiles_roughness.png', { isColor: false, flipY: true }),
        loadTex('/assets/textures/board_tiles_metallic.png',  { isColor: false, flipY: true }),
        loadTex('/assets/textures/board_tiles_ao.png',        { isColor: false, flipY: true })
      ]);

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

      // Helper to add underbelly pale-white shading to King dragons (15% tighter mask)
      const applyKingBellyShader = (mat, bellyWhiteVec) => {
        mat.onBeforeCompile = (shader) => {
          shader.vertexShader = `
            varying vec3 vBellyPos;
            varying vec3 vBellyNorm;
            ${shader.vertexShader}
          `.replace(
            '#include <begin_vertex>',
            `
            #include <begin_vertex>
            vBellyPos = position;
            vBellyNorm = normal;
            `
          );

          shader.fragmentShader = `
            varying vec3 vBellyPos;
            varying vec3 vBellyNorm;
            ${shader.fragmentShader}
          `.replace(
            '#include <map_fragment>',
            `
            #include <map_fragment>
            // Dragon King underbelly & chest osteoderm plates mask (further slimmed around core central sternum/belly)
            float yFactor = smoothstep(0.33, 0.505, vBellyPos.y) * (1.0 - smoothstep(1.248, 1.495, vBellyPos.y));
            float xFactor = 1.0 - smoothstep(0.08, 0.180, abs(vBellyPos.x));
            float zFactor = 1.0 - smoothstep(-0.075, 0.075, vBellyPos.z);
            float normFactor = smoothstep(0.33, -0.14, vBellyNorm.z);
            float bellyMask = clamp(yFactor * xFactor * zFactor * normFactor, 0.0, 1.0);

            // Blend underside towards dignified pale-white stone base
            vec3 bellyWhite = ${bellyWhiteVec};
            diffuseColor.rgb = mix(diffuseColor.rgb, bellyWhite, bellyMask * 0.90);
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
      applyKingBellyShader(this.materials.kw, 'vec3(0.86, 0.86, 0.88)');

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
      applyKingBellyShader(this.materials.kb, 'vec3(0.72, 0.73, 0.76)');

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
        const cathedralGLTF = await loadGLB('/assets/models/gothic_cathedral.glb');
        cathedralGLTF.scene.rotation.y = Math.PI;
        cathedralGLTF.scene.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
            if (child.material) {
              const mName = child.material.name || '';
              if (!mName.includes('Glass') && !mName.includes('Ember')) {
                child.material.roughness = Math.max(child.material.roughness ?? 0.65, 0.68);
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

      updateProgress(82, '6種の純ドラゴン骨格・2K竜鱗石彫アセットを覚醒中...');
      const pieceMap = [
        ['p', '/assets/models/pawn.glb'],
        ['r', '/assets/models/rook.glb'],
        ['n', '/assets/models/knight.glb'],
        ['b', '/assets/models/bishop.glb'],
        ['q', '/assets/models/queen.glb'],
        ['k', '/assets/models/king.glb']
      ];

      await Promise.all(
        pieceMap.map(async ([code, url]) => {
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
        })
      );

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
      bodyMinY: scaledBodyMinY
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
    this.activeMixers.delete(inst.mixer);
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
    }

    const inst = this.pieceInstances.get(square);
    if (inst) {
      this._updateInspector(inst);
      if (inst.color === this.chess.turn()) {
        this.selectedSquare = square;
        this.legalMovesForSelected = this.chess.moves({ square, verbose: true });
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

  _resetInspector() {
    const feed = document.getElementById('combat-feed');
    if (feed) {
      feed.innerHTML = '<div class="combat-entry">🐉 崩れた石畳と古代ルーン魔法陣の祭壇で、石造ドラゴン群が覚醒しました…</div>';
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

    if (attacker) {
      await this._animateMoveAndCombat(attacker, defender, moveObj, capturedSquare);
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

    if (this.chess.inCheck()) {
      this.sfx.playCheckHorn();
    }

    this._logCombatMove(moveObj);
    this._updateBoardHighlights();
    this.updateHUD();

    this.isBusy = false;

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

      if (this.actionCamEnabled) {
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
      this.vfx.spawnShatterExplosion(
        defenderPos,
        this._getPieceMaterial(defender.type, defender.color),
        defender.color === 'w'
      );

      await this._wait(260);
      this._removePieceInstance(capturedSquare);

      this._playPieceAnimation(attacker, 'Move', true);
      await this._tweenPosition(attacker.root, strikePos, targetPos, 0.28, false);
      attacker.root.rotation.y = attacker.defaultYaw;
      this._playPieceAnimation(attacker, 'Idle', true);

      if (this.actionCamEnabled && this.savedCameraState) {
        await this._wait(250);
        this._tweenCamera(this.savedCameraState.pos, this.savedCameraState.target, 0.55);
        this.savedCameraState = null;
      }
    } else {
      const dur = Math.min(0.75, Math.max(0.38, distance * 0.14));
      this._playPieceAnimation(attacker, 'Move', true);
      this.sfx.playStoneSlide(dur);
      await this._tweenPosition(attacker.root, startPos, targetPos, dur, attacker.type === 'n');
      attacker.root.rotation.y = attacker.defaultYaw;
      this._playPieceAnimation(attacker, 'Idle', true);
    }

    this.pieceInstances.delete(moveObj.from);
    attacker.square = moveObj.to;
    attacker.root.traverse((c) => {
      if (c.isMesh) c.userData.square = moveObj.to;
    });
    this.pieceInstances.set(moveObj.to, attacker);
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
        const aiMove = chooseBestMove(this.chess, this.aiDepth);
        if (aiMove) {
          this.executeMove(aiMove);
        }
      }, 360);
    }
  }

  _logCombatMove(moveObj) {
    const feed = document.getElementById('combat-feed');
    if (!feed) return;

    const actorFaction = moveObj.color === 'w' ? '白竜石' : '黒曜竜';
    const pieceTitle = PIECE_INFO[moveObj.piece]?.shortName || '石造竜';
    let msg = '';

    if (moveObj.captured) {
      const victimTitle = PIECE_INFO[moveObj.captured]?.shortName || '石造竜';
      msg = `🔥 ${actorFaction}の${pieceTitle}が ${moveObj.to.toUpperCase()} の${victimTitle}を竜炎と牙で粉砕！ (${moveObj.san})`;
    } else if (moveObj.san.includes('+')) {
      msg = `⚡ ${actorFaction}の${pieceTitle}が ${moveObj.to.toUpperCase()} へ飛来 — 覇王古竜に王手咆哮！`;
    } else {
      msg = `🐉 ${actorFaction}の${pieceTitle}がルーン聖痕 ${moveObj.to.toUpperCase()} へ進撃 (${moveObj.san})`;
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
        chip.addEventListener('click', () => this.executeMove(m));
        quickSpellsEl.appendChild(chip);
      }
    }
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

  _showGameOverModal() {
    const modal = document.getElementById('gameover-modal');
    const title = document.getElementById('gameover-title');
    const sub = document.getElementById('gameover-subtitle');
    if (!modal || !title || !sub) return;

    if (this.chess.isCheckmate()) {
      const winner = this.chess.turn() === 'w' ? '黒曜竜の眷属 (Obsidian Brood)' : '白竜石の聖堂群 (Alabaster Brood)';
      title.textContent = 'SANCTUM CONQUERED — 覇王古竜陥落';
      sub.textContent = `竜石の聖域にて ${winner} が勝利の咆哮を上げました！`;
    } else {
      title.textContent = 'ARCANE STALEMATE — 竜魔力の均衡';
      sub.textContent = '双竜群の魔力が拮抗し、聖域は静寂に包まれました。';
    }
    modal.classList.remove('hidden');
  }

  _bindUIEvents() {
    window.addEventListener('resize', () => {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
      this.composer.setSize(window.innerWidth, window.innerHeight);
    });

    const dom = this.renderer.domElement;
    dom.addEventListener('pointerdown', (e) => {
      this.pointerDownPos.set(e.clientX, e.clientY);
    });

    dom.addEventListener('pointerup', (e) => {
      if (e.button !== 0) return;
      const dist = Math.hypot(e.clientX - this.pointerDownPos.x, e.clientY - this.pointerDownPos.y);
      if (dist > 6) return;

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
      white:     { pos: new THREE.Vector3(0, 8.2, 11.6),  target: new THREE.Vector3(0, 0.65, 0) },
      black:     { pos: new THREE.Vector3(0, 8.2, -11.6), target: new THREE.Vector3(0, 0.65, 0) },
      overhead:  { pos: new THREE.Vector3(0, 15.2, 0.01), target: new THREE.Vector3(0, 0, 0) },
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
      });
    });

    document.getElementById('chk-action-cam')?.addEventListener('change', (e) => {
      this.actionCamEnabled = e.target.checked;
    });

    document.getElementById('game-mode-select')?.addEventListener('change', (e) => {
      this.gameMode = e.target.value;
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
    });

    document.getElementById('ai-depth-select')?.addEventListener('change', (e) => {
      this.aiDepth = parseInt(e.target.value, 10) || 2;
    });

    document.getElementById('lighting-select')?.addEventListener('change', (e) => {
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
      } else if (toast) {
        toast.textContent = `⚠️ 「${input.value}」は現在の局面で無効な号令です (例: e4, Nf3, ワイバーン f3)`;
      }
    });

    document.getElementById('btn-battle-demo')?.addEventListener('click', () => {
      this.triggerBattleDemo();
    });

    const resetMatch = () => {
      if (this.isBusy) return;
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
      this.chess.undo();
      if (this.gameMode === 'pva' && this.chess.turn() === 'b') {
        this.chess.undo();
      }
      this.lastMove = null;
      this.selectedSquare = null;
      this.legalMovesForSelected = [];
      this.syncBoardFromFEN();
      this.updateHUD();
    });

    document.getElementById('btn-hint')?.addEventListener('click', () => {
      if (this.isBusy || this.chess.isGameOver()) return;
      const best = chooseBestMove(this.chess, 2);
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
        if (toast) toast.textContent = '🎙️ お使いのブラウザは音声認識非対応です。テキスト欄に呪文を入力してください。';
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
            ? `🎙️ 音声詠唱発動: 「${transcript}」!`
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
    this._updateClocks(performance.now());

    this.composer.render();
  }
}

window.addEventListener('DOMContentLoaded', () => {
  new WizardsChessApp();
});
