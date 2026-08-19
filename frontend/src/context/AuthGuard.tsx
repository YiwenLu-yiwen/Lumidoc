import React, { ReactNode, useState, useEffect, useRef, useCallback } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { ProjectAccessLevel } from './authTypes';
import { customToast } from '@/utils/toast';
import { projectApi } from '@/api/project';

// 全局错误状态管理，避免多个组件重复处理同一错误
const globalErrorState = {
  lastErrorPath: '',
  errorCount: 0,
  maxRetries: 3,
  redirected: false
};

interface AuthGuardProps {
  children: ReactNode;
  requireAuth?: boolean;
  projectAccess?: boolean;  // 是否需要验证项目访问权限
  requiredLevel?: ProjectAccessLevel; // 所需的项目访问级别
}

export const AuthGuard: React.FC<AuthGuardProps> = ({
  children,
  requireAuth = true,
  projectAccess = false,
  requiredLevel = ProjectAccessLevel.VIEWER
}) => {
  const { isAuthenticated, hasProjectAccess, updateUserProjectAccess, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [verified, setVerified] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const errorMessageShown = useRef(false);
  const processCompleted = useRef(false);

  // 从路径中提取项目ID (如果有)
  const getProjectIdFromPath = useCallback((): string | null => {
    // 检查会话存储中是否已有导航状态，优先使用
    const navigatingToProject = sessionStorage.getItem('navigating_to_project');
    if (navigatingToProject) {
      console.log(`[AuthGuard] 使用导航状态中的项目ID: ${navigatingToProject}`);
      return navigatingToProject;
    }

    // 否则从URL中提取
    const matches = location.pathname.match(/\/project\/([^/]+)/);
    const projectId = matches ? matches[1] : null;

    if (projectId) {
      console.log(`[AuthGuard] 从URL提取项目ID: ${projectId}`);
    }

    return projectId;
  }, [location.pathname]);

  // 显示错误消息并重定向到首页
  const showErrorAndRedirect = useCallback((message: string) => {
    if (!errorMessageShown.current && !globalErrorState.redirected) {
      errorMessageShown.current = true;
      globalErrorState.redirected = true;

      // 记录当前路径和错误计数
      if (location.pathname === globalErrorState.lastErrorPath) {
        globalErrorState.errorCount++;
      } else {
        globalErrorState.lastErrorPath = location.pathname;
        globalErrorState.errorCount = 1;
      }

      // 检查是否正在导航中，如果是则不进行重定向
      const isNavigating = sessionStorage.getItem('navigating_to_project');
      if (isNavigating) {
        console.log(`[AuthGuard] 检测到正在导航中(${isNavigating})，暂不显示错误`);
        // 设置延迟重置重定向状态
        setTimeout(() => {
          globalErrorState.redirected = false;
          errorMessageShown.current = false;
        }, 3000);
        return;
      }

      // 如果错误计数超过最大重试次数，考虑是否重置权限缓存
      if (globalErrorState.errorCount >= globalErrorState.maxRetries) {
        console.error(`[AuthGuard] 页面 ${location.pathname} 重试次数过多`);

        // 先检查用户是否登录，以及是否存在项目权限缓存
        const storedPermissions = localStorage.getItem('lumidoc_project_permissions');
        const hasPermissions = storedPermissions && Object.keys(JSON.parse(storedPermissions || '{}')).length > 0;

        // 仅在用户已登录但没有权限缓存时才重置
        if (isAuthenticated && !hasPermissions) {
          console.log('[AuthGuard] 用户已登录但无权限缓存，进行重置');
          try {
            // 清空所有权限相关缓存
            localStorage.removeItem('lumidoc_project_permissions');

            // 清空所有访问记录
            Object.keys(sessionStorage).forEach(key => {
              if (key.startsWith('visited_project_') || key === 'navigating_to_project') {
                sessionStorage.removeItem(key);
              }
            });

            // 显示错误并重定向
            customToast.error('无法验证项目权限，请重新登录');

            // 重定向后重置错误计数
            setTimeout(() => {
              globalErrorState.errorCount = 0;
              globalErrorState.redirected = false;
              errorMessageShown.current = false;
            }, 3000);

            navigate('/', { replace: true });
          } catch (e) {
            console.error('[AuthGuard] 清空缓存失败:', e);
          }
        } else {
          // 用户未登录或有权限缓存，显示友好提示，避免完全重置
          customToast.error(message);

          // 延迟重置重定向状态
          setTimeout(() => {
            globalErrorState.redirected = false;
            errorMessageShown.current = false;
          }, 3000);

          navigate('/', { replace: true });
        }
      } else {
        // 错误次数少于最大重试次数，只显示错误消息
        customToast.error(message);

        // 延迟重置重定向状态
        setTimeout(() => {
          globalErrorState.redirected = false;
          errorMessageShown.current = false;
        }, 3000);

        navigate('/', { replace: true });
      }
    }
  }, [isAuthenticated, location.pathname, navigate]);

  // 清理潜在的权限冲突
  const cleanupPermissionConflicts = useCallback((projectId: string) => {
    try {
      console.log(`[AuthGuard] 检查并清理项目(${projectId})的权限冲突...`);

      // 读取权限缓存
      const storedPermissions = localStorage.getItem('lumidoc_project_permissions');
      if (storedPermissions) {
        const permissions = JSON.parse(storedPermissions);

        // 确保权限一致
        if (permissions[projectId]) {
          // 项目权限存在，确保用户对象中也有同样的权限
          if (user && (!user.projects || !user.projects[projectId])) {
            console.log(`[AuthGuard] 修复权限不一致：用户对象中缺少项目(${projectId})的权限`);
            updateUserProjectAccess(projectId, permissions[projectId]);
          }
        } else if (user && user.projects && user.projects[projectId]) {
          // 用户对象中有权限，但缓存中没有，更新缓存
          console.log(`[AuthGuard] 修复权限不一致：缓存中缺少项目(${projectId})的权限`);
          permissions[projectId] = user.projects[projectId];
          localStorage.setItem('lumidoc_project_permissions', JSON.stringify(permissions));
        }
      }
    } catch (e) {
      console.error('[AuthGuard] 清理权限冲突失败:', e);
    }
  }, [updateUserProjectAccess, user]);

  useEffect(() => {
    // 重置错误状态和处理状态
    errorMessageShown.current = false;
    processCompleted.current = false;

    // 如果不需要项目权限验证，直接通过
    if (!projectAccess) {
      setVerified(true);
      setIsLoading(false);
      processCompleted.current = true;
      return;
    }

    // 如果需要项目权限但用户未登录，重定向到登录页
    if (projectAccess && !isAuthenticated) {
      setVerified(false);
      setIsLoading(false);
      processCompleted.current = true;
      return;
    }

    const projectId = getProjectIdFromPath();

    // 如果URL中没有项目ID，无法验证权限
    if (!projectId) {
      setVerified(false);
      setIsLoading(false);
      processCompleted.current = true;
      return;
    }

    // 验证项目ID格式是否正确（应该是数字）
    if (!/^\d+$/.test(projectId)) {
      setVerified(false);
      setIsLoading(false);
      showErrorAndRedirect('项目ID格式无效');
      processCompleted.current = true;
      return;
    }

    console.log(`[AuthGuard] 开始验证项目(${projectId})的访问权限...`);

    // 清理潜在的权限冲突
    cleanupPermissionConflicts(projectId);

    // 检查用户是否已有此项目权限
    if (hasProjectAccess(projectId, requiredLevel)) {
      console.log(`[AuthGuard] 用户已有项目权限: ${projectId}`);

      // 验证项目存在但不阻塞UI
      setVerified(true);
      setIsLoading(false);
      processCompleted.current = true;

      // 后台验证项目存在性
      projectApi.getProject(projectId)
        .catch((error) => {
          console.error(`[AuthGuard] 获取项目(${projectId})失败，但用户有权限:`, error);
        });
      return;
    }

    // 优先验证：如果看起来是用户自己的项目，直接授权
    if (user && (user.id === projectId ||
        (user.id && projectId.includes(user.id)) ||
        (user.username && projectId.includes(user.username)))) {
      console.log(`[AuthGuard] 检测到用户关联的项目: ${projectId}，自动授予所有者权限`);
      updateUserProjectAccess(projectId, ProjectAccessLevel.OWNER);
      setVerified(true);
      setIsLoading(false);
      processCompleted.current = true;
      return;
    }

    // 简化权限验证流程
    const verifyAccess = async () => {
      try {
        // 尝试获取项目，成功则授予基本权限
        await projectApi.getProject(projectId);
        console.log(`[AuthGuard] 项目(${projectId})存在，设置基本查看权限`);
        updateUserProjectAccess(projectId, ProjectAccessLevel.VIEWER);
        setVerified(true);

        // 记录项目已访问
        sessionStorage.setItem(`visited_project_${projectId}`, 'true');
      } catch (error) {
        console.error(`[AuthGuard] 获取项目(${projectId})失败:`, error);
        const visited = sessionStorage.getItem(`visited_project_${projectId}`);
        if (visited) {
          setVerified(false);
          showErrorAndRedirect('无权访问此项目');
        } else {
          // 首次访问，可能是正在创建的项目
          sessionStorage.setItem(`visited_project_${projectId}`, 'true');
          // 尝试自动授予临时权限
          updateUserProjectAccess(projectId, ProjectAccessLevel.VIEWER);
          setVerified(true);
        }
      } finally {
        setIsLoading(false);
        processCompleted.current = true;
      }
    };

    // 执行验证
    verifyAccess();

    // 超时处理
    const timeoutId = setTimeout(() => {
      if (!processCompleted.current) {
        console.warn('[AuthGuard] 权限验证超时');
        setIsLoading(false);
        // 设置默认权限，避免用户等待
        updateUserProjectAccess(projectId, ProjectAccessLevel.VIEWER);
        setVerified(true);
        processCompleted.current = true;
      }
    }, 3000); // 减少超时时间

    return () => clearTimeout(timeoutId);
  }, [cleanupPermissionConflicts, getProjectIdFromPath, projectAccess, isAuthenticated, location.pathname, user, requiredLevel, hasProjectAccess, updateUserProjectAccess, showErrorAndRedirect]);

  // 如果路由需要认证但用户未登录
  if (requireAuth && !isAuthenticated) {
    // 保存当前URL，以便登录后重定向回来
    const returnUrl = encodeURIComponent(location.pathname);
    return <Navigate to={`/login?returnUrl=${returnUrl}`} replace />;
  }

  // 如果正在加载中
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mb-4"></div>
          <p className="text-gray-300">验证权限中...</p>
        </div>
      </div>
    );
  }

  // 如果权限验证通过，显示内容
  return verified ? <>{children}</> : null;
};

export default AuthGuard;
