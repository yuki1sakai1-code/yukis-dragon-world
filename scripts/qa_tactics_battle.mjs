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

  // 1. Initial State: Tactics Mode (HP battle) in setting panel
  console.log('Taking screenshot of settings panel with Change Battle Mode...');
  await page.evaluate(() => {
    const app = window.__wizardsChess;
    app.selectSquare('e3'); // Select Wyvern to show inspector stats
  });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${outDir}/qa_battle_mode_setting_tactics.png` });

  // 2. Click '♟️ 従来のチェス' button in the settings panel
  console.log('Clicking "♟️ 従来のチェス" button in Change Battle Mode panel...');
  await page.click('#btn-mode-classic');
  await page.waitForTimeout(800);

  const classicState = await page.evaluate(() => {
    const app = window.__wizardsChess;
    const btnClassicActive = document.getElementById('btn-mode-classic')?.classList.contains('active');
    const btnTacticsActive = document.getElementById('btn-mode-tactics')?.classList.contains('active');
    const selTopVal = document.getElementById('combat-rule-select')?.value;
    const selPanelVal = document.getElementById('battle-mode-select')?.value;
    const rpgStatsDisplay = document.getElementById('inspector-rpg-stats')?.style.display;
    const toast = document.getElementById('status-toast')?.textContent;
    return {
      combatRule: app.combatRule,
      btnClassicActive,
      btnTacticsActive,
      selTopVal,
      selPanelVal,
      rpgStatsDisplay,
      toast
    };
  });
  console.log('Classic Mode Switch State:', classicState);
  await page.screenshot({ path: `${outDir}/qa_battle_mode_setting_classic.png` });

  // 3. Click '⚔️ HP・攻防バトル' button to switch back
  console.log('Clicking "⚔️ HP・攻防バトル" button in Change Battle Mode panel...');
  await page.click('#btn-mode-tactics');
  await page.waitForTimeout(800);

  const tacticsState = await page.evaluate(() => {
    const app = window.__wizardsChess;
    const btnClassicActive = document.getElementById('btn-mode-classic')?.classList.contains('active');
    const btnTacticsActive = document.getElementById('btn-mode-tactics')?.classList.contains('active');
    const selTopVal = document.getElementById('combat-rule-select')?.value;
    const selPanelVal = document.getElementById('battle-mode-select')?.value;
    const rpgStatsDisplay = document.getElementById('inspector-rpg-stats')?.style.display;
    const toast = document.getElementById('status-toast')?.textContent;
    return {
      combatRule: app.combatRule,
      btnClassicActive,
      btnTacticsActive,
      selTopVal,
      selPanelVal,
      rpgStatsDisplay,
      toast
    };
  });
  console.log('Tactics Mode Switch State:', tacticsState);
  await page.screenshot({ path: `${outDir}/qa_battle_mode_setting_restored.png` });

  await browser.close();
  console.log('All QA steps completed successfully!');
}

runQA().catch(err => {
  console.error('QA Failed:', err);
  process.exit(1);
});
