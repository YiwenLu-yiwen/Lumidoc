/**
 * 后端健康检查API
 * 检测各个服务是否启动并可用
 */

import { apiClient } from './client';

export interface ServiceStatus {
  name: string;
  url: string;
  status: 'online' | 'offline' | 'unknown';
  response_time?: number;
  error?: string;
}

export interface BackendHealthStatus {
  gateway: ServiceStatus;
  services: ServiceStatus[];
  overall: 'healthy' | 'degraded' | 'offline';
  timestamp: string;
}

// 核心服务配置
const CORE_SERVICES = [
  { name: 'Gateway', url: 'http://localhost:8888', path: '/health' },
  { name: 'Auth', url: 'http://localhost:8007', path: '/health' },
  { name: 'Backend', url: 'http://localhost:8000', path: '/health' },
  { name: 'File', url: 'http://localhost:8004', path: '/health' },
  { name: 'FileProc', url: 'http://localhost:8005', path: '/health' },
  { name: 'LightRAG', url: 'http://localhost:8006', path: '/health' },
  { name: 'Graph', url: 'http://localhost:8003', path: '/health' },
  { name: 'Chat', url: 'http://localhost:8001', path: '/health' },
  { name: 'Question', url: 'http://localhost:8002', path: '/health' },
  { name: 'Monitoring', url: 'http://localhost:8008', path: '/health' },
  { name: 'Project', url: 'http://localhost:8020', path: '/health' },
  { name: 'LLM', url: 'http://localhost:8080', path: '/health' }
];

/**
 * 检查单个服务健康状态
 */
async function checkServiceHealth(service: typeof CORE_SERVICES[0]): Promise<ServiceStatus> {
  const startTime = Date.now();
  
  try {
    // 创建带超时的fetch Promise
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5秒超时
    
    const response = await fetch(`${service.url}${service.path}`, {
      method: 'GET',
      signal: controller.signal,
      headers: {
        'Accept': 'application/json'
      }
    });
    
    clearTimeout(timeoutId);
    const responseTime = Date.now() - startTime;
    
    if (response.ok) {
      return {
        name: service.name,
        url: service.url,
        status: 'online',
        response_time: responseTime
      };
    } else {
      return {
        name: service.name,
        url: service.url,
        status: 'offline',
        response_time: responseTime,
        error: `HTTP ${response.status}`
      };
    }
  } catch (error) {
    const responseTime = Date.now() - startTime;
    
    let errorMessage = '连接失败';
    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        errorMessage = '请求超时';
      } else {
        errorMessage = error.message;
      }
    }
    
    return {
      name: service.name,
      url: service.url,
      status: 'offline',
      response_time: responseTime,
      error: errorMessage
    };
  }
}

/**
 * 检查Gateway是否可用
 */
export async function checkGatewayHealth(): Promise<ServiceStatus> {
  const gateway = CORE_SERVICES.find(s => s.name === 'Gateway');
  if (!gateway) {
    return {
      name: 'Gateway',
      url: 'http://localhost:8888',
      status: 'offline',
      error: '配置错误'
    };
  }
  
  return await checkServiceHealth(gateway);
}

/**
 * 快速检查后端是否启动（只检查Gateway和Backend）
 */
export async function quickBackendCheck(): Promise<boolean> {
  try {
    const gatewayStatus = await checkGatewayHealth();
    return gatewayStatus.status === 'online';
  } catch {
    return false;
  }
}

/**
 * 全面的后端健康检查
 */
export async function checkBackendHealth(): Promise<BackendHealthStatus> {
  console.log('[Health Check] 开始检查后端服务状态');
  
  // 并发检查所有服务
  const servicePromises = CORE_SERVICES.map(service => checkServiceHealth(service));
  const serviceStatuses = await Promise.all(servicePromises);
  
  // 分离Gateway和其他服务
  const gatewayStatus = serviceStatuses.find(s => s.name === 'Gateway') || {
    name: 'Gateway',
    url: 'http://localhost:8888',
    status: 'offline' as const,
    error: '未找到Gateway状态'
  };
  
  const otherServices = serviceStatuses.filter(s => s.name !== 'Gateway');
  
  // 计算整体状态
  const onlineCount = serviceStatuses.filter(s => s.status === 'online').length;
  const totalCount = serviceStatuses.length;
  
  let overall: 'healthy' | 'degraded' | 'offline';
  if (gatewayStatus.status === 'offline') {
    overall = 'offline'; // Gateway离线则整体离线
  } else if (onlineCount === totalCount) {
    overall = 'healthy';
  } else if (onlineCount >= totalCount * 0.7) {
    overall = 'degraded'; // 70%以上服务在线视为降级
  } else {
    overall = 'offline';
  }
  
  const result = {
    gateway: gatewayStatus,
    services: otherServices,
    overall,
    timestamp: new Date().toISOString()
  };
  
  console.log('[Health Check] 后端状态检查完成:', result);
  return result;
}

/**
 * 等待后端服务启动
 */
export async function waitForBackend(maxWaitTime = 60000, checkInterval = 2000): Promise<boolean> {
  console.log('[Health Check] 等待后端服务启动...');
  
  const startTime = Date.now();
  
  while (Date.now() - startTime < maxWaitTime) {
    const isOnline = await quickBackendCheck();
    if (isOnline) {
      console.log('[Health Check] 后端服务已启动');
      return true;
    }
    
    console.log('[Health Check] 后端未就绪，继续等待...');
    await new Promise(resolve => setTimeout(resolve, checkInterval));
  }
  
  console.log('[Health Check] 等待后端服务超时');
  return false;
}