import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/gov': { target: 'http://localhost:8001', changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/gov/, '') },
      '/api/hw':  { target: 'http://localhost:8002', changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/hw/, '') },
      '/api/tel': { target: 'http://localhost:8003', changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/tel/, '') },
    },
  },
})
