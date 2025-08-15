/**
 * 生产环境安全日志工具
 * 只在开发环境输出日志，生产环境完全静默
 */

const isDevelopment = import.meta.env.VITE_DEBUG_MODE === 'true' && 
                     import.meta.env.VITE_DEPLOYMENT_MODE !== 'production';

export const logger = {
  log: (...args: any[]) => {
    if (isDevelopment) {
      console.log(...args);
    }
  },
  
  warn: (...args: any[]) => {
    if (isDevelopment) {
      console.warn(...args);
    }
  },
  
  error: (...args: any[]) => {
    if (isDevelopment) {
      console.error(...args);
    }
  },
  
  info: (...args: any[]) => {
    if (isDevelopment) {
      console.info(...args);
    }
  },
  
  debug: (...args: any[]) => {
    if (isDevelopment) {
      console.debug(...args);
    }
  }
};

// 在生产环境禁用所有console方法
if (!isDevelopment) {
  window.console.log = () => {};
  window.console.warn = () => {};
  window.console.error = () => {};
  window.console.info = () => {};
  window.console.debug = () => {};
}