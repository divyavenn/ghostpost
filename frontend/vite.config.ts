import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';


export default defineConfig({
  plugins: [react()],
  define: {
    // Provide a polyfill for process.env
    'process.env': {
      NODE_ENV: JSON.stringify(process.env.NODE_ENV || 'development')
    },
    // Fallback for just 'process'
    'process': {
      env: {
        NODE_ENV: JSON.stringify(process.env.NODE_ENV || 'development')
      }
    }
  }
});