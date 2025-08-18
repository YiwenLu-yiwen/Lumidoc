import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sparkles, CheckCircle, XCircle } from 'lucide-react';
import { LoginInterface } from '@/components/auth/LoginInterface';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { authApi } from '@/api/auth';
import { detectBrowserLanguage, getTranslation } from '@/utils/language';

export function AuthPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, login } = useAuth();
  
  // 获取当前语言并创建翻译函数
  const currentLanguage = detectBrowserLanguage();
  const t = (key: keyof typeof import('@/utils/language').translations['zh-CN']) => {
    return getTranslation(currentLanguage, key);
  };
  
  // 从URL参数获取模式，默认为登录
  const mode = searchParams.get('mode') || 'login';
  const isRegisterMode = mode === 'register';

  // 获取当前主题
  const { isDarkMode } = useTheme();

  // 状态管理
  const [isLoading, setIsLoading] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [authMessage, setAuthMessage] = useState<{
    type: 'success' | 'error' | null;
    text: string;
  }>({ type: null, text: '' });

  // 如果用户已登录，重定向到应用
  useEffect(() => {
    if (user) {
      navigate('/app');
    }
  }, [user, navigate]);

  // 处理登录
  const handleLogin = async (credentials: { email: string; password: string }) => {
    setIsLoading(true);
    setAuthMessage({ type: null, text: '' });
    
    try {
      // 调用真实的认证API（注意：后端期望username字段，但可以传邮箱）
      const response = await authApi.login(credentials.email, credentials.password);
      
      // 验证响应数据完整性
      if (!response || !response.access_token || !response.id) {
        throw new Error('登录响应数据不完整，请重试');
      }
      
      // 构造用户数据
      const userData = {
        id: response.id.toString(),
        username: response.username,
        nickname: response.nickname || response.username
      };
      
      // 先显示成功消息
      setAuthMessage({ type: 'success', text: t('loginSuccess') });
      
      // 延迟调用认证上下文和跳转
      setTimeout(() => {
        // 使用认证上下文保存用户信息
        login(userData, response.access_token);
        
        setIsTransitioning(true);
        
        // 添加简单的页面淡出效果（无缩放）
        const pageElement = document.documentElement;
        pageElement.style.transition = 'opacity 0.5s ease-out';
        pageElement.style.opacity = '0.9';
        
        // 由于useEffect会自动触发跳转，这里不需要手动navigate
      }, 2000); // 显示成功消息2秒
    } catch (error: any) {
      console.error('登录错误:', error);
      
      let errorMessage = t('loginFailedCheckCredentials');
      
      // 优先检查HTTP状态码
      if (error.response?.status === 401) {
        errorMessage = t('accountOrPasswordIncorrect');
      } else if (error.response?.status === 400) {
        errorMessage = t('loginFailedCheckCredentials');
      } else if (error.response?.status >= 500) {
        errorMessage = t('serverError');
      } else if (error.message) {
        // 检查error.message中是否包含已知的错误信息
        const message = error.message.toLowerCase();
        if (message.includes('账号') || message.includes('密码') || message.includes('password') || message.includes('account')) {
          errorMessage = t('accountOrPasswordIncorrect');
        } else if (message.includes('网络') || message.includes('network') || message.includes('fetch')) {
          errorMessage = t('networkError');
        } else {
          // 默认为登录失败
          errorMessage = t('loginFailedCheckCredentials');
        }
      }
      
      setAuthMessage({ 
        type: 'error', 
        text: errorMessage
      });
    } finally {
      setIsLoading(false);
    }
  };

  // 处理注册
  const handleRegister = async (userData: { email: string; password: string; username: string }) => {
    setIsLoading(true);
    setAuthMessage({ type: null, text: '' });
    
    try {
      // 调用真实的注册API
      await authApi.register(userData.username, userData.password, userData.email, userData.username);
      
      // 注册成功后自动登录
      const loginResponse = await authApi.login(userData.email, userData.password);
      
      // 构造用户数据
      const newUser = {
        id: loginResponse.id.toString(),
        username: loginResponse.username,
        nickname: loginResponse.nickname || loginResponse.username
      };
      
      // 先显示成功消息
      setAuthMessage({ type: 'success', text: t('registerSuccess') });
      
      // 延迟调用认证上下文和跳转
      setTimeout(() => {
        // 使用认证上下文保存用户信息
        login(newUser, loginResponse.access_token);
        
        setIsTransitioning(true);
        
        // 添加简单的页面淡出效果（无缩放）
        const pageElement = document.documentElement;
        pageElement.style.transition = 'opacity 0.5s ease-out';
        pageElement.style.opacity = '0.9';
        
        // 由于useEffect会自动触发跳转，这里不需要手动navigate
      }, 2000); // 显示成功消息2秒
    } catch (error: any) {
      let errorMessage = t('registrationFailed');
      
      // 优先检查HTTP状态码
      if (error.response?.status === 400) {
        errorMessage = t('userExistsOrInvalidInput');
      } else if (error.response?.status === 409) {
        errorMessage = t('userExistsOrInvalidInput');
      } else if (error.response?.status >= 500) {
        errorMessage = t('serverError');
      } else if (error.message) {
        // 检查error.message中是否包含已知的错误信息
        const message = error.message.toLowerCase();
        if (message.includes('用户') || message.includes('邮箱') || message.includes('user') || message.includes('email') || message.includes('exist')) {
          errorMessage = t('userExistsOrInvalidInput');
        } else if (message.includes('网络') || message.includes('network') || message.includes('fetch')) {
          errorMessage = t('networkError');
        } else {
          // 默认为注册失败
          errorMessage = t('registrationFailed');
        }
      }
      
      setAuthMessage({ 
        type: 'error', 
        text: errorMessage
      });
    } finally {
      setIsLoading(false);
    }
  };

  // 返回首页
  const handleBackToHome = () => {
    navigate('/');
  };

  return (
    <div className={`min-h-screen transition-all duration-700 relative ${
      isDarkMode ? 'bg-[#212121] text-gray-100' : 'bg-white text-gray-900'
    } ${isTransitioning ? 'opacity-90' : ''}`}>
      {/* 成功/失败提示框 - 固定在右上角，增强动画效果 */}
      {authMessage.type && (
        <div className={`fixed top-6 right-6 z-50 px-6 py-4 rounded-lg shadow-xl border-l-4 flex items-center space-x-3 transition-all duration-700 ${
          authMessage.type === 'success'
            ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-500 text-green-800 dark:bg-gradient-to-r dark:from-green-900/30 dark:to-emerald-900/30 dark:border-green-400 dark:text-green-300 animate-bounce-once'
            : 'bg-red-50 border-red-500 text-red-800 dark:bg-red-900/20 dark:border-red-400 dark:text-red-300 animate-shake'
        } animate-in slide-in-from-right-5 fade-in duration-500`}>
          {authMessage.type === 'success' ? (
            <CheckCircle className="w-6 h-6 text-green-600 dark:text-green-400 animate-pulse" />
          ) : (
            <XCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
          )}
          <span className={`font-semibold ${authMessage.type === 'success' ? 'text-lg' : ''}`}>
            {authMessage.text}
          </span>
          {authMessage.type === 'success' && (
            <div className="ml-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-ping"></div>
            </div>
          )}
        </div>
      )}

      {/* 顶部导航栏 */}
      <header className={`border-b transition-colors duration-300 ${
        isDarkMode ? 'border-gray-800 bg-[#171717]' : 'border-gray-200 bg-white'
      }`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* 左侧：Logo - 可点击返回首页 */}
            <div 
              className="flex items-center space-x-3 cursor-pointer hover:opacity-80 transition-opacity"
              onClick={handleBackToHome}
            >
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                isDarkMode ? 'bg-gradient-to-r from-blue-600 to-purple-600' : 'bg-gradient-to-r from-blue-500 to-purple-500'
              }`}>
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                Lumidoc Intelligence
              </h1>
            </div>

            {/* 右侧：空白占位 */}
            <div></div>
          </div>
        </div>
      </header>

      {/* 认证内容区域 - 充分利用垂直空间 */}
      <main className="flex-1 flex items-center justify-center px-4 py-8 min-h-[calc(100vh-8rem)]">
        <div className="w-full max-w-lg">
          {/* 品牌标题 */}
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4">
              <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                Lumidoc Intelligence
              </span>
            </h2>
          </div>

          {/* 登录/注册表单 */}
          <LoginInterface
            onLogin={handleLogin}
            onRegister={handleRegister}
            isLoading={isLoading}
          />
        </div>
      </main>

      {/* 底部 */}
      <footer className={`border-t py-6 ${
        isDarkMode ? 'border-gray-800 bg-[#171717]' : 'border-gray-200 bg-white'
      }`}>
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <p className={`text-sm ${
              isDarkMode ? 'text-gray-400' : 'text-gray-500'
            }`}>
              © 2024 Lumidoc Intelligence
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}