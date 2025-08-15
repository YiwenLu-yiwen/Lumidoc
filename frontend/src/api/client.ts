import axios from 'axios';
import { mocked } from './mocks';
import { ProjectAccessLevel } from '@/context/AuthContext';

// 统一使用Gateway URL访问所有后端服务
const gatewayURL = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
const baseURL = gatewayURL;

// 从环境变量获取API前缀
const apiPrefix = import.meta.env.VITE_API_PREFIX || '/api';

// 打印所有环境变量，便于调试
console.log('[API Client] 环境变量:',{
  API_GATEWAY_URL: import.meta.env.VITE_API_GATEWAY_URL,
  PROJECT_SERVICE_URL: import.meta.env.VITE_PROJECT_SERVICE_URL,
  CHAT_SERVICE_URL: import.meta.env.VITE_CHAT_SERVICE_URL,
  RAG_SERVICE_URL: import.meta.env.VITE_RAG_SERVICE_URL,
  FILE_SERVICE_URL: import.meta.env.VITE_FILE_SERVICE_URL,
  DEBUG_MODE: import.meta.env.VITE_DEBUG_MODE,
  LOG_LEVEL: import.meta.env.VITE_LOG_LEVEL,
  API_PREFIX: import.meta.env.VITE_API_PREFIX
});

console.log('[API Client] 使用Gateway URL:', gatewayURL);
console.log('[API Client] 使用API前缀:', apiPrefix);
console.log('[API Client] 所有服务将通过Gateway统一访问');


// 添加mock拦截器
const addMockHandlers = () => {
  // 拦截获取项目权限的请求
  mocked.onGet(`${apiPrefix}/user_permissions/projects`).reply(() => {
    console.log('[模拟API] 拦截项目权限请求');
    
    // 获取存储在localStorage中的用户信息
    const userJson = localStorage.getItem('stp_user');
    if (!userJson) {
      console.log('[模拟API] 用户未登录，无法获取项目权限');
      return [401, { detail: '用户未登录' }];
    }
    
    let user;
    try {
      user = JSON.parse(userJson);
    } catch (e) {
      console.error('[模拟API] 解析用户数据失败:', e);
      return [500, { detail: '用户数据无效' }];
    }
    
    // 从实际存储的项目列表中构建权限数据
    const projectsJson = localStorage.getItem('stp_projects');
    let projects = [];
    try {
      if (projectsJson) {
        projects = JSON.parse(projectsJson);
      }
    } catch (e) {
      console.error('[模拟API] 解析项目数据失败:', e);
    }
    
    // 为每个项目构建一个权限记录，假设创建者是拥有者
    const userProjects = projects
      .filter((project: any) => project && project.id)
      .map((project: any) => ({
        project_id: project.id,
        // 假设所有已知项目用户都有查看权限，但只有自己创建的项目才有拥有者权限
        // 这里使用一个简单规则：ID包含用户ID的视为用户创建
        access_level: project.creator_id === user.id ? 
          ProjectAccessLevel.OWNER : ProjectAccessLevel.VIEWER
      }));
    
    console.log('[模拟API] 返回模拟的项目权限:', userProjects);
    return [200, userProjects];
  });
};

// 判断是否启用模拟API
const useMockApi = import.meta.env.VITE_USE_MOCK_API === 'true';

// 从环境变量获取超时配置，或使用默认值
const getTimeoutFromEnv = (timeoutEnvVar: keyof ImportMetaEnv, defaultValue: number): number => {
  const envValue = import.meta.env[timeoutEnvVar];
  if (envValue && !isNaN(Number(envValue))) {
    return Number(envValue);
  }
  return defaultValue;
};

// 默认API超时设置（毫秒）
const DEFAULT_TIMEOUT = getTimeoutFromEnv('VITE_API_DEFAULT_TIMEOUT', 60000);

// Create axios instance with auth interceptor
export const apiClient = axios.create({
  baseURL,
  timeout: DEFAULT_TIMEOUT, // 使用环境变量或默认超时时间
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  },
  // 明确告诉axios不要发送cookie，避免CORS问题
  withCredentials: false,
  // 设置验证状态码
  validateStatus: (status) => status >= 200 && status < 500, // 只有状态码大于500才被视为错误
  // 确保响应类型为json，避免HTML响应导致的解析错误
  responseType: 'json',
  // 添加请求拦截器，确保请求的响应类型为json
  transformRequest: [
    function(data, headers) {
      if(headers && !headers['Accept']) {
        headers['Accept'] = 'application/json';
      }
      if(data && typeof data === 'object') {
        return JSON.stringify(data);
      }
      return data;
    }
  ],
  // 添加响应拦截器，预处理响应数据
  transformResponse: [
    function(data) {
      // 打印原始响应数据类型，帮助调试
      console.log('[API Client] 响应数据类型:', typeof data);
      
      // 如果响应是字符串且以<!DOCTYPE开头，说明是HTML而非JSON
      if(typeof data === 'string' && data.trim().startsWith('<!DOCTYPE')) {
        console.error('[API Client] 接收到HTML响应而非JSON, 可能是跨域问题或后端错误');
        // 返回一个错误对象作为响应数据
        return { error: true, message: 'Received HTML instead of JSON', htmlResponse: true };
      }
      
      // 尝试解析字符串响应
      if(typeof data === 'string' && data.trim().length > 0) {
        try {
          console.log('[API Client] 尝试解析字符串响应');
          return JSON.parse(data);
        } catch (e) {
          console.error('[API Client] 解析响应数据失败:', e);
          // 返回原始数据，让axios继续处理
        }
      }
      
      return data;
    }
  ]
});

