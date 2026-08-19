/**
 * 后端健康检查API
 * 检测各个服务是否启动并可用
 */

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

// 核心服务配置 - 仅检查关键服务，避免资源耗尽
const CORE_SERVICES = [
  { name: 'Gateway', url: 'http://localhost:8888', path: '/healthz' },
  { name: 'Auth', url: 'http://localhost:8007', path: '/healthz' },
  { name: 'LightRAG', url: 'http://localhost:8006', path: '/healthz' }
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
        'Accept': 'application/json',
        'X-Service-Discovery-Check': 'true'
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
 * 快速检查后端是否启动（只检查Gateway）
 */
export async function quickBackendCheck(): Promise<boolean> {
  try {
    // 只检查Gateway，避免过多请求
    const response = await fetch('http://localhost:8888/healthz', {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'X-Service-Discovery-Check': 'true'
      },
      signal: AbortSignal.timeout(3000) // 3秒超时
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * 简化的后端健康检查 - 只检查Gateway
 */
export async function checkBackendHealth(): Promise<BackendHealthStatus> {
  console.log('[Health Check] 执行简化健康检查（仅Gateway）');
  
  try {
    const gatewayStatus = await checkGatewayHealth();
    
    // 基于Gateway状态推断其他服务状态
    const mockServices: ServiceStatus[] = [
      { name: 'Auth', url: 'http://localhost:8007', status: gatewayStatus.status, response_time: 0 },
      { name: 'File', url: 'http://localhost:8004', status: gatewayStatus.status, response_time: 0 },
      { name: 'LightRAG', url: 'http://localhost:8006', status: gatewayStatus.status, response_time: 0 }
    ];
    
    // 计算整体状态
    const overall: BackendHealthStatus['overall'] = gatewayStatus.status === 'online' ? 'healthy' : 'offline';
    
    const result = {
      gateway: gatewayStatus,
      services: mockServices,
      overall,
      timestamp: new Date().toISOString()
    };
    
    console.log('[Health Check] 后端状态检查完成:', result);
    return result;
    
  } catch (error) {
    console.error('[Health Check] Gateway检查失败:', error);
    
    // 错误情况下返回离线状态
    const offlineGateway: ServiceStatus = {
      name: 'Gateway',
      url: 'http://localhost:8888',
      status: 'offline',
      error: error instanceof Error ? error.message : '检查失败'
    };
    
    const offlineServices: ServiceStatus[] = [
      { name: 'Auth', url: 'http://localhost:8007', status: 'offline', error: '无法连接' },
      { name: 'File', url: 'http://localhost:8004', status: 'offline', error: '无法连接' },
      { name: 'LightRAG', url: 'http://localhost:8006', status: 'offline', error: '无法连接' }
    ];
    
    return {
      gateway: offlineGateway,
      services: offlineServices,
      overall: 'offline',
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * 等待后端服务启动
 */
export async function waitForBackend(maxWaitTime = 60000, checkInterval = 10000): Promise<boolean> {
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
