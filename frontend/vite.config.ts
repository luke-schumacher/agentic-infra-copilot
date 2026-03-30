import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const govHost  = process.env.VITE_GOV_HOST  || 'localhost'
const hwHost   = process.env.VITE_HW_HOST   || 'localhost'
const telHost  = process.env.VITE_TEL_HOST  || 'localhost'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/gov': { target: `http://${govHost}:8001`, changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/gov/, '') },
      '/api/hw':  { target: `http://${hwHost}:8002`,  changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/hw/, '') },
      '/api/tel': { target: `http://${telHost}:8003`, changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/tel/, '') },
    },
  },
})
