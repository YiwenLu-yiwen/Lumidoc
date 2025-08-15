import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, 
  Paperclip, 
  Copy, 
  Edit, 
  Trash2, 
  ThumbsUp, 
  ThumbsDown, 
  RotateCcw,
  Check,
  X,
  Brain,
  Zap,
  Settings2,
  Mic,
  MicOff
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import ReactMarkdown from 'react-markdown';
import { detectAutoTheme } from '@/utils/language';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isThinking?: boolean;
  thinkingContent?: string;
  model?: 'thinking' | 'fast';
  isEditing?: boolean;
  originalContent?: string;
  thinkingSteps?: string[];
  currentThinkingStep?: number;
}

interface ChatGPTInterfaceProps {
  onSendMessage?: (message: string, model: 'thinking' | 'fast') => void;
  isLoading?: boolean;
  selectedModel?: 'thinking' | 'fast';
  onModelChange?: (model: 'thinking' | 'fast') => void;
}

// 思考步骤显示组件
function ThinkingSteps({ steps, currentStep }: { steps: string[], currentStep: number }) {
  const [displayText, setDisplayText] = useState('');
  const [isTyping, setIsTyping] = useState(true);
  
  useEffect(() => {
    if (currentStep < steps.length) {
      const currentText = steps[currentStep];
      let charIndex = 0;
      setDisplayText('');
      setIsTyping(true);
      
      const typeText = () => {
        if (charIndex < currentText.length) {
          setDisplayText(currentText.slice(0, charIndex + 1));
          charIndex++;
          setTimeout(typeText, 30); // 打字效果速度
        } else {
          setIsTyping(false);
          // 显示完当前步骤后，等待一会儿再继续下一步
          setTimeout(() => {
            if (currentStep < steps.length - 1) {
              // 这里应该由父组件来控制步骤切换
            }
          }, 1000);
        }
      };
      
      typeText();
    }
  }, [steps, currentStep]);
  
  return (
    <div className="mb-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border-l-4 border-gray-400">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"></div>
        <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
          思考中...
        </span>
      </div>
      <div className="text-sm text-gray-600 dark:text-gray-300 min-h-[20px]">
        {displayText}
        {isTyping && <span className="animate-pulse">|</span>}
      </div>
    </div>
  );
}

// 模拟消息数据
const mockMessages: Message[] = [
  {
    id: '1',
    role: 'user',
    content: '请帮我分析这份财务报告，重点关注收入增长和成本控制情况。',
    timestamp: new Date('2024-01-15T10:30:00')
  },
  {
    id: '2',
    role: 'assistant',
    content: `我来帮您分析这份财务报告的收入增长和成本控制情况。

## 收入增长分析

### 营业收入趋势
- **总营业收入**: 同比增长15.2%，达到5.8亿元
- **主营业务收入**: 占比92.3%，增长13.8%
- **其他业务收入**: 占比7.7%，增长28.5%

### 收入结构变化
1. **产品销售收入**: 4.2亿元 (↑12.5%)
2. **服务收入**: 1.1亿元 (↑22.3%)  
3. **授权收入**: 0.5亿元 (↑8.7%)

## 成本控制情况

### 成本结构优化
- **营业成本**: 3.2亿元，成本率下降2.1个百分点至55.2%
- **销售费用**: 0.8亿元，费用率控制在13.8%
- **管理费用**: 0.4亿元，同比下降5.3%

### 关键指标改善
- **毛利率**: 44.8% (↑2.1pp)
- **净利率**: 18.5% (↑1.8pp)
- **ROE**: 15.2% (↑2.3pp)

总体来看，公司在收入增长的同时，成本控制效果显著，盈利能力持续提升。`,
    timestamp: new Date('2024-01-15T10:31:00'),
    model: 'thinking',
    thinkingSteps: [
      '正在分析财务报告的整体结构...',
      '计算收入增长率和趋势变化...',
      '评估成本控制措施的有效性...',
      '分析盈利能力指标的变化...',
      '综合各项指标得出结论...'
    ]
  },
  {
    id: '3',
    role: 'user',
    content: '能详细说明一下毛利率提升的主要原因吗？',
    timestamp: new Date('2024-01-15T10:35:00')
  },
  {
    id: '4',
    role: 'assistant',
    content: `毛利率提升2.1个百分点的主要原因包括：

## 1. 产品结构优化 🎯
- **高毛利产品占比提升**: 从38%提升至45%
- **低毛利传统业务收缩**: 占比从25%下降至18%
- **新产品贡献**: 新推出的高端产品线贡献22%收入

## 2. 成本控制措施 💰
### 原材料成本优化
- 供应链整合节约成本3.2%
- 批量采购降低单价1.8%
- 替代材料应用节约2.1%

### 生产效率提升
- 自动化改造提升效率15%
- 良品率从94.2%提升至97.8%
- 人工成本占比下降1.5个百分点

## 3. 规模效应显现 📈
- 固定成本分摊减少
- 研发费用摊销效率提升
- 管理费用占收入比例下降

这些因素共同作用，使得毛利率实现了显著提升。`,
    timestamp: new Date('2024-01-15T10:36:00'),
    model: 'fast'
  }
];

