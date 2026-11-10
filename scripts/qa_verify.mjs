import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { preview } from 'vite';
import { chromium } from 'playwright';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const MODELS_DIR = path.join(ROOT_DIR, 'public', 'assets', 'models');
const TEXTURES_DIR = path.join(ROOT_DIR, 'public', 'assets', 'textures');
const RENDERS_DIR = path.join(ROOT_DIR, 'public', 'assets', 'renders');

fs.mkdirSync(RENDERS_DIR, { recursive: true });

function readPngDimensions(filePath) {
  const buf = fs.readFileSync(filePath);
  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);
  return { width, height, bytes: buf.length };
}

async function verifyDiskAssets() {
  const expectedModels = [
    'gothic_cathedral.glb',
    'pawn.glb',
    'rook.glb',
    'knight.glb',
    'bishop.glb',
    'queen.glb',
    'king.glb'
  ];

  const modelReport = [];
  for (const name of expectedModels) {
    const full = path.join(MODELS_DIR, name);
    if (!fs.existsSync(full)) {
      throw new Error(`Missing GLB model: ${full}`);
    }
    const stat = fs.statSync(full);
    modelReport.push({ name, sizeMB: +(stat.size / (1024 * 1024)).toFixed(2) });
  }

  const requiredTextures = [
    'white_piece_albedo.png', 'white_piece_normal.png', 'white_piece_roughness.png',
    'white_piece_metallic.png', 'white_piece_ao.png', 'white_piece_emission.png',
    'black_piece_albedo.png', 'black_piece_normal.png', 'black_piece_roughness.png',
    'black_piece_metallic.png', 'black_piece_ao.png', 'black_piece_emission.png',
    'cathedral_stone_albedo.png', 'cathedral_stone_normal.png', 'cathedral_stone_roughness.png', 'cathedral_stone_ao.png',
    'cathedral_floor_albedo.png', 'cathedral_floor_normal.png', 'cathedral_floor_roughness.png', 'cathedral_floor_ao.png',
    'stained_glass_albedo.png', 'stained_glass_emission.png', 'stained_glass_roughness.png',
    'board_frame_albedo.png', 'board_frame_normal.png', 'board_frame_roughness.png', 'board_frame_metallic.png',
    'board_tiles_albedo.png', 'board_tiles_normal.png', 'board_tiles_roughness.png', 'board_tiles_metallic.png', 'board_tiles_ao.png'
  ];

  for (const req of requiredTextures) {
    if (!fs.existsSync(path.join(TEXTURES_DIR, req))) {
      throw new Error(`Missing required 2K PBR texture: ${req}`);
    }
  }

  const texFiles = fs.readdirSync(TEXTURES_DIR).filter((f) => f.endsWith('.png')).sort();
  const texReport = [];
  for (const file of texFiles) {
    const full = path.join(TEXTURES_DIR, file);
    const { width, height, bytes } = readPngDimensions(full);
    if (width !== 2048 || height !== 2048) {
      throw new Error(`Texture ${file} has non-2K dimensions: ${width}x${height}`);
    }
    texReport.push({ file, width, height, sizeKB: Math.round(bytes / 1024) });
  }

  return { modelCount: modelReport.length, models: modelReport, textureCount: texReport.length };
}

