import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ProjectProvider } from './context/ProjectContext'
import { ThemeProvider } from './context/ThemeContext'
import { AuthGuard } from './context/AuthGuard'
import { ProjectAccessLevel } from './context/authTypes'
import { BackendStatusWrapper } from './components/error/BackendStatusWrapper'
import { BackendOfflineError } from './components/error/BackendOfflineError'
import './index.css' // 确保全局样式生效
import { Toaster } from 'react-hot-toast'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'

const ProjectSelect = lazy(() => import('./features/project/ProjectSelect'))
const ChatGPTHomePage = lazy(() =>
  import('./components/home/ChatGPTHomePage').then((module) => ({
    default: module.ChatGPTHomePage,
  })),
)
const AuthPage = lazy(() =>
  import('./pages/AuthPage').then((module) => ({ default: module.AuthPage })),
)
const ErrorPage = lazy(() =>
  import('./pages/ErrorPage').then((module) => ({ default: module.ErrorPage })),
)
const MainApp = lazy(() =>
  import('./pages/MainApp').then((module) => ({ default: module.MainApp })),
)
const ModernDashboard = lazy(() =>
  import('./components/dashboard/ModernDashboard').then((module) => ({
    default: module.ModernDashboard,
  })),
)
const DocumentAnalysis = lazy(() =>
  import('./components/document/DocumentAnalysis').then((module) => ({
    default: module.DocumentAnalysis,
  })),
)
const ChatLayout = lazy(() => import('./features/chat/ChatLayout'))
const RagManager = lazy(() => import('./features/rag/RagManager'))
const SettingsPage = lazy(() =>
  import('./features/settings/SettingsPage').then((module) => ({
    default: module.SettingsPage,
  })),
)
const RouteFallback = () => (
  <div className="flex min-h-screen items-center justify-center bg-background text-foreground">
    <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary" />
    <span className="sr-only">正在加载页面</span>
  </div>
)

// 全局token检查组件
const TokenChecker: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [checking, setChecking] = useState(true);
  
  // 在组件加载时检查token
  useEffect(() => {
    const token = localStorage.getItem('lumidoc_token');
    
    if (token) {
      console.log('[TokenChecker] 发现已保存的token，长度:', token.length);
      
      // 立即设置为非检查状态，不使用setTimeout
      setChecking(false);
    } else {
      console.log('[TokenChecker] 未找到保存的token');
      setChecking(false);
    }
  }, []);

  if (checking) {
    console.log('[TokenChecker] 正在验证token...');
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#343541] text-white">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mb-4"></div>
          <p className="text-gray-300">正在加载...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};

