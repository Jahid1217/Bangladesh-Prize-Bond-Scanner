import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During development the Vite server proxies API calls to the FastAPI backend.
// On the phone, use the production build served by FastAPI over HTTPS.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
