import { defineConfig } from 'vite'

export default defineConfig({
  root: '.',
  base: '/webui/',
  publicDir: 'public',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
  },
  server: {
    port: 5173,
    host: true,
  },
})