import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Send,
  Paperclip,
  Mic,
  Square,
  RotateCcw,
  Copy,
  ThumbsUp,
  ThumbsDown,
  BookOpen,
  FileText,
  Code,
  Calculator,
  Zap,
  Brain,
  Sparkles,
  ChevronDown,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Avatar } from '@/components/ui/avatar';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '@/context/AuthContext';

// 消息类型定义
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  isThinking?: boolean;
  thinkingSteps?: string[];
  attachments?: FileAttachment[];
  model?: 'fast' | 'thinking' | 'code' | 'creative';
  citations?: Citation[];
  metadata?: {
    tokens?: number;
    processingTime?: number;
    confidence?: number;
  };
}

interface FileAttachment {
  id: string;
  name: string;
  type: string;
  size: number;
  url?: string;
}

interface Citation {
  id: string;
  source: string;
  title: string;
  snippet: string;
  url?: string;
}

interface ModelOption {
  id: 'fast' | 'thinking' | 'code' | 'creative';
  name: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  badge?: string;
}

// 模型选项配置
const modelOptions: ModelOption[] = [
  {
    id: 'fast',
    name: '快速回答',
    description: '快速响应，适合简单问题',
    icon: <Zap className="w-4 h-4" />,
    color: 'text-green-600 bg-green-50 dark:bg-green-950',
    badge: '秒回'
  },
  {
    id: 'thinking',
    name: '深度思考',
    description: '深度分析，适合复杂问题',
    icon: <Brain className="w-4 h-4" />,
    color: 'text-blue-600 bg-blue-50 dark:bg-blue-950',
    badge: '推荐'
  },
  {
    id: 'code',
    name: '代码助手',
    description: '专业代码分析和生成',
    icon: <Code className="w-4 h-4" />,
    color: 'text-purple-600 bg-purple-50 dark:bg-purple-950'
  },
  {
    id: 'creative',
    name: '创意写作',
    description: '创意内容和文档写作',
    icon: <Sparkles className="w-4 h-4" />,
    color: 'text-pink-600 bg-pink-50 dark:bg-pink-950'
  }
];

// 快速操作建议
const quickSuggestions = [
  { text: '帮我分析这份文档', icon: <FileText className="w-4 h-4" /> },
  { text: '总结项目进展', icon: <BookOpen className="w-4 h-4" /> },
  { text: '生成代码示例', icon: <Code className="w-4 h-4" /> },
  { text: '数据可视化建议', icon: <Calculator className="w-4 h-4" /> }
];

