import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': process.env.VITE_BACKEND_URL ?? 'http://backend:8000',
      '/sse': process.env.VITE_BACKEND_URL ?? 'http://backend:8000',
    },
  },
  test: {
    passWithNoTests: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
  },
})
