import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * 自定义钩子用于处理认证状态，提供认证检查、路由保护等功能
 * @param {boolean} requireAuth - 是否需要认证才能访问
 * @param {boolean} redirectToLogin - 未认证时是否重定向到登录页
 * @param {boolean} showToast - 是否显示提示消息（由于AuthGuard已经显示了提示，这里默认不再显示）
 */
export const useAuthState = (requireAuth = true, redirectToLogin = true) => {
  const { isAuthenticated, user, token } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthorized, setIsAuthorized] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        setIsLoading(true);
        
        // 如果需要认证但用户未登录
        if (requireAuth && !isAuthenticated) {
          if (redirectToLogin) {
            // 移除重复的提示，由AuthGuard负责显示
            const returnUrl = encodeURIComponent(location.pathname + location.search);
            navigate(`/login?returnUrl=${returnUrl}`, { replace: true });
          }
          setIsAuthorized(false);
        } else {
          // 用户已登录或不需要认证
          setIsAuthorized(true);
        }
      } catch (error) {
        console.error('认证检查失败:', error);
        setIsAuthorized(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, [isAuthenticated, user, token, requireAuth, redirectToLogin, navigate, location]);

  return {
    isLoading,
    isAuthenticated,
    isAuthorized,
    user,
    token
  };
};

export default useAuthState; 