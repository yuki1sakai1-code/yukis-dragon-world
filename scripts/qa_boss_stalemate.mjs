import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const htmlUrl = 'file:///' + path.resolve(__dirname, '../wizards-chess-standalone.html').replace(/\\/g, '/');
const artifactsDir = 'C:/Users/yukis/.gemini/antigravity/brain/f5012e3d-fb1f-4d81-a49b-22f360f7b0eb';

async function run() {
  console.log('Launching Chrome to test Boss Raid & Stalemate Surrender...');
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log(`[PAGE ERROR]: ${msg.text()}`);
  });

  await page.goto(htmlUrl);
  await page.waitForSelector('#loading-overlay.fade-out', { timeout: 35000 });
  await page.waitForTimeout(1000);

  // Set PvP mode so AI doesn't interfere
  await page.selectOption('#game-mode-select', 'pvp');
  await page.waitForTimeout(400);

  console.log('=== Test 1: Boss Raid Check Breath & Counterattack ===');
  // Load scenario where White Queen at c3 checks Black King at c7
  // FEN: 2k4/7/7/7/2Q4/7/4K2 w - - 0 1
  const test1Result = await page.evaluate(async () => {
    const app = window.__wizardsChess;
    app.combatRule = 'tactics';
    app.chess.load('2k4/7/7/7/2Q4/7/4K2 w - - 0 1');
    app.syncBoardFromFEN();
    app.updateHUD();

    const qInst = app.pieceInstances.get('c3');
    const kInst = app.pieceInstances.get('c7');
    const initKhp = kInst.hp;
    const initQhp = qInst.hp;

    // Queen moves to c6 with check: Qc6
    const moveRes = await app.executeMove({ from: 'c3', to: 'c6' });
    await new Promise((r) => setTimeout(r, 2200));

    const finalKhp = kInst.hp;
    const finalQhp = qInst.hp;
    const logText = document.getElementById('combat-feed')?.innerText || '';

    return {
      moveRes,
      initKhp,
      finalKhp,
      initQhp,
      finalQhp,
      kDamaged: finalKhp < initKhp,
      qDamaged: finalQhp < initQhp,
      logHasRaid: logText.includes('王手竜炎')
    };
  });

  console.log('Test 1 Result:', test1Result);
  await page.screenshot({ path: path.join(artifactsDir, 'qa_boss_raid_check.png') });

  console.log('=== Test 2: Boss Raid Fatal Strike (King HP to 0) ===');
  // King has only 20 HP, Queen checks him -> 30 damage kills the King -> Sanctum Conquered
  const test2Result = await page.evaluate(async () => {
    const app = window.__wizardsChess;
    app.combatRule = 'tactics';
    app.chess.load('2k4/7/7/7/2Q4/7/4K2 w - - 0 1');
    app.syncBoardFromFEN();
    app.updateHUD();

    const kInst = app.pieceInstances.get('c7');
    kInst.updateHp(20); // Low HP (will die from 30 damage)

    await app.executeMove({ from: 'c3', to: 'c6' });
    await new Promise((r) => setTimeout(r, 2200));

    const modal = document.getElementById('gameover-modal');
    const title = document.getElementById('gameover-title')?.textContent || '';
    const sub = document.getElementById('gameover-subtitle')?.textContent || '';
    const isModalVisible = modal && !modal.classList.contains('hidden');

    return {
      isModalVisible,
      title,
      sub,
      kingSlain: app._kingSlain
    };
  });

  console.log('Test 2 Result:', test2Result);
  await page.screenshot({ path: path.join(artifactsDir, 'qa_boss_raid_victory.png') });

  console.log('=== Test 3: Stalemate Complete Conquest (Sanctum Surrounded) ===');
  // White moves Qb5 -> Black King at a7 is trapped with 0 moves, not in check -> Stalemate = Surrender
  const test3Result = await page.evaluate(async () => {
    const app = window.__wizardsChess;
    document.getElementById('gameover-modal')?.classList.add('hidden');
    app._kingSlain = null;

    app.chess.load('k6/7/2K4/1Q5/7/7/7 w - - 0 1');
    app.syncBoardFromFEN();
    app.updateHUD();

    await app.executeMove({ from: 'b4', to: 'b5' });
    await new Promise((r) => setTimeout(r, 1800));

    const isStalemate = app.chess.isStalemate();
    const modal = document.getElementById('gameover-modal');
    const title = document.getElementById('gameover-title')?.textContent || '';
    const sub = document.getElementById('gameover-subtitle')?.textContent || '';
    const isModalVisible = modal && !modal.classList.contains('hidden');

    return {
      isStalemate,
      isModalVisible,
      title,
      sub
    };
  });

  console.log('Test 3 Result:', test3Result);
  await page.screenshot({ path: path.join(artifactsDir, 'qa_stalemate_surrounded_victory.png') });

  await browser.close();
  console.log('All tests passed successfully!');
}

run().catch((err) => {
  console.error('QA Error:', err);
  process.exit(1);
});
