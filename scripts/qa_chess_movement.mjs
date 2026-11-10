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

  // Select PvP
  await page.selectOption('#game-mode-select', 'pvp');
  await page.waitForTimeout(500);

  // Execute attack move: White Queen at b3 attacks Black Rook at b7
  const moveResult = await page.evaluate(async () => {
    const app = window.__wizardsChess;
    const move = {
      from: 'b3',
      to: 'b7',
      piece: 'q',
      color: 'w',
      captured: 'r',
      san: 'Qxb7'
    };
    
    // Execute move
    await app.executeMove(move);
    
    // Check piece positions after move
    const pieceAtB3 = app.pieceInstances.get('b3');
    const pieceAtB7 = app.pieceInstances.get('b7');
    const engineTurn = app.chess.turn();
    
    return {
      pieceAtB3Exists: Boolean(pieceAtB3),
      pieceAtB7Type: pieceAtB7 ? pieceAtB7.type : null,
      pieceAtB7Color: pieceAtB7 ? pieceAtB7.color : null,
      pieceAtB7Square: pieceAtB7 ? pieceAtB7.square : null,
      engineTurn
    };
  });

  console.log('Move execution result:', moveResult);

  const screenshotPath = path.resolve(__dirname, 'qa_chess_no_retreat.png');
  await page.screenshot({ path: screenshotPath });
  console.log('Saved screenshot to:', screenshotPath);

  await browser.close();
  console.log('Movement test completed successfully!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
