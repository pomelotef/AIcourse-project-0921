import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiTarget = process.env.LABPULSE_API_URL ?? 'http://127.0.0.1:8000'
const port = Number(process.env.LABPULSE_WEB_PORT ?? 5173)

export default defineConfig({
  plugins: [react()],
  server: {
    port,
    strictPort: true,
    proxy: { '/api': apiTarget },
  },
})
