import { defineConfig, mergeConfig } from 'vite'
import config from './vite.config'

// Keep shipped plugins/aliases, but never load env files or proxy to a backend.
export default defineConfig({
  ...mergeConfig(config, { envDir: false }),
  // Do not race the live preview's dependency optimizer/cache.
  cacheDir: 'node_modules/.vite-messages-check',
  server: { host: '127.0.0.1', strictPort: true, proxy: {} },
})