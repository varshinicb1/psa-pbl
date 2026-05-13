import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// Dev-time proxy so the UI can call the FastAPI backend without CORS hassles.
// Backend runs at: http://127.0.0.1:8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // UI uses /api/snapshot, /api/health, etc.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // WebSocket stream
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
})

