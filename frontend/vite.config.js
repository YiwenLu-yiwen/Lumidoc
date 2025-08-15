var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { URL } from 'url';
// 从URL中提取端口的工具函数
function getPortFromUrl(url, defaultPort) {
    if (defaultPort === void 0) { defaultPort = 3000; }
    if (!url)
        return defaultPort;
    try {
        var parsedUrl = new URL(url);
        return parseInt(parsedUrl.port) || defaultPort;
    }
    catch (error) {
        console.warn("\u65E0\u6CD5\u4ECEURL\u89E3\u6790\u7AEF\u53E3: ".concat(url, ", \u4F7F\u7528\u9ED8\u8BA4\u7AEF\u53E3: ").concat(defaultPort));
        return defaultPort;
    }
}
// 根据DEPLOYMENT_MODE配置URL
function getServiceUrl(env, baseUrl, serverUrl) {
    var deploymentMode = env.DEPLOYMENT_MODE || 'localhost';
    if (deploymentMode === 'server' && serverUrl) {
        return serverUrl;
    }
    return baseUrl;
}
// https://vitejs.dev/config/
export default defineConfig(function (_a) {
    var _b, _c, _d, _e, _f, _g, _h, _j, _k, _l;
    var mode = _a.mode;
    // 加载项目根目录的.env文件
    var env = loadEnv(mode, path.resolve(__dirname, '../..'), '');
    // 根据DEPLOYMENT_MODE动态配置URL
    var deploymentMode = env.DEPLOYMENT_MODE || 'localhost';
    // 配置服务器URL映射（当DEPLOYMENT_MODE=server时使用）
    var serverIP = env.SERVER_IP || '115.29.191.36'; // 默认IP，可在.env中配置
    var serverConfig = {
        API_GATEWAY_URL: (_b = env.API_GATEWAY_URL) === null || _b === void 0 ? void 0 : _b.replace('localhost', serverIP),
        CHAT_SERVICE_URL: (_c = env.CHAT_SERVICE_URL) === null || _c === void 0 ? void 0 : _c.replace('localhost', serverIP),
        PROJECT_SERVICE_URL: (_d = env.PROJECT_SERVICE_URL) === null || _d === void 0 ? void 0 : _d.replace('localhost', serverIP),
        RAG_SERVICE_URL: (_e = env.RAG_SERVICE_URL) === null || _e === void 0 ? void 0 : _e.replace('localhost', serverIP),
        FILE_SERVICE_URL: (_f = env.FILE_SERVICE_URL) === null || _f === void 0 ? void 0 : _f.replace('localhost', serverIP),
        QUESTION_SERVICE_URL: (_g = env.QUESTION_SERVICE_URL) === null || _g === void 0 ? void 0 : _g.replace('localhost', serverIP),
        GRAPH_SERVICE_URL: (_h = env.GRAPH_SERVICE_URL) === null || _h === void 0 ? void 0 : _h.replace('localhost', serverIP),
        AUTH_SERVICE_URL: (_j = env.AUTH_SERVICE_URL) === null || _j === void 0 ? void 0 : _j.replace('localhost', serverIP),
        MONITORING_SERVICE_URL: (_k = env.MONITORING_SERVICE_URL) === null || _k === void 0 ? void 0 : _k.replace('localhost', serverIP),
        FRONTEND_URL: (_l = env.FRONTEND_URL) === null || _l === void 0 ? void 0 : _l.replace('localhost', serverIP),
    };
    // 根据部署模式选择配置
    var actualConfig = {
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
        console.log("\u52A0\u8F7D\u73AF\u5883\u53D8\u91CF (DEPLOYMENT_MODE: ".concat(deploymentMode, ", SERVER_IP: ").concat(serverIP, "):"), __assign(__assign({}, actualConfig), { DEBUG_MODE: env.DEBUG_MODE, LOG_LEVEL: env.LOG_LEVEL }));
    }
    // 前端开发服务器端口，从实际配置URL提取
    var frontendUrl = actualConfig.FRONTEND_URL || 'http://localhost:3000';
    var frontendPort = getPortFromUrl(frontendUrl, 3000);
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
                    rewrite: function (path) { return path.replace(/^\/api/, ''); },
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
    };
});
