import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const hubPort = env.HUB_PORT || env.PORT || '8080'
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(import.meta.dirname, './src'),
      },
    },
    server: {
      proxy: {
        '/api': `http://127.0.0.1:${hubPort}`,
      },
    },
    build: {
      rolldownOptions: {
        output: {
          codeSplitting: {
            groups: [
              { name: 'recharts', test: /\/node_modules\/recharts\// },
              {
                name: 'markdown',
                test: /\/node_modules\/(react-markdown|remark-|mdast-|micromark|unist-|vfile)/,
              },
            ],
          },
        },
      },
    },
  }
})