export function ChatGPTInterface({ 
  onSendMessage, 
  isLoading = false,
  selectedModel = 'thinking',
  onModelChange 
}: ChatGPTInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>(mockMessages);
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [currentModel, setCurrentModel] = useState<'thinking' | 'fast'>(selectedModel);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState('');
  
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 获取当前主题
  const isDarkMode = detectAutoTheme() === 'dark';

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 自动调整文本框高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // 发送消息
  const handleSendMessage = () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');

    // 调用外部发送消息回调
    onSendMessage?.(input.trim(), currentModel);

    // 模拟AI回复（实际应用中由外部处理）
    if (!onSendMessage) {
      setTimeout(() => {
        const aiMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: '这是一个模拟回复。在实际应用中，这里会显示AI的真实回复。',
          timestamp: new Date(),
          model: currentModel,
          ...(currentModel === 'thinking' && {
            thinkingContent: '让我思考一下这个问题...\n\n分析用户的询问...\n\n准备回复...'
          })
        };
        setMessages(prev => [...prev, aiMessage]);
      }, 1000);
    }
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 复制消息内容
  const copyMessage = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      // 可以添加成功提示
    } catch (err) {
      console.error('复制失败:', err);
    }
  };

  // 开始编辑消息
  const startEditMessage = (messageId: string, content: string) => {
    setEditingMessageId(messageId);
    setEditingContent(content);
  };

  // 保存编辑
  const saveEditMessage = () => {
    if (!editingMessageId || !editingContent.trim()) return;

    setMessages(prev => prev.map(msg => 
      msg.id === editingMessageId 
        ? { ...msg, content: editingContent.trim(), originalContent: msg.content }
        : msg
    ));

    setEditingMessageId(null);
    setEditingContent('');
  };

  // 取消编辑
  const cancelEditMessage = () => {
    setEditingMessageId(null);
    setEditingContent('');
  };

  // 删除消息
  const deleteMessage = (messageId: string) => {
    setMessages(prev => prev.filter(msg => msg.id !== messageId));
  };

  // 重新生成回复
  const regenerateMessage = (messageId: string) => {
    const messageIndex = messages.findIndex(msg => msg.id === messageId);
    if (messageIndex === -1 || messages[messageIndex].role !== 'assistant') return;

    // 重新生成逻辑
    console.log('重新生成消息:', messageId);
  };

  // 文件上传
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    console.log('上传文件:', files);
    // 处理文件上传逻辑
  };

  // 语音输入
  const toggleRecording = () => {
    setIsRecording(!isRecording);
    // 实现语音识别逻辑
  };

  return (
    <div className={`flex flex-col h-full ${isDarkMode ? 'bg-[#212121]' : 'bg-white'}`}>
      {/* 聊天头部 */}
      <div className={`flex items-center justify-between p-4 border-b ${isDarkMode ? 'border-gray-800 bg-[#171717]' : 'border-gray-200 bg-white'}`}>
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">Lumidoc 智能助手</h2>
          <div className="flex items-center gap-2">
            <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${
              currentModel === 'thinking' 
                ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400'
                : 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
            }`}>
              {currentModel === 'thinking' ? (
                <><Brain className="w-3 h-3" /> 思考模型</>
              ) : (
                <><Zap className="w-3 h-3" /> 快速模型</>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowModelSelector(!showModelSelector)}
              className="p-1"
            >
              <Settings2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
        
        {showModelSelector && (
          <div className="absolute top-16 right-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-2 z-50">
            <div className="space-y-1">
              <button
                onClick={() => {
                  setCurrentModel('thinking');
                  onModelChange?.('thinking');
                  setShowModelSelector(false);
                }}
                className={`w-full text-left px-3 py-2 rounded flex items-center gap-2 ${
                  currentModel === 'thinking' ? 'bg-purple-100 dark:bg-purple-900/30' : 'hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                <Brain className="w-4 h-4" />
                <div>
                  <div className="font-medium">思考模型</div>
                  <div className="text-xs text-gray-500">深度思考，详细回复</div>
                </div>
              </button>
              <button
                onClick={() => {
                  setCurrentModel('fast');
                  onModelChange?.('fast');
                  setShowModelSelector(false);
                }}
                className={`w-full text-left px-3 py-2 rounded flex items-center gap-2 ${
                  currentModel === 'fast' ? 'bg-green-100 dark:bg-green-900/30' : 'hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                <Zap className="w-4 h-4" />
                <div>
                  <div className="font-medium">快速模型</div>
                  <div className="text-xs text-gray-500">快速响应，简洁回复</div>
                </div>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[70%] ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
              {/* 消息头部 */}
              <div className={`flex items-center gap-2 mb-2 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                  message.role === 'user' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
                }`}>
                  {message.role === 'user' ? 'U' : 'AI'}
                </div>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {message.timestamp.toLocaleTimeString()}
                </span>
                {message.model && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    message.model === 'thinking' 
                      ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400'
                      : 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
                  }`}>
                    {message.model === 'thinking' ? '思考' : '快速'}
                  </span>
                )}
              </div>

              {/* 思考过程（仅思考模型） */}
              {message.model === 'thinking' && message.thinkingSteps && (
                <ThinkingSteps 
                  steps={message.thinkingSteps} 
                  currentStep={message.currentThinkingStep || message.thinkingSteps.length - 1} 
                />
              )}

              {/* 消息内容 */}
              <div
                className={`relative group p-4 rounded-2xl ${
                  message.role === 'user'
                    ? isDarkMode 
                      ? 'bg-[#2d2d30] text-white' 
                      : 'bg-[#f0f0f0] text-gray-900'
                    : isDarkMode 
                      ? 'bg-[#1e1e1e] text-gray-100' 
                      : 'bg-white text-gray-900 border border-gray-200'
                }`}
              >
                {editingMessageId === message.id ? (
                  <div className="space-y-3">
                    <Textarea
                      value={editingContent}
                      onChange={(e) => setEditingContent(e.target.value)}
                      className="min-h-[80px] bg-white dark:bg-gray-700"
                      autoFocus
                    />
                    <div className="flex gap-2">
                      <Button size="sm" onClick={saveEditMessage}>
                        <Check className="w-4 h-4" />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={cancelEditMessage}>
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="prose prose-sm max-w-none dark:prose-invert">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>
                )}

                {/* 消息操作按钮 */}
                {editingMessageId !== message.id && (
                  <div className={`absolute top-2 ${message.role === 'user' ? 'left-2' : 'right-2'} opacity-0 group-hover:opacity-100 transition-opacity`}>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyMessage(message.content)}
                        className="p-1 h-6 w-6 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                      >
                        <Copy className="w-3 h-3" />
                      </Button>
                      
                      {message.role === 'user' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => startEditMessage(message.id, message.content)}
                          className="p-1 h-6 w-6 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                        >
                          <Edit className="w-3 h-3" />
                        </Button>
                      )}
                      
                      {message.role === 'assistant' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => regenerateMessage(message.id)}
                          className="p-1 h-6 w-6 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                        >
                          <RotateCcw className="w-3 h-3" />
                        </Button>
                      )}
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteMessage(message.id)}
                        className="p-1 h-6 w-6 text-red-500 hover:text-red-700"
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>

              {/* AI 消息反馈 */}
              {message.role === 'assistant' && editingMessageId !== message.id && (
                <div className="flex items-center gap-2 mt-2">
                  <Button variant="ghost" size="sm" className="p-1 h-6 w-6 text-gray-400 hover:text-green-500">
                    <ThumbsUp className="w-3 h-3" />
                  </Button>
                  <Button variant="ghost" size="sm" className="p-1 h-6 w-6 text-gray-400 hover:text-red-500">
                    <ThumbsDown className="w-3 h-3" />
                  </Button>
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="max-w-[70%]">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-6 h-6 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center text-xs font-medium text-white">
                  AI
                </div>
                <span className="text-xs text-gray-500">正在输入...</span>
              </div>
              <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-2xl">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className={`p-4 border-t ${isDarkMode ? 'border-gray-800 bg-[#171717]' : 'border-gray-200 bg-white'}`}>
        <div className="relative">
          <div className="flex items-end gap-3">
            {/* 附件按钮 */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              <Paperclip className="w-5 h-5" />
            </Button>

            {/* 输入框 */}
            <div className="flex-1 relative">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入消息... (Enter发送，Shift+Enter换行)"
                className="min-h-[44px] max-h-[200px] pr-12 resize-none"
                disabled={isLoading}
              />
              
              {/* 语音输入按钮 */}
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleRecording}
                className={`absolute right-2 top-2 p-2 ${
                  isRecording ? 'text-red-500 hover:text-red-600' : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                }`}
              >
                {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </Button>
            </div>

            {/* 发送按钮 */}
            <Button
              onClick={handleSendMessage}
              disabled={!input.trim() || isLoading}
              className="p-2 bg-blue-600 hover:bg-blue-700 text-white"
            >
              <Send className="w-5 h-5" />
            </Button>
          </div>

          {/* 快捷提示 */}
          <div className="flex items-center justify-between mt-2 text-xs text-gray-500 dark:text-gray-400">
            <span>支持 Markdown 格式</span>
            <span>当前模型: {currentModel === 'thinking' ? '思考模型' : '快速模型'}</span>
          </div>
        </div>

        {/* 隐藏的文件输入 */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,.pdf,.doc,.docx,.txt"
          onChange={handleFileUpload}
          className="hidden"
        />
      </div>
    </div>
  );
}