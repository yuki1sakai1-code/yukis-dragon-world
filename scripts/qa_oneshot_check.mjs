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

  const optionsText = await page.evaluate(() => {
    const sel = document.getElementById('battle-mode-select');
    return Array.from(sel.options).map(o => o.text);
  });
  console.log('Battle mode select options:', optionsText);

  const btnClassic = await page.$('#btn-mode-classic');
  const btnText = await btnClassic.textContent();
  console.log('Button text:', btnText.trim());

  await btnClassic.click();
  await page.waitForTimeout(500);

  const toastText = await page.$eval('#status-toast', el => el.textContent);
  console.log('Toast text:', toastText);

  const screenshotPath = path.resolve(__dirname, 'qa_oneshot_battle.png');
  await page.screenshot({ path: screenshotPath });
  console.log('Saved screenshot to:', screenshotPath);

  await browser.close();
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});

