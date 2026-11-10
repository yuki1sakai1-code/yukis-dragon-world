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
  await page.goto(fileUrl);
  await page.waitForSelector('#loading-overlay.fade-out', { timeout: 30000 });

  // Tactics battle mode & PvP
  await page.selectOption('#battle-mode-select', 'tactics');
  await page.selectOption('#game-mode-select', 'pvp');
  await page.waitForTimeout(500);

  const combatResult = await page.evaluate(async () => {
    const app = window.__wizardsChess;
    const whiteQueen = app.pieceInstances.get('b3');
    const blackRook = app.pieceInstances.get('b7');
    
    // Simulate Queen moving from b3 to b7 attacking Black Rook
    const move = {
      from: 'b3',
      to: 'b7',
      piece: 'q',
      color: 'w',
      captured: 'r',
      san: 'Qxb7'
    };
    
    await app._animateMoveAndCombat(whiteQueen, blackRook, move, app.squareToWorld('b3'), app.squareToWorld('b7'));
    
    return {
      whiteQueenHP: whiteQueen.hp,
      blackRookHP: blackRook.hp,
      whiteQueenSquare: whiteQueen.square,
      feedEntries: Array.from(document.querySelectorAll('.combat-entry')).map(e => e.textContent).slice(0, 3)
    };
  });

  console.log('Combat result:', combatResult);

  await page.waitForTimeout(1000);
  const screenshotPath = path.resolve(__dirname, 'qa_counterattack_verified.png');
  await page.screenshot({ path: screenshotPath });
  console.log('Saved screenshot to:', screenshotPath);

  await browser.close();
}

run().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
