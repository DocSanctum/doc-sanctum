import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// Vite's string shorthand rewrites Host to the target, which the backend's Host
// allowlist rejects, so keep the browser's Host just as nginx does in prod.
const backendProxy = {
  target: process.env.VITE_BACKEND_URL ?? 'http://backend:8000',
  changeOrigin: false,
}

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': backendProxy,
      '/sse': backendProxy,
    },
  },
  test: {
    passWithNoTests: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
  },
})
