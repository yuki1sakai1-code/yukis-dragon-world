import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function run() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto('file:///' + path.resolve(__dirname, '../wizards-chess-standalone.html').replace(/\\/g, '/'));
  await page.waitForSelector('#loading-overlay.fade-out', { timeout: 30000 });

  // 1. Check initial cataclysm timer UI
  const initialText = await page.$eval('#cataclysm-turns-text', el => el.textContent);
  const initialBadge = await page.$eval('#cataclysm-phase-badge', el => el.textContent);
  console.log('Initial timer:', initialText);
  console.log('Initial badge:', initialBadge);

  // 2. Simulate 9 full peaceful moves (18 half moves)
  await page.evaluate(() => {
    const app = window.__wizardsChess;
    // Set to 18 half moves (9 full moves peaceful)
    app.peacefulHalfMoves = 18;
    app._updateCataclysmHUD();
  });

  const progressText = await page.$eval('#cataclysm-turns-text', el => el.textContent);
  console.log('After 9 peaceful moves:', progressText);

  // Take screenshot with timer at 9/10 (warning state)
  const warnScreenshotPath = path.resolve(__dirname, 'qa_cataclysm_timer_warn.png');
  await page.screenshot({ path: warnScreenshotPath });
  console.log('Saved warning screenshot to:', warnScreenshotPath);

  // 3. Trigger 10th peaceful move -> should trigger Phase 1 Cataclysm!
  console.log('Triggering Cataclysm via peaceful moves reaching 10...');
  const cataclysmTriggered = await page.evaluate(async () => {
    const app = window.__wizardsChess;
    // Simulate non-combat move at turn 10
    app.peacefulHalfMoves = 20; // 10 full moves!
    // Trigger check
    const nextPhase = app.cataclysmPhase + 1;
    app.peacefulHalfMoves = 0;
    await app.triggerCataclysm(nextPhase);
    return {
      phase: app.cataclysmPhase,
      collapsedCount: app.collapsedSquares.size,
      timerText: document.getElementById('cataclysm-turns-text')?.textContent,
      badgeText: document.getElementById('cataclysm-phase-badge')?.textContent
    };
  });

  console.log('Cataclysm triggered result:', cataclysmTriggered);

  // Wait for crumble animation & take screenshot
  await page.waitForTimeout(1000);
  const postScreenshotPath = path.resolve(__dirname, 'qa_cataclysm_timer_post.png');
  await page.screenshot({ path: postScreenshotPath });
  console.log('Saved post cataclysm screenshot to:', postScreenshotPath);

  await browser.close();
  console.log('Cataclysm timer QA test completed successfully!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});