export default function EnhancedChatInterface() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState<'fast' | 'thinking' | 'code' | 'creative'>('thinking');
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 自动滚动到底部
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // 自动调整输入框高度
  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [inputValue]);

  // 发送消息
  const handleSendMessage = async () => {
    if (!inputValue.trim() && attachments.length === 0) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
      attachments: attachments.length > 0 ? [...attachments] : undefined,
      model: selectedModel
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setAttachments([]);
    setIsLoading(true);
    setShowSuggestions(false);

    // 模拟AI回复
    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `基于您的 ${modelOptions.find(m => m.id === selectedModel)?.name} 请求，我正在处理您的问题...\n\n这是一个示例回答，展示了如何处理您的输入。实际回答会根据您的具体问题和选择的模型提供相应的深度分析。`,
        timestamp: new Date(),
        model: selectedModel,
        metadata: {
          tokens: 150,
          processingTime: 2.3,
          confidence: 0.95
        }
      };
      
      setMessages(prev => [...prev, assistantMessage]);
      setIsLoading(false);
    }, 1500);
  };

  // 键盘快捷键
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 文件上传
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const newAttachments = files.map(file => ({
      id: Date.now().toString() + Math.random(),
      name: file.name,
      type: file.type,
      size: file.size
    }));
    setAttachments(prev => [...prev, ...newAttachments]);
  };

  // 删除附件
  const removeAttachment = (id: string) => {
    setAttachments(prev => prev.filter(att => att.id !== id));
  };

  // 使用建议
  const handleSuggestion = (suggestion: string) => {
    setInputValue(suggestion);
    setShowSuggestions(false);
    textareaRef.current?.focus();
  };

  // 渲染消息
  const renderMessage = (message: Message) => {
    const isUser = message.role === 'user';
    const selectedModelOption = modelOptions.find(m => m.id === message.model);

    return (
      <div key={message.id} className={`mb-6 ${isUser ? 'ml-12' : 'mr-12'}`}>
        <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
          {/* 助手头像 */}
          {!isUser && (
            <Avatar className="w-8 h-8 flex-shrink-0">
              <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Brain className="w-4 h-4 text-white" />
              </div>
            </Avatar>
          )}

          {/* 消息内容 */}
          <div className={`flex-1 ${isUser ? 'text-right' : ''}`}>
            {/* 消息头部 */}
            <div className={`flex items-center gap-2 mb-1 ${isUser ? 'justify-end' : 'justify-start'}`}>
              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {isUser ? '您' : 'Lumidoc'}
              </span>
              {selectedModelOption && (
                <span className={`text-xs px-2 py-0.5 rounded-full ${selectedModelOption.color}`}>
                  {selectedModelOption.badge || selectedModelOption.name}
                </span>
              )}
              <span className="text-xs text-gray-500">
                {message.timestamp.toLocaleTimeString('zh-CN', { 
                  hour: '2-digit', 
                  minute: '2-digit' 
                })}
              </span>
            </div>

            {/* 消息气泡 */}
            <div
              className={`
                relative px-4 py-3 rounded-2xl shadow-sm
                ${isUser 
                  ? 'bg-blue-500 text-white ml-8' 
                  : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
                }
              `}
            >
              {/* 附件显示 */}
              {message.attachments && message.attachments.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-2">
                  {message.attachments.map(att => (
                    <div
                      key={att.id}
                      className="flex items-center gap-2 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-xs"
                    >
                      <FileText className="w-3 h-3" />
                      <span>{att.name}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* 消息文本 */}
              <div className={`${isUser ? 'text-white' : 'text-gray-900 dark:text-gray-100'}`}>
                <div className="prose prose-sm max-w-none dark:prose-invert">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
              </div>

              {/* 元数据 */}
              {message.metadata && !isUser && (
                <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600 text-xs text-gray-500 flex gap-4">
                  {message.metadata.tokens && (
                    <span>Tokens: {message.metadata.tokens}</span>
                  )}
                  {message.metadata.processingTime && (
                    <span>用时: {message.metadata.processingTime}s</span>
                  )}
                  {message.metadata.confidence && (
                    <span>可信度: {Math.round(message.metadata.confidence * 100)}%</span>
                  )}
                </div>
              )}
            </div>

            {/* 消息操作 */}
            {!isUser && (
              <div className="flex items-center gap-1 mt-2">
                <Button size="sm" variant="ghost" className="h-6 px-2 text-xs">
                  <Copy className="w-3 h-3 mr-1" />
                  复制
                </Button>
                <Button size="sm" variant="ghost" className="h-6 px-2 text-xs">
                  <ThumbsUp className="w-3 h-3 mr-1" />
                  好评
                </Button>
                <Button size="sm" variant="ghost" className="h-6 px-2 text-xs">
                  <ThumbsDown className="w-3 h-3 mr-1" />
                  差评
                </Button>
                <Button size="sm" variant="ghost" className="h-6 px-2 text-xs">
                  <RotateCcw className="w-3 h-3 mr-1" />
                  重生成
                </Button>
              </div>
            )}
          </div>

          {/* 用户头像 */}
          {isUser && (
            <Avatar className="w-8 h-8 flex-shrink-0">
              <img
                src={user?.avatar || `https://ui-avatars.com/api/?name=${user?.username || 'User'}&background=3b82f6&color=fff`}
                alt={user?.username || 'User'}
              />
            </Avatar>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-950">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 && showSuggestions ? (
          /* 欢迎界面和建议 */
          <div className="h-full flex flex-col items-center justify-center max-w-3xl mx-auto">
            <div className="text-center mb-8">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Brain className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                欢迎使用 Lumidoc 智能助手
              </h1>
              <p className="text-gray-600 dark:text-gray-400">
                我可以帮您分析文档、回答问题、生成内容，让我们开始对话吧！
              </p>
            </div>

            {/* 快速建议 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
              {quickSuggestions.map((suggestion, index) => (
                <Button
                  key={index}
                  variant="outline"
                  className="h-auto p-4 text-left justify-start hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                  onClick={() => handleSuggestion(suggestion.text)}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center">
                      {suggestion.icon}
                    </div>
                    <span className="text-sm">{suggestion.text}</span>
                  </div>
                </Button>
              ))}
            </div>
          </div>
        ) : (
          /* 消息列表 */
          <div className="max-w-4xl mx-auto">
            {messages.map(renderMessage)}
            {isLoading && (
              <div className="mb-6 mr-12">
                <div className="flex gap-3">
                  <Avatar className="w-8 h-8 flex-shrink-0">
                    <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                      <Brain className="w-4 h-4 text-white animate-pulse" />
                    </div>
                  </Avatar>
                  <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex gap-1">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                      </div>
                      <span className="text-sm text-gray-500">正在思考...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 输入区域 */}
      <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950">
        <div className="max-w-4xl mx-auto px-6 py-4">
          {/* 附件显示 */}
          {attachments.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {attachments.map(att => (
                <div
                  key={att.id}
                  className="flex items-center gap-2 bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded-lg"
                >
                  <FileText className="w-4 h-4" />
                  <span className="text-sm">{att.name}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="w-4 h-4 p-0 hover:bg-gray-200 dark:hover:bg-gray-700"
                    onClick={() => removeAttachment(att.id)}
                  >
                    <X className="w-3 h-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          {/* 主输入区域 */}
          <div className="relative">
            <Textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入您的问题，按 Enter 发送，Shift + Enter 换行..."
              className="min-h-[50px] pr-24 resize-none border-gray-300 dark:border-gray-600 focus:border-blue-500 dark:focus:border-blue-400"
              disabled={isLoading}
            />

            {/* 右侧操作按钮 */}
            <div className="absolute right-2 bottom-2 flex items-center gap-1">
              {/* 语音输入 */}
              <Button
                size="sm"
                variant="ghost"
                className="w-8 h-8 p-0"
                onClick={() => setIsRecording(!isRecording)}
                disabled={isLoading}
              >
                {isRecording ? (
                  <Square className="w-4 h-4 text-red-500" />
                ) : (
                  <Mic className="w-4 h-4" />
                )}
              </Button>

              {/* 文件上传 */}
              <Button
                size="sm"
                variant="ghost"
                className="w-8 h-8 p-0"
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
              >
                <Paperclip className="w-4 h-4" />
              </Button>

              {/* 发送按钮 */}
              <Button
                size="sm"
                className="w-8 h-8 p-0 bg-blue-500 hover:bg-blue-600 disabled:opacity-50"
                onClick={handleSendMessage}
                disabled={isLoading || (!inputValue.trim() && attachments.length === 0)}
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* 底部工具栏 */}
          <div className="flex items-center justify-between mt-3 text-sm text-gray-500">
            {/* 模型选择器 */}
            <div className="relative">
              <Button
                size="sm"
                variant="ghost"
                className="gap-2"
                onClick={() => setShowModelSelector(!showModelSelector)}
              >
                {modelOptions.find(m => m.id === selectedModel)?.icon}
                <span>{modelOptions.find(m => m.id === selectedModel)?.name}</span>
                <ChevronDown className="w-3 h-3" />
              </Button>

              {showModelSelector && (
                <div className="absolute bottom-full left-0 mb-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-2 w-64">
                  {modelOptions.map(option => (
                    <button
                      key={option.id}
                      className={`
                        w-full text-left p-3 rounded-lg transition-colors mb-1
                        ${selectedModel === option.id 
                          ? 'bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800' 
                          : 'hover:bg-gray-50 dark:hover:bg-gray-700'
                        }
                      `}
                      onClick={() => {
                        setSelectedModel(option.id);
                        setShowModelSelector(false);
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${option.color}`}>
                          {option.icon}
                        </div>
                        <div>
                          <div className="font-medium flex items-center gap-2">
                            {option.name}
                            {option.badge && (
                              <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 px-1.5 py-0.5 rounded">
                                {option.badge}
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5">
                            {option.description}
                          </div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center gap-4">
              <span>{inputValue.length} 字符</span>
              <span>Lumidoc AI 提供技术支持</span>
            </div>
          </div>
        </div>
      </div>

      {/* 隐藏的文件输入 */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={handleFileUpload}
        accept=".pdf,.doc,.docx,.txt,.md,.jpg,.png,.gif"
      />
    </div>
  );
}
