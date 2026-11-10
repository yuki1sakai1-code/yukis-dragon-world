import { chromium } from 'playwright';
import path from 'path';

async function runQA() {
  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
    args: ['--enable-webgl', '--ignore-gpu-blocklist']
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();

  page.on('console', msg => {
    console.log(`[Page Console ${msg.type()}]: ${msg.text()}`);
  });

  const htmlPath = path.resolve('wizards-chess-standalone.html');
  console.log(`Loading: file://${htmlPath}`);
  await page.goto(`file://${htmlPath}`, { waitUntil: 'domcontentloaded' });

  console.log('Waiting for loading overlay to fade out...');
  await page.waitForSelector('#loading-overlay.fade-out', { state: 'attached', timeout: 60000 });
  await page.waitForTimeout(3000);

  const outDir = 'C:/Users/yukis/.gemini/antigravity/brain/f5012e3d-fb1f-4d81-a49b-22f360f7b0eb';

  // 1. Set mode to PvP so AI doesn't interfere
  await page.evaluate(() => {
    const app = window.__wizardsChess;
    app.gameMode = 'pvp';
  });

  console.log('--- Move 1: e3 Wyvern attacks f5 Queen (1st time) ---');
  await page.evaluate(async () => {
    const app = window.__wizardsChess;
    await app.executeMove({ from: 'e3', to: 'f5' });
  });
  await page.waitForTimeout(2800);

  // Black makes a passive move: a5 -> a4
  console.log('--- Black Move 1: a5 -> a4 ---');
  await page.evaluate(async () => {
    const app = window.__wizardsChess;
    // Check legal moves for black or move a5 -> a4
    await app.executeMove({ from: 'a5', to: 'a4' });
  });
  await page.waitForTimeout(1500);

  console.log('--- Move 2: e3 Wyvern attacks f5 Queen (2nd time) ---');
  await page.evaluate(async () => {
    const app = window.__wizardsChess;
    await app.executeMove({ from: 'e3', to: 'f5' });
  });
  await page.waitForTimeout(2800);

  // Black makes another passive move: b7 -> b6
  console.log('--- Black Move 2: b7 -> b6 ---');
  await page.evaluate(async () => {
    const app = window.__wizardsChess;
    await app.executeMove({ from: 'b7', to: 'b6' });
  });
  await page.waitForTimeout(1500);

  // Now White's turn again. e3 Wyvern wants to attack f5 Queen for the 3rd time!
  console.log('--- Checking 3rd attack repetition block on e3 -> f5 ---');
  const repetitionCheck = await page.evaluate(async () => {
    const app = window.__wizardsChess;
    app.selectSquare('e3');
    const legalTargets = app.legalMovesForSelected.map(m => m.to);
    const isF5InLegalMoves = legalTargets.includes('f5');

    // Try executing the 3rd repeated move
    const execResult = await app.executeMove({ from: 'e3', to: 'f5' });
    const toast = document.getElementById('status-toast')?.textContent;

    return {
      legalTargetsForE3: legalTargets,
      isF5Allowed: isF5InLegalMoves,
      execResult,
      toast
    };
  });

  console.log('Repetition Rule Check Result:', repetitionCheck);
  await page.screenshot({ path: `${outDir}/qa_anti_stalemate_toast.png` });

  await browser.close();
  console.log('Anti-stalemate QA finished successfully!');
}

runQA().catch(err => {
  console.error('QA Failed:', err);
  process.exit(1);
});

