import path from 'path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { version } from './package.json'

export default defineConfig({
  plugins: [react()],
  define: {
    // What `next.config.ts` injects for a real build. Defined here too so the
    // footer under test renders the version it would ship with rather than the
    // `dev` fallback, and so the manifest stays the only place the number is
    // written down.
    'process.env.NEXT_PUBLIC_APP_VERSION': JSON.stringify(version),
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
})