async function runQA() {
  console.log('=== 1. Verifying 3D GLB Models & 2K (2048x2048) Dragon-Stone PBR Textures on Disk ===');
  const assetSummary = await verifyDiskAssets();
  console.log(`Verified ${assetSummary.modelCount} GLB models and ${assetSummary.textureCount} 2048x2048 PNG textures.`);

  console.log('=== 2. Starting Vite Production Preview Server ===');
  const server = await preview({
    root: ROOT_DIR,
    preview: {
      port: 4173,
      strictPort: false
    }
  });
  const address = server.httpServer.address();
  const url = `http://localhost:${address.port}`;
  console.log(`Vite preview listening at ${url}`);

  const consoleErrors = [];
  const pageErrors = [];

  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
    args: ['--enable-webgl', '--ignore-gpu-blocklist']
  });

  try {
    const context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      deviceScaleFactor: 1
    });
    const page = await context.newPage();

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    page.on('pageerror', (err) => {
      pageErrors.push(err.message || String(err));
    });

    console.log('=== 3. Loading Three.js WebGL App & Waiting for Sanctum Ready ===');
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForSelector('#loading-overlay.fade-out', { state: 'attached', timeout: 60000 });
    await page.waitForTimeout(900);

    const sceneMetrics = await page.evaluate(() => {
      const app = window.__wizardsChess;
      if (!app) return { error: 'window.__wizardsChess not found' };

      const pieceCount = app.pieceInstances.size;
      const animChecks = [];
      let allHave4Anims = true;
      let allHave7Bones = true;

      for (const [sq, inst] of app.pieceInstances.entries()) {
        const keys = Object.keys(inst.actions);
        const hasIdle = keys.some((k) => k.toLowerCase().includes('idle'));
        const hasMove = keys.some((k) => k.toLowerCase().includes('move'));
        const hasAttack = keys.some((k) => k.toLowerCase().includes('attack'));
        const hasHit = keys.some((k) => k.toLowerCase().includes('hit'));
        if (!hasIdle || !hasMove || !hasAttack || !hasHit) {
          allHave4Anims = false;
        }
        if (inst.boneCount < 7) {
          allHave7Bones = false;
        }
        animChecks.push({ sq, type: inst.type, color: inst.color, boneCount: inst.boneCount, clips: keys });
      }

      const checkMat = (mat) => {
        if (!mat) return null;
        const maps = ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap'];
        const info = {};
        for (const m of maps) {
          const img = mat[m]?.image;
          info[m] = img ? { width: img.width, height: img.height } : null;
        }
        return info;
      };

      return {
        pieceCount,
        allHave4Anims,
        allHave7Bones,
        samplePieceAnims: animChecks.slice(0, 6),
        whiteMaterialMaps: checkMat(app.materials.w),
        blackMaterialMaps: checkMat(app.materials.b),
        boardTilesMaps: checkMat(app.materials.tileLight),
        boardSquaresCount: app.boardSquares.size,
        activeMixersCount: app.activeMixers.size
      };
    });

    console.log('Scene Metrics:', JSON.stringify(sceneMetrics, null, 2));
    if (!sceneMetrics.allHave4Anims || !sceneMetrics.allHave7Bones || (sceneMetrics.pieceCount !== 14 && sceneMetrics.pieceCount !== 28) || sceneMetrics.boardSquaresCount !== 49) {
      throw new Error('Scene metrics failed validation: ' + JSON.stringify(sceneMetrics));
    }

    // Screenshot 1: qa_main_view.png (Select Wyvern Knight on e4 in Endgame)
    console.log('=== 4. Capturing Screenshot 1: qa_main_view.png ===');
    await page.evaluate(() => {
      window.__wizardsChess.selectSquare('e4');
    });
    await page.waitForTimeout(550);
    const mainShotPath = path.join(RENDERS_DIR, 'qa_main_view.png');
    await page.screenshot({ path: mainShotPath, fullPage: false });
    console.log(`Saved ${mainShotPath}`);

    // Screenshot 2: qa_statue_closeup.png (Focus Twin-Headed Hydra Bishop on c3 + Macro close-up + Attack pose)
    console.log('=== 5. Capturing Screenshot 2: qa_statue_closeup.png ===');
    await page.selectOption('#game-mode-select', 'pvp');
    await page.evaluate(async () => {
      window.__wizardsChess.selectedSquare = 'c3';
      window.__wizardsChess.focusSelectedStatueMacro('c3');
    });
    await page.waitForTimeout(950);
    await page.click('.anim-test-btn[data-anim="Attack"]');
    await page.waitForTimeout(360);
    const closeupShotPath = path.join(RENDERS_DIR, 'qa_statue_closeup.png');
    await page.screenshot({ path: closeupShotPath, fullPage: false });
    console.log(`Saved ${closeupShotPath}`);

    // Reset board to PvA opening before Cathedral & Battle screenshots
    await page.click('#btn-new-game');
    await page.selectOption('#game-mode-select', 'pva');
    await page.waitForTimeout(250);

    // Screenshot 3: qa_cathedral_view.png (Grand Hall camera + Moonlit Rose Window lighting)
    console.log('=== 6. Capturing Screenshot 3: qa_cathedral_view.png ===');
    await page.selectOption('#lighting-select', 'moonlit');
    await page.click('[data-cam="cathedral"]');
    await page.waitForTimeout(1100);
    const cathedralShotPath = path.join(RENDERS_DIR, 'qa_cathedral_view.png');
    await page.screenshot({ path: cathedralShotPath, fullPage: false });
    console.log(`Saved ${cathedralShotPath}`);

    // Screenshot 4: qa_battle_shatter.png (Candlelight + White Throne + Dragon-Stone Battle Shatter)
    console.log('=== 7. Capturing Screenshot 4: qa_battle_shatter.png ===');
    await page.selectOption('#lighting-select', 'candlelight');
    await page.click('[data-cam="white"]');
    await page.waitForTimeout(900);

    await page.click('#btn-battle-demo');
    await page.waitForFunction(
      () => window.__wizardsChess && window.__wizardsChess.vfx && window.__wizardsChess.vfx.shards.length > 0,
      { timeout: 12000, polling: 40 }
    );
    await page.waitForTimeout(130);

    const battleMetrics = await page.evaluate(() => {
      const app = window.__wizardsChess;
      return {
        shardsCount: app.vfx.shards.length,
        shockwavesCount: app.vfx.shockwaves.length,
        sparksCount: app.vfx.sparks.length,
        combatFeedTop: document.querySelector('#combat-feed .combat-entry')?.textContent || ''
      };
    });
    console.log('Battle Metrics at capture moment:', JSON.stringify(battleMetrics, null, 2));

    const battleShotPath = path.join(RENDERS_DIR, 'qa_battle_shatter.png');
    await page.screenshot({ path: battleShotPath, fullPage: false });
    console.log(`Saved ${battleShotPath}`);

    await page.waitForTimeout(1000);
    console.log('Console Errors:', consoleErrors.length);
    console.log('Page Errors:', pageErrors.length);

    if (consoleErrors.length > 0 || pageErrors.length > 0) {
      console.error('Errors detected:', { consoleErrors, pageErrors });
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
    server.httpServer.close();
  }
}

runQA().catch((err) => {
  console.error('QA Script Failed:', err);
  process.exit(1);
});
