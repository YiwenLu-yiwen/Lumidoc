import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sparkles, CheckCircle, XCircle } from 'lucide-react';
import { LoginInterface } from '@/components/auth/LoginInterface';
import { useAuth } from '@/context/AuthContext';
import { detectAutoTheme } from '@/utils/language';
import { authApi } from '@/api/auth';

export function AuthPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, login } = useAuth();
  
  // 从URL参数获取模式，默认为登录
  const mode = searchParams.get('mode') || 'login';
  const isRegisterMode = mode === 'register';

  // 获取当前主题
  const isDarkMode = detectAutoTheme() === 'dark';

  // 状态管理
  const [isLoading, setIsLoading] = useState(false);
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
      // 调用真实的认证API
      const response = await authApi.login(credentials.email, credentials.password);
      
      // 构造用户数据
      const userData = {
        id: response.id.toString(),
        username: response.username,
        nickname: response.nickname || response.username
      };
      
      // 使用认证上下文保存用户信息
      login(userData, response.access_token);
      
      // 显示成功消息
      setAuthMessage({ type: 'success', text: '登录成功！正在跳转...' });
      
      // 延迟跳转以显示成功消息
      setTimeout(() => {
        navigate('/app');
      }, 2000);
    } catch (error: any) {
      let errorMessage = '登录失败，请检查邮箱和密码';
      
      // 处理具体的错误信息
      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.response?.status === 401) {
        errorMessage = '账号或密码错误';
      } else if (error.message) {
        errorMessage = error.message;
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
      
      // 使用认证上下文保存用户信息
      login(newUser, loginResponse.access_token);
      
      // 显示成功消息
      setAuthMessage({ type: 'success', text: '注册成功！正在跳转...' });
      
      // 延迟跳转以显示成功消息
      setTimeout(() => {
        navigate('/app');
      }, 2000);
    } catch (error: any) {
      let errorMessage = '注册失败，请重试';
      
      // 处理具体的错误信息
      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.response?.status === 400) {
        errorMessage = error.response.data?.detail || '用户已存在或输入信息有误';
      } else if (error.message) {
        errorMessage = error.message;
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
    <div className={`min-h-screen transition-colors duration-300 relative ${
      isDarkMode ? 'bg-[#212121] text-gray-100' : 'bg-white text-gray-900'
    }`}>
      {/* 成功/失败提示框 - 固定在右上角 */}
      {authMessage.type && (
        <div className={`fixed top-6 right-6 z-50 px-6 py-4 rounded-lg shadow-lg border-l-4 flex items-center space-x-3 animate-in slide-in-from-right-5 fade-in duration-500 ${
          authMessage.type === 'success'
            ? 'bg-green-50 border-green-500 text-green-800 dark:bg-green-900/20 dark:border-green-400 dark:text-green-300'
            : 'bg-red-50 border-red-500 text-red-800 dark:bg-red-900/20 dark:border-red-400 dark:text-red-300'
        }`}>
          {authMessage.type === 'success' ? (
            <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
          ) : (
            <XCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
          )}
          <span className="font-medium">{authMessage.text}</span>
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

            {/* 右侧：简化状态指示 */}
            <div className={`text-sm font-medium ${
              isDarkMode ? 'text-gray-400' : 'text-gray-600'
            }`}>
              {isRegisterMode ? '注册' : '登录'}
            </div>
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