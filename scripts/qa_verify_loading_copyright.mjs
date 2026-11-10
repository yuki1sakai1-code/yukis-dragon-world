import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const htmlUrl = 'file:///' + path.resolve(__dirname, '../wizards-chess-standalone.html').replace(/\\/g, '/');
const artifactsDir = 'C:/Users/yukis/.gemini/antigravity/brain/f5012e3d-fb1f-4d81-a49b-22f360f7b0eb';

async function run() {
  console.log('Capturing Loading Screen with Copyright...');
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Pause page execution or intercept immediately to snap loading overlay
  await page.goto(htmlUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#loading-overlay', { timeout: 10000 });

  // Check text content of loading-copyright
  const copyrightText = await page.evaluate(() => {
    const el = document.querySelector('.loading-copyright');
    return el ? el.innerText.trim() : null;
  });

  console.log('Captured Copyright text on Loading Screen:', copyrightText);

  // Take screenshot of loading screen
  const screenshotPath = path.join(artifactsDir, 'qa_loading_screen_copyright.png');
  await page.screenshot({ path: screenshotPath });

  await browser.close();

  if (copyrightText && copyrightText.includes('All Rights Reserved') && copyrightText.includes('yuki1sakai1-code')) {
    console.log('SUCCESS: Loading screen has copyright notice!');
  } else {
    throw new Error('Copyright notice not found on loading screen: ' + copyrightText);
  }
}

run().catch((err) => {
  console.error('QA Error:', err);
  process.exit(1);
});

