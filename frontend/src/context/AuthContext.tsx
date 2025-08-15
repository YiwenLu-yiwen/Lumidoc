// 导出用户角色和项目权限枚举放在最上方，避免循环依赖
export enum UserRole {
  ADMIN = "admin",
  USER = "user",
  GUEST = "guest"
}

// 定义项目访问权限类型
export enum ProjectAccessLevel {
  OWNER = "owner",     // 可以做所有操作，包括删除项目
  EDITOR = "editor",   // 可以编辑、上传和删除文件
  VIEWER = "viewer",   // 只能查看文件
  NONE = "none"        // 无权限
}

// 导入放在枚举之后，避免循环引用
import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import axios, { AxiosResponse, AxiosError } from 'axios';

interface User {
  id: string;
  username: string;
  nickname: string;
  role?: UserRole;  // 用户角色
  projects?: Record<string, ProjectAccessLevel>;  // 用户拥有的项目权限
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (user: User, token: string) => void;
  logout: () => void;
  refreshToken: () => Promise<void>;
  getToken: () => string | null;
  isAuthenticated: boolean;
  hasProjectAccess: (projectId: string, requiredLevel?: ProjectAccessLevel) => boolean;
  getUserRole: () => UserRole;
  isAdmin: () => boolean;
  updateUserProjectAccess: (projectId: string, accessLevel: ProjectAccessLevel) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const USER_KEY = 'stp_user';
const TOKEN_KEY = 'stp_token';

// 配置全局HTTP请求拦截器
const setupAxiosInterceptors = (logout: () => void) => {
  axios.interceptors.response.use(
    (response: AxiosResponse) => response,
    (error: AxiosError) => {
      // 当响应状态码为401（未授权）时，表示token可能已过期或无效
      if (error.response && error.response.status === 401) {
        console.warn('收到401错误响应，用户认证无效或已过期');
        // 特殊处理：如果错误发生在特定请求中，则不自动跳转
        const isSpecialRequest = error.config && 
          (error.config.url?.includes('/chat/history') || 
           error.config.url?.includes('/api/auth'));
        
        if (!isSpecialRequest) {
          // 清除状态并重定向到登录页面
          logout();
        }
      }
      return Promise.reject(error);
    }
  );
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const u = localStorage.getItem(USER_KEY);
    return u ? JSON.parse(u) : null;
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!token);

  // 组件渲染性能优化：使用useRef避免不必要的re-render
  const projectPermissionsRef = useRef<Record<string, ProjectAccessLevel>>({});
  
  // 初始化函数：一次性读取所有缓存数据
  useEffect(() => {
    // 初始化时检查localStorage中的token
    const storedToken = localStorage.getItem('stp_token');
    if (storedToken) {
      // 添加防止重复初始化的标志
      if ((window as any).__authInitialized) {
        console.log('[AuthContext] 已初始化，跳过重复初始化');
        return;
      }
      
      try {
        const storedUser = localStorage.getItem('stp_user');
        if (storedUser) {
          const userData = JSON.parse(storedUser);
          console.log('[AuthContext] 恢复用户状态:', userData.username);
          
          // 设置用户状态
          setUser(userData);
          setToken(storedToken);
          setIsAuthenticated(true);
          
          // 尝试读取项目权限
          const storedPermissions = localStorage.getItem('stp_project_permissions');
          if (storedPermissions) {
            try {
              const permissions = JSON.parse(storedPermissions);
              console.log('[AuthContext] 从localStorage读取项目权限数据');
              
              // 更新引用，避免触发状态更新
              projectPermissionsRef.current = permissions;
              
              // 将权限数据添加到用户对象
              setUser((prev: User | null) => {
                if (!prev) return userData;
                return {
                  ...prev,
                  projects: permissions
                };
              });
            } catch (e) {
              console.error('[AuthContext] 解析项目权限数据失败:', e);
            }
          }
          
          // 设置初始化标志
          (window as any).__authInitialized = true;
        }
      } catch (e) {
        console.error('[AuthContext] 初始化用户状态时出错:', e);
        // 出错时清除缓存
        localStorage.removeItem('stp_token');
        localStorage.removeItem('stp_user');
      }
    }
  }, []);
  
  // 更新用户项目访问权限的功能
  const updateUserProjectAccess = useCallback((
    projectId: string,
    accessLevel: ProjectAccessLevel
  ) => {
    if (!projectId || !accessLevel) return;
    
    // 首先更新引用
    projectPermissionsRef.current[projectId] = accessLevel;
    
    // 更新localStorage，但不触发重渲染
    try {
      localStorage.setItem('stp_project_permissions', JSON.stringify(projectPermissionsRef.current));
    } catch (e) {
      console.error('[AuthContext] 保存项目权限到localStorage失败:', e);
    }
    
    // 最后才更新状态，减少渲染次数
    setUser((prevUser: User | null) => {
      if (!prevUser) return null;
      
      return {
        ...prevUser,
        projects: {
          ...(prevUser.projects || {}),
          [projectId]: accessLevel
        }
      };
    });
  }, []);

  // 登录时保存 user 和 token
  const login = (user: User, token: string) => {
    console.log('[AuthContext] 开始登录流程, user:', user, 'token:', token ? token.substring(0, 15) + '...' : 'null');
    
    try {
      // 清除现有数据，确保从干净状态开始
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(TOKEN_KEY);
      console.log('[AuthContext] 已清除现有存储数据');
      
      // 确保用户对象具有必要的字段
      const completeUser = {
        ...user,
        // 如果没有角色，则设置默认角色
        role: user.role || UserRole.USER,
        // 如果没有项目权限映射，则初始化为空对象
        projects: user.projects || {}
      };
      
      console.log('[AuthContext] 完整用户对象:', completeUser);
      
      // 直接保存到localStorage
      localStorage.setItem(USER_KEY, JSON.stringify(completeUser));
      localStorage.setItem(TOKEN_KEY, token);
      console.log('[AuthContext] 已将 User 和 Token 保存到 localStorage');

      // 验证保存
      const savedToken = localStorage.getItem(TOKEN_KEY);
      const savedUser = localStorage.getItem(USER_KEY);
      console.log('[AuthContext] 验证保存 - Token:', savedToken ? savedToken.substring(0, 15) + '...' : '保存失败', 
                   'User:', savedUser ? '已保存' : '保存失败');

      // 同步更新 React 状态
      setUser(completeUser);
      setToken(token);
      setIsAuthenticated(true);
      
      console.log('[AuthContext] 登录完成，React 状态已更新');

    } catch (error) {
      console.error('[AuthContext] 登录过程中出错 (保存或更新状态时):', error);
      // 可以在这里添加更具体的错误处理，比如清除状态
      setUser(null);
      setToken(null);
      setIsAuthenticated(false);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(TOKEN_KEY);
    }
  };

  // 登出时清除 user 和 token，并跳转首页
  const logout = useCallback(() => {
    console.log('[AuthContext] 用户登出');
    setUser(null);
    setToken(null);
    setIsAuthenticated(false);
    
    // 清空所有与Lumidoc相关的 localStorage 和 sessionStorage
    const stpKeys = [
      USER_KEY,
      TOKEN_KEY,
      'stp_project_permissions',
      'stp_projects',
      'stp_current_project'
    ];
    
    // 清除指定的键
    stpKeys.forEach(key => localStorage.removeItem(key));
    
    // 清空与项目相关的本地存储
    try {
      const keysToRemove = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.includes('project') || key.includes('stp_'))) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach(key => localStorage.removeItem(key));
      
      // 清除会话存储中的Lumidoc相关数据
      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        if (key && (key.includes('stp_') || key.includes('project'))) {
          sessionStorage.removeItem(key);
        }
      }
      
