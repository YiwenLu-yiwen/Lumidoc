import React, { useState } from 'react';
import { Lock, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function AuthModal({ open, onClose }: Props) {
  const { login } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [nickname, setNickname] = useState('');
  const [error, setError] = useState('');
  const [showReset, setShowReset] = useState(false);
  const [resetUser, setResetUser] = useState('');
  const [resetPwd, setResetPwd] = useState('');
  const [resetMsg, setResetMsg] = useState('');
  const [registerSuccess, setRegisterSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [countdown, setCountdown] = useState(3);

  // 统一通过Gateway访问认证服务
  const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888'

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username || !password) {
      setError('账号或密码不能为空');
      return;
    }
    if (isRegister) {
      if (username.length < 4) {
        setError('账号至少需要4位');
        return;
      }
      if (password.length < 6) {
        setError('密码至少需要6位');
        return;
      }
      if (username === password) {
        setError('账号和密码不能一致');
        return;
      }
    }
    
    setIsLoading(true);
    try {
      const url = isRegister 
        ? `${gatewayUrl}/auth/api/register` 
        : `${gatewayUrl}/auth/api/token`;
      
      console.log(`[AuthModal] 通过Gateway访问认证服务: ${url}`);
      
      let fetchOptions;
      if (isRegister) {
        const registerData: {
          username: string;
          password: string;
          nickname: string;
          email?: string;
        } = { 
          username, 
          password,
          nickname: nickname || "momo" // 如果未提供昵称，默认使用"momo"
        };
        
        // 不主动设置email字段，除非用户名明确是邮箱格式
        if (username.includes('@') && username.includes('.')) {
          registerData.email = username; // 只有当用户名是有效的邮箱格式时才用作邮箱
        }
        
        console.log(`[AuthModal] 注册数据:`, registerData);
        
        fetchOptions = {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(registerData),
        };
      } else {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        fetchOptions = {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData.toString(),
        };
      }
      console.log(`[AuthModal] 发送${isRegister ? '注册' : '登录'}请求到: ${url}`, 
        isRegister ? JSON.parse(fetchOptions.body) : fetchOptions.body);
      
      try {
        const res = await fetch(url, fetchOptions);
        console.log(`[AuthModal] 响应状态: ${res.status}, ${res.statusText}`);
        
        if (!res.ok) {
          let errorDetail = res.statusText;
          try {
            const errorData = await res.json();
            console.log("[AuthModal] 错误数据:", errorData);
            errorDetail = errorData.detail || errorData.message || '请求失败';
          } catch (e) {
            console.error("[AuthModal] 无法解析错误响应:", e);
          }
          
          if (isRegister && errorDetail.includes('已存在')) {
            setError('账号已存在');
          } else {
            setError(errorDetail);
          }
          setIsLoading(false);
          return;
        }
        
        const data = await res.json();
        console.log(`[AuthModal] 响应数据:`, data);

        // 处理注册成功的情况
        if (isRegister) {
          console.log('注册成功，接收到数据:', data);
          // 显示注册成功信息
          setRegisterSuccess(true);
          setError('');
          setIsLoading(false);
          
          // 保存注册信息用于自动登录
          const registerUsername = username;
          const registerPassword = password;
          
          // 清空表单
          setUsername('');
          setPassword('');
          setNickname('');
          
          // 开始倒计时，3秒后自动登录
          setCountdown(3);
          const countdownInterval = setInterval(() => {
            setCountdown(prev => {
              if (prev <= 1) {
                clearInterval(countdownInterval);
                // 倒计时结束后自动登录
                (async () => {
                  try {
                    console.log('[AuthModal] 尝试自动登录注册的账户:', registerUsername);
                    const formData = new URLSearchParams();
                    formData.append('username', registerUsername);
                    formData.append('password', registerPassword);
                    
                    const loginRes = await fetch(`${gatewayUrl}/auth/api/token`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                      body: formData.toString(),
                    });
                    
                    console.log('[AuthModal] 自动登录响应状态:', loginRes.status);
                    
                    if (loginRes.ok) {
                      const loginData = await loginRes.json();
                      console.log('[AuthModal] 自动登录成功，接收到数据:', loginData);
                      
                      if (loginData.access_token) {
                        const userData = {
                          id: loginData.id?.toString() || '',
                          username: loginData.username || '',
                          nickname: loginData.nickname || ''
                        };
                        
                        // 保存token和用户信息
                        localStorage.setItem('stp_token', loginData.access_token);
                        localStorage.setItem('stp_user', JSON.stringify(userData));
                        
                        // 调用登录成功处理，但传递标记表明是注册后登录
                        login(userData, loginData.access_token);
                        
                        // 由于自动登录成功，直接关闭模态框，不再跳转
                        onClose();
                      } else {
                        console.error('[AuthModal] 自动登录成功但未收到有效token');
                        setIsRegister(false); // 切换到登录模式
                        onClose(); // 关闭模态框
                      }
                    } else {
                      console.error('[AuthModal] 自动登录失败，状态码:', loginRes.status);
                      try {
                        const errorData = await loginRes.json();
                        console.error('[AuthModal] 自动登录错误信息:', errorData);
                      } catch (e) {
                        console.error('[AuthModal] 无法解析自动登录错误响应');
                      }
                      setIsRegister(false); // 切换到登录模式
                      onClose(); // 关闭模态框
                    }
                  } catch (err) {
                    console.error('[AuthModal] 自动登录失败:', err);
                    // 自动登录失败，切换到登录模式
                    setIsRegister(false);
                    onClose(); // 关闭模态框
                  }
                })();
                return 0;
              }
              return prev - 1;
            });
          }, 1000);
          
          return;
        }

        // 处理登录成功的情况
        try {
          console.log('登录成功，接收到数据:', data);
          
          // 确保收到了有效的token
          if (!data.access_token) {
            console.error('未收到访问令牌');
            setError('登录异常，未收到有效令牌');
            setIsLoading(false);
            return;
          }

          // 先清除之前可能存在的token
          localStorage.removeItem('stp_token');
          localStorage.removeItem('stp_user');
          
          // 保存用户数据（避免undefined值）
          const userData = {
            id: data.id?.toString() || '',
            username: data.username || '',
            nickname: data.nickname || ''
          };
          
          // 先保存token到localStorage
          try {
            console.log('保存token到localStorage:', data.access_token.substring(0, 15) + '...');
            localStorage.setItem('stp_token', data.access_token);
            localStorage.setItem('stp_user', JSON.stringify(userData));
            
            // 验证token是否正确保存
            const savedToken = localStorage.getItem('stp_token');
            console.log('验证保存的token:', savedToken ? savedToken.substring(0, 15) + '...' : '无');
          } catch (storageError) {
            console.error('保存到localStorage失败:', storageError);
          }
          
          handleLoginSuccess(userData, data.access_token);
        } catch (err) {
          console.error('登录过程中出错:', err);
          setError('登录过程中出现错误，请重试');
          setIsLoading(false);
        }
      } catch (err) {
        console.error('登录请求错误:', err);
        setError('无法连接到认证服务器，请检查网络连接');
        setIsLoading(false);
      }
    } catch (err: any) {
      console.error('登录请求错误:', err);
      setError('账号或密码错误');
      setIsLoading(false);
    }
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetMsg('');
    if (!resetUser || !resetPwd) {
      setResetMsg('账号或新密码不能为空');
      return;
    }
    if (resetUser === resetPwd) {
      setResetMsg('账号和新密码不能一致');
      return;
    }
    try {
      console.log('[AuthModal] 发送密码重置请求...');
      
      const res = await fetch(`${gatewayUrl}/auth/api/reset_password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: resetUser, new_password: resetPwd }),
      });
      
      console.log(`[AuthModal] 密码重置响应状态: ${res.status}`);
      const data = await res.json();
      console.log('[AuthModal] 密码重置响应数据:', data);
      
      if (!res.ok) {
        setResetMsg(data.detail || '重置失败');
        return;
      }
      setResetMsg('密码重置成功');
      setTimeout(() => {
        setShowReset(false);
        setResetUser('');
        setResetPwd('');
        setResetMsg('');
      }, 2000);
    } catch (err: any) {
      console.error('[AuthModal] 密码重置错误:', err);
      setResetMsg('重置失败');
    }
  };

  const handleLoginSuccess = async (userData: any, token: string) => {
    // 调用login函数设置用户信息和token
    login(userData, token);
    
    // 简化登录后权限加载，避免可能的重复渲染
    // 登录后权限加载由AuthContext内部处理，这里不再主动调用
    
    // 更新UI状态
    setRegisterSuccess(true);
    setError('');
    setIsLoading(false);
    
    // 显示简短的成功消息
    console.log("登录成功，正在关闭...");
    
    // 如果是注册后自动登录，不需要再次启动倒计时（注册流程中已经有倒计时了）
    if(!isRegister) {
      // 开始倒计时
      setCountdown(3);
      const countdownInterval = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            clearInterval(countdownInterval);
            // 倒计时结束后关闭模态框，不再跳转
            onClose();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      // 对于注册后自动登录，直接关闭模态框，不再跳转
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50">
      <div className="relative bg-[#232325] text-white rounded-lg shadow-lg w-full max-w-md p-0 overflow-hidden">
        <button
          className="absolute top-4 right-6 text-gray-400 hover:text-white text-2xl z-20"
          onClick={onClose}
          aria-label="关闭"
        >✕</button>
        
        {/* 成功倒计时提示 - 确保放在绝对中央 */}
        {registerSuccess && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#232325]/90 z-10 backdrop-blur-sm">
            <div className="text-center bg-gradient-to-b from-green-900/40 to-green-900/20 p-8 rounded-xl border border-green-500/30 shadow-xl">
              <div className="text-4xl mb-3 text-green-400">✓</div>
              <div className="text-xl text-green-300 font-medium mb-2">
                {isRegister 
                  ? `注册成功，正在自动登录...` 
                  : `登录成功！`}
              </div>
              <div className="mt-3 text-2xl text-green-400 font-bold">{countdown}</div>
              <div className="text-green-300/80 text-sm">秒后自动跳转</div>
            </div>
          </div>
        )}

        <div className="flex flex-col items-center pt-10 pb-6">
          <Lock className="w-10 h-10 mb-2" />
          <div className="text-2xl font-bold mb-1">Lumidoc WebUI</div>
          <div className="text-lg mb-8">{isRegister ? '账号注册' : '账号登录'}</div>
        </div>
        {showReset ? (
          <form onSubmit={handleReset} className="w-full flex flex-col gap-6 px-10">
            <div className="flex flex-col gap-1">
              <label className="text-gray-400 text-sm mb-1">账号</label>
              <input
                className="bg-[#18181b] border border-gray-700 rounded px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                type="text"
                placeholder="请输入账号"
                value={resetUser}
                onChange={e => setResetUser(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-gray-400 text-sm mb-1">新密码</label>
              <div className="relative">
                <input
                  className="bg-[#18181b] border border-gray-700 rounded px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 w-full"
                  type={showPassword ? "text" : "password"}
                  placeholder="请输入新密码"
                  value={resetPwd}
                  onChange={e => setResetPwd(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            {resetMsg && (
              <div className="text-center text-sm mb-2">
                <span className={resetMsg.includes('成功') ? 'text-green-400' : 'text-red-400'}>{resetMsg}</span>
              </div>
            )}
            <button
              type="submit"
              className="w-full bg-white text-black font-semibold rounded-full py-3 mt-2 transition hover:bg-gray-200"
            >
              重置密码
            </button>
            <button
              type="button"
              className="text-gray-400 hover:underline text-sm mt-2"
              onClick={() => {
                setShowReset(false);
                setResetUser('');
                setResetPwd('');
                setResetMsg('');
              }}
            >
              返回登录
            </button>
          </form>
        ) : (
          <form onSubmit={handleSubmit} className="w-full flex flex-col gap-6 px-10">
            <div className="flex flex-col gap-1">
              <label className="text-gray-400 text-sm mb-1">账号</label>
              <input
                className="bg-[#18181b] border border-gray-700 rounded px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                type="text"
                placeholder={isRegister ? "请输入注册账号" : "请输入账号"}
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
              />
            </div>
            {isRegister && (
              <div className="flex flex-col gap-1">
                <label className="text-gray-400 text-sm mb-1">昵称</label>
                <input
                  className="bg-[#18181b] border border-gray-700 rounded px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  type="text"
                  placeholder="请输入昵称（选填）"
                  value={nickname}
                  onChange={e => setNickname(e.target.value)}
                />
              </div>
            )}
            <div className="flex flex-col gap-1">
              <label className="text-gray-400 text-sm mb-1">密码</label>
              <div className="relative">
                <input
                  className="bg-[#18181b] border border-gray-700 rounded px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 w-full"
                  type={showPassword ? "text" : "password"}
                  placeholder={isRegister ? "请输入注册密码" : "请输入密码"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            {error && (
              <div className="text-center text-sm text-red-400 mb-2">{error}</div>
            )}
            <button
              type="submit"
              className="w-full bg-white text-black font-semibold rounded-full py-3 mt-2 transition hover:bg-gray-200"
              disabled={isLoading || registerSuccess}
            >
              {isLoading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-black" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  处理中...
                </span>
              ) : (
                isRegister ? '注册' : '登录'
              )}
            </button>
          </form>
        )}
        {/* 底部操作栏 */}
        {!showReset && (
          <div className="flex justify-between w-full px-10 mt-6 mb-8 text-sm">
            <button
              className="text-gray-400 hover:underline"
              onClick={() => setShowReset(true)}
              type="button"
            >
              忘记密码？
            </button>
            <button
              className="text-gray-400 hover:underline"
              onClick={() => {
                setIsRegister(!isRegister);
                setError('');
              }}
              type="button"
              disabled={registerSuccess}
            >
              {isRegister ? '去登录' : '注册'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
