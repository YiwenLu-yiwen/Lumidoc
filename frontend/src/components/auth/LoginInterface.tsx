import React, { useState } from 'react';
import { Eye, EyeOff, Mail, Lock, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { detectAutoTheme } from '@/utils/language';

interface LoginInterfaceProps {
  onLogin?: (credentials: { email: string; password: string }) => void;
  onRegister?: (userData: { email: string; password: string; username: string }) => void;
  isLoading?: boolean;
}

export function LoginInterface({ onLogin, onRegister, isLoading = false }: LoginInterfaceProps) {
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    username: ''
  });
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  
  // 重置错误状态当切换模式时
  const switchMode = (mode: boolean) => {
    setIsLoginMode(mode);
    setErrors({});
    setFormData({ email: '', password: '', username: '' });
  };

  // 获取当前主题
  const isDarkMode = detectAutoTheme() === 'dark';

  // 表单验证
  const validateForm = () => {
    const newErrors: { [key: string]: string } = {};

    if (!formData.email) {
      newErrors.email = '请输入邮箱地址';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = '请输入有效的邮箱地址';
    }

    if (!formData.password) {
      newErrors.password = '请输入密码';
    } else if (formData.password.length < 6) {
      newErrors.password = '密码至少需要6位';
    }

    if (!isLoginMode && !formData.username) {
      newErrors.username = '请输入用户名';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // 处理表单提交
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) return;

    if (isLoginMode) {
      onLogin?.(formData);
    } else {
      onRegister?.(formData);
    }
  };

  // 更新表单数据
  const updateFormData = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // 清除对应字段的错误
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  return (
    <div className={`w-full`}>
      <div className={`w-full p-8 rounded-2xl shadow-lg ${isDarkMode ? 'bg-[#171717] border border-gray-800' : 'bg-white border border-gray-200'}`}>

        {/* 切换登录/注册模式 */}
        <div className={`flex rounded-lg p-1 mb-6 ${isDarkMode ? 'bg-gray-800' : 'bg-gray-100'}`}>
          <button
            type="button"
            onClick={() => switchMode(true)}
            disabled={isLoading}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              isLoginMode
                ? isDarkMode
                  ? 'bg-gray-600 text-white'
                  : 'bg-white text-gray-900 shadow-sm'
                : isDarkMode
                  ? 'text-gray-400 hover:text-gray-200'
                  : 'text-gray-600 hover:text-gray-900'
            } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            登录
          </button>
          <button
            type="button"
            onClick={() => switchMode(false)}
            disabled={isLoading}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              !isLoginMode
                ? isDarkMode
                  ? 'bg-gray-600 text-white'
                  : 'bg-white text-gray-900 shadow-sm'
                : isDarkMode
                  ? 'text-gray-400 hover:text-gray-200'
                  : 'text-gray-600 hover:text-gray-900'
            } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            注册
          </button>
        </div>

        {/* 登录表单 */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 用户名字段（仅注册时显示） */}
          {!isLoginMode && (
            <div>
              <label className={`block text-sm font-medium mb-2 ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                用户名
              </label>
              <div className="relative">
                <User className={`absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`} />
                <Input
                  type="text"
                  value={formData.username}
                  onChange={(e) => updateFormData('username', e.target.value)}
                  className={`pl-10 ${isDarkMode ? 'bg-gray-800 border-gray-700 text-white' : 'bg-white border-gray-300'}`}
                  placeholder="输入用户名"
                  disabled={isLoading}
                />
              </div>
              {errors.username && (
                <p className="mt-1 text-sm text-red-500">{errors.username}</p>
              )}
            </div>
          )}

          {/* 邮箱字段 */}
          <div>
            <label className={`block text-sm font-medium mb-2 ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>
              邮箱地址
            </label>
            <div className="relative">
              <Mail className={`absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`} />
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => updateFormData('email', e.target.value)}
                className={`pl-10 ${isDarkMode ? 'bg-gray-800 border-gray-700 text-white' : 'bg-white border-gray-300'}`}
                placeholder="输入邮箱地址"
                disabled={isLoading}
              />
            </div>
            {errors.email && (
              <p className="mt-1 text-sm text-red-500">{errors.email}</p>
            )}
          </div>

          {/* 密码字段 */}
          <div>
            <label className={`block text-sm font-medium mb-2 ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>
              密码
            </label>
            <div className="relative">
              <Lock className={`absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`} />
              <Input
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={(e) => updateFormData('password', e.target.value)}
                className={`pl-10 pr-10 ${isDarkMode ? 'bg-gray-800 border-gray-700 text-white' : 'bg-white border-gray-300'}`}
                placeholder="输入密码"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className={`absolute right-3 top-1/2 transform -translate-y-1/2 ${isDarkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-700'}`}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {errors.password && (
              <p className="mt-1 text-sm text-red-500">{errors.password}</p>
            )}
          </div>

          {/* 忘记密码链接（仅登录时显示） */}
          {isLoginMode && (
            <div className="text-right">
              <button
                type="button"
                className={`text-sm ${isDarkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-600 hover:text-gray-900'} hover:underline`}
              >
                忘记密码？
              </button>
            </div>
          )}

          {/* 提交按钮 */}
          <Button
            type="submit"
            disabled={isLoading}
            className={`w-full py-3 ${isDarkMode ? 'bg-gray-600 hover:bg-gray-700' : 'bg-gray-800 hover:bg-gray-900'} text-white font-medium`}
          >
            {isLoading ? (
              <div className="flex items-center justify-center">
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                {isLoginMode ? '登录中...' : '注册中...'}
              </div>
            ) : (
              isLoginMode ? '登录' : '注册'
            )}
          </Button>
        </form>

        {/* 提示信息 */}
        <div className={`mt-6 text-center text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
          {isLoginMode ? (
            <>
              还没有账号？
              <button
                type="button"
                onClick={() => setIsLoginMode(false)}
                className={`ml-1 ${isDarkMode ? 'text-gray-200 hover:text-white' : 'text-gray-900 hover:text-black'} hover:underline`}
              >
                立即注册
              </button>
            </>
          ) : (
            <>
              已有账号？
              <button
                type="button"
                onClick={() => setIsLoginMode(true)}
                className={`ml-1 ${isDarkMode ? 'text-gray-200 hover:text-white' : 'text-gray-900 hover:text-black'} hover:underline`}
              >
                立即登录
              </button>
            </>
          )}
        </div>

      </div>
    </div>
  );
}