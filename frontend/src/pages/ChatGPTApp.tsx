import React, { useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import ChatGPTMainLayout from '@/components/layout/ChatGPTMainLayout';
import { AuthGuard } from '@/context/AuthGuard';
import { useAuth } from '@/context/AuthContext';
import { detectAutoTheme } from '@/utils/language';

// 懒加载页面组件
const EnhancedChatInterface = React.lazy(() => import('@/components/chat/EnhancedChatInterface'));
const ModernDashboard = React.lazy(() => import('@/components/dashboard/ModernDashboard'));
const FileManager = React.lazy(() => import('@/features/files/FileManager'));
const GraphViewer = React.lazy(() => import('@/features/graph/GraphViewer'));
const ProjectLayout = React.lazy(() => import('@/features/project/ProjectLayout'));
const SettingsPage = React.lazy(() => import('@/features/settings/SettingsPage'));

// 加载占位符
const LoadingSpinner = () => (
  <div className="flex items-center justify-center h-full">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
  </div>
);

// ChatGPT 风格的主应用组件
export default function ChatGPTApp() {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  // 初始化主题
  useEffect(() => {
    detectAutoTheme('auto');
  }, []);

  // 如果正在加载，显示加载状态
  if (isLoading) {
    return <LoadingSpinner />;
  }

  // 主路由配置
  return (
    <AuthGuard>
      <div className="h-screen bg-gray-50 dark:bg-gray-900">
        <Routes>
          {/* 主 ChatGPT 界面路由 */}
          <Route
            path="/*"
            element={
              <ChatGPTMainLayout>
                <React.Suspense fallback={<LoadingSpinner />}>
                  <Routes>
                    {/* 默认重定向到聊天 */}
                    <Route path="/" element={<Navigate to="/chat" replace />} />
                    
                    {/* 聊天界面 */}
                    <Route path="/chat" element={<EnhancedChatInterface />} />
                    <Route path="/chat/:chatId" element={<EnhancedChatInterface />} />
                    
                    {/* Dashboard - 保持你现有的优秀设计 */}
                    <Route path="/dashboard" element={<ModernDashboard />} />
                    
                    {/* 文件管理 */}
                    <Route path="/files" element={<FileManager />} />
                    <Route path="/files/:projectId" element={<FileManager />} />
                    
                    {/* 知识图谱 */}
                    <Route path="/graph" element={<GraphViewer />} />
                    <Route path="/graph/:projectId" element={<GraphViewer />} />
                    
                    {/* 项目管理 */}
                    <Route path="/projects" element={<ProjectLayout />} />
                    <Route path="/projects/:projectId/*" element={<ProjectLayout />} />
                    
                    {/* 设置页面 */}
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/settings/:section" element={<SettingsPage />} />
                    
                    {/* 404 处理 */}
                    <Route path="*" element={<Navigate to="/chat" replace />} />
                  </Routes>
                </React.Suspense>
              </ChatGPTMainLayout>
            }
          />
        </Routes>
      </div>
    </AuthGuard>
  );
}

// 导出路由配置供其他地方使用
export const chatGPTRoutes = [
  { path: '/chat', name: '智能对话', icon: '💬' },
  { path: '/dashboard', name: 'Dashboard', icon: '📊' },
  { path: '/files', name: '文件管理', icon: '📁' },
  { path: '/graph', name: '知识图谱', icon: '🕸️' },
  { path: '/projects', name: '项目管理', icon: '👥' },
  { path: '/settings', name: '设置', icon: '⚙️' }
];