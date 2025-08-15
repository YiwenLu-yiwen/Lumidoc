import { useState, useEffect, useRef } from 'react';
import { 
  Brain, 
  Zap, 
  Check, 
  ChevronDown, 
  Wifi, 
  WifiOff, 
  Server,
  Cloud,
  HardDrive
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ModelInfo, getAvailableModels } from '@/api/modelService';
import { detectAutoTheme } from '@/utils/language';

interface ModelSelectorProps {
  selectedModel?: ModelInfo | null;
  onModelSelect: (model: ModelInfo) => void;
  disabled?: boolean;
  className?: string;
}

export function ModelSelector({ 
  selectedModel, 
  onModelSelect, 
  disabled = false,
  className = '' 
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  // const [currentLanguage] = useState('zh-CN'); // 简化语言处理
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 获取当前主题
  const isDarkMode = detectAutoTheme() === 'dark';

  // 获取翻译文本的简化函数
  // const t = (key: string) => getTranslation(currentLanguage, key as any);

  // 获取提供商图标
  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'openai':
      case 'azure':
        return <Cloud className="w-3 h-3" />;
      case 'deepseek':
        return <Server className="w-3 h-3" />;
      case 'ollama':
      case 'local':
        return <HardDrive className="w-3 h-3" />;
      default:
        return <Server className="w-3 h-3" />;
    }
  };

  // 获取提供商颜色
  const getProviderColor = (provider: string) => {
    switch (provider) {
      case 'openai':
        return 'text-green-500';
      case 'azure':
        return 'text-blue-500';
      case 'deepseek':
        return 'text-purple-500';
      case 'ollama':
      case 'local':
        return 'text-orange-500';
      default:
        return 'text-gray-500';
    }
  };

  // 加载模型列表
  useEffect(() => {
    const loadModels = async () => {
      setLoading(true);
      try {
        const response = await getAvailableModels();
        setModels(response.models);
        
        // 如果没有选中模型，自动选择第一个可用模型
        if (!selectedModel && response.models.length > 0) {
          const firstAvailable = response.models.find(m => m.isAvailable);
          if (firstAvailable) {
            onModelSelect(firstAvailable);
          }
        }
      } catch (error) {
        console.error('加载模型列表失败:', error);
      } finally {
        setLoading(false);
      }
    };

    loadModels();
  }, [selectedModel, onModelSelect]);

  // 点击外部关闭下拉菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 按类型和可用性分组模型
  const groupedModels = models.reduce((acc, model) => {
    const key = model.type;
    if (!acc[key]) {
      acc[key] = { available: [], unavailable: [] };
    }
    
    if (model.isAvailable) {
      acc[key].available.push(model);
    } else {
      acc[key].unavailable.push(model);
    }
    
    return acc;
  }, {} as Record<string, { available: ModelInfo[], unavailable: ModelInfo[] }>);

  const handleModelSelect = (model: ModelInfo) => {
    if (!model.isAvailable || disabled) return;
    onModelSelect(model);
    setIsOpen(false);
  };

  if (loading) {
    return (
      <div className={`flex items-center space-x-2 px-3 py-2 rounded-lg ${
        isDarkMode ? 'bg-gray-700' : 'bg-gray-100'
      }`}>
        <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500"></div>
        <span className="text-sm">加载模型...</span>
      </div>
    );
  }

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* 选择器按钮 */}
      <Button
        variant="outline"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={`w-full justify-between ${
          isDarkMode 
            ? 'bg-gray-800 border-gray-700 hover:bg-gray-700' 
            : 'bg-white border-gray-200 hover:bg-gray-50'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <div className="flex items-center space-x-2 flex-1 min-w-0">
          {selectedModel ? (
            <>
              {/* 模型类型图标 */}
              {selectedModel.type === 'thinking' ? (
                <Brain className="w-4 h-4 text-purple-500" />
              ) : (
                <Zap className="w-4 h-4 text-green-500" />
              )}
              
              {/* 模型信息 */}
              <div className="flex items-center space-x-2 flex-1 min-w-0">
                <span className="font-medium truncate">
                  {selectedModel.displayName}
                </span>
                
                {/* 提供商图标 */}
                <div className={`flex items-center ${getProviderColor(selectedModel.provider)}`}>
                  {getProviderIcon(selectedModel.provider)}
                </div>
                
                {/* 可用性指示器 */}
                {selectedModel.isAvailable ? (
                  <Wifi className="w-3 h-3 text-green-500" />
                ) : (
                  <WifiOff className="w-3 h-3 text-red-500" />
                )}
              </div>
            </>
          ) : (
            <span className="text-gray-500">选择模型</span>
          )}
        </div>
        
        <ChevronDown className={`w-4 h-4 transition-transform ${
          isOpen ? 'transform rotate-180' : ''
        }`} />
      </Button>

      {/* 下拉菜单 */}
      {isOpen && (
        <div className={`absolute top-full left-0 right-0 mt-2 py-2 rounded-xl shadow-2xl z-50 max-h-96 overflow-y-auto ${
          isDarkMode ? 'bg-[#2a2a2a] border border-gray-700' : 'bg-white border border-gray-200'
        }`}>
          {/* 思考模型分组 */}
          {groupedModels.thinking && (
            <div className="mb-4">
              <div className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider flex items-center space-x-2 ${
                isDarkMode ? 'text-gray-400' : 'text-gray-500'
              }`}>
                <Brain className="w-3 h-3" />
                <span>思考模型</span>
              </div>
              
              {/* 可用的思考模型 */}
              {groupedModels.thinking.available.map((model) => (
                <button
                  key={model.id}
                  onClick={() => handleModelSelect(model)}
                  className={`w-full px-4 py-3 text-left flex items-center justify-between transition-colors ${
                    selectedModel?.id === model.id
                      ? isDarkMode ? 'bg-purple-900/30 text-purple-300' : 'bg-purple-50 text-purple-700'
                      : isDarkMode ? 'hover:bg-gray-700 text-gray-200' : 'hover:bg-gray-50 text-gray-700'
                  }`}
                >
                  <div className="flex items-center space-x-3 flex-1 min-w-0">
                    <div className={`flex items-center ${getProviderColor(model.provider)}`}>
                      {getProviderIcon(model.provider)}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{model.displayName}</div>
                      {model.description && (
                        <div className={`text-xs truncate ${
                          isDarkMode ? 'text-gray-400' : 'text-gray-500'
                        }`}>
                          {model.description}
                        </div>
                      )}
                    </div>
                    
                    <Wifi className="w-3 h-3 text-green-500" />
                  </div>
                  
                  {selectedModel?.id === model.id && (
                    <Check className="w-4 h-4 text-purple-500" />
                  )}
                </button>
              ))}
              
              {/* 不可用的思考模型 */}
              {groupedModels.thinking.unavailable.map((model) => (
                <button
                  key={model.id}
                  disabled
                  className={`w-full px-4 py-3 text-left flex items-center justify-between opacity-50 cursor-not-allowed ${
                    isDarkMode ? 'text-gray-400' : 'text-gray-500'
                  }`}
                >
                  <div className="flex items-center space-x-3 flex-1 min-w-0">
                    <div className={`flex items-center ${getProviderColor(model.provider)}`}>
                      {getProviderIcon(model.provider)}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{model.displayName}</div>
                      {model.description && (
                        <div className="text-xs truncate">
                          {model.description}
                        </div>
                      )}
                    </div>
                    
                    <WifiOff className="w-3 h-3 text-red-500" />
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* 快速模型分组 */}
          {groupedModels.fast && (
            <div>
              <div className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider flex items-center space-x-2 ${
                isDarkMode ? 'text-gray-400' : 'text-gray-500'
              }`}>
                <Zap className="w-3 h-3" />
                <span>快速模型</span>
              </div>
              
              {/* 可用的快速模型 */}
              {groupedModels.fast.available.map((model) => (
                <button
                  key={model.id}
                  onClick={() => handleModelSelect(model)}
                  className={`w-full px-4 py-3 text-left flex items-center justify-between transition-colors ${
                    selectedModel?.id === model.id
                      ? isDarkMode ? 'bg-green-900/30 text-green-300' : 'bg-green-50 text-green-700'
                      : isDarkMode ? 'hover:bg-gray-700 text-gray-200' : 'hover:bg-gray-50 text-gray-700'
                  }`}
                >
                  <div className="flex items-center space-x-3 flex-1 min-w-0">
                    <div className={`flex items-center ${getProviderColor(model.provider)}`}>
                      {getProviderIcon(model.provider)}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{model.displayName}</div>
                      {model.description && (
                        <div className={`text-xs truncate ${
                          isDarkMode ? 'text-gray-400' : 'text-gray-500'
                        }`}>
                          {model.description}
                        </div>
                      )}
                    </div>
                    
                    <Wifi className="w-3 h-3 text-green-500" />
                  </div>
                  
                  {selectedModel?.id === model.id && (
                    <Check className="w-4 h-4 text-green-500" />
                  )}
                </button>
              ))}
              
              {/* 不可用的快速模型 */}
              {groupedModels.fast.unavailable.map((model) => (
                <button
                  key={model.id}
                  disabled
                  className={`w-full px-4 py-3 text-left flex items-center justify-between opacity-50 cursor-not-allowed ${
                    isDarkMode ? 'text-gray-400' : 'text-gray-500'
                  }`}
                >
                  <div className="flex items-center space-x-3 flex-1 min-w-0">
                    <div className={`flex items-center ${getProviderColor(model.provider)}`}>
                      {getProviderIcon(model.provider)}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{model.displayName}</div>
                      {model.description && (
                        <div className="text-xs truncate">
                          {model.description}
                        </div>
                      )}
                    </div>
                    
                    <WifiOff className="w-3 h-3 text-red-500" />
                  </div>
                </button>
              ))}
            </div>
          )}

          {models.length === 0 && (
            <div className={`px-4 py-6 text-center ${
              isDarkMode ? 'text-gray-400' : 'text-gray-500'
            }`}>
              <Server className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">暂无可用模型</p>
              <p className="text-xs mt-1">请检查LLM服务连接</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}