import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const htmlUrl = 'file:///' + path.resolve(__dirname, '../wizards-chess-standalone.html').replace(/\\/g, '/');
const artifactsDir = 'C:/Users/yukis/.gemini/antigravity/brain/f5012e3d-fb1f-4d81-a49b-22f360f7b0eb';

async function run() {
  console.log('Testing default battle mode is One-Shot Battle (classic)...');
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  await page.goto(htmlUrl);
  await page.waitForSelector('#loading-overlay.fade-out', { timeout: 35000 });
  await page.waitForTimeout(1000);

  const check = await page.evaluate(() => {
    const app = window.__wizardsChess;
    const rule = app.combatRule;

    const selectTop = document.getElementById('combat-rule-select')?.value;
    const selectSide = document.getElementById('battle-mode-select')?.value;
    const btnClassicActive = document.getElementById('btn-mode-classic')?.classList.contains('active');
    const btnTacticsActive = document.getElementById('btn-mode-tactics')?.classList.contains('active');

    // Check if HP bar sprites are hidden by default
    let hpBarsVisibleCount = 0;
    for (const inst of app.pieceInstances.values()) {
      if (inst.hpBarSprite && inst.hpBarSprite.visible) {
        hpBarsVisibleCount++;
      }
    }

    // Check inspector RPG stats section
    const rpgStatsDisplay = document.getElementById('inspector-rpg-stats')?.style.display;

    return {
      combatRule: rule,
      selectTop,
      selectSide,
      btnClassicActive,
      btnTacticsActive,
      hpBarsVisibleCount,
      rpgStatsDisplay
    };
  });

  console.log('Default State Verification:', check);

  const screenshotPath = path.join(artifactsDir, 'qa_default_oneshot_mode.png');
  await page.screenshot({ path: screenshotPath });

  await browser.close();

  if (
    check.combatRule === 'classic' &&
    check.selectTop === 'classic' &&
    check.selectSide === 'classic' &&
    check.btnClassicActive === true &&
    check.btnTacticsActive === false &&
    check.hpBarsVisibleCount === 0 &&
    check.rpgStatsDisplay === 'none'
  ) {
    console.log('SUCCESS: Default mode is One-Shot Battle (classic)!');
  } else {
    throw new Error('Default mode verification failed: ' + JSON.stringify(check));
  }
}

run().catch((err) => {
  console.error('QA Error:', err);
  process.exit(1);
});

