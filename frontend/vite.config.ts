/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Everything stays on loopback: the dev server binds to 127.0.0.1 and proxies /api to the backend.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // theme.test.ts reads the design tokens from index.css?raw, which needs CSS enabled.
    css: { include: [/index\.css/] },
  },
})
