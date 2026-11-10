import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function run() {
  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 }
  });

  const fileUrl = 'file:///' + path.resolve(__dirname, '../wizards-chess-standalone.html').replace(/\\/g, '/');
  console.log('Navigating to:', fileUrl);

  const loadingStatuses = [];
  page.on('console', msg => {
    // console.log('[Browser]', msg.text());
  });

  // Track DOM loading text changes
  await page.exposeFunction('onStatusChange', (text) => {
    loadingStatuses.push(text);
  });

  await page.addInitScript(() => {
    const observer = new MutationObserver(() => {
      const el = document.getElementById('loading-status');
      if (el && el.textContent) {
        window.onStatusChange(el.textContent);
      }
    });
    window.addEventListener('DOMContentLoaded', () => {
      const el = document.getElementById('loading-status');
      if (el) {
        observer.observe(el, { childList: true, characterData: true, subtree: true });
        window.onStatusChange(el.textContent);
      }
    });
  });

  await page.goto(fileUrl);

  // Wait for loading overlay to fade out
  await page.waitForSelector('#loading-overlay.fade-out', { timeout: 30000 });
  console.log('Loading statuses seen:', loadingStatuses);

  // Screenshot initial board
  await page.screenshot({ path: path.resolve(__dirname, 'qa_loaded.png') });

  // 1. Verify Battle Mode Settings
  const battleModeSelect = await page.$('#battle-mode-select');
  const battleModeVal = await battleModeSelect.inputValue();
  console.log('Current battle mode:', battleModeVal);

  // 2. Select white pawn (e2 in 7x7 is d2 or similar, let's inspect pieces on board)
  const boardPieces = await page.evaluate(() => {
    const app = window.__DRAGON_APP__ || window.app;
    const pieces = [];
    if (app && app.pieceInstances) {
      for (const [sq, p] of app.pieceInstances) {
        pieces.push({ sq, type: p.type, color: p.color, hp: p.hp, atk: p.atk, def: p.def });
      }
    }
    return pieces;
  });
  console.log('Board pieces count:', boardPieces.length);
  console.log('Sample piece data (Tactics mode):', boardPieces.slice(0, 3));

  // 3. Test Cataclysm button
  console.log('Testing Cataclysm demo button...');
  const cataclysmBtn = await page.$('#btn-cataclysm-demo');
  if (cataclysmBtn) {
    await cataclysmBtn.click();
    // Wait for cataclysm animation
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.resolve(__dirname, 'qa_cataclysm_phase1.png') });
    console.log('Cataclysm Phase 1 executed!');

    const collapsedCount = await page.evaluate(() => {
      const app = window.__DRAGON_APP__ || window.app;
      return app ? app.collapsedSquares.size : 0;
    });
    console.log('Collapsed squares count:', collapsedCount);
  }

  await browser.close();
  console.log('Verification script completed successfully!');
}

run().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});

