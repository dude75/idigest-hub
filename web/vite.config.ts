import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const hubPort = env.HUB_PORT || env.PORT || '8080'
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': `http://127.0.0.1:${hubPort}`,
      },
    },
  }
})
