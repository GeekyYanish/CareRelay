import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8001',
      '/a2a': 'http://127.0.0.1:8001',
      '/mcp': 'http://127.0.0.1:8001',
    },
  },
  test: { environment: 'jsdom', setupFiles: './tests/setup.ts', exclude: ['tests/e2e/**', 'node_modules/**'] },
})