// 请求拦截器：统一通过Gateway访问所有服务
apiClient.interceptors.request.use((config) => {
  console.log(`[API Client] 通过Gateway发送请求: ${config.method?.toUpperCase()} ${config.url}`);
  
  // RAG服务路径处理：/rag/* -> /lightrag/*（匹配Gateway配置）
  // 修复：避免对已经包含lightrag的URL再次替换
  if (config.url?.includes('/rag/') && !config.url?.includes('/lightrag/')) {
    config.url = config.url.replace('/rag/', '/lightrag/');
    console.log(`[API Client] RAG请求路径已调整为Gateway路径: ${config.url}`);
  }
  
  // 如果URL不是以/api/开头，不是完整的http URL，不是LightRAG请求，也不是以/file/开头的文件服务请求，则添加API前缀
  if (config.url && !config.url.startsWith('/api/') && !config.url.startsWith('http') && !config.url.startsWith('/lightrag/') && !config.url.startsWith('/file/')) {
    config.url = `${apiPrefix}${config.url.startsWith('/') ? '' : '/'}${config.url}`;
    console.log(`[API Client] 添加API前缀: ${config.url}`);
  }
  
  // 请求URL字符串
  const url = config.url || '';
  
  // 为不同类型的请求设置不同的超时时间
  if (url.includes('/user_permissions/projects')) {
    // 项目权限请求 - 缩短超时时间，避免用户等待过长
    console.log(`[API Client] 设置项目权限请求超时时间: 5000ms`);
    config.timeout = 5000; // 5秒
  } else if (url.includes('/projects')) {
    // 项目相关请求
    console.log(`[API Client] 设置项目请求超时时间: 8000ms`);
    config.timeout = 8000; // 8秒
  } else if (url.includes('/auth/')) {
    // 认证相关请求
    console.log(`[API Client] 设置认证请求超时时间: 8000ms`);
    config.timeout = 8000;
  } else {
    // 其他请求使用默认超时
    config.timeout = 15000;
  }
  
  return config;
});


// 维护已知的无效请求路径列表，避免多次触发登出
const invalidRequestPaths = new Set<string>();

// 检查是否应该忽略401错误而不触发重定向
const shouldIgnore401 = (url: string | undefined): boolean => {
  // 如果URL未定义，不忽略
  if (!url) return false;
  
  // 忽略清空聊天历史和一些不重要的API
  return url.includes('/chat/history/') || 
         url.includes('/auth/') ||
         url.includes('/health') ||
         url.includes('/user_permissions/projects') || // 添加权限检查API，避免循环重定向
         url.includes('/api/projects/'); // 添加项目API，避免循环重定向
};


// 验证token是否为合法JWT格式
const isValidJWT = (token: string): boolean => {
  if (!token) return false;
  
  // 去除Bearer前缀
  if (token.startsWith('Bearer ')) {
    token = token.substring(7);
  }
  
  // JWT由三部分组成，用.分隔
  const parts = token.split('.');
  if (parts.length !== 3) {
    return false;
  }
  
  // 每部分应该是Base64URL编码
  try {
    // 不实际解码，只检查格式
    return parts.every(part => {
      return /^[A-Za-z0-9_-]+$/g.test(part);
    });
  } catch (e) {
    return false;
  }
};

// 检查并清理无效的token
const checkAndCleanToken = () => {
  const token = localStorage.getItem('stp_token');
  if (token && !isValidJWT(token)) {
    console.warn('[API Client] 检测到无效的令牌格式，将清除本地存储');
    localStorage.removeItem('stp_token');
    localStorage.removeItem('stp_user');
    return null;
  }
  return token;
};

