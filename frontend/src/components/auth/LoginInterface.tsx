import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Eye, EyeOff, Mail, Lock, User, Check, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useTheme } from '@/context/ThemeContext';
import { useLanguage } from '@/context/LanguageContext';

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
  const [validationStatus, setValidationStatus] = useState<{ [key: string]: boolean }>({});
  
  // 重置错误状态当切换模式时
  const switchMode = (mode: boolean) => {
    setIsLoginMode(mode);
    setErrors({});
    setValidationStatus({});
    setFormData({ email: '', password: '', username: '' });
  };

  // 获取当前主题和语言
  const { isDarkMode } = useTheme();
  const { t } = useLanguage();

  // 密码强度检查规则 - 在t函数定义后
  const passwordRules = useMemo(() => [
    { key: 'length', test: (pwd: string) => pwd.length >= 6, label: t('atLeastSixCharacters') },
    { key: 'letter', test: (pwd: string) => /[a-zA-Z]/.test(pwd), label: t('containsLetters') },
    { key: 'number', test: (pwd: string) => /\d/.test(pwd), label: t('containsNumbers') },
  ], [t]);

  // 实时验证函数
  const validateField = useCallback((field: string, value: string) => {
    let errorMessage: string | undefined;
    let isValid: boolean | undefined;

    switch (field) {
      case 'email':
        if (!value) {
          errorMessage = t('pleaseEnterEmail');
          isValid = false;
        } else if (!/\S+@\S+\.\S+/.test(value)) {
          errorMessage = t('pleaseEnterValidEmail');
          isValid = false;
        } else {
          isValid = true;
        }
        break;
      
      case 'username':
        if (!isLoginMode) {
          if (!value) {
            errorMessage = t('pleaseEnterUsername');
            isValid = false;
          } else if (value.length < 4) {
            errorMessage = t('usernameMinLength');
            isValid = false;
          } else {
            isValid = true;
          }
        }
        break;
      
      case 'password':
        if (!value) {
          errorMessage = t('pleaseEnterPassword');
          isValid = false;
        } else if (!isLoginMode) {
          // 注册模式下检查密码强度
          const failedRules = passwordRules.filter(rule => !rule.test(value));
          if (failedRules.length > 0) {
            errorMessage = `${t('passwordRequirementsNotMet')}：${failedRules.map(r => r.label).join('、')}`;
            isValid = false;
          } else {
            isValid = true;
          }
        } else if (value.length < 6) {
          errorMessage = t('passwordMinLength');
          isValid = false;
        } else {
          isValid = true;
        }
        break;
    }

    if (isValid === undefined) return;

    setErrors(previousErrors => {
      const nextErrors = { ...previousErrors };
      if (errorMessage) nextErrors[field] = errorMessage;
      else delete nextErrors[field];
      return nextErrors;
    });
    setValidationStatus(previousStatus => ({ ...previousStatus, [field]: isValid }));
  }, [isLoginMode, passwordRules, t]);

  // 实时检查输入
  useEffect(() => {
    if (!isLoginMode) {
      // 注册模式下实时验证所有字段
      validateField('email', formData.email);
      validateField('username', formData.username);
      validateField('password', formData.password);
    }
  }, [formData, isLoginMode, validateField]);

  // 表单验证
  const validateForm = () => {
    const newErrors: { [key: string]: string } = {};

    if (!formData.email) {
      newErrors.email = t('pleaseEnterEmail');
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = t('pleaseEnterValidEmail');
    }

    if (!formData.password) {
      newErrors.password = t('pleaseEnterPassword');
    } else if (formData.password.length < 6) {
      newErrors.password = t('passwordMinLength');
    }

    if (!isLoginMode && !formData.username) {
      newErrors.username = t('pleaseEnterUsername');
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
    // 实时验证
    setTimeout(() => validateField(field, value), 100);
  };

  return (
    <div className={`w-full`}>
      <div className={`w-full p-8 rounded-2xl shadow-lg ${isDarkMode ? 'bg-[#343541] border border-gray-700' : 'bg-white border border-gray-200'}`}>

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
            {t('login')}
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
            {t('register')}
          </button>
        </div>

        {/* 登录表单 */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 用户名字段（仅注册时显示） */}
          {!isLoginMode && (
            <div>
              <label className={`block text-sm font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-700'}`}>
                {t('username')}
              </label>
              <div className="relative">
                <User className={`absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`} />
                <Input
                  type="text"
                  value={formData.username}
                  onChange={(e) => updateFormData('username', e.target.value)}
                  className={`pl-10 pr-10 ${isDarkMode ? 'bg-gray-600 border-gray-500 text-white placeholder-gray-300' : 'bg-white border-gray-300'} ${
                    formData.username && (validationStatus.username === true ? 'border-green-500' : validationStatus.username === false ? 'border-red-500' : '')
                  }`}
                  placeholder={t('enterUsername')}
                  disabled={isLoading}
                />
                {formData.username && (
                  <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                    {validationStatus.username === true ? (
                      <Check className="w-4 h-4 text-green-500" />
                    ) : validationStatus.username === false ? (
                      <X className="w-4 h-4 text-red-500" />
                    ) : null}
                  </div>
                )}
              </div>
              {errors.username && (
                <p className="mt-1 text-sm text-red-500">{errors.username}</p>
              )}
            </div>
          )}

          {/* 邮箱字段 */}
          <div>
            <label className={`block text-sm font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-700'}`}>
              {t('emailAddress')}
            </label>
            <div className="relative">
              <Mail className={`absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`} />
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => updateFormData('email', e.target.value)}
                className={`pl-10 pr-10 ${isDarkMode ? 'bg-gray-600 border-gray-500 text-white placeholder-gray-300' : 'bg-white border-gray-300'} ${
                  formData.email && (validationStatus.email === true ? 'border-green-500' : validationStatus.email === false ? 'border-red-500' : '')
                }`}
                placeholder={t('enterEmail')}
                disabled={isLoading}
              />
              {formData.email && (
                <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                  {validationStatus.email === true ? (
                    <Check className="w-4 h-4 text-green-500" />
                  ) : validationStatus.email === false ? (
                    <X className="w-4 h-4 text-red-500" />
                  ) : null}
                </div>
              )}
            </div>
            {errors.email && (
              <p className="mt-1 text-sm text-red-500">{errors.email}</p>
            )}
          </div>

          {/* 密码字段 */}
          <div>
            <label className={`block text-sm font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-700'}`}>
              {t('password')}
            </label>
            <div className="relative">
              <Lock className={`absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`} />
              <Input
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={(e) => updateFormData('password', e.target.value)}
                className={`pl-10 pr-10 ${isDarkMode ? 'bg-gray-600 border-gray-500 text-white placeholder-gray-300' : 'bg-white border-gray-300'} ${
                  formData.password && (validationStatus.password === true ? 'border-green-500' : validationStatus.password === false ? 'border-red-500' : '')
                }`}
                placeholder={t('enterPassword')}
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
            
            {/* 密码强度指示器（仅注册模式） */}
            {!isLoginMode && formData.password && (
              <div className="mt-2 space-y-1">
                <div className="text-xs font-medium text-gray-600 dark:text-gray-400">{t('passwordStrengthRequirements')}</div>
                {passwordRules.map((rule) => {
                  const passed = rule.test(formData.password);
                  return (
                    <div key={rule.key} className={`flex items-center text-xs ${passed ? 'text-green-600 dark:text-green-400' : 'text-gray-500 dark:text-gray-400'}`}>
                      {passed ? (
                        <Check className="w-3 h-3 mr-1" />
                      ) : (
                        <X className="w-3 h-3 mr-1" />
                      )}
                      {rule.label}
                    </div>
                  );
                })}
              </div>
            )}
            
            {errors.password && (
              <p className="mt-1 text-sm text-red-500">{errors.password}</p>
            )}
          </div>

          {/* 忘记密码链接（仅登录时显示） */}
          {isLoginMode && (
            <div className="text-right">
              <button
                type="button"
                className={`text-sm ${isDarkMode ? 'text-gray-300 hover:text-white' : 'text-gray-600 hover:text-gray-900'} hover:underline`}
              >
                {t('forgotPassword')}
              </button>
            </div>
          )}

          {/* 提交按钮 */}
          <Button
            type="submit"
            disabled={isLoading}
            className={`w-full py-3 ${isDarkMode ? 'bg-gray-700 hover:bg-gray-800' : 'bg-gray-800 hover:bg-gray-900'} text-white font-medium`}
          >
            {isLoading ? (
              <div className="flex items-center justify-center">
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                {isLoginMode ? t('loginLoading') : t('registerLoading')}
              </div>
            ) : (
              isLoginMode ? t('login') : t('register')
            )}
          </Button>
        </form>

        {/* 提示信息 */}
        <div className={`mt-6 text-center text-sm ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
          {isLoginMode ? (
            <>
              {t('noAccount')}
              <button
                type="button"
                onClick={() => setIsLoginMode(false)}
                className={`ml-1 ${isDarkMode ? 'text-white hover:text-gray-200' : 'text-gray-900 hover:text-black'} hover:underline`}
              >
                {t('registerNow')}
              </button>
            </>
          ) : (
            <>
              {t('hasAccount')}
              <button
                type="button"
                onClick={() => setIsLoginMode(true)}
                className={`ml-1 ${isDarkMode ? 'text-white hover:text-gray-200' : 'text-gray-900 hover:text-black'} hover:underline`}
              >
                {t('loginNow')}
              </button>
            </>
          )}
        </div>

      </div>
    </div>
  );
}
