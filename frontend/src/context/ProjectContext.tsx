import React, { createContext, useContext, useState, useEffect } from 'react';
import { Project } from '@/api/project';
import { useAuth } from '@/context/AuthContext';

interface ProjectContextType {
  projects: Project[];
  loading: boolean;
  error: string | null;
  apiStatus: string;
  refreshProjects: () => Promise<void>;
  lastErrorDetail: any;  // 添加详细错误信息
}

const ProjectContext = createContext<ProjectContextType>({
  projects: [],
  loading: false,
  error: null,
  apiStatus: '',
  refreshProjects: async () => {},
  lastErrorDetail: null,
});

export const useProjects = () => useContext(ProjectContext);

// 用于保存项目的固定顺序
const PROJECT_ORDER_KEY = 'stp_projects_order';

// 获取保存的项目顺序
const getSavedProjectOrder = (): Record<string, number> => {
  try {
    const savedOrder = localStorage.getItem(PROJECT_ORDER_KEY);
    if (savedOrder) {
      return JSON.parse(savedOrder);
    }
  } catch (e) {
    console.error('[ProjectContext] 读取项目顺序失败:', e);
  }
  return {};
};

// 保存项目顺序
const saveProjectOrder = (projects: Project[]) => {
  try {
    // 创建项目ID到顺序索引的映射
    const orderMap: Record<string, number> = {};
    projects.forEach((project, index) => {
      orderMap[project.id] = index;
    });
    localStorage.setItem(PROJECT_ORDER_KEY, JSON.stringify(orderMap));
    console.log('[ProjectContext] 项目顺序已保存:', orderMap);
  } catch (e) {
    console.error('[ProjectContext] 保存项目顺序失败:', e);
  }
};

// 根据保存的顺序对项目列表进行排序
const sortProjectsByOrder = (projects: Project[]): Project[] => {
  const orderMap = getSavedProjectOrder();
  
  // 如果没有保存的顺序或为空，直接返回原始项目列表
  if (Object.keys(orderMap).length === 0) {
    return [...projects];
  }
  
  // 对项目进行排序
  return [...projects].sort((a, b) => {
    // 如果两个项目都有保存的顺序，按顺序排序
    if (a.id in orderMap && b.id in orderMap) {
      return orderMap[a.id] - orderMap[b.id];
    }
    // 如果只有a有保存的顺序，a排在前面
    if (a.id in orderMap) {
      return -1;
    }
    // 如果只有b有保存的顺序，b排在前面
    if (b.id in orderMap) {
      return 1;
    }
    // 如果都没有保存的顺序，按创建时间排序
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  });
};

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState('');
  const [lastErrorDetail, setLastErrorDetail] = useState<any>(null);
  const { user, token, logout } = useAuth();

  const refreshProjects = async () => {
    // 防抖处理：检查是否正在加载中，避免重复调用
    if (loading) {
      console.log('[ProjectContext] 已经在加载项目列表，忽略重复请求');
      return;
    }
    
    // 优先使用来自 AuthContext 的 token
    const activeToken = token;
    const contextUser = user;
    
    if (!contextUser || !activeToken) {
      console.log('[ProjectContext] 用户未登录或没有token，清除项目列表');
      setProjects([]); // 确保在未登录时清空项目
      setApiStatus('用户未登录');
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      setLastErrorDetail(null);
      setApiStatus('正在加载项目列表...');
      console.log('[ProjectContext] 开始加载项目列表，当前用户:', 
                  contextUser.username, '(ID:', contextUser.id, ')');
      console.log('[ProjectContext] 使用token (前20位):', 
        activeToken ? activeToken.substring(0, 20) + '...' : '无token');
      
      // 创建请求控制器用于超时处理
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30秒超时
      
      // 统一通过Gateway访问项目服务
      const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
      const requestUrl = `${gatewayUrl}/api/projects/`;
      console.log('[ProjectContext] 通过Gateway请求项目列表:', requestUrl);
      
      // 如果缓存中有项目列表，先显示缓存数据
      try {
        const cachedProjects = localStorage.getItem('stp_projects');
        if (cachedProjects) {
          const parsedProjects = JSON.parse(cachedProjects);
          if (Array.isArray(parsedProjects) && parsedProjects.length > 0) {
            console.log('[ProjectContext] 使用缓存的项目列表:', parsedProjects.length);
            // 使用保存的顺序对缓存的项目进行排序
            const sortedProjects = sortProjectsByOrder(parsedProjects);
            setProjects(sortedProjects);
            setApiStatus(`使用缓存数据: ${parsedProjects.length} 个项目`);
          }
        }
      } catch (e) {
        console.error('[ProjectContext] 读取项目缓存失败:', e);
      }
      
      // 直接请求后端API，指定信号和模式
      const response = await fetch(requestUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${activeToken}`
        },
        signal: controller.signal,
        mode: 'cors', // 明确指定CORS模式
        credentials: 'same-origin' // 不发送cookie
      });
      
      // 清除超时
      clearTimeout(timeoutId);
      
      console.log('[ProjectContext] 项目列表请求响应:', response.status, response.statusText);
      setApiStatus(`API状态: ${response.status} ${response.statusText}`);
      
      if (!response.ok) {
        let errorDetail = '';
        let errorData = null;
        try {
          errorData = await response.json();
          console.error('[ProjectContext] 错误响应:', errorData);
          errorDetail = errorData.detail || JSON.stringify(errorData);
          setLastErrorDetail(errorData);
        } catch (e) {
          errorDetail = await response.text();
          console.error('[ProjectContext] 错误响应文本:', errorDetail);
          setLastErrorDetail({ text: errorDetail });
        }
        
        if (response.status === 401) {
          // === 关键修改 ===
          // 认证失败，调用 AuthContext 的 logout 处理
          console.error('[ProjectContext] 认证失败 (401)，调用 logout...');
          logout(); // 使用 AuthContext 的 logout 来统一处理
        } else if (response.status === 500) {
          setError(`服务器内部错误: ${errorDetail}`);
          console.error('[ProjectContext] 服务器内部错误:', errorDetail);
          
          // 使用缓存项目，不影响用户体验
          const cachedProjects = localStorage.getItem('stp_projects');
          if (cachedProjects) {
            try {
              const projects = JSON.parse(cachedProjects);
              console.log('[ProjectContext] 服务器错误，使用缓存项目列表');
              // 使用保存的顺序对缓存的项目进行排序
              const sortedProjects = sortProjectsByOrder(projects);
              setProjects(sortedProjects);
              setError('服务器暂时不可用，显示缓存数据');
            } catch (e) {
              console.error('[ProjectContext] 解析缓存项目失败:', e);
            }
          }
        } else {
          // 对于其他非 401, 500 的错误
          setError(`获取项目列表失败: ${response.status} ${errorDetail}`);
          
          // 同样尝试使用缓存
          const cachedProjects = localStorage.getItem('stp_projects');
          if (cachedProjects) {
            try {
              const projects = JSON.parse(cachedProjects);
              console.log('[ProjectContext] 请求失败，使用缓存项目列表');
              // 使用保存的顺序对缓存的项目进行排序
              const sortedProjects = sortProjectsByOrder(projects);
              setProjects(sortedProjects);
            } catch (e) {
              console.error('[ProjectContext] 解析缓存项目失败:', e);
            }
          }
        }
        setLoading(false);
        return; // 错误处理后直接返回
      }
      
      // 请求成功
      const data = await response.json();
      if (Array.isArray(data)) {
        // 获取新项目列表后，保存当前项目顺序（如果没有保存过）
        const currentOrder = getSavedProjectOrder();
        const newProjects = data;
        
        // 如果是首次加载项目或有新项目，更新项目顺序
        if (Object.keys(currentOrder).length === 0 || 
            newProjects.some(project => !(project.id in currentOrder))) {
          saveProjectOrder(newProjects);
        }
        
        // 使用保存的顺序对新获取的项目进行排序
        const sortedProjects = sortProjectsByOrder(newProjects);
        setProjects(sortedProjects);
        setApiStatus(`成功加载了 ${data.length} 个项目`);
        console.log('[ProjectContext] 成功加载项目列表，数量:', data.length);
        
        // 保存到本地存储作为缓存
        try {
          localStorage.setItem('stp_projects', JSON.stringify(data));
          console.log('[ProjectContext] 项目列表已缓存到本地存储');
        } catch (e) {
          console.error('[ProjectContext] 缓存项目列表失败:', e);
        }
      } else {
        console.error('[ProjectContext] API返回的项目列表不是数组:', data);
        setError('获取到的项目列表格式不正确');
      }
    } catch (err: any) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        console.error('[ProjectContext] 请求超时');
        setError('请求超时，请稍后重试');
      } else {
        // 网络错误或其他fetch错误
        console.error('[ProjectContext] 加载项目失败 (catch):', err);
        setError(err.message || '加载项目时发生网络错误');
      }
      setApiStatus(`加载失败: ${err.message}`);
      setLastErrorDetail(err);
      
      // 网络错误时也尝试使用缓存数据
      const cachedProjects = localStorage.getItem('stp_projects');
      if (cachedProjects) {
        try {
          const projects = JSON.parse(cachedProjects);
          console.log('[ProjectContext] 网络错误，使用缓存项目列表');
          // 使用保存的顺序对缓存的项目进行排序
          const sortedProjects = sortProjectsByOrder(projects);
          setProjects(sortedProjects);
          setError((prevError) => prevError + ' (显示缓存数据)');
        } catch (e) {
          console.error('[ProjectContext] 解析缓存项目失败:', e);
          setProjects([]);
        }
      } else {
        setProjects([]);
      }
    } finally {
      setLoading(false);
    }
  };

  // 当用户状态变化时刷新项目列表 - 保持不变
  useEffect(() => {
    console.log('[ProjectContext] 用户状态或 Token 变化，用户:', user?.username, 'Token存在:', !!token);
    if (user && token) {
      refreshProjects();
    } else {
      // 用户登出或初始加载时 token/user 不存在，清除项目状态
      setProjects([]);
      setApiStatus('用户未登录');
      setError(null);
      setLastErrorDetail(null);
    }
  }, [user, token]); // 保持依赖项

  return (
    <ProjectContext.Provider value={{ 
      projects, 
      loading, 
      error, 
      apiStatus, 
      refreshProjects, 
      lastErrorDetail 
    }}>
      {children}
    </ProjectContext.Provider>
  );
}; 