import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import TextareaAutosize from 'react-textarea-autosize';
import { 
  Copy, 
  Edit3, 
  Trash2, 
  History, 
  Send, 
  MessageSquare, 
  User,
  Bot,
  Brain,
  ChevronDown,
  ChevronRight
} from 'lucide-react';
import { detectAutoTheme } from '@/utils/language';

// 导入迁移按钮组件
import MigrationButton from './components/MigrationButton';

// 是否开启调试模式
const DEBUG_MODE = import.meta.env.VITE_DEBUG_MODE === 'true';

// 欢迎消息
const WELCOME_MESSAGE = `What can I help with?`;

// 移除连接建立前缀的函数
const removeConnectionPrefix = (content: string): string => {
  if (!content) return content;
  
  // 移除 ": connection established" 前缀（支持各种变体）
  let cleaned = content.replace(/^:?\s*connection\s+established[\s\n]*/i, '');
  
  // 移除其他可能的连接状态前缀
  cleaned = cleaned.replace(/^:?\s*connected[\s\n]*/i, '');
  cleaned = cleaned.replace(/^:?\s*已连接[\s\n]*/i, '');
  cleaned = cleaned.replace(/^:?\s*连接已建立[\s\n]*/i, '');
  
  return cleaned;
};

// 处理特殊格式的消息内容
const processSpecialFormat = (content: string): string => {
  if (!content) return content;
  
  // 首先移除连接前缀
  let processed = removeConnectionPrefix(content);
  
  // 判断是否包含特殊格式
  if (!processed.includes("<") && !processed.includes("entity") && !processed.includes("relationship") && !processed.includes("#")) {
    return processed;
  }
  
  // 移除特殊标记
  processed = processed.replace(/<COMPLETE>/g, "");
  processed = processed.replace(/<\|COMPLETE\|>/g, "");
  processed = processed.replace(/<\|>/g, "");
  processed = processed.replace(/<类别>/g, "");
  processed = processed.replace(/<knowledge_graph>/g, "");
  processed = processed.replace(/<document_chunks>/g, "");
  
  // 移除实体标记格式
  processed = processed.replace(/\("entity"[^"]*"([^"]+)"\)/g, "$1");
  processed = processed.replace(/\("entity"<[^>]*>[^"]*"([^"]+)"\)/g, "$1");
  processed = processed.replace(/\("relationship"<[^>]*>[^"]*"([^"]+)"\)/g, "$1");
  processed = processed.replace(/\("content_keywords"[^"]*"([^"]+)"\)/g, "$1");
  
  // 旧的实体标记格式
  const entityRegex = /\("([^"]+)"<\|>[^"]+<\|>[^"]+<\|>"([^"]+)"\)/g;
  processed = processed.replace(entityRegex, "$2");
  
  // 清理多余的井号分隔符
  processed = processed.replace(/#+/g, "");
  
  // 移除角色标记
  processed = processed.replace(/<assistant>/gi, "");
  processed = processed.replace(/<user>/gi, "");
  processed = processed.replace(/<system>/gi, "");
  processed = processed.replace(/<human>/gi, "");
  processed = processed.replace(/<ai>/gi, "");
  
  // 移除其他可能的控制标记
  processed = processed.replace(/<begin>/gi, "");
  processed = processed.replace(/<end>/gi, "");
  
  return processed;
};

// 解析思考模型的输出格式（支持 deepseek-r1 和传统格式）
const parseThinkingModelOutput = (content: string): { thinking: string; answer: string } => {
  if (!content) return { thinking: "", answer: "" };
  
  // 首先移除连接前缀
  const cleanedContent = removeConnectionPrefix(content);
  
  // 1. 检查 deepseek-r1 的 <think>...</think> 格式
  const deepseekThinkPattern = /<think>([\s\S]*?)<\/think>([\s\S]*)/;
  const deepseekMatch = cleanedContent.match(deepseekThinkPattern);
  
  if (deepseekMatch) {
    const thinking = deepseekMatch[1].trim();
    const answer = deepseekMatch[2].trim();
    return {
      thinking,
      answer: answer || thinking // 如果没有answer部分，使用thinking作为答案
    };
  }
  
  // 2. 检查传统的思考标记格式
  const thinkingPattern = /🤔 \*\*思考过程：\*\*\n(.*?)\n\n\*\*回答：\*\*\n(.*)/s;
  const match = cleanedContent.match(thinkingPattern);
  
  if (match) {
    return {
      thinking: match[1].trim(),
      answer: match[2].trim()
    };
  }
  
  // 3. 检查是否只有思考内容（传统格式）
  const thinkingOnlyPattern = /🤔 \*\*思考过程：\*\*\n(.*)/s;
  const thinkingOnlyMatch = cleanedContent.match(thinkingOnlyPattern);
  
  if (thinkingOnlyMatch) {
    return {
      thinking: thinkingOnlyMatch[1].trim(),
      answer: ""
    };
  }
  
  // 4. 没有思考标记，直接返回为答案
  return {
    thinking: "",
    answer: cleanedContent
  };
};

// 消息类型定义
interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: string;
  thinking?: string; // 添加思考内容字段
}

const MAX_MESSAGES = 500;

export default function ChatLayout() {
  const { projectId } = useParams<{ projectId: string }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editMessageId, setEditMessageId] = useState<string | null>(null);
  const [isComposing, setIsComposing] = useState(false);
  const [streamingComplete, setStreamingComplete] = useState(true);
  const [showStreamingAlert, setShowStreamingAlert] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showDebugPanel, setShowDebugPanel] = useState(false);
  const forceRefreshTimer = useRef<NodeJS.Timeout | null>(null);
  const [requestTimeout, setRequestTimeout] = useState<NodeJS.Timeout | null>(null);
  const [_editOriginalValue, setEditOriginalValue] = useState('');
  const [_initialized, setInitialized] = useState(false);
  const [lastError, _setLastError] = useState<string | null>(null);
  const [_isHistoryLoaded, setIsHistoryLoaded] = useState(false);
  const loadedRef = useRef(false);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [showHistorySelector, setShowHistorySelector] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [historyPage, setHistoryPage] = useState(0);
  const [isMigrating, setIsMigrating] = useState(false);
  const [migrationResult, setMigrationResult] = useState<any>(null);
  const [collapsedThinking, setCollapsedThinking] = useState<Set<string>>(new Set());

  // 主题模式检测
  const isDarkMode = detectAutoTheme() === 'dark';

  // 切换思考内容折叠状态
  const toggleThinkingCollapse = (messageId: string) => {
    setCollapsedThinking(prev => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
      }
      return newSet;
    });
  };

  // 可折叠的思考内容组件
  const CollapsibleThinking: React.FC<{
    thinking: string;
    messageId: string;
    isCollapsed: boolean;
    onToggle: () => void;
  }> = ({ thinking, isCollapsed, onToggle }) => (
    <div className={`mb-4 border-l-2 border-purple-500 pl-4 rounded-lg ${
      isDarkMode ? 'bg-purple-900/10' : 'bg-purple-50'
    }`}>
      <button
        onClick={onToggle}
        className={`flex items-center text-sm font-medium mb-2 transition-colors ${
          isDarkMode ? 'text-purple-400 hover:text-purple-300' : 'text-purple-600 hover:text-purple-700'
        }`}
      >
        {isCollapsed ? (
          <ChevronRight className="w-4 h-4 mr-1" />
        ) : (
          <ChevronDown className="w-4 h-4 mr-1" />
        )}
        <Brain className="w-4 h-4 mr-2" />
        思考过程
      </button>
      {!isCollapsed && (
        <div className={`text-sm whitespace-pre-wrap leading-relaxed p-3 rounded-lg ${
          isDarkMode ? 'bg-gray-800 text-gray-300' : 'bg-white text-gray-700'
        } border ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          {thinking}
        </div>
      )}
    </div>
  );

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // 当消息变化时滚动到底部 - 修改为只在特定情况下滚动
  useEffect(() => {
    // 只有在发送新消息或接收新消息时才滚动到底部
    if (isLoading || (!streamingComplete && messages.length > 0 && !messages[messages.length - 1].isUser)) {
      scrollToBottom();
    }
  }, [messages, isLoading, streamingComplete]);

  // 优化处理滚动事件，防止不必要的黄色警告显示
  useEffect(() => {
    const handleScroll = () => {
      // 滚动时不触发警告，除非是用户手动取消请求
    };
    
    // 为消息容器添加滚动事件监听器
    const container = messagesContainerRef.current;
    if (container) {
      container.addEventListener('scroll', handleScroll);
    }
    
    return () => {
      if (container) {
        container.removeEventListener('scroll', handleScroll);
      }
    };
  }, []);

  // 加载聊天历史 - 修改为支持存档消息和分页
  const loadChatHistory = async (includeArchivedMessages = false, page = 0) => {
    if (loadedRef.current && !includeArchivedMessages && page === 0) return;
    
    try {
      const token = localStorage.getItem('stp_token');
      const userId = JSON.parse(localStorage.getItem('stp_user') || '{}').id || 'unknown';
      
      const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8000';
      // 构建包含归档参数的URL - 通过Gateway访问
      const url = `${gatewayUrl}/chat/api/chat/history/${projectId || 'default'}?user_id=${userId}&include_archived=${includeArchivedMessages}&offset=${page * 50}&limit=50`;
      
      console.log('正在加载聊天历史，请求URL:', url);
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data && Array.isArray(data) && data.length > 0) {
          // 转换历史消息格式并加载
          const historyMessages = data.map((msg: any) => ({
            id: msg.id || Date.now().toString() + Math.random().toString(),
            content: processSpecialFormat(msg.content || ''),
            isUser: msg.role === 'user',
            timestamp: msg.timestamp || new Date().toISOString()
          }));
          
          console.log(`已加载 ${historyMessages.length} 条聊天历史`);
          
          // 如果是加载更多历史消息，则追加到现有消息末尾
          if (page > 0 || includeArchivedMessages) {
            setMessages(prev => [...prev, ...historyMessages]);
          } else {
            setMessages(historyMessages);
          }
          
          setIsHistoryLoaded(true);
        } else if (page === 0 && !includeArchivedMessages) {
          // 如果是首次加载且没有消息，则清空消息列表
          console.log('没有聊天历史记录');
          setMessages([]);
        } else {
          // 如果是加载更多历史，但没有更多数据，提示用户
          console.log('没有更多历史消息了');
          // 可以添加提示：没有更多历史消息
        }
      } else {
        console.error('加载聊天历史失败:', response.statusText);
        const errorText = await response.text();
        console.error('错误详情:', errorText);
      }
    } catch (error) {
      console.error('加载聊天历史出错:', error);
    }
    
    if (!includeArchivedMessages && page === 0) {
      loadedRef.current = true;
    }
  };

  // 加载更多历史消息
  const loadMoreHistory = () => {
    const nextPage = historyPage + 1;
    setHistoryPage(nextPage);
    loadChatHistory(includeArchived, nextPage);
  };

  // 切换是否包含归档消息
  const toggleArchivedMessages = () => {
    const newValue = !includeArchived;
    setIncludeArchived(newValue);
    setHistoryPage(0); // 重置分页
    loadChatHistory(newValue, 0); // 重新加载消息
  };

  // 保存消息到数据库
  const saveChatMessage = async (message: Message) => {
    try {
      const token = localStorage.getItem('stp_token');
      const userId = JSON.parse(localStorage.getItem('stp_user') || '{}').id || 'unknown';
      
      const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
      const url = `${gatewayUrl}/chat/api/chat/save`;
      
      console.log('正在保存聊天消息，请求URL:', url, 'message:', message);
      
      const messageData = {
        id: message.id,
        content: message.content,
        role: message.isUser ? 'user' : 'assistant',
        user_id: userId,
        project_id: projectId || 'default',
        timestamp: message.timestamp
      };
      
      console.log('准备发送的消息数据:', messageData);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(messageData)
      });
          
      if (response.ok) {
        console.log('保存聊天消息成功');
        const result = await response.json();
        console.log('保存结果:', result);
      } else {
        const errorText = await response.text();
        console.error('保存聊天消息失败:', response.statusText, errorText);
      }
    } catch (error) {
      console.error('保存聊天消息失败:', error);
    }
  };
              
  // 清除聊天历史
  const clearChatHistory = async () => {
    if (!confirm('确定要清除所有聊天记录吗？此操作不可撤销。')) return;
    
    try {
      const token = localStorage.getItem('stp_token');
      const userId = JSON.parse(localStorage.getItem('stp_user') || '{}').id || 'unknown';
      
      const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8000';
      // 修正API路径，确保使用正确的端点 - 通过Gateway访问
      const url = `${gatewayUrl}/chat/api/chat/history/${projectId || 'default'}?user_id=${userId}`;
      
      console.log('正在清除聊天历史，请求URL:', url);
      
      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        setMessages([]);
        console.log('聊天历史已成功清除');
      } else {
        console.error('清除聊天历史失败:', response.statusText);
        const errorText = await response.text();
        console.error('错误详情:', errorText);
        alert('清除聊天历史失败，请稍后再试');
      }
    } catch (error) {
      console.error('清除聊天历史出错:', error);
      alert('清除聊天历史出错，请稍后再试');
    }
  };

  // 在组件挂载时确保状态正确初始化
  useEffect(() => {
    // 确保流式完成状态被设置为true
    setStreamingComplete(true);
    setIsLoading(false);
    setInitialized(true);
    console.log('ChatLayout组件已初始化，重置所有状态');
    
    // 加载聊天历史
    loadChatHistory();
    
    // 清除任何可能存在的中断请求
    if (abortControllerRef.current) {
      console.log('组件初始化，取消可能存在的旧请求');
      try {
      abortControllerRef.current.abort();
      } catch (e) {
        // 忽略中断过程中的任何错误
      }
      abortControllerRef.current = null;
    }
    
    // 添加强制刷新定时器
    const refreshTimer = setInterval(() => {
      // 简单的状态修改，触发重新渲染
      setMessages(prev => [...prev]);
    }, 3000);
    
    // 组件卸载时的清理
    return () => {
      if (abortControllerRef.current) {
        console.log('组件卸载，取消未完成的请求');
        
        try {
        abortControllerRef.current.abort();
        } catch (e) {
          // 忽略中断过程中的任何错误
        }
        
        abortControllerRef.current = null;
      }
      
      // 清除强制刷新定时器
      clearInterval(refreshTimer);
    };
  }, []);

  // 强制重置状态函数 - 添加不显示黄色警告功能
  const forceResetState = () => {
    console.log('用户强制重置聊天状态');
    
    // 取消任何正在进行的请求
    if (abortControllerRef.current) {
      try {
        abortControllerRef.current.abort();
      } catch (e) {
        console.error('中断请求时出错:', e);
      }
      abortControllerRef.current = null;
    }
    
    // 清除超时计时器
    if (requestTimeout) {
      clearTimeout(requestTimeout);
      setRequestTimeout(null);
    }
    
    // 清除刷新计时器
    if (forceRefreshTimer.current) {
      clearInterval(forceRefreshTimer.current);
    }
    
    // 重置所有状态
    setIsLoading(false);
    setStreamingComplete(true);
    setIsProcessing(false);
    // 当用户手动点击重置按钮时才显示黄色警告
    setShowStreamingAlert(true);
    
    // 强制立即重建刷新计时器
    forceRefreshTimer.current = setInterval(() => {
      setMessages(prevMessages => [...prevMessages]);
    }, 5000);
    
    // 更新最后一条思考中的消息
    setMessages(prev => {
      const newMessages = [...prev];
      let updated = false;
      
      // 找到最后一条思考中的消息
      for (let i = newMessages.length - 1; i >= 0; i--) {
        if (!newMessages[i].isUser && (!newMessages[i].content || newMessages[i].content.trim() === '')) {
          // 将空消息替换为错误提示
          newMessages[i] = {
            ...newMessages[i],
            content: "消息处理已被用户手动取消，请重新发送您的问题。"
          };
          updated = true;
        break;
      }
    }
    
      // 如果没有找到空消息但有非用户消息，更新最后一条非用户消息
      if (!updated) {
        for (let i = newMessages.length - 1; i >= 0; i--) {
          if (!newMessages[i].isUser) {
            // 在内容后附加一个提示，告知用户状态已被重置
            newMessages[i] = {
              ...newMessages[i],
              content: newMessages[i].content + "\n\n*消息处理已被用户手动中断并重置。*"
            };
            break;
          }
        }
      }
      
      return newMessages;
    });
    
    // 通知用户状态已重置
    alert('聊天状态已被强制解除锁定，现在您可以正常发送消息了');
    
    // 3秒后隐藏提示条
    setTimeout(() => {
      setShowStreamingAlert(false);
    }, 3000);
  };

  // UI交互处理函数
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
  };

  const handleEdit = (messageId: string, content: string) => {
    setEditMessageId(messageId);
    setIsEditing(true);
    setInputValue(content);
    setEditOriginalValue(content);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditMessageId(null);
    setInputValue('');
    setEditOriginalValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 如果是组合输入法编辑中，不要提交
    if (isComposing) return;
    
    // Enter提交但Shift+Enter换行
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };
  
  const handleCompositionStart = () => {
    setIsComposing(true);
  };
  
  const handleCompositionEnd = () => {
    setIsComposing(false);
  };
  
  const toggleDebugPanel = () => {
    setShowDebugPanel(!showDebugPanel);
  };
  
  const handleManualReset = () => {
    forceResetState();
  };

  // 消息提交处理 - 添加避免频繁显示警告的逻辑
  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    
    // 如果已经在处理中，直接返回
    if (isProcessing || !streamingComplete || isLoading || !inputValue.trim()) {
      return;
    }
    
    try {
      // 设置为处理中状态
      setIsProcessing(true);
      setStreamingComplete(false);
      
      // 添加超时处理 - 30秒后自动中断请求但不显示黄色警告
      const timeoutId = setTimeout(() => {
        console.log('请求超时(30秒)，自动中断');
        if (abortControllerRef.current) {
          abortControllerRef.current.abort();
          abortControllerRef.current = null;
        }
        
        // 更新消息状态
        setMessages(prev => {
          const newMessages = [...prev];
          // 找到并更新最后一个机器人消息
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (!newMessages[i].isUser && !newMessages[i].content) {
              newMessages[i] = {
                ...newMessages[i],
                content: "请求超时，请重新发送您的问题或稍后再试。如果问题持续，请尝试使用右下角的\"解除锁定状态\"按钮。"
              };
              break;
            }
          }
          return newMessages;
        });
        
        // 重置所有状态
        setIsLoading(false);
        setIsProcessing(false);
        setStreamingComplete(true);
        
        // 超时时不显示黄色警告，避免滚动时警告频繁弹出
      }, 30000); // 30秒超时
      
      setRequestTimeout(timeoutId);
      
      // 添加强制滚动的计时器，确保思考中动画显示
      setTimeout(() => {
        scrollToBottom();
      }, 100);
      
      // 创建用户消息和思考中消息
      const userMessage: Message = {
            id: Date.now().toString(),
            content: inputValue,
            isUser: true,
            timestamp: new Date().toISOString(),
          };
      
      const thinkingMessage: Message = {
            id: (Date.now() + 1).toString(),
            content: '',
            isUser: false,
            timestamp: new Date().toISOString(),
          };
      
      // 立即添加消息到界面，使思考中动画可见
          setMessages(prev => {
            const arr = [...prev, userMessage, thinkingMessage];
            return arr.length > MAX_MESSAGES ? arr.slice(-MAX_MESSAGES) : arr;
          });
      
      // 使用专用函数保存用户消息到数据库
      console.log('保存用户消息到数据库');
      await saveChatMessage(userMessage);
      
      // 强制滚动到底部显示思考中动画
      setTimeout(() => {
        scrollToBottom();
      }, 50);
      
      // 清空输入框
      setInputValue('');
      
      // 设置加载状态
      setIsLoading(true);
      
      // 获取token
        const token = localStorage.getItem('stp_token');
        
        try {
        // 创建中断控制器
          const controller = new AbortController();
          abortControllerRef.current = controller;
        
        // 通过Gateway访问聊天服务API
        const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8000';
        const url = `${gatewayUrl}/chat/api/chat/stream`;
        
        // 发送请求
        const response = await fetch(url, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
          body: JSON.stringify({ 
            content: userMessage.content,
            message: userMessage.content,
            project_id: projectId || 'default',
            search_mode: 'hybrid', 
            use_graph: true,
            user_id: JSON.parse(localStorage.getItem('stp_user') || '{}').id || 'unknown'
          }),
            signal: controller.signal,
          });
          
        if (!response.ok) {
          throw new Error(`API返回状态码 ${response.status}`);
        }
          
        if (!response.body) {
          throw new Error('No response body');
        }
        
        // 读取流式响应
          const reader = response.body.getReader();
          const decoder = new TextDecoder('utf-8');
          let buffer = '';
          let aiReply = '';
          let done = false;
          
        // 不断读取流式数据
          while (!done) {
            const { value, done: doneReading } = await reader.read();
            done = doneReading;
            
            if (value) {
              // 解码二进制数据
              const chunk = decoder.decode(value);
              buffer += chunk;
              
              // 处理可能的多行SSE数据
              const lines = buffer.split('\n\n');
              buffer = lines.pop() || ''; // 保留最后一个不完整的行
              
              for (const line of lines) {
                if (line.trim() === '') continue;
                
                // 解析SSE格式
                if (line.startsWith('data: ')) {
                  try {
                    const jsonStr = line.slice(6); // 去掉 "data: " 前缀
                    const data = JSON.parse(jsonStr);
                    
                    // 如果有错误消息
                    if (data.error) {
                    setMessages(prev => prev.map((m, idx) =>
                      idx === prev.length - 1 && !m.isUser
                          ? { ...m, content: `发生错误：${data.error}` }
                          : m
                      ));
                      continue;
                    }
                    
                    // 如果是完成标记
                    if (data.done) {
                      done = true;
                      continue;
                    }
                    
                    // 累积回复内容
                    if (data.content) {
                      // 处理特殊标记
                      const processedContent = processSpecialFormat(data.content);
                      aiReply += processedContent;
                      
                      // 解析思考模型的输出
                      const { thinking, answer } = parseThinkingModelOutput(aiReply);
                      
                      // 检查是否含有完成标记
                      if (data.content.includes("<COMPLETE>") || 
                          data.content.includes("<|COMPLETE|>") ||
                          data.content.includes("COMPLETE")) {
                        console.log('在内容中检测到完成标记');
                        done = true;
                        setStreamingComplete(true);
                        setIsLoading(false);
                        setIsProcessing(false);
                      }
                      
                    // 更新思考中消息内容
                      setMessages(prev => {
                        const arr = [...prev];
                      // 从后向前查找第一个非用户消息，视为思考中消息
                      for (let i = arr.length - 1; i >= 0; i--) {
                        if (!arr[i].isUser) {
                          arr[i] = { 
                            ...arr[i], 
                            content: answer || aiReply, 
                            thinking: thinking || undefined 
                          };
                          break;
                        }
                        }
                        return arr;
                      });
                    
                    // 收到内容块后强制滚动到底部
                    setTimeout(() => {
                      scrollToBottom();
                    }, 10);
                    }
                  } catch (e) {
                  console.error('解析SSE数据时出错:', e);
                    // 发生解析错误时也重置状态
                    setStreamingComplete(true);
                    setIsLoading(false);
                    setIsProcessing(false);
                  }
                }
              }
            }
          }
          
          // 完成后设置流式完成标志
          setStreamingComplete(true);
          setIsLoading(false);
          setIsProcessing(false);
          console.log('消息流式处理完成，状态已重置');
          
          // 保存AI回复到数据库
          if (aiReply) {
            // 解析最终的思考内容和回答
            const finalParsed = parseThinkingModelOutput(aiReply);
            const aiMessage: Message = {
              id: (Date.now() + 2).toString(),
              content: finalParsed.answer || aiReply,
              isUser: false,
              timestamp: new Date().toISOString(),
              thinking: finalParsed.thinking || undefined,
            };
            
            console.log('保存AI回复到数据库');
            await saveChatMessage(aiMessage);
          }
        
        // 清除请求超时
        if (requestTimeout) {
          clearTimeout(requestTimeout);
          setRequestTimeout(null);
        }
        } catch (error: any) {
          // 确保错误情况下也重置所有状态
          setStreamingComplete(true);
          setIsLoading(false);
          setIsProcessing(false);
          
        // 错误处理
          if (error.name === 'AbortError') {
          console.log('聊天请求被中断，这是预期行为');
          
          // 中断消息内容
          const interruptionMessage = "消息处理被中断，请重新发送您的问题。";
          
          // 更新前端显示
          setMessages(prev => {
            const newMessages = [...prev];
            // 找到并更新最后一个机器人消息
            for (let i = newMessages.length - 1; i >= 0; i--) {
              if (!newMessages[i].isUser && !newMessages[i].content) {
                newMessages[i] = {
                  ...newMessages[i],
                  content: interruptionMessage
                };
                break;
              }
            }
            return newMessages;
          });
        } else {
          console.error('聊天请求出错:', error);
          setMessages(prev => {
            const newMessages = [...prev];
            // 找到并更新最后一个机器人消息
            for (let i = newMessages.length - 1; i >= 0; i--) {
              if (!newMessages[i].isUser) {
                newMessages[i] = {
                  ...newMessages[i],
                  content: `发生错误：${error.message || error.toString()}`
                };
                break;
              }
            }
            return newMessages;
          });
        }
        
        // 确保所有状态都被重置
        abortControllerRef.current = null;
            
        // 清除请求超时
        if (requestTimeout) {
          clearTimeout(requestTimeout);
          setRequestTimeout(null);
                }
              }
      } catch (error: any) {
      console.error('处理消息提交出错:', error);
      setIsProcessing(false);
        setStreamingComplete(true);
        setIsLoading(false);
      
      // 清除请求超时
      if (requestTimeout) {
        clearTimeout(requestTimeout);
        setRequestTimeout(null);
      }
    }
  };
    
  // 添加手动触发迁移消息的函数
  const triggerMigration = async (days: number = 30) => {
    if (!confirm(`确定要将${days}天前的聊天历史迁移到数据库吗？`)) return;
    
    try {
      setIsMigrating(true);
      
      const token = localStorage.getItem('stp_token');
      const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
      const url = `${gatewayUrl}/chat/api/chat/migrate?days=${days}`;
      
      console.log('通过Gateway触发聊天历史迁移，请求URL:', url);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log('迁移结果:', result);
        setMigrationResult(result.data);
        alert(`迁移完成: 已迁移 ${result.data.messages_migrated} 条消息`);
      } else {
        console.error('迁移请求失败:', response.statusText);
        const errorText = await response.text();
        console.error('错误详情:', errorText);
        alert('迁移失败: ' + response.statusText);
      }
    } catch (error) {
      console.error('触发迁移时出错:', error);
      alert('迁移请求出错，请查看控制台日志');
    } finally {
      setIsMigrating(false);
    }
  };

  // 渲染UI
  return (
    <div className={`h-screen flex flex-col transition-colors duration-300 ${
      isDarkMode ? 'bg-[#212121] text-gray-100' : 'bg-white text-gray-900'
    }`}>
      {/* 顶部导航栏 */}
      <div className={`w-full py-4 px-6 border-b flex justify-center items-center transition-colors duration-300 ${
        isDarkMode ? 'border-gray-800 bg-[#171717]' : 'border-gray-200 bg-white'
      }`}>
        <div className="flex-1"></div>
        <div className="flex items-center space-x-3">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
            isDarkMode ? 'bg-gradient-to-r from-blue-600 to-purple-600' : 'bg-gradient-to-r from-blue-500 to-purple-500'
          }`}>
            <MessageSquare className="w-4 h-4 text-white" />
          </div>
          <div className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            Lumidoc Intelligence 聊天
          </div>
        </div>
        <div className="flex-1 flex justify-end space-x-3">
          <button 
            onClick={() => setShowHistorySelector(!showHistorySelector)}
            className={`p-2 rounded-lg transition-colors ${
              isDarkMode ? 'text-gray-400 hover:text-white hover:bg-gray-700' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
            title="查看历史消息"
          >
            <History className="w-5 h-5" />
          </button>
          <button 
            onClick={clearChatHistory}
            className={`p-2 rounded-lg transition-colors ${
              isDarkMode ? 'text-gray-400 hover:text-white hover:bg-gray-700' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
            title="清除所有聊天记录"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>
      </div>
      
      {/* 历史消息选择器 */}
      {showHistorySelector && (
        <div className={`border-b p-4 transition-colors duration-300 ${
          isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-200'
        }`}>
          <div className="flex justify-between items-center mb-3">
            <div className="text-lg font-semibold">历史消息</div>
            <button 
              onClick={() => setShowHistorySelector(false)}
              className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                isDarkMode ? 'text-gray-400 hover:text-white hover:bg-gray-700' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
              }`}
            >
              关闭
            </button>
          </div>
          <div className="space-y-3">
            <label className="flex items-center text-sm">
              <input 
                type="checkbox" 
                checked={includeArchived} 
                onChange={toggleArchivedMessages}
                className="mr-3 rounded"
              />
              包含归档消息（30天前）
            </label>
            <div className="flex flex-wrap gap-3">
              <button 
                onClick={loadMoreHistory}
                className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                  isDarkMode ? 'text-blue-400 hover:text-blue-300 bg-blue-900/20 hover:bg-blue-900/30' : 'text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100'
                }`}
              >
                加载更多历史消息
              </button>
              <button 
                onClick={() => triggerMigration(30)}
                disabled={isMigrating}
                className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                  isMigrating 
                    ? 'text-gray-500 cursor-not-allowed' 
                    : isDarkMode 
                      ? 'text-green-400 hover:text-green-300 bg-green-900/20 hover:bg-green-900/30' 
                      : 'text-green-600 hover:text-green-700 bg-green-50 hover:bg-green-100'
                }`}
                title="将30天前的消息迁移到数据库存档"
              >
                {isMigrating ? '迁移中...' : '归档旧消息'}
              </button>
            </div>
          </div>
          
          {/* 显示迁移结果 */}
          {migrationResult && (
            <div className={`mt-3 text-sm p-3 rounded-lg ${
              isDarkMode ? 'text-gray-300 bg-gray-700' : 'text-gray-700 bg-white border border-gray-200'
            }`}>
              <div>迁移结果: 处理{migrationResult.projects_processed}个项目，迁移{migrationResult.messages_migrated}条消息</div>
              {migrationResult.errors > 0 && <div className="text-red-500 mt-1">发生{migrationResult.errors}个错误</div>}
            </div>
          )}
        </div>
      )}
      
      {/* 主要聊天区域 - 使用相对定位和灵活布局 */}
      <div className="relative flex-1 flex flex-col overflow-hidden">
        {/* 滚动消息区域 - 填充可用空间 */}
        <div 
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto py-6 px-6 pb-32"
        >
          {messages.length === 0 ? (
            /* 空消息状态 - 完全居中显示 */
            <div className="h-full flex flex-col items-center justify-center">
              <div className={`text-center space-y-6 max-w-2xl mx-auto ${
                isDarkMode ? 'text-gray-300' : 'text-gray-600'
              }`}>
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto ${
                  isDarkMode ? 'bg-gradient-to-r from-blue-600 to-purple-600' : 'bg-gradient-to-r from-blue-500 to-purple-500'
                }`}>
                  <MessageSquare className="w-8 h-8 text-white" />
                </div>
                <div>
                  <h2 className="text-3xl font-bold mb-3 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                    开始智能对话
                  </h2>
                  <p className="text-lg">
                    基于Graph RAG技术，支持多模型协作的智能问答系统
                  </p>
                  <p className="text-sm mt-3 opacity-70">
                    您可以询问任何问题，我会基于知识图谱为您提供精准回答
                  </p>
                </div>
              </div>
            </div>
          ) : (
            // 有消息时显示聊天记录
            <div className="max-w-4xl mx-auto w-full">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`mb-6 flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`flex items-start space-x-4 max-w-[85%] ${
                    message.isUser ? 'flex-row-reverse space-x-reverse' : ''
                  }`}>
                    {/* 头像 */}
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                      message.isUser 
                        ? isDarkMode ? 'bg-blue-600' : 'bg-blue-500'
                        : isDarkMode ? 'bg-purple-600' : 'bg-purple-500'
                    }`}>
                      {message.isUser ? (
                        <User className="w-4 h-4 text-white" />
                      ) : (
                        <Bot className="w-4 h-4 text-white" />
                      )}
                    </div>
                    
                    {/* 消息内容 */}
                    <div className={`rounded-2xl px-4 py-3 relative group ${
                      message.isUser
                        ? isDarkMode 
                          ? 'bg-blue-600 text-white'
                          : 'bg-blue-500 text-white'
                        : isDarkMode 
                          ? 'bg-gray-800 text-gray-100 border border-gray-700'
                          : 'bg-white text-gray-900 border border-gray-200 shadow-sm'
                    }`}>
                      {message.isUser ? (
                        <>
                          {/* 用户消息 */}
                          <div className="whitespace-pre-wrap leading-relaxed text-sm">{message.content}</div>
                          {/* 编辑按钮 */}
                          <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            {message.id === editMessageId ? (
                              <button
                                onClick={handleCancelEdit}
                                className={`p-1 rounded text-xs ${
                                  isDarkMode ? 'text-gray-300 hover:text-white' : 'text-gray-600 hover:text-gray-800'
                                }`}
                              >
                                取消
                              </button>
                            ) : (
                              <button
                                onClick={() => handleEdit(message.id, message.content)}
                                className={`p-1 rounded transition-colors ${
                                  isDarkMode ? 'text-gray-300 hover:text-white hover:bg-blue-700' : 'text-gray-600 hover:text-gray-800 hover:bg-blue-400'
                                }`}
                              >
                                <Edit3 className="w-4 h-4" />
                              </button>
                            )}
                          </div>
                        </>
                      ) : (
                        <>
                          {/* AI消息 */}
                          {message.content ? (
                            <>
                              {/* 显示思考内容（使用可折叠组件） */}
                              {message.thinking && (
                                <CollapsibleThinking
                                  thinking={message.thinking}
                                  messageId={message.id}
                                  isCollapsed={collapsedThinking.has(message.id)}
                                  onToggle={() => toggleThinkingCollapse(message.id)}
                                />
                              )}
                              
                              {/* 显示回答内容 */}
                              <div className={`leading-relaxed text-sm ${
                                isDarkMode ? 'text-gray-100' : 'text-gray-900'
                              }`}>
                                <div className="prose prose-sm max-w-none">
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {message.content}
                                  </ReactMarkdown>
                                </div>
                              </div>
                              {/* 复制按钮 */}
                              <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                  onClick={() => {
                                    const fullContent = message.thinking 
                                      ? `思考过程：\n${message.thinking}\n\n回答：\n${message.content}`
                                      : message.content;
                                    navigator.clipboard.writeText(fullContent);
                                  }}
                                  className={`p-1 rounded transition-colors ${
                                    isDarkMode ? 'text-gray-400 hover:text-white hover:bg-gray-700' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                                  }`}
                                >
                                  <Copy className="w-4 h-4" />
                                </button>
                              </div>
                            </>
                          ) : (
                            <div className={`flex items-center space-x-3 ${
                              isDarkMode ? 'text-gray-300' : 'text-gray-600'
                            }`}>
                              <div className="flex space-x-1">
                                <div className={`w-2 h-2 rounded-full animate-pulse ${
                                  isDarkMode ? 'bg-purple-400' : 'bg-purple-500'
                                }`}></div>
                                <div className={`w-2 h-2 rounded-full animate-pulse ${
                                  isDarkMode ? 'bg-purple-400' : 'bg-purple-500'
                                }`} style={{ animationDelay: '0.2s' }}></div>
                                <div className={`w-2 h-2 rounded-full animate-pulse ${
                                  isDarkMode ? 'bg-purple-400' : 'bg-purple-500'
                                }`} style={{ animationDelay: '0.4s' }}></div>
                              </div>
                              <span className="text-sm">AI正在思考中...</span>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
        
        {/* 输入区域固定在底部 */}
        <div className={`w-full border-t py-4 px-6 fixed bottom-0 left-0 right-0 z-10 transition-colors duration-300 ${
          isDarkMode ? 'border-gray-800 bg-[#212121]' : 'border-gray-200 bg-white'
        }`}>
          <div className="max-w-4xl mx-auto">
            <form onSubmit={handleSubmit} className={`relative rounded-2xl shadow-lg transition-colors duration-300 ${
              isDarkMode ? 'bg-gray-800 border border-gray-700' : 'bg-white border border-gray-200'
            }`}>
              <TextareaAutosize
                value={inputValue}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                onCompositionStart={handleCompositionStart}
                onCompositionEnd={handleCompositionEnd}
                placeholder="输入您的问题，按 Enter 发送..."
                className={`w-full bg-transparent px-4 py-3 pr-12 resize-none rounded-2xl focus:outline-none transition-colors duration-300 ${
                  isDarkMode 
                    ? 'text-gray-100 placeholder-gray-400' 
                    : 'text-gray-900 placeholder-gray-500'
                }`}
                minRows={1}
                maxRows={6}
                disabled={isProcessing || !streamingComplete || isLoading}
              />
              <button
                type="submit"
                className={`absolute bottom-3 right-3 p-2 rounded-xl transition-all duration-200 ${
                  isProcessing || !streamingComplete || isLoading || !inputValue.trim()
                    ? 'text-gray-400 cursor-not-allowed'
                    : isDarkMode
                      ? 'text-gray-400 hover:text-white hover:bg-blue-600'
                      : 'text-gray-500 hover:text-white hover:bg-blue-500'
                }`}
                disabled={isProcessing || !streamingComplete || isLoading || !inputValue.trim()}
              >
                <Send className="w-4 h-4" />
              </button>
              
              {/* 调试开关按钮 */}
              {DEBUG_MODE && (
                <button
                  type="button"
                  onClick={toggleDebugPanel}
                  className="absolute right-[-45px] bottom-0 text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded"
                >
                  调试
                </button>
              )}
            </form>
            {isEditing && (
              <div className={`mt-2 text-sm flex justify-end transition-colors duration-300 ${
                isDarkMode ? 'text-gray-400' : 'text-gray-600'
              }`}>
                <div>编辑模式</div>
                <button
                  type="button"
                  onClick={handleCancelEdit}
                  className={`ml-3 px-2 py-1 rounded transition-colors ${
                    isDarkMode ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'
                  }`}
                >
                  取消
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* 思考中状态弹窗 */}
      {showStreamingAlert && (
        <div className={`fixed top-20 right-4 px-4 py-3 rounded-xl shadow-lg z-50 transition-colors duration-300 ${
          isDarkMode ? 'bg-yellow-600 text-white' : 'bg-yellow-100 text-yellow-800 border border-yellow-200'
        }`}>
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium">消息处理被中断，已重置状态</span>
          </div>
        </div>
      )}
      
      {/* 状态指示器和控制按钮 */}
      <div className="fixed bottom-24 right-6 z-40 space-y-3">
        {!streamingComplete && (
          <div className={`px-4 py-2 rounded-xl text-sm flex items-center gap-2 shadow-lg transition-colors duration-300 ${
            isDarkMode ? 'bg-blue-600 text-white border border-blue-500' : 'bg-blue-50 text-blue-700 border border-blue-200'
          }`}>
            <div className="flex space-x-1">
              <div className={`w-2 h-2 rounded-full animate-pulse ${
                isDarkMode ? 'bg-white' : 'bg-blue-500'
              }`}></div>
              <div className={`w-2 h-2 rounded-full animate-pulse ${
                isDarkMode ? 'bg-white' : 'bg-blue-500'
              }`} style={{ animationDelay: '0.2s' }}></div>
              <div className={`w-2 h-2 rounded-full animate-pulse ${
                isDarkMode ? 'bg-white' : 'bg-blue-500'
              }`} style={{ animationDelay: '0.4s' }}></div>
            </div>
            <span className="font-medium">AI正在思考...</span>
          </div>
        )}
        <button
          onClick={handleManualReset}
          className={`px-3 py-2 rounded-xl text-xs shadow-lg transition-all duration-200 ${
            isDarkMode 
              ? 'bg-red-600 hover:bg-red-700 text-white' 
              : 'bg-red-50 hover:bg-red-100 text-red-700 border border-red-200'
          } opacity-70 hover:opacity-100`}
          title="当AI回复卡住时，使用此按钮重置聊天状态"
        >
          解除锁定状态
        </button>
      </div>
      
      {/* 调试面板 */}
      {showDebugPanel && (
        <div className={`border-t p-3 text-xs font-mono overflow-x-auto transition-colors duration-300 ${
          isDarkMode ? 'border-gray-700 bg-gray-800 text-gray-300' : 'border-gray-200 bg-gray-50 text-gray-700'
        }`}>
          <div className="space-y-1">
            <div>
              <strong>状态:</strong> 
              <span className={`ml-2 px-2 py-1 rounded text-xs ${
                isLoading ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'
              }`}>
                {isLoading ? '加载中' : '空闲'}
              </span>
              <span className={`ml-2 px-2 py-1 rounded text-xs ${
                streamingComplete ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
              }`}>
                {streamingComplete ? '流式完成' : '流式处理中'}
              </span>
              <span className={`ml-2 px-2 py-1 rounded text-xs ${
                isProcessing ? 'bg-orange-100 text-orange-800' : 'bg-gray-100 text-gray-800'
              }`}>
                {isProcessing ? '处理中' : '未处理'}
              </span>
            </div>
            {lastError && (
              <div className="text-red-500 mt-2 p-2 bg-red-50 rounded">
                <strong>错误:</strong> {lastError}
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* 将迁移按钮添加到界面中 */}
      <MigrationButton 
        onTriggerMigration={triggerMigration}
        isMigrating={isMigrating}
        days={30}
      />
    </div>
  );
}