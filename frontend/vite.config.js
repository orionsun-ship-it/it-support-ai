import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// /api/* is proxied to VITE_API_BASE_URL (default: localhost:8000) and the
// /api prefix is stripped before forwarding. In production, configure this via
// .env.production or use a reverse proxy (nginx/Caddy) instead.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiBase = env.VITE_API_BASE_URL || 'http://localhost:8000';
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: apiBase,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  };
});
