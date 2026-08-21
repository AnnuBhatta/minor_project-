import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000';

  // Convert HTTP to WebSocket protocol for WS proxy
  const wsTarget = backendTarget.replace(/^http/, 'ws');

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
        },
        '/ws': {
          target: wsTarget,
          changeOrigin: true,
          ws: true,
          secure: false,
          rewrite: (path) => path, // Keep the path as-is
          configure: (proxy, _options) => {
            proxy.on('error', (err, _req, _res) => {
              console.log('WebSocket proxy error:', err);
            });
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              console.log('WebSocket proxy request:', req.url);
            });
          },
        },
      },
    },
  };
});