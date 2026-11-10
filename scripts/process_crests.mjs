import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

async function main() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage();

  const whiteSrc = 'C:/Users/yukis/.gemini/antigravity/brain/f5012e3d-fb1f-4d81-a49b-22f360f7b0eb/crest_alabaster_white_1794267648961.jpg';
  const blackSrc = 'C:/Users/yukis/.gemini/antigravity/brain/f5012e3d-fb1f-4d81-a49b-22f360f7b0eb/crest_obsidian_black_1794267672633.jpg';

  const whiteB64 = fs.readFileSync(whiteSrc).toString('base64');
  const blackB64 = fs.readFileSync(blackSrc).toString('base64');

  fs.mkdirSync('public/assets/images', { recursive: true });

  await page.setContent('<canvas id="c" width="256" height="256"></canvas>');

  async function resizeAndSave(b64, outPath) {
    const dataUrl = await page.evaluate(async (base64) => {
      const canvas = document.getElementById('c');
      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      const img = new Image();
      await new Promise((res, rej) => {
        img.onload = res;
        img.onerror = rej;
        img.src = 'data:image/jpeg;base64,' + base64;
      });
      ctx.clearRect(0, 0, 256, 256);
      ctx.drawImage(img, 0, 0, 256, 256);
      return canvas.toDataURL('image/png');
    }, b64);

    const base64Data = dataUrl.replace(/^data:image\/png;base64,/, '');
    fs.writeFileSync(outPath, Buffer.from(base64Data, 'base64'));
    console.log('Saved:', outPath, 'Bytes:', fs.statSync(outPath).size);
  }

  await resizeAndSave(whiteB64, 'public/assets/images/crest_alabaster_white.png');
  await resizeAndSave(blackB64, 'public/assets/images/crest_obsidian_black.png');

  await browser.close();
  console.log('Done processing crests.');
}

main().catch(console.error);

