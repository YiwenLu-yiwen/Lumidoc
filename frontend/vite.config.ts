import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { URL } from 'url'

// 从URL中提取端口的工具函数
function getPortFromUrl(url: string, defaultPort = 3000): number {
  if (!url) return defaultPort;
  try {
    const parsedUrl = new URL(url);
    return parseInt(parsedUrl.port) || defaultPort;
  } catch (error) {
    console.warn(`无法从URL解析端口: ${url}, 使用默认端口: ${defaultPort}`);
    return defaultPort;
  }
}

// 根据DEPLOYMENT_MODE配置URL
function getServiceUrl(env: any, baseUrl: string, serverUrl?: string): string {
  const deploymentMode = env.DEPLOYMENT_MODE || 'localhost';
  
  if (deploymentMode === 'server' && serverUrl) {
    return serverUrl;
  }
  
  return baseUrl;
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 加载项目根目录的.env文件
  const env = loadEnv(mode, path.resolve(__dirname, '../..'), '')
  
  // 根据DEPLOYMENT_MODE动态配置URL
  const deploymentMode = env.DEPLOYMENT_MODE || 'localhost';
  
  // 配置服务器URL映射（当DEPLOYMENT_MODE=server时使用）
  const serverIP = env.SERVER_IP || '115.29.191.36'; // 默认IP，可在.env中配置
  const serverConfig = {
    API_GATEWAY_URL: env.API_GATEWAY_URL?.replace('localhost', serverIP),
    CHAT_SERVICE_URL: env.CHAT_SERVICE_URL?.replace('localhost', serverIP),
    PROJECT_SERVICE_URL: env.PROJECT_SERVICE_URL?.replace('localhost', serverIP),
    RAG_SERVICE_URL: env.RAG_SERVICE_URL?.replace('localhost', serverIP),
    FILE_SERVICE_URL: env.FILE_SERVICE_URL?.replace('localhost', serverIP),
    QUESTION_SERVICE_URL: env.QUESTION_SERVICE_URL?.replace('localhost', serverIP),
    GRAPH_SERVICE_URL: env.GRAPH_SERVICE_URL?.replace('localhost', serverIP),
    AUTH_SERVICE_URL: env.AUTH_SERVICE_URL?.replace('localhost', serverIP),
    MONITORING_SERVICE_URL: env.MONITORING_SERVICE_URL?.replace('localhost', serverIP),
    FRONTEND_URL: env.FRONTEND_URL?.replace('localhost', serverIP),
  };
  
  // 根据部署模式选择配置
  const actualConfig = {
    API_GATEWAY_URL: getServiceUrl(env, env.API_GATEWAY_URL, serverConfig.API_GATEWAY_URL),
    CHAT_SERVICE_URL: getServiceUrl(env, env.CHAT_SERVICE_URL, serverConfig.CHAT_SERVICE_URL),
    PROJECT_SERVICE_URL: getServiceUrl(env, env.PROJECT_SERVICE_URL, serverConfig.PROJECT_SERVICE_URL),
    RAG_SERVICE_URL: getServiceUrl(env, env.RAG_SERVICE_URL, serverConfig.RAG_SERVICE_URL),
    FILE_SERVICE_URL: getServiceUrl(env, env.FILE_SERVICE_URL, serverConfig.FILE_SERVICE_URL),
    QUESTION_SERVICE_URL: getServiceUrl(env, env.QUESTION_SERVICE_URL, serverConfig.QUESTION_SERVICE_URL),
    GRAPH_SERVICE_URL: getServiceUrl(env, env.GRAPH_SERVICE_URL, serverConfig.GRAPH_SERVICE_URL),
    AUTH_SERVICE_URL: getServiceUrl(env, env.AUTH_SERVICE_URL, serverConfig.AUTH_SERVICE_URL),
    MONITORING_SERVICE_URL: getServiceUrl(env, env.MONITORING_SERVICE_URL, serverConfig.MONITORING_SERVICE_URL),
    FRONTEND_URL: getServiceUrl(env, env.FRONTEND_URL, serverConfig.FRONTEND_URL),
  };
  
  // 只在开发环境打印环境变量
  if (mode === 'development') {
    console.log(`加载环境变量 (DEPLOYMENT_MODE: ${deploymentMode}, SERVER_IP: ${serverIP}):`, {
      ...actualConfig,
      DEBUG_MODE: env.DEBUG_MODE,
      LOG_LEVEL: env.LOG_LEVEL,
    });
  }
  
  // 前端开发服务器端口，从实际配置URL提取
  const frontendUrl = actualConfig.FRONTEND_URL || 'http://localhost:3000';
  const frontendPort = getPortFromUrl(frontendUrl, 3000);
  
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: frontendPort,
      proxy: {
        '/api': {
          target: actualConfig.PROJECT_SERVICE_URL,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
    build: {
      // 生产环境构建优化
      minify: 'terser',
      terserOptions: {
        compress: {
          // 移除console语句
          drop_console: mode === 'production',
          drop_debugger: true,
          pure_funcs: mode === 'production' ? ['console.log', 'console.warn', 'console.error', 'console.info', 'console.debug'] : [],
        },
        mangle: {
          // 混淆变量名
          properties: false,
        },
        format: {
          // 移除注释
          comments: false,
        },
      },
      rollupOptions: {
        output: {
          // 代码分割，防止单个文件过大
          manualChunks: {
            vendor: ['react', 'react-dom'],
            antd: ['antd'],
            utils: ['axios', 'date-fns'],
          },
        },
      },
      // 源码映射：生产环境禁用，开发环境启用
      sourcemap: mode === 'development',
    },
    define: {
      // 将根目录.env中的环境变量传递给前端，使用实际配置
      'import.meta.env.VITE_API_GATEWAY_URL': JSON.stringify(actualConfig.API_GATEWAY_URL),
      'import.meta.env.VITE_CHAT_SERVICE_URL': JSON.stringify(actualConfig.CHAT_SERVICE_URL),
      'import.meta.env.VITE_PROJECT_SERVICE_URL': JSON.stringify(actualConfig.PROJECT_SERVICE_URL), 
      'import.meta.env.VITE_RAG_SERVICE_URL': JSON.stringify(actualConfig.RAG_SERVICE_URL),
      'import.meta.env.VITE_FILE_SERVICE_URL': JSON.stringify(actualConfig.FILE_SERVICE_URL),
      'import.meta.env.VITE_QUESTION_SERVICE_URL': JSON.stringify(actualConfig.QUESTION_SERVICE_URL),
      'import.meta.env.VITE_GRAPH_SERVICE_URL': JSON.stringify(actualConfig.GRAPH_SERVICE_URL),
      'import.meta.env.VITE_AUTH_SERVICE_URL': JSON.stringify(actualConfig.AUTH_SERVICE_URL),
      'import.meta.env.VITE_MONITORING_SERVICE_URL': JSON.stringify(actualConfig.MONITORING_SERVICE_URL),
      'import.meta.env.VITE_FRONTEND_URL': JSON.stringify(actualConfig.FRONTEND_URL),
      // 生产环境下强制设置安全值
      'import.meta.env.VITE_DEBUG_MODE': JSON.stringify(mode === 'production' ? 'false' : env.DEBUG_MODE),
      'import.meta.env.VITE_LOG_LEVEL': JSON.stringify(mode === 'production' ? 'error' : env.LOG_LEVEL),
      'import.meta.env.VITE_DEPLOYMENT_MODE': JSON.stringify(deploymentMode),
      'import.meta.env.VITE_DEFAULT_QUERY_MODE': JSON.stringify(env.DEFAULT_QUERY_MODE),
      'import.meta.env.VITE_DEFAULT_STREAM': JSON.stringify(env.DEFAULT_STREAM),
    },
  }
})