// Add auth interceptor
apiClient.interceptors.request.use((config) => {
  try {
    // 记录请求信息
    console.log(`[API Client] 发送请求: ${config.method?.toUpperCase()} ${config.url}`);
    
    // 首先检查并清理无效token
    let token = checkAndCleanToken();
    
    // 确保令牌格式正确 - 检查是否为RS256格式（应该包含两个点）
    if (token) {
      // 检查令牌是否已包含Bearer前缀，如果有则去除
      if (token.startsWith('Bearer ')) {
        token = token.substring(7);
      }
      
      // 检查令牌格式 - RS256令牌应该有两个点分隔的段
      if (!token.includes('.') || token.split('.').length < 3) {
        console.error('[API Client] 令牌格式不正确，可能不是有效的JWT');
      }
      
      // 截取token部分显示以避免整个token暴露在日志中
      const tokenPreview = token.substring(0, 10) + '...';
      console.log(`[API Client] 添加Authorization头到 ${config.url}: Bearer ${tokenPreview}`);
      
      // 确保headers对象存在
      config.headers = config.headers || {};
      
      // 设置Authorization头，确保格式正确 - 总是添加Bearer前缀
      config.headers['Authorization'] = `Bearer ${token}`;
      
      // 添加防缓存头，确保请求不被缓存
      if (config.method?.toLowerCase() === 'get') {
        config.headers['Cache-Control'] = 'no-cache, no-store';
        config.headers['Pragma'] = 'no-cache';
      }
      
      // 检查和记录所有请求头
      const headersLog = Object.keys(config.headers).map(key => 
        `${key}: ${key.toLowerCase() === 'authorization' 
          ? 'Bearer ' + tokenPreview 
          : String(config.headers[key])}`
      );
      console.log(`[API Client] 请求头: ${headersLog.join(', ')}`);
    } else {
      // 如果是认证相关的路径，不显示警告
      if (!config.url?.includes('/auth/')) {
        console.warn(`[API Client] 请求 ${config.url} 没有找到token`);
      }
    }
    
    return config;
  } catch (error) {
    console.error('[API Client] 添加token时出错:', error);
    return config;
  }
}, (error) => {
  console.error('[API Client] 请求拦截器错误:', error);
  return Promise.reject(error);
});

// 解析cookie获取新令牌
const getTokenFromCookie = (): string | null => {
  const cookies = document.cookie.split(';');
  for (let i = 0; i < cookies.length; i++) {
    const cookie = cookies[i].trim();
    if (cookie.startsWith('access_token=')) {
      const value = cookie.substring('access_token='.length);
      // 检查是否以'Bearer '开头，如果是，去除它
      return value.startsWith('Bearer ') ? value.substring(7) : value;
    }
  }
  return null;
};

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    // 只记录非健康检查的请求
    if (!response.config.url?.includes('/health')) {
      console.log(`[API Client] 请求成功: ${response.config.method?.toUpperCase()} ${response.config.url} - 状态码: ${response.status}`);
    }
    
    // 检查cookie中是否有新的token（服务器刷新的）
    const newToken = getTokenFromCookie();
    if (newToken) {
      // 验证新token是否有效
      if (isValidJWT(newToken)) {
        // 从cookie中删除token，防止泄露
        document.cookie = 'access_token=; Max-Age=0; path=/; sameSite=lax;';
        
        // 更新localStorage中的token
        localStorage.setItem('stp_token', newToken);
        console.log('[API Client] 检测到token更新，已更新本地存储');
      } else {
        console.error('[API Client] 从cookie获取的token无效，忽略');
      }
    }
    
    return response;
  },
  (error) => {
    // 如果请求被取消，不记录错误
    if (axios.isCancel(error)) {
      console.log('[API Client] 请求被取消');
      return Promise.reject(error);
    }
    
    const requestInfo = error.config ? 
      `${error.config.method?.toUpperCase()} ${error.config.url}` : 
      '未知请求';
    
    // 如果是超时错误，简化错误处理
    if (error.code === 'ECONNABORTED') {
      console.warn(`[API Client] 请求超时: ${requestInfo}`);
      return Promise.reject(error);
    }
    
    console.error(`[API Client] 请求失败: ${requestInfo}`);
    
    // 处理401未授权错误
    if (error.response?.status === 401) { 
      console.error('[API Client] 接收到401未授权错误, URL:', error.config?.url);
      
      // 如果这个请求路径应该被忽略，不触发登出
      if (shouldIgnore401(error.config?.url)) {
        console.warn(`[API Client] 忽略此路径的401错误: ${error.config?.url}`);
        // 直接返回错误，不触发任何重定向
        return Promise.reject(error);
      }
      
      // 记录此无效请求路径
      if (error.config?.url) {
        invalidRequestPaths.add(error.config.url);
      }
      
      // 检查令牌是否有效
      const token = localStorage.getItem('stp_token');
      const isTokenValid = token && isValidJWT(token);
      
      // 如果令牌无效或不存在，直接清除
      if (!isTokenValid) {
        console.warn('[API Client] 检测到无效令牌或令牌不存在，执行清理');
        localStorage.removeItem('stp_token');
        localStorage.removeItem('stp_user');
        
        // 直接跳转到首页，不显示确认对话框
        if (window.location.pathname !== '/' && window.location.pathname !== '/login') {
          console.log('[API Client] 跳转到首页');
          window.location.href = '/';
          return new Promise(() => {});  // 挂起当前请求
        }
      }
    } else {
      // 记录其他错误
      console.error('[API Client] API错误 (非401):', {
        url: error.config?.url,
        method: error.config?.method,
        status: error.response?.status,
        data: error.response?.data,
        message: error.message
      });
    }
    
    return Promise.reject(error);
  }
);

// 如果启用模拟API，添加模拟处理程序
if (useMockApi) {
  console.log('[API Client] 已启用模拟API');
  addMockHandlers();
} 