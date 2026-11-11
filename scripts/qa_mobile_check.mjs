import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const htmlUrl = 'file:///' + path.resolve(__dirname, '../index.html').replace(/\\/g, '/');
const artifactsDir = 'C:/Users/yukis/.gemini/antigravity/brain/f5012e3d-fb1f-4d81-a49b-22f360f7b0eb';

async function run() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });

  // ------------------------------------------------------------------
  // 1. Mobile Portrait QA (390x844, Touch Device)
  // ------------------------------------------------------------------
  const mobileErrors = [];
  const mobilePage = await browser.newPage({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    deviceScaleFactor: 2
  });
  mobilePage.on('pageerror', (err) => mobileErrors.push(`pageerror: ${err.message}`));
  mobilePage.on('console', (msg) => {
    if (msg.type() === 'error') mobileErrors.push(`console.error: ${msg.text()}`);
  });

  await mobilePage.goto(htmlUrl);
  await mobilePage.waitForSelector('#loading-overlay.fade-out', { timeout: 35000 });
  await mobilePage.waitForTimeout(900);

  // Inspect initial mobile layout geometry
  const initialLayout = await mobilePage.evaluate(() => {
    const leftRect = document.getElementById('left-panel')?.getBoundingClientRect();
    const rightRect = document.getElementById('right-panel')?.getBoundingClientRect();
    const topRect = document.querySelector('.top-hud')?.getBoundingClientRect();
    const dockRect = document.getElementById('mobile-dock')?.getBoundingClientRect();
    const leftStyle = getComputedStyle(document.getElementById('left-panel'));
    const rightStyle = getComputedStyle(document.getElementById('right-panel'));
    const fov = window.__wizardsChess?.camera?.fov;
    return {
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      cameraFov: fov,
      topHud: topRect ? { x: topRect.x, y: topRect.y, w: topRect.width, h: topRect.height, right: topRect.right } : null,
      mobileDock: dockRect ? { x: dockRect.x, y: dockRect.y, w: dockRect.width, h: dockRect.height, right: dockRect.right } : null,
      leftPanel: { opacity: leftStyle.opacity, pointerEvents: leftStyle.pointerEvents, x: leftRect?.x, right: leftRect?.right },
      rightPanel: { opacity: rightStyle.opacity, pointerEvents: rightStyle.pointerEvents, x: rightRect?.x, right: rightRect?.right }
    };
  });
  console.log('Mobile Initial Layout:', JSON.stringify(initialLayout, null, 2));
  await mobilePage.screenshot({ path: path.join(artifactsDir, 'qa_mobile_fixed_board.png') });

  // Open Right Drawer via mobile dock
  await mobilePage.click('#btn-mobile-right');
  await mobilePage.waitForTimeout(450);
  const rightOpenState = await mobilePage.evaluate(() => {
    const panel = document.getElementById('right-panel');
    const backdrop = document.getElementById('mobile-drawer-backdrop');
    return {
      isOpen: panel?.classList.contains('mobile-open'),
      backdropHidden: backdrop?.classList.contains('hidden'),
      opacity: getComputedStyle(panel).opacity
    };
  });
  console.log('Right Drawer Open State:', rightOpenState);

  // Verify two-way sync in mobile right drawer
  await mobilePage.selectOption('#mobile-lighting-select', 'candlelight');
  await mobilePage.selectOption('#mobile-ai-depth-select', '3');
  await mobilePage.selectOption('#mobile-game-mode-select', 'pvp');
  const syncCheck = await mobilePage.evaluate(() => ({
    topLighting: document.getElementById('lighting-select')?.value,
    topAiDepth: document.getElementById('ai-depth-select')?.value,
    topGameMode: document.getElementById('game-mode-select')?.value,
    appAiDepth: window.__wizardsChess?.aiDepth,
    appGameMode: window.__wizardsChess?.gameMode
  }));
  console.log('Mobile Two-way Sync Check:', syncCheck);

  // Restore defaults cleanly before screenshot
  await mobilePage.selectOption('#mobile-lighting-select', 'moonlit');
  await mobilePage.selectOption('#mobile-ai-depth-select', '2');
  await mobilePage.selectOption('#mobile-game-mode-select', 'pva');
  await mobilePage.waitForTimeout(200);
  await mobilePage.screenshot({ path: path.join(artifactsDir, 'qa_mobile_fixed_right_drawer.png') });

  // Close Right Drawer via close button
  await mobilePage.click('#right-panel [data-close-drawer]');
  await mobilePage.waitForTimeout(400);

  // Open Left Drawer via mobile dock
  await mobilePage.click('#btn-mobile-left');
  await mobilePage.waitForTimeout(450);
  await mobilePage.screenshot({ path: path.join(artifactsDir, 'qa_mobile_fixed_left_drawer.png') });

  // Close Left Drawer by tapping backdrop
  await mobilePage.click('#mobile-drawer-backdrop', { position: { x: 375, y: 400 }, force: true });
  await mobilePage.waitForTimeout(400);
  const closedState = await mobilePage.evaluate(() => ({
    leftOpen: document.getElementById('left-panel')?.classList.contains('mobile-open'),
    rightOpen: document.getElementById('right-panel')?.classList.contains('mobile-open'),
    backdropHidden: document.getElementById('mobile-drawer-backdrop')?.classList.contains('hidden')
  }));
  console.log('After Backdrop Close State:', closedState);

  // Test Hint from mobile dock
  await mobilePage.click('#btn-mobile-hint');
  await mobilePage.waitForTimeout(300);
  const hintToast = await mobilePage.textContent('#status-toast');
  console.log('Mobile Hint Toast:', hintToast);
  await mobilePage.screenshot({ path: path.join(artifactsDir, 'qa_mobile_hint_toast.png') });

  // Switch scenario from right drawer -> should auto-close drawer and display full standard 7x7 board
  await mobilePage.click('#btn-mobile-right');
  await mobilePage.waitForTimeout(400);
  await mobilePage.selectOption('#scenario-select', 'standard');
  await mobilePage.waitForTimeout(450);
  const autoClosedAfterScenario = await mobilePage.evaluate(() => ({
    rightOpen: document.getElementById('right-panel')?.classList.contains('mobile-open'),
    backdropHidden: document.getElementById('mobile-drawer-backdrop')?.classList.contains('hidden')
  }));
  console.log('Auto-closed After Scenario Change:', autoClosedAfterScenario);
  await mobilePage.screenshot({ path: path.join(artifactsDir, 'qa_mobile_standard_board.png') });

  // Test tapping a piece (e.g. c2 pawn) via actual screen tap coordinates
  const c2ScreenPos = await mobilePage.evaluate(() => {
    const app = window.__wizardsChess;
    const worldPos = app.squareToWorld('c2');
    worldPos.y += 0.6;
    worldPos.project(app.camera);
    return {
      x: (worldPos.x * 0.5 + 0.5) * window.innerWidth,
      y: (-worldPos.y * 0.5 + 0.5) * window.innerHeight
    };
  });
  await mobilePage.touchscreen.tap(c2ScreenPos.x, c2ScreenPos.y);
  await mobilePage.waitForTimeout(250);
  const selectedAfterTap = await mobilePage.evaluate(() => window.__wizardsChess?.selectedSquare);
  console.log('Mobile Touch Tap Selected Square (expect c2):', selectedAfterTap);

  await mobilePage.close();

  // ------------------------------------------------------------------
  // 2. Desktop Regression QA (1440x900)
  // ------------------------------------------------------------------
  const pcErrors = [];
  const pcPage = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  pcPage.on('pageerror', (err) => pcErrors.push(`pageerror: ${err.message}`));
  pcPage.on('console', (msg) => {
    if (msg.type() === 'error') pcErrors.push(`console.error: ${msg.text()}`);
  });

  await pcPage.goto(htmlUrl);
  await pcPage.waitForSelector('#loading-overlay.fade-out', { timeout: 35000 });
  await pcPage.waitForTimeout(900);

  const pcLayout = await pcPage.evaluate(() => {
    const leftRect = document.getElementById('left-panel')?.getBoundingClientRect();
    const rightRect = document.getElementById('right-panel')?.getBoundingClientRect();
    const dockDisplay = getComputedStyle(document.getElementById('mobile-dock')).display;
    const fov = window.__wizardsChess?.camera?.fov;
    return {
      cameraFov: fov,
      dockDisplay,
      leftWidth: leftRect?.width,
      rightWidth: rightRect?.width,
      centerGap: rightRect && leftRect ? rightRect.left - leftRect.right : 0
    };
  });
  console.log('PC Layout Check:', pcLayout);
  await pcPage.screenshot({ path: path.join(artifactsDir, 'qa_pc_regression.png') });
  await pcPage.close();

  await browser.close();

  console.log('Mobile Console/Page Errors:', mobileErrors);
  console.log('PC Console/Page Errors:', pcErrors);
  if (mobileErrors.length > 0 || pcErrors.length > 0) {
    process.exit(1);
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
