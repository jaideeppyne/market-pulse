import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

// Built assets are served by FastAPI under /static (StaticFiles mount → ../frontend),
// and / returns ../frontend/index.html. So base must be /static/.
export default defineConfig({
  plugins: [react()],
  base: '/static/',
  build: {
    outDir: fileURLToPath(new URL('../frontend', import.meta.url)),
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/ws': { target: 'ws://127.0.0.1:8765', ws: true },
    },
  },
})
