import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/sse': 'http://localhost:8000',
    },
  },
  test: {
    passWithNoTests: true,
  },
})