      console.log('[AuthContext] 已清理所有Lumidoc相关的存储数据');
    } catch (e) {
      console.error('[AuthContext] 清理本地存储出错:', e);
    }
    
    // 清空 IndexedDB（如有）
    if (window.indexedDB) {
      // 如有多个数据库名可列出
      const dbs = ['stp_db']; // 如有多个数据库名请补充
      dbs.forEach(dbName => {
        try {
          const req = window.indexedDB.deleteDatabase(dbName);
          req.onsuccess = () => console.log(`[AuthContext] 已删除IndexedDB: ${dbName}`);
          req.onerror = () => console.error(`[AuthContext] 删除IndexedDB失败: ${dbName}`);
          req.onblocked = () => console.warn(`[AuthContext] IndexedDB删除被阻止: ${dbName}`);
        } catch (e) {
          console.error(`[AuthContext] 删除IndexedDB出错: ${dbName}`, e);
        }
      });
    }
    
    // 直接跳转到首页，不使用setTimeout避免不必要的延迟
    window.location.href = '/';
  }, []);

  // 安装拦截器
  useEffect(() => {
    setupAxiosInterceptors(logout);
  }, [logout]);

  // 获取 token
  const getToken = useCallback(() => token, [token]);
  
  // 获取用户角色，默认为 GUEST
  const getUserRole = useCallback((): UserRole => {
    return user?.role || UserRole.GUEST;
  }, [user]);

  // 判断用户是否是管理员
  const isAdmin = useCallback((): boolean => {
    return getUserRole() === UserRole.ADMIN;
  }, [getUserRole]);
  
  // 判断用户是否有项目访问权限
  const hasProjectAccess = useCallback((projectId: string, requiredLevel: ProjectAccessLevel = ProjectAccessLevel.VIEWER): boolean => {
    // 管理员有所有项目的全部权限
    if (isAdmin()) {
      console.log(`[AuthContext] 用户是管理员，自动拥有项目(${projectId})的所有权限`);
      return true;
    }
    
    // 未登录用户没有任何权限
    if (!user || !projectId) {
      console.log(`[AuthContext] 用户未登录或项目ID为空，无权限访问项目(${projectId})`);
      return false;
    }
    
    // 特殊规则：增强判断用户是否与项目相关
    if (user.id) {
      // 检查项目ID和用户ID是否有关联
      if (projectId.includes(user.id) || user.id.includes(projectId) ||
          (user.username && projectId.includes(user.username)) ||
          (user.nickname && projectId.includes(user.nickname))) {
        console.log(`[AuthContext] 检测到用户相关的项目(${projectId})，自动授予所有者权限`);
        
        // 如果用户项目权限中没有此项目，添加权限
        if (!user.projects || !user.projects[projectId]) {
          updateUserProjectAccess(projectId, ProjectAccessLevel.OWNER);
        }
        
        return true;
      }
    }
    
    // 检查用户是否有特定项目的权限
    const userProjects = user.projects || {};
    
    const accessLevel = userProjects[projectId];
    
    // 如果用户没有此项目的权限记录，给予基本查看权限
    if (!accessLevel) {
      console.log(`[AuthContext] 用户(${user.username})没有项目(${projectId})的权限记录，授予基本查看权限`);
      updateUserProjectAccess(projectId, ProjectAccessLevel.VIEWER);
      return true;
    }
    
    // 权限等级判断
    let hasAccess = false;
    switch (requiredLevel) {
      case ProjectAccessLevel.OWNER:
        hasAccess = accessLevel === ProjectAccessLevel.OWNER;
        break;
      case ProjectAccessLevel.EDITOR:
        hasAccess = accessLevel === ProjectAccessLevel.OWNER || 
               accessLevel === ProjectAccessLevel.EDITOR;
        break;
      case ProjectAccessLevel.VIEWER:
        hasAccess = accessLevel === ProjectAccessLevel.OWNER || 
               accessLevel === ProjectAccessLevel.EDITOR || 
               accessLevel === ProjectAccessLevel.VIEWER;
        break;
      default:
        hasAccess = false;
    }
    
    console.log(`[AuthContext] 用户(${user.username})对项目(${projectId})的权限检查结果: ${hasAccess ? '有权访问' : '无权访问'}, 当前权限: ${accessLevel}, 需要权限: ${requiredLevel}`);
    return hasAccess;
  }, [user, isAdmin, updateUserProjectAccess]);

  // 刷新 token
  const refreshToken = useCallback(async (retryCount = 0) => {
    if (!token) return;
    try {
      console.log(`[AuthContext] 正在刷新token... (尝试 ${retryCount + 1}/3)`);
      const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
      const res = await fetch(`${gatewayUrl}/auth/api/refresh`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Token refresh failed: ${res.status}`);
      const data = await res.json();
      if (data.access_token) {
        console.log('[AuthContext] token刷新成功');
        setToken(data.access_token);
        localStorage.setItem(TOKEN_KEY, data.access_token);
      } else {
        throw new Error('No access token in response');
      }
    } catch (error) {
      console.error(`[AuthContext] token刷新失败 (尝试 ${retryCount + 1}/3):`, error);
      
      // 重试机制：最多重试3次
      if (retryCount < 2) {
        const delay = Math.pow(2, retryCount) * 1000; // 指数退避：1秒，2秒，4秒
        console.log(`[AuthContext] ${delay}ms后重试token刷新...`);
        setTimeout(() => {
          refreshToken(retryCount + 1);
        }, delay);
      } else {
        console.error('[AuthContext] token刷新重试次数已用尽，执行登出');
        logout();
      }
    }
  }, [token, logout]);

  // 检查token是否即将过期
  const checkTokenExpiration = useCallback(() => {
    if (!token) return;
    
    try {
      // 解析JWT token (不验证签名)
      const tokenParts = token.split('.');
      if (tokenParts.length !== 3) {
        console.warn('[AuthContext] 无效的JWT格式');
        return;
      }
      
      // 解码载荷部分
      const payload = JSON.parse(atob(tokenParts[1]));
      
      // 获取过期时间
      const exp = payload.exp * 1000; // 转换为毫秒
      const now = Date.now();
      
      // 计算剩余有效期（分钟）
      const remainingMinutes = (exp - now) / (1000 * 60);
      
      console.log(`[AuthContext] token剩余有效期: ${remainingMinutes.toFixed(2)}分钟`);
      
      // 如果剩余有效期小于60分钟，刷新token（提前到1小时）
      if (remainingMinutes < 60) {
        console.log('[AuthContext] token即将过期，正在刷新...');
        refreshToken();
      }
    } catch (error) {
      console.error('[AuthContext] 检查token过期时间出错:', error);
    }
  }, [token, refreshToken]);
  
  // 智能监控token过期时间
  useEffect(() => {
    if (!token) return;
    
    // 初始检查token
    checkTokenExpiration();
    
    // 设置定期检查
    const interval = setInterval(() => {
      checkTokenExpiration();
    }, 60 * 1000); // 每分钟检查一次
    
    // 为用户活动添加token刷新检查
    const activityEvents = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    
    // 防抖动处理，避免频繁检查
    let debounceTimeout: ReturnType<typeof setTimeout> | null = null;
    const handleUserActivity = () => {
      if (debounceTimeout) {
        clearTimeout(debounceTimeout);
      }
      debounceTimeout = setTimeout(() => {
        checkTokenExpiration();
      }, 5000); // 用户活动后5秒检查token
    };
    
    // 添加用户活动监听器
    activityEvents.forEach(event => {
      window.addEventListener(event, handleUserActivity);
    });
    
    return () => {
      clearInterval(interval);
      if (debounceTimeout) {
        clearTimeout(debounceTimeout);
      }
      activityEvents.forEach(event => {
        window.removeEventListener(event, handleUserActivity);
      });
    };
  }, [token, checkTokenExpiration]);

  // 页面可见性变化时检查token
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden && token) {
        console.log('[AuthContext] 页面变为可见，检查token状态');
        checkTokenExpiration();
      }
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [checkTokenExpiration, token]);

  return (
    <AuthContext.Provider value={{ 
      user, 
      token, 
      login, 
      logout, 
      refreshToken, 
      getToken,
      isAuthenticated,
      hasProjectAccess,
      getUserRole,
      isAdmin,
      updateUserProjectAccess
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
