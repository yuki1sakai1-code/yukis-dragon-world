import { defineConfig } from 'vite';

export default defineConfig({
  base: './', // Use relative path so assets work in subpaths like GitHub Pages (/yukis-dragon-world/)
  build: {
    chunkSizeWarningLimit: 2000,
  }
});
