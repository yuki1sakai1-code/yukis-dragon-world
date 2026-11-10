import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { execFileSync, execSync } from 'node:child_process';

const rootDir = process.cwd();
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'dragon-chess-pack-'));
const blenderExe = 'C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe';

console.log('=== 1. Building Vite Production Bundle ===');
execSync('npm run build', { stdio: 'inherit' });

const distDir = path.join(rootDir, 'dist');
const assetsDir = path.join(distDir, 'assets');
const assetFiles = fs.readdirSync(assetsDir);

const cssFile = assetFiles.find((f) => f.endsWith('.css'));
const jsFile = assetFiles.find((f) => f.endsWith('.js'));

const cssContent = fs.readFileSync(path.join(assetsDir, cssFile), 'utf8');
const jsContent = fs.readFileSync(path.join(assetsDir, jsFile), 'utf8');

console.log('=== 2. Compressing 2K Dragon-Stone PBR Maps & Cathedral GLB to WebP via Headless Blender ===');
const texKeys = [
  'white_piece_albedo',
  'white_piece_normal',
  'white_piece_roughness',
  'white_piece_metallic',
  'white_piece_ao',
  'white_piece_emission',
  'black_piece_albedo',
  'black_piece_normal',
  'black_piece_roughness',
  'black_piece_metallic',
  'black_piece_ao',
  'black_piece_emission',
  'board_tiles_albedo',
  'board_tiles_normal',
  'board_tiles_roughness',
  'board_tiles_metallic',
  'board_tiles_ao'
];

const pyScriptPath = path.join(tmpDir, 'pack_webp.py');
const pyCode = `
import os, bpy

root_dir = ${JSON.stringify(rootDir)}
tmp_dir = ${JSON.stringify(tmpDir)}
tex_keys = ${JSON.stringify(texKeys)}

scene = bpy.context.scene
scene.render.image_settings.file_format = 'WEBP'
scene.render.image_settings.quality = 86

for key in tex_keys:
    src = os.path.join(root_dir, 'public', 'assets', 'textures', f'{key}.png')
    dst = os.path.join(tmp_dir, f'{key}.webp')
    img = bpy.data.images.load(src)
    img.save_render(dst, scene=scene)
    bpy.data.images.remove(img)

bpy.ops.wm.read_factory_settings(use_empty=True)
cat_src = os.path.join(root_dir, 'public', 'assets', 'models', 'gothic_cathedral.glb')
cat_dst = os.path.join(tmp_dir, 'gothic_cathedral_webp.glb')
bpy.ops.import_scene.gltf(filepath=cat_src)
bpy.ops.export_scene.gltf(
    filepath=cat_dst,
    export_format='GLB',
    export_image_format='WEBP',
    export_image_quality=84,
    export_yup=True
)
print('PACK_WEBP_DONE')
`;
fs.writeFileSync(pyScriptPath, pyCode, 'utf8');
execFileSync(blenderExe, ['-b', '--factory-startup', '-P', pyScriptPath], { stdio: 'inherit' });

const embeddedTextures = {};
for (const key of texKeys) {
  const webpPath = path.join(tmpDir, `${key}.webp`);
  const buf = fs.readFileSync(webpPath);
  embeddedTextures[`/assets/textures/${key}.png`] = `data:image/webp;base64,${buf.toString('base64')}`;
}

const modelMap = {
  '/assets/models/gothic_cathedral.glb': path.join(tmpDir, 'gothic_cathedral_webp.glb'),
  '/assets/models/pawn.glb': path.join(rootDir, 'public', 'assets', 'models', 'pawn.glb'),
  '/assets/models/rook.glb': path.join(rootDir, 'public', 'assets', 'models', 'rook.glb'),
  '/assets/models/knight.glb': path.join(rootDir, 'public', 'assets', 'models', 'knight.glb'),
  '/assets/models/bishop.glb': path.join(rootDir, 'public', 'assets', 'models', 'bishop.glb'),
  '/assets/models/queen.glb': path.join(rootDir, 'public', 'assets', 'models', 'queen.glb'),
  '/assets/models/king.glb': path.join(rootDir, 'public', 'assets', 'models', 'king.glb')
};

const embeddedModels = {};
for (const [url, filePath] of Object.entries(modelMap)) {
  const buf = fs.readFileSync(filePath);
  embeddedModels[url] = buf.toString('base64');
}

const embeddedAudio = {};
const bgmPath = path.join(rootDir, 'public', 'assets', 'audio', 'Beyond_the_Great_Crest.mp3');
if (fs.existsSync(bgmPath)) {
  const bgmBuf = fs.readFileSync(bgmPath);
  embeddedAudio['Beyond_the_Great_Crest.mp3'] = `data:audio/mp3;base64,${bgmBuf.toString('base64')}`;
  embeddedAudio['/assets/audio/Beyond_the_Great_Crest.mp3'] = embeddedAudio['Beyond_the_Great_Crest.mp3'];
}

console.log('=== 3. Assembling Self-Contained wizards-chess-standalone.html ===');
let html = fs.readFileSync(path.join(rootDir, 'index.html'), 'utf8');
html = html.replace(/<link[^>]*href="\/src\/style\.css"[^>]*>/i, () => `<style>\n${cssContent}\n</style>`);

// Inline UI image assets into HTML as base64 data URIs
html = html.replace(/(src|href)="(\/assets\/images\/[^"]+)"/g, (match, attr, relPath) => {
  const fullPath = path.join(rootDir, 'public', relPath.replace(/^\//, ''));
  if (fs.existsSync(fullPath)) {
    const ext = path.extname(fullPath).toLowerCase();
    const mime = ext === '.png' ? 'image/png' : (ext === '.jpg' || ext === '.jpeg') ? 'image/jpeg' : 'image/webp';
    const b64 = fs.readFileSync(fullPath).toString('base64');
    return `${attr}="data:${mime};base64,${b64}"`;
  }
  return match;
});

const embeddedPayloadScript = `<script>
window.__EMBEDDED_ASSETS__ = {
  textures: ${JSON.stringify(embeddedTextures)},
  models: ${JSON.stringify(embeddedModels)},
  audio: ${JSON.stringify(embeddedAudio)}
};
</script>`;

const safeJsContent = jsContent.replace(/<\/script>/gi, '<\\/script>');
const inlineBundleScript = `<script type="module">\n${safeJsContent}\n</script>`;

html = html.replace(
  /<script[^>]*src="\/src\/main\.js"[^>]*><\/script>/i,
  () => `${embeddedPayloadScript}\n${inlineBundleScript}`
);

const outPath = path.join(rootDir, 'wizards-chess-standalone.html');
fs.writeFileSync(outPath, html, 'utf8');
fs.rmSync(tmpDir, { recursive: true, force: true });

const sizeMB = (fs.statSync(outPath).size / (1024 * 1024)).toFixed(2);
console.log(`Successfully generated: ${outPath} (${sizeMB} MB)`);
