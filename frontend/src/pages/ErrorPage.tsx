import { useNavigate, useRouteError, useLocation } from 'react-router-dom';
import { AlertTriangle, Home, RefreshCw, ArrowLeft, Mail, Bug, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { detectAutoTheme } from '@/utils/language';

interface ErrorInfo {
  status?: number;
  statusText?: string;
  message?: string;
  stack?: string;
}

export function ErrorPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const error = useRouteError() as ErrorInfo;
  const isDarkMode = detectAutoTheme() === 'dark';

  // 获取详细错误信息
  const getDetailedErrorInfo = () => {
    const timestamp = new Date().toISOString();
    const userAgent = navigator.userAgent;
    const referrer = document.referrer || '直接访问';
    
    if (error?.status === 404) {
      return {
        title: '页面未找到 (404)',
        description: '抱歉，您访问的页面不存在或已被移动。',
        suggestion: '请检查URL是否正确，或返回首页继续浏览。',
        details: {
          errorCode: 'PAGE_NOT_FOUND',
          requestedPath: location.pathname,
          timestamp,
          possibleCauses: [
            'URL地址输入错误',
            '页面已被删除或移动',
            '链接已过期',
            '服务器路由配置问题'
          ]
        }
      };
    }
    
    if (error?.status === 403) {
      return {
        title: '访问被拒绝 (403)',
        description: '您没有权限访问此页面或资源。',
        suggestion: '请联系管理员获取相应权限，或返回上一页。',
        details: {
          errorCode: 'ACCESS_DENIED',
          requestedPath: location.pathname,
          timestamp,
          possibleCauses: [
            '用户权限不足',
            'JWT令牌已过期',
            '项目访问权限限制',
            '服务器认证配置问题'
          ]
        }
      };
    }
    
    if (error?.status === 500) {
      return {
        title: '服务器内部错误 (500)',
        description: '服务器遇到了一个内部错误，无法完成您的请求。',
        suggestion: '请稍后重试，如果问题持续存在，请联系技术支持。',
        details: {
          errorCode: 'INTERNAL_SERVER_ERROR',
          requestedPath: location.pathname,
          timestamp,
          possibleCauses: [
            '后端服务崩溃',
            '数据库连接失败',
            'API接口异常',
            '服务器资源不足'
          ]
        }
      };
    }

    // 网络错误
    if (error?.message?.includes('fetch') || error?.message?.includes('network')) {
      return {
        title: '网络连接错误',
        description: '无法连接到服务器，请检查您的网络连接。',
        suggestion: '请检查网络连接状态，或稍后重试。',
        details: {
          errorCode: 'NETWORK_ERROR',
          requestedPath: location.pathname,
          timestamp,
          possibleCauses: [
            '网络连接中断',
            '服务器无响应',
            'DNS解析失败',
            '防火墙阻止连接'
          ]
        }
      };
    }

    // JavaScript运行时错误
    if (error?.message) {
      return {
        title: '应用程序错误',
        description: error.message,
        suggestion: '请刷新页面重试，如果问题持续存在，请联系技术支持。',
        details: {
          errorCode: 'RUNTIME_ERROR',
          requestedPath: location.pathname,
          timestamp,
          errorStack: error.stack || '无堆栈信息',
          possibleCauses: [
            'JavaScript运行时异常',
            '组件渲染错误',
            '状态管理问题',
            '第三方库兼容性问题'
          ]
        }
      };
    }
    
    return {
      title: '未知错误',
      description: '系统遇到了意外错误，无法确定具体原因。',
      suggestion: '请尝试刷新页面或返回首页，如果问题持续存在，请联系技术支持。',
      details: {
        errorCode: 'UNKNOWN_ERROR',
        requestedPath: location.pathname,
        timestamp,
        userAgent,
        referrer,
        possibleCauses: [
          '浏览器兼容性问题',
          '缓存数据损坏',
          '系统资源不足',
          '未知的程序异常'
        ]
      }
    };
  };

  const errorInfo = getDetailedErrorInfo();

  const handleGoHome = () => {
    navigate('/');
  };

  const handleGoBack = () => {
    navigate(-1);
  };

  const handleRefresh = () => {
    window.location.reload();
  };

  // 发送技术支持邮件
  const handleContactSupport = () => {
    const subject = encodeURIComponent(`Lumidoc Intelligence 错误报告 - ${errorInfo.details.errorCode}`);
    const body = encodeURIComponent(`
亲爱的技术支持团队，

我在使用 Lumidoc Intelligence 时遇到了以下错误：

错误信息：
- 错误代码：${errorInfo.details.errorCode}
- 错误标题：${errorInfo.title}
- 错误描述：${errorInfo.description}
- 访问路径：${errorInfo.details.requestedPath}
- 发生时间：${errorInfo.details.timestamp}

可能原因：
${errorInfo.details.possibleCauses.map(cause => `- ${cause}`).join('\n')}

用户环境：
- 浏览器：${navigator.userAgent}
- 当前URL：${window.location.href}
- 来源页面：${document.referrer || '直接访问'}

${errorInfo.details.errorStack ? `错误堆栈：\n${errorInfo.details.errorStack}` : ''}

请协助解决此问题，谢谢！

此邮件由 Lumidoc Intelligence 错误页面自动生成。
    `);
    
    window.location.href = `mailto:wil.yiwen.lu@gmail.com?subject=${subject}&body=${body}`;
  };

  return (
    <div className={`min-h-screen flex items-center justify-center px-4 py-8 ${
      isDarkMode ? 'bg-[#212121] text-gray-100' : 'bg-white text-gray-900'
    }`}>
      {/* 错误页面容器 */}
      <div className={`max-w-4xl w-full space-y-8`}>
        {/* 主要错误信息 */}
        <div className={`text-center space-y-6 p-8 rounded-2xl border ${
          isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
        } shadow-2xl`}>
          {/* 错误图标 */}
          <div className="flex justify-center">
            <div className={`p-6 rounded-full ${
              isDarkMode ? 'bg-red-900/30' : 'bg-red-100'
            }`}>
              <AlertTriangle className={`w-16 h-16 ${
                isDarkMode ? 'text-red-400' : 'text-red-600'
              }`} />
            </div>
          </div>

          {/* 错误标题和描述 */}
          <div className="space-y-4">
            <h1 className="text-4xl font-bold">
              {errorInfo.title}
            </h1>
            <p className={`text-lg max-w-2xl mx-auto ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
              {errorInfo.description}
            </p>
            <p className={`text-sm max-w-2xl mx-auto ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
              {errorInfo.suggestion}
            </p>
          </div>

          {/* 操作按钮 */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
            <Button
              onClick={handleGoHome}
              className="flex items-center space-x-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white border-0"
            >
              <Home className="w-4 h-4" />
              <span>返回首页</span>
            </Button>
            
            <Button
              onClick={handleGoBack}
              variant="outline"
              className={`flex items-center space-x-2 px-6 py-3 ${
                isDarkMode 
                  ? 'border-gray-600 text-gray-300 hover:bg-gray-800 hover:text-white' 
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              <ArrowLeft className="w-4 h-4" />
              <span>返回上页</span>
            </Button>
            
            <Button
              onClick={handleRefresh}
              variant="outline"
              className={`flex items-center space-x-2 px-6 py-3 ${
                isDarkMode 
                  ? 'border-gray-600 text-gray-300 hover:bg-gray-800 hover:text-white' 
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              <RefreshCw className="w-4 h-4" />
              <span>刷新页面</span>
            </Button>
          </div>
        </div>

        {/* 详细错误信息 */}
        <div className={`p-6 rounded-2xl border ${
          isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
        } shadow-xl`}>
          <div className="grid md:grid-cols-2 gap-6">
            {/* 错误详情 */}
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <Bug className={`w-5 h-5 ${isDarkMode ? 'text-red-400' : 'text-red-600'}`} />
                <h3 className="text-lg font-semibold">错误详情</h3>
              </div>
              
              <div className="space-y-3 text-sm">
                <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <span className="font-medium">错误代码：</span>
                  <span className={`ml-2 ${isDarkMode ? 'text-red-400' : 'text-red-600'}`}>
                    {errorInfo.details.errorCode}
                  </span>
                </div>
                
                <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <span className="font-medium">访问路径：</span>
                  <span className="ml-2 font-mono text-xs">
                    {errorInfo.details.requestedPath}
                  </span>
                </div>
                
                <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <div className="flex items-center space-x-2">
                    <Clock className="w-4 h-4" />
                    <span className="font-medium">发生时间：</span>
                  </div>
                  <span className="ml-6 text-xs">
                    {new Date(errorInfo.details.timestamp).toLocaleString('zh-CN')}
                  </span>
                </div>
              </div>
            </div>

            {/* 可能原因 */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">可能原因</h3>
              <ul className="space-y-2 text-sm">
                {errorInfo.details.possibleCauses.map((cause, index) => (
                  <li key={index} className={`flex items-start space-x-2 p-2 rounded ${
                    isDarkMode ? 'bg-gray-800' : 'bg-gray-50'
                  }`}>
                    <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                      isDarkMode ? 'bg-orange-900 text-orange-300' : 'bg-orange-100 text-orange-600'
                    }`}>
                      {index + 1}
                    </span>
                    <span>{cause}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* 技术支持联系 */}
        <div className={`p-6 rounded-2xl border text-center ${
          isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
        } shadow-xl`}>
          <div className="space-y-4">
            <div className="flex justify-center">
              <div className={`p-4 rounded-full ${
                isDarkMode ? 'bg-blue-900/30' : 'bg-blue-100'
              }`}>
                <Mail className={`w-8 h-8 ${
                  isDarkMode ? 'text-blue-400' : 'text-blue-600'
                }`} />
              </div>
            </div>
            
            <div className="space-y-2">
              <h3 className="text-xl font-semibold">需要技术支持？</h3>
              <p className={`text-sm max-w-md mx-auto ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                如果问题持续存在，请点击下方按钮联系我们的技术支持团队。我们会自动为您生成包含错误详情的邮件。
              </p>
            </div>

            <Button
              onClick={handleContactSupport}
              className="flex items-center space-x-2 px-6 py-3 bg-green-600 hover:bg-green-700 text-white border-0"
            >
              <Mail className="w-4 h-4" />
              <span>联系技术支持</span>
            </Button>
            
            <p className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
              支持邮箱：wil.yiwen.lu@gmail.com
            </p>
          </div>
        </div>

        {/* 页脚信息 */}
        <div className="text-center">
          <p className={`text-sm ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
            © {new Date().getFullYear()} Lumidoc Intelligence
          </p>
        </div>
      </div>
    </div>
  );
}