// 企业级路由配置
const router = createBrowserRouter([
  // 首页路由
  {
    path: "/",
    element: <ChatGPTHomePage />,
    errorElement: <ErrorPage />
  },
  {
    path: "/webui",
    element: <Navigate to="/" replace />,
    errorElement: <ErrorPage />
  },
  {
    path: "/webui/",
    element: <Navigate to="/" replace />,
    errorElement: <ErrorPage />
  },
  
  // 认证页面路由
  {
    path: "/auth",
    element: <AuthPage />,
    errorElement: <ErrorPage />
  },
  {
    path: "/login",
    element: <Navigate to="/auth" replace />,
    errorElement: <ErrorPage />
  },
  
  // 主应用路由 - 企业级功能模块
  {
    path: "/app",
    element: (
      <AuthGuard>
        <MainApp />
      </AuthGuard>
    ),
    errorElement: <ErrorPage />,
    children: [
      {
        index: true,
        element: <Navigate to="/app/dashboard" replace />
      },
      {
        path: "dashboard",
        element: <ModernDashboard />,
        errorElement: <ErrorPage />
      },
      {
        path: "documents",
        element: <DocumentAnalysis />,
        errorElement: <ErrorPage />
      },
      {
        path: "projects",
        element: <ProjectSelect />,
        errorElement: <ErrorPage />
      },
      {
        path: "chat",
        element: <ChatLayout />,
        errorElement: <ErrorPage />
      },
      {
        path: "rag",
        element: <RagManager />,
        errorElement: <ErrorPage />
      },
      {
        path: "settings",
        element: <SettingsPage />,
        errorElement: <ErrorPage />
      },
      {
        path: "admin",
        element: <div>{typeof window !== 'undefined' && window.navigator.language.startsWith('zh') ? '管理员面板开发中...' : 'Admin panel under development...'}</div>,
        errorElement: <ErrorPage />
      },
      {
        path: "*",
        element: <ErrorPage />
      }
    ]
  },
  
  // 项目相关路由
  {
    path: "/project/:projectId",
    element: (
      <AuthGuard projectAccess requiredLevel={ProjectAccessLevel.VIEWER}>
        <MainApp />
      </AuthGuard>
    ),
    errorElement: <ErrorPage />
  },
  
  // 专门的错误页面路由
  {
    path: "/error",
    element: <ErrorPage />,
    errorElement: <ErrorPage />
  },
  
  // 后端离线错误页面路由（用于调试和直接访问）
  {
    path: "/backend-offline",
    element: <BackendOfflineError />,
    errorElement: <ErrorPage />
  },
  
  // 保留旧路由兼容性
  {
    path: "/projects",
    element: <Navigate to="/app/projects" replace />,
    errorElement: <ErrorPage />
  },
  
  // 捕获所有未匹配的路由
  {
    path: "*",
    element: <ErrorPage />
  }
]);

// 创建一个内部应用组件，在AuthProvider内部使用useAuth
const AppContent = () => {
  // 性能优化：添加防止循环导航的保护
  const navigationStateRef = useRef({
    lastPathname: '',
    redirectCount: 0,
    MAX_REDIRECTS: 3,
    timestamp: 0
  });
  
  // 启动时清除导航状态
  useEffect(() => {
    const navigationState = navigationStateRef.current;
    // 清除任何可能导致循环的导航状态
    sessionStorage.removeItem('navigating_to_project');
    Object.keys(sessionStorage).forEach(key => {
      if (key.startsWith('navigating_') || key.startsWith('visited_project_')) {
        sessionStorage.removeItem(key);
      }
    });
    
    // 添加导航监听器以防止循环导航
    const handleNavigation = () => {
      const currentPathname = window.location.pathname;
      const now = Date.now();
      
      if (currentPathname === navigationState.lastPathname && 
          now - navigationState.timestamp < 1000) {
        navigationState.redirectCount++;
        console.warn(`[App] 检测到可能的导航循环: ${currentPathname}, 计数: ${navigationState.redirectCount}`);
        
        if (navigationState.redirectCount >= navigationState.MAX_REDIRECTS) {
          console.error(`[App] 检测到导航循环，尝试终止`);
          window.removeEventListener('popstate', handleNavigation);
          sessionStorage.clear();
          localStorage.removeItem('lumidoc_project_permissions');
          window.location.href = '/';
          return;
        }
      } else {
        navigationState.redirectCount = 0;
      }
      
      navigationState.lastPathname = currentPathname;
      navigationState.timestamp = now;
    };
    
    window.addEventListener('popstate', handleNavigation);
    
    return () => {
      window.removeEventListener('popstate', handleNavigation);
    };
  }, []);

  return (
    <ThemeProvider>
      <ProjectProvider>
        <TokenChecker>
          <BackendStatusWrapper enableHealthCheck={true}>
            <div className="min-h-screen">
              <Toaster
                position="bottom-center"
                toastOptions={{
                  className: 'bg-card text-card-foreground',
                  style: {
                    background: 'hsl(var(--card))',
                    color: 'hsl(var(--card-foreground))',
                  },
                  duration: 3000,
                }}
              />
              <Suspense fallback={<RouteFallback />}>
                <RouterProvider router={router} />
              </Suspense>
            </div>
          </BackendStatusWrapper>
        </TokenChecker>
      </ProjectProvider>
    </ThemeProvider>
  );
};

// 主App组件现在只负责提供上下文
function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App
