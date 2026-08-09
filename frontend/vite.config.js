import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// No esbuild loader override: every file containing JSX now uses a .jsx
// extension, so the default handling applies.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 3000,
    proxy: {
      // The API base URL is relative by default (see src/config.js), so dev
      // traffic routes through here and needs no CORS exemption.
      '/api': {
        target: 'http://127.0.0.1:5988',
        changeOrigin: true,
      },
    },
  },
})
