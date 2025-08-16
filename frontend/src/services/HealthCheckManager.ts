/**
 * 全局健康检查管理器 - 单例模式
 * 确保整个应用只有一个健康检查实例运行
 */

import { checkBackendHealth, BackendHealthStatus } from '../api/health';

interface HealthCheckSubscriber {
  id: string;
  onHealthChange: (status: BackendHealthStatus | null) => void;
  onOnlineChange: (isOnline: boolean) => void;
}

class HealthCheckManager {
  private static instance: HealthCheckManager | null = null;
  private subscribers: HealthCheckSubscriber[] = [];
  private currentStatus: BackendHealthStatus | null = null;
  private isOnline: boolean | null = null;
  private isChecking: boolean = false;
  private checkInterval: number = 300000; // 5分钟
  private intervalId: NodeJS.Timeout | null = null;
  private lastCheckTime: number = 0;
  private enabled: boolean = false;

  private constructor() {
    console.log('[HealthCheckManager] 创建全局健康检查管理器实例');
  }

  static getInstance(): HealthCheckManager {
    if (!HealthCheckManager.instance) {
      HealthCheckManager.instance = new HealthCheckManager();
    }
    return HealthCheckManager.instance;
  }

  // 启用健康检查
  enable(checkInterval: number = 300000): void {
    if (this.enabled) {
      console.log('[HealthCheckManager] 健康检查已启用，跳过重复启用');
      return;
    }

    this.enabled = true;
    this.checkInterval = checkInterval;
    console.log(`[HealthCheckManager] 启用健康检查，间隔: ${checkInterval}ms (${checkInterval / 60000}分钟)`);

    // 立即执行一次检查
    this.performHealthCheck();

    // 启动定期检查
    this.startPeriodicCheck();
  }

  // 禁用健康检查
  disable(): void {
    this.enabled = false;
    this.stopPeriodicCheck();
    console.log('[HealthCheckManager] 健康检查已禁用');
  }

  // 订阅健康状态变化
  subscribe(subscriber: HealthCheckSubscriber): () => void {
    this.subscribers.push(subscriber);
    console.log(`[HealthCheckManager] 新增订阅者: ${subscriber.id}，当前订阅者数量: ${this.subscribers.length}`);

    // 立即通知当前状态
    if (this.currentStatus) {
      subscriber.onHealthChange(this.currentStatus);
    }
    if (this.isOnline !== null) {
      subscriber.onOnlineChange(this.isOnline);
    }

    // 返回取消订阅函数
    return () => {
      this.subscribers = this.subscribers.filter(s => s.id !== subscriber.id);
      console.log(`[HealthCheckManager] 移除订阅者: ${subscriber.id}，剩余订阅者数量: ${this.subscribers.length}`);
    };
  }

  // 手动执行健康检查
  async checkHealth(): Promise<BackendHealthStatus | null> {
    return await this.performHealthCheck();
  }

  // 获取当前状态
  getCurrentStatus(): { status: BackendHealthStatus | null; isOnline: boolean | null; lastCheckTime: number } {
    return {
      status: this.currentStatus,
      isOnline: this.isOnline,
      lastCheckTime: this.lastCheckTime
    };
  }

  // 执行健康检查
  private async performHealthCheck(): Promise<BackendHealthStatus | null> {
    if (this.isChecking) {
      console.log('[HealthCheckManager] 健康检查正在进行中，跳过重复检查');
      return this.currentStatus;
    }

    this.isChecking = true;
    console.log('[HealthCheckManager] 开始执行健康检查');

    try {
      const status = await checkBackendHealth();
      const wasOnline = this.isOnline;
      const newIsOnline = status.overall === 'healthy' || status.overall === 'degraded';

      this.currentStatus = status;
      this.isOnline = newIsOnline;
      this.lastCheckTime = Date.now();

      console.log(`[HealthCheckManager] 健康检查完成，状态: ${status.overall}, 在线: ${newIsOnline}`);

      // 通知所有订阅者
      this.notifySubscribers(status, newIsOnline);

      // 如果状态发生变化，记录日志
      if (wasOnline !== null && wasOnline !== newIsOnline) {
        console.log(`[HealthCheckManager] 后端状态变化: ${wasOnline ? '在线' : '离线'} -> ${newIsOnline ? '在线' : '离线'}`);
      }

      return status;
    } catch (error) {
      console.error('[HealthCheckManager] 健康检查失败:', error);
      
      const wasOnline = this.isOnline;
      this.isOnline = false;
      this.lastCheckTime = Date.now();

      // 通知订阅者离线状态
      if (wasOnline !== false) {
        this.notifyOnlineChange(false);
      }

      return null;
    } finally {
      this.isChecking = false;
    }
  }

  // 启动定期检查
  private startPeriodicCheck(): void {
    this.stopPeriodicCheck(); // 确保没有重复的定时器

    this.intervalId = setInterval(() => {
      if (this.enabled && !this.isChecking) {
        console.log('[HealthCheckManager] 执行定期健康检查');
        this.performHealthCheck();
      }
    }, this.checkInterval);

    console.log(`[HealthCheckManager] 定期检查已启动，间隔: ${this.checkInterval}ms`);
  }

  // 停止定期检查
  private stopPeriodicCheck(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
      console.log('[HealthCheckManager] 定期检查已停止');
    }
  }

  // 通知所有订阅者
  private notifySubscribers(status: BackendHealthStatus, isOnline: boolean): void {
    this.subscribers.forEach(subscriber => {
      try {
        subscriber.onHealthChange(status);
        subscriber.onOnlineChange(isOnline);
      } catch (error) {
        console.error(`[HealthCheckManager] 通知订阅者 ${subscriber.id} 失败:`, error);
      }
    });
  }

  // 通知在线状态变化
  private notifyOnlineChange(isOnline: boolean): void {
    this.subscribers.forEach(subscriber => {
      try {
        subscriber.onOnlineChange(isOnline);
      } catch (error) {
        console.error(`[HealthCheckManager] 通知订阅者 ${subscriber.id} 在线状态变化失败:`, error);
      }
    });
  }
}

export default HealthCheckManager;