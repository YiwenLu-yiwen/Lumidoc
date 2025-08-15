import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// 简化的稳定配置
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    strictPort: true,
    // 减少文件监听的资源消耗
    watch: {
      usePolling: false,
      interval: 1000,
    },
    // 禁用hmr重启频率限制
    hmr: {
      overlay: false,
    },
  },
  build: {
    // 简化构建配置
    minify: 'esbuild',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          antd: ['antd'],
        },
      },
    },
  },
  // 简化环境变量定义
  define: {
    'import.meta.env.VITE_API_GATEWAY_URL': JSON.stringify('http://localhost:8888'),
    'import.meta.env.VITE_CHAT_SERVICE_URL': JSON.stringify('http://localhost:8001'),
    'import.meta.env.VITE_PROJECT_SERVICE_URL': JSON.stringify('http://localhost:8020'),
    'import.meta.env.VITE_RAG_SERVICE_URL': JSON.stringify('http://localhost:8006'),
    'import.meta.env.VITE_FILE_SERVICE_URL': JSON.stringify('http://localhost:8004'),
    'import.meta.env.VITE_QUESTION_SERVICE_URL': JSON.stringify('http://localhost:8002'),
    'import.meta.env.VITE_GRAPH_SERVICE_URL': JSON.stringify('http://localhost:8003'),
    'import.meta.env.VITE_AUTH_SERVICE_URL': JSON.stringify('http://localhost:8007'),
    'import.meta.env.VITE_MONITORING_SERVICE_URL': JSON.stringify('http://localhost:8008'),
    'import.meta.env.VITE_FRONTEND_URL': JSON.stringify('http://localhost:3000'),
    'import.meta.env.VITE_DEBUG_MODE': JSON.stringify('true'),
    'import.meta.env.VITE_LOG_LEVEL': JSON.stringify('info'),
  },
  // 优化性能
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom'],
    exclude: ['@vite/client', '@vite/env'],
  },
})