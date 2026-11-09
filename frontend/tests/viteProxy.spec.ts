// @vitest-environment node
import { describe, expect, it } from 'vitest'
import config from '../vite.config'

describe('dev server proxy', () => {
  it.each(['/api', '/sse'])('keeps the browser Host header for %s', (path) => {
    expect(config.server?.proxy?.[path]).toMatchObject({ changeOrigin: false })
  })
})
