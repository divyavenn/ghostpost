import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd());
  const isDev = command === 'serve';
  
  return {
    // CRITICAL: Base path for Docker/nginx deployment
    base: './',
    
    plugins: [react()],
    
    // Include Lottie files as static assets
    assetsInclude: ['**/*.lottie'],
    
    // Build configuration
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      sourcemap: isDev,
      minify: !isDev ? 'esbuild' : false,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom'],
            router: ['react-router-dom'],
            ui: ['lottie-react', '@lottiefiles/dotlottie-react']
          }
        }
      }
    },
    
    server: {
      port: 3000,
      host: true,
      watch: {
        usePolling: true,
      },
      // Only for development - nginx handles this in production
      proxy: isDev ? {
        '/api': {
          target: env.VITE_APP_BACKEND_ADDRESS || 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, '')
        }
      } : undefined
    },
    
    esbuild: {
      target: "esnext",
      platform: "browser",
    },
    
    define: {
      VITE_APP_BACKEND_ADDRESS: JSON.stringify(env.VITE_APP_BACKEND_ADDRESS),
    },
  };
});