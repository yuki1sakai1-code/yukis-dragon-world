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

  // 1. Verify Combat Cam setting UI exists
  const camSelect = await page.$('#combat-cam-select');
  const initialMode = await camSelect.inputValue();
  console.log('Initial combat cam mode:', initialMode);

  // 2. Select overhead (俯瞰) view to simulate user looking from above / pulled back
  const overheadBtn = await page.$('.cam-btn[data-cam="overhead"]');
  if (overheadBtn) {
    await overheadBtn.click();
    await page.waitForTimeout(900); // wait for camera tween to overhead
  }

  // Check camera state in overhead view
  const camStateBefore = await page.evaluate(() => {
    const app = window.__wizardsChess;
    return {
      pos: { x: app.camera.position.x, y: app.camera.position.y, z: app.camera.position.z },
      isOverviewing: app._isOverviewingCamera(),
      combatCamMode: app.combatCamMode
    };
  });
  console.log('Camera before combat (Overhead):', camStateBefore);

  // Take screenshot of overhead view with setting UI visible
  await page.screenshot({ path: path.resolve(__dirname, 'qa_cam_overhead_before.png') });

  // 3. Trigger combat from overhead view with 'smart' mode:
  // Camera should NOT zoom in, should stay in overhead position!
  const combatPromise = page.evaluate(async () => {
    const app = window.__wizardsChess;
    const whiteQueen = app.pieceInstances.get('b3');
    const blackRook = app.pieceInstances.get('b7');
    const move = { from: 'b3', to: 'b7', piece: 'q', color: 'w', captured: 'r', san: 'Qxb7' };

    // Start combat
    const animPromise = app._animateMoveAndCombat(whiteQueen, blackRook, move, app.squareToWorld('b3'), app.squareToWorld('b7'));
    
    // Sample camera position during attack breath
    await app._wait(300); // during breath
    const midBreathPos = {
      x: app.camera.position.x,
      y: app.camera.position.y,
      z: app.camera.position.z
    };
    
    await animPromise;
    return {
      midBreathPos,
      endPos: { x: app.camera.position.x, y: app.camera.position.y, z: app.camera.position.z }
    };
  });

  // Capture screenshot right in the middle of dragon breath in overhead view
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.resolve(__dirname, 'qa_cam_overhead_breath.png') });

  const combatCamResult = await combatPromise;
  console.log('Combat camera result (mid & end pos):', combatCamResult);

  // 4. Test button toggles: switch to '⚔️ 常に拡大' and '🛡️ 拡大なし'
  const btnCloseup = await page.$('#btn-cam-closeup-mode');
  await btnCloseup.click();
  await page.waitForTimeout(300);
  const modeAfterCloseup = await page.evaluate(() => window.__wizardsChess.combatCamMode);
  console.log('Mode after clicking closeup button:', modeAfterCloseup);

  const btnFree = await page.$('#btn-cam-free');
  await btnFree.click();
  await page.waitForTimeout(300);
  const modeAfterFree = await page.evaluate(() => window.__wizardsChess.combatCamMode);
  console.log('Mode after clicking free button:', modeAfterFree);

  // Switch back to smart
  const btnSmart = await page.$('#btn-cam-smart');
  await btnSmart.click();
  await page.waitForTimeout(300);
  const modeAfterSmart = await page.evaluate(() => window.__wizardsChess.combatCamMode);
  console.log('Mode after clicking smart button:', modeAfterSmart);

  await page.screenshot({ path: path.resolve(__dirname, 'qa_cam_settings_panel.png') });

  await browser.close();
  console.log('Combat camera QA test completed successfully!');
}

run().catch(err => {
  console.error('QA Test error:', err);
  process.exit(1);
});

