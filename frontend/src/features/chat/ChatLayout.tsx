import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import TextareaAutosize from 'react-textarea-autosize';
import { 
  Copy, 
  Edit3, 
  Trash2, 
  History, 
  Send,
  Square,
  MessageSquare, 
  User,
  Bot,
  Brain,
  ChevronDown,
  ChevronRight
} from 'lucide-react';
import { useTheme } from '@/context/ThemeContext';
import { useLanguage } from '@/context/LanguageContext';
import { useProjects } from '@/context/ProjectContext';
import { useSelectedModel } from '@/hooks/useModel';
import { deleteConversation } from '@/api/conversations';
import { createChatRequestPayload } from './chatRequest';

// 导入迁移按钮组件
import MigrationButton from './components/MigrationButton';

// 是否开启调试模式
const DEBUG_MODE = import.meta.env.VITE_DEBUG_MODE === 'true';

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

interface ChatHistoryMessage {
  id?: string;
  content?: string;
  role?: string;
  timestamp?: string;
}

interface MigrationResult {
  projects_processed: number;
  messages_migrated: number;
  errors: number;
}

const MAX_MESSAGES = 500;

export default function ChatLayout() {
  const { projectId: routeProjectId } = useParams<{ projectId: string }>();
  const { projects } = useProjects();
  const [searchParams, setSearchParams] = useSearchParams();
  const projectId = routeProjectId || projects[0]?.id;
  const storageKey = `lumidoc-conversation:${projectId || 'default'}`;
  const conversationId = searchParams.get('conversation') || sessionStorage.getItem(storageKey) || 'legacy';
  useEffect(() => { sessionStorage.setItem(storageKey, conversationId); }, [storageKey, conversationId]);
  useEffect(() => {
    const onDeleted = (event: Event) => {
      const detail = (event as CustomEvent<{ projectId: string; conversationId: string }>).detail;
      if (detail.projectId !== projectId || detail.conversationId !== conversationId) return;
      const nextId = crypto.randomUUID();
      sessionStorage.setItem(storageKey, nextId);
      setSearchParams(params => { params.set('conversation', nextId); return params; }, { replace: true });
    };
    window.addEventListener('conversation-deleted', onDeleted);
    return () => window.removeEventListener('conversation-deleted', onDeleted);
  }, [projectId, conversationId, storageKey, setSearchParams]);
  return <ChatConversation key={`${projectId}/${conversationId}`} projectId={projectId} conversationId={conversationId} />;
}

function ChatConversation({ projectId, conversationId }: { projectId?: string; conversationId: string }) {
  const { selectedModel } = useSelectedModel();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const followBottom = useRef(true);
  const submitting = useRef(false);
  const streamFinished = useRef<Promise<void> | null>(null);
  const [streamAccepted, setStreamAccepted] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editMessageId, setEditMessageId] = useState<string | null>(null);
  const [isComposing, setIsComposing] = useState(false);
  const [streamingComplete, setStreamingComplete] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showDebugPanel, setShowDebugPanel] = useState(false);
  const requestTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const historyRequest = useRef(0);
  const [backgroundPending, setBackgroundPending] = useState(false);
  const [, setEditOriginalValue] = useState('');
  const [, setInitialized] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [, setIsHistoryLoaded] = useState(false);
  const loadedRef = useRef(false);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [showHistorySelector, setShowHistorySelector] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [historyPage, setHistoryPage] = useState(0);
  const [isMigrating, setIsMigrating] = useState(false);
  const [migrationResult, setMigrationResult] = useState<MigrationResult | null>(null);
  const [collapsedThinking, setCollapsedThinking] = useState<Set<string>>(new Set());

  // 主题模式和语言检测
  const { isDarkMode } = useTheme();
  const { currentLanguage, t } = useLanguage();


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
        {currentLanguage === 'zh-CN' ? '思考过程' : 'Thinking Process'}
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
    const container = messagesContainerRef.current;
    if (container && followBottom.current) container.scrollTop = container.scrollHeight;
  };

  // 只跟随消息容器底部；用户阅读历史时保留其滚动位置。
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 优化处理滚动事件，防止不必要的黄色警告显示
  useEffect(() => {
    const handleScroll = () => {
      const container = messagesContainerRef.current;
      if (container) followBottom.current = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
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
  const loadChatHistory = useCallback(async (includeArchivedMessages = false, page = 0) => {
    if (loadedRef.current && !includeArchivedMessages && page === 0) return;
    const requestId = ++historyRequest.current;
    
    try {
      const token = localStorage.getItem('lumidoc_token');
      const userId = JSON.parse(localStorage.getItem('lumidoc_user') || '{}').id || 'unknown';
      
      const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
      // 构建包含归档参数的URL - 通过Gateway访问
      const url = `${gatewayUrl}/chat/api/chat/history/${projectId || 'default'}?user_id=${userId}&include_archived=${includeArchivedMessages}&offset=${page * 50}&limit=50&session_id=${encodeURIComponent(conversationId)}`;
      
      console.log('正在加载聊天历史，请求URL:', url);
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        // 丢弃项目切换或发送新消息之前发起的历史请求。
        if (requestId !== historyRequest.current) return;
        if (data && Array.isArray(data) && data.length > 0) {
          // 转换历史消息格式并加载
          const historyMessages = (data as ChatHistoryMessage[]).map((msg) => ({
            id: msg.id || Date.now().toString() + Math.random().toString(),
            content: processSpecialFormat(msg.content || ''),
            isUser: msg.role === 'user',
            timestamp: msg.timestamp || new Date().toISOString()
          }));
          
          console.log(`已加载 ${historyMessages.length} 条聊天历史`);
          
          // 如果是加载更多历史消息，则追加到现有消息末尾
          if (page > 0) {
            setMessages(prev => Array.from(new Map([...historyMessages, ...prev].map(msg => [msg.id, msg])).values()));
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
      setLastError(error instanceof Error ? error.message : '加载聊天历史出错');
    }
    
    if (!includeArchivedMessages && page === 0) {
      loadedRef.current = true;
    }
  }, [projectId, conversationId]);

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
    loadedRef.current = false;
    void loadChatHistory(newValue, 0); // 重新加载消息
  };

  // 清除聊天历史
  const [isDeleting, setIsDeleting] = useState(false);
  const clearChatHistory = async () => {
    if (!projectId || isDeleting) return;
    if (!confirm(currentLanguage === 'zh-CN' ? '确定要删除当前会话吗？' : 'Delete this conversation?')) return;
    setIsDeleting(true);
    try {
      await deleteConversation(projectId, conversationId);
    } catch (error) {
      setLastError(error instanceof Error ? error.message : '会话删除失败');
      setIsDeleting(false);
    }
  };

  // 在组件挂载时确保状态正确初始化
  useEffect(() => {
    // 确保流式完成状态被设置为true
    setStreamingComplete(true);
    setIsLoading(false);
    setInitialized(true);
    console.log('ChatLayout组件已初始化，重置所有状态');
    
    // 切换项目时重新读取历史，并清除上一项目的消息。
    loadedRef.current = false;
    setMessages([]);
    void loadChatHistory();
    
    // 清除任何可能存在的中断请求
    if (abortControllerRef.current) {
      console.log('组件初始化，取消可能存在的旧请求');
      try {
      abortControllerRef.current.abort();
      } catch {
        // 忽略中断过程中的任何错误
      }
      abortControllerRef.current = null;
    }
    
    // 组件卸载时的清理
    return () => {
      historyRequest.current++;
      if (requestTimeout.current) clearTimeout(requestTimeout.current);
      if (abortControllerRef.current) {
        console.log('组件卸载，取消未完成的请求');
        
        try {
        abortControllerRef.current.abort();
        } catch {
          // 忽略中断过程中的任何错误
        }
        
        abortControllerRef.current = null;
      }
      
    };
  }, [loadChatHistory]);

  // 返回聊天页面时跟踪服务端任务，完成后重新加载已保存的回复。
  useEffect(() => {
    let disposed = false;
    let wasPending = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
        const userId = JSON.parse(localStorage.getItem('lumidoc_user') || '{}').id || 'unknown';
        const response = await fetch(`${gatewayUrl}/chat/api/chat/pending/${projectId || 'default'}?user_id=${encodeURIComponent(userId)}&session_id=${encodeURIComponent(conversationId)}`, {
          headers: { Authorization: `Bearer ${localStorage.getItem('lumidoc_token')}` },
        });
        if (!response.ok) return;
        const data = await response.json();
        if (disposed || typeof data.pending !== 'boolean') return;
        setBackgroundPending(data.pending);
        if (!abortControllerRef.current && wasPending && !data.pending) {
          loadedRef.current = false;
          await loadChatHistory();
        }
        wasPending = data.pending;
      } catch {
        // 暂时的网络错误不影响当前对话，下一次继续检查。
      } finally {
        if (!disposed) timer = setTimeout(poll, 2000);
      }
    };
    void poll();
    return () => { disposed = true; clearTimeout(timer); };
  }, [projectId, conversationId, loadChatHistory]);

  const stopGeneration = async () => {
    if (isStopping) return;
    setIsStopping(true);
    setLastError(null);
    try {
      const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
      const userId = JSON.parse(localStorage.getItem('lumidoc_user') || '{}').id || 'unknown';
      const response = await fetch(`${gatewayUrl}/chat/api/chat/stop/${projectId || 'default'}?user_id=${encodeURIComponent(userId)}&session_id=${encodeURIComponent(conversationId)}`, {
        method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('lumidoc_token')}` },
      });
      if (!response.ok) throw new Error(currentLanguage === 'zh-CN' ? '停止生成失败，请重试。' : 'Could not stop generation. Please retry.');
      // 等待已取消的流退出，避免上一请求的清理影响下一条消息。
      await streamFinished.current;
      setBackgroundPending(false);
      loadedRef.current = false;
      await loadChatHistory();
      window.dispatchEvent(new Event('chat-updated'));
    } catch (error) {
      setLastError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsStopping(false);
    }
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
  
  // 消息提交处理 - 添加避免频繁显示警告的逻辑
  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    
    // 如果已经在处理中，直接返回
    if (isStopping || submitting.current || backgroundPending || isProcessing || !streamingComplete || isLoading || !inputValue.trim()) {
      return;
    }
    
    let finishStream!: () => void;
    streamFinished.current = new Promise(resolve => { finishStream = resolve; });
    setStreamAccepted(false);
    try {
      submitting.current = true;
      followBottom.current = true;
      // 新消息优先，未完成的历史读取不能覆盖当前对话。
      historyRequest.current++;
      loadedRef.current = true;
      // 设置为处理中状态
      setIsProcessing(true);
      setStreamingComplete(false);
      
      // 为本地模型预留首次加载和检索时间，到期后解除输入锁定。
      const timeoutId = setTimeout(() => {
        console.log('聊天请求超时，自动中断');
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
                content: "请求超时，请重新发送您的问题或稍后再试。"
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
      }, 180000); // 本地模型首次响应最多等待三分钟
      
      requestTimeout.current = timeoutId;
      
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
      
      // 用户消息和最终回复由服务端统一保存。
      
      // 强制滚动到底部显示思考中动画
      setTimeout(() => {
        scrollToBottom();
      }, 50);
      
      // 清空输入框
      setInputValue('');
      
      // 设置加载状态
      setIsLoading(true);
      
      // 获取token
        const token = localStorage.getItem('lumidoc_token');
        
        try {
        // 创建中断控制器
          const controller = new AbortController();
          abortControllerRef.current = controller;
        
        // 通过Gateway访问聊天服务API
        const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
        const url = `${gatewayUrl}/chat/api/chat/stream`;
        
        // 发送请求
        const response = await fetch(url, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
          body: JSON.stringify(createChatRequestPayload({
            content: userMessage.content,
            projectId,
            userId: JSON.parse(localStorage.getItem('lumidoc_user') || '{}').id,
            modelId: selectedModel?.id,
            conversationId,
          })),
            signal: controller.signal,
          });
          
        if (!response.ok) {
          throw new Error(`API返回状态码 ${response.status}`);
        }
          
        setStreamAccepted(true);
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
              const chunk = decoder.decode(value, { stream: true });
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
                    
                    if (data.stopped) {
                      setMessages(prev => prev.map((m, idx) => idx === prev.length - 1 && !m.isUser && !m.content
                        ? { ...m, content: currentLanguage === 'zh-CN' ? '已停止生成。' : 'Generation stopped.' } : m));
                    }
                    // 如果是完成标记
                    if (data.done) {
                      done = true;
                      continue;
                    }
                    
                    // 累积回复内容
                    if (data.content) {
                      // 处理特殊标记
                      const processedContent = data.content;
                      aiReply += processedContent;
                      
                      // 解析思考模型的输出
                      const { thinking, answer } = parseThinkingModelOutput(aiReply);
                      
                      // 检查是否含有完成标记
                      if (data.content.includes("<COMPLETE>") || 
                          data.content.includes("<|COMPLETE|>")) {
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
          window.dispatchEvent(new Event('chat-updated'));
          
        // 清除请求超时
        if (requestTimeout.current) {
          clearTimeout(requestTimeout.current);
          requestTimeout.current = null;
        }
        } catch (error: unknown) {
          // 确保错误情况下也重置所有状态
          setStreamingComplete(true);
          setIsLoading(false);
          setIsProcessing(false);
          const errorMessage = error instanceof Error ? error.message : String(error);
          
        // 错误处理
          if (error instanceof Error && error.name === 'AbortError') {
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
          setLastError(errorMessage);
          setMessages(prev => {
            const newMessages = [...prev];
            // 找到并更新最后一个机器人消息
            for (let i = newMessages.length - 1; i >= 0; i--) {
              if (!newMessages[i].isUser) {
                newMessages[i] = {
                  ...newMessages[i],
                  content: `发生错误：${errorMessage}`
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
        if (requestTimeout.current) {
          clearTimeout(requestTimeout.current);
          requestTimeout.current = null;
                }
              }
      } catch (error: unknown) {
      console.error('处理消息提交出错:', error);
      setLastError(error instanceof Error ? error.message : String(error));
      setIsProcessing(false);
        setStreamingComplete(true);
        setIsLoading(false);
      
      // 清除请求超时
      if (requestTimeout.current) {
        clearTimeout(requestTimeout.current);
        requestTimeout.current = null;
      }
    } finally {
      submitting.current = false;
      setStreamAccepted(false);
      finishStream();
    }
  };
    
  // 添加手动触发迁移消息的函数
  const triggerMigration = async (days: number = 30) => {
    if (!confirm(`确定要将${days}天前的聊天历史迁移到数据库吗？`)) return;
    
    try {
      setIsMigrating(true);
      
      const token = localStorage.getItem('lumidoc_token');
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
      setLastError(error instanceof Error ? error.message : '触发迁移时出错');
      alert('迁移请求出错，请查看控制台日志');
    } finally {
      setIsMigrating(false);
    }
  };

  // 渲染UI
  return (
    <div className={`h-full min-h-0 flex flex-col transition-colors duration-300 ${
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
            {currentLanguage === 'zh-CN' ? 'Lumidoc Intelligence 聊天' : 'Lumidoc Intelligence Chat'}
          </div>
        </div>
        <div className="flex-1 flex justify-end space-x-3">
          <button 
            onClick={() => setShowHistorySelector(!showHistorySelector)}
            className={`p-2 rounded-lg transition-colors ${
              isDarkMode ? 'text-gray-400 hover:text-white hover:bg-gray-700' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
            title={currentLanguage === 'zh-CN' ? '查看历史消息' : 'View History Messages'}
          >
            <History className="w-5 h-5" />
          </button>
          <button 
            onClick={clearChatHistory}
            disabled={isDeleting}
            className={`p-2 rounded-lg transition-colors ${
              isDarkMode ? 'text-gray-400 hover:text-white hover:bg-gray-700' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
            title={currentLanguage === 'zh-CN' ? '删除当前会话' : 'Delete current conversation'}
            aria-label={currentLanguage === 'zh-CN' ? '删除当前会话' : 'Delete current conversation'}
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
            <div className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              {currentLanguage === 'zh-CN' ? '历史消息' : 'History Messages'}
            </div>
            <button 
              onClick={() => setShowHistorySelector(false)}
              className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                isDarkMode ? 'text-gray-400 hover:text-white hover:bg-gray-700' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
              }`}
            >
              {currentLanguage === 'zh-CN' ? '关闭' : 'Close'}
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
              {currentLanguage === 'zh-CN' ? '包含归档消息（30天前）' : 'Include archived messages (30 days ago)'}
            </label>
            <div className="flex flex-wrap gap-3">
              <button 
                onClick={loadMoreHistory}
                className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                  isDarkMode ? 'text-blue-400 hover:text-blue-300 bg-blue-900/20 hover:bg-blue-900/30' : 'text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100'
                }`}
              >
                {currentLanguage === 'zh-CN' ? '加载更多历史消息' : 'Load More History Messages'}
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
                title={currentLanguage === 'zh-CN' ? '将30天前的消息迁移到数据库存档' : 'Migrate messages older than 30 days to database archive'}
              >
                {isMigrating 
                  ? (currentLanguage === 'zh-CN' ? '迁移中...' : 'Migrating...')
                  : (currentLanguage === 'zh-CN' ? '归档旧消息' : 'Archive Old Messages')
                }
              </button>
            </div>
          </div>
          
          {/* 显示迁移结果 */}
          {migrationResult && (
            <div className={`mt-3 text-sm p-3 rounded-lg ${
              isDarkMode ? 'text-gray-300 bg-gray-700' : 'text-gray-700 bg-white border border-gray-200'
            }`}>
              <div>
                {currentLanguage === 'zh-CN' 
                  ? `迁移结果: 处理${migrationResult.projects_processed}个项目，迁移${migrationResult.messages_migrated}条消息`
                  : `Migration result: Processed ${migrationResult.projects_processed} projects, migrated ${migrationResult.messages_migrated} messages`
                }
              </div>
              {migrationResult.errors > 0 && (
                <div className="text-red-500 mt-1">
                  {currentLanguage === 'zh-CN' 
                    ? `发生${migrationResult.errors}个错误`
                    : `${migrationResult.errors} errors occurred`
                  }
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* 主要聊天区域 - 使用相对定位和灵活布局 */}
      <div className="relative min-h-0 flex-1 flex flex-col overflow-hidden">
        {/* 滚动消息区域 - 填充可用空间 */}
        <div 
          ref={messagesContainerRef}
          aria-label="Chat messages"
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain py-6 px-6 pb-6 md:pb-8"
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
                    {currentLanguage === 'zh-CN' ? '开始智能对话' : 'Start Intelligent Conversation'}
                  </h2>
                  <p className="text-lg">{t('intelligentQASystem')}</p>
                  <p className="text-sm mt-3 opacity-70">
                    {currentLanguage === 'zh-CN' 
                      ? '您可以询问任何问题，我会基于知识图谱为您提供精准回答'
                      : 'You can ask any question, and I will provide accurate answers based on knowledge graphs'
                    }
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
                                {currentLanguage === 'zh-CN' ? '取消' : 'Cancel'}
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
                                      ? currentLanguage === 'zh-CN'
                                      ? `思考过程：\n${message.thinking}\n\n回答：\n${message.content}`
                                      : `Thinking Process:\n${message.thinking}\n\nAnswer:\n${message.content}`
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
                              <span className="text-sm">
                                {currentLanguage === 'zh-CN' ? 'AI正在思考中...' : 'AI is thinking...'}
                              </span>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}

            </div>
          )}
        </div>
        
        {/* 输入区域固定在底部 */}
        <div className={`w-full shrink-0 border-t py-4 px-4 md:px-6 z-10 transition-colors duration-300 ${
          isDarkMode ? 'border-gray-800 bg-[#212121]' : 'border-gray-200 bg-white'
        }`}>
          <div className="max-w-4xl mx-auto">
            {backgroundPending && !isLoading && (
              <p role="status" className="mb-2 text-sm text-blue-600">
                {currentLanguage === 'zh-CN' ? '回复正在后台生成，离开页面后仍会继续' : 'Reply continues in the background'}
              </p>
            )}
            {lastError && <p role="alert" className="mb-2 text-sm text-red-600">{lastError}</p>}
            <form onSubmit={handleSubmit} className={`relative rounded-2xl shadow-lg transition-colors duration-300 ${
              isDarkMode ? 'bg-gray-800 border border-gray-700' : 'bg-white border border-gray-200'
            }`}>
              <TextareaAutosize
                value={inputValue}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                onCompositionStart={handleCompositionStart}
                onCompositionEnd={handleCompositionEnd}
                placeholder={currentLanguage === 'zh-CN' ? '输入您的问题，按 Enter 发送...' : 'Enter your question, press Enter to send...'}
                className={`w-full bg-transparent px-4 py-3 pr-12 resize-none rounded-2xl focus:outline-none transition-colors duration-300 ${
                  isDarkMode 
                    ? 'text-gray-100 placeholder-gray-400' 
                    : 'text-gray-900 placeholder-gray-500'
                }`}
                minRows={1}
                maxRows={6}
                disabled={backgroundPending || isProcessing || !streamingComplete || isLoading}
              />
              {(backgroundPending || isProcessing || !streamingComplete || isLoading || isStopping) ? (
                <button type="button" onClick={() => void stopGeneration()}
                  disabled={isStopping || (!streamAccepted && !backgroundPending)}
                  aria-label={currentLanguage === 'zh-CN' ? '停止生成' : 'Stop generating'}
                  className="absolute bottom-3 right-3 flex items-center gap-1 rounded-lg bg-red-50 px-2 py-1 text-sm text-red-700 disabled:opacity-50">
                  <Square className="h-3 w-3" fill="currentColor" />
                  {isStopping ? (currentLanguage === 'zh-CN' ? '正在停止…' : 'Stopping…') : (currentLanguage === 'zh-CN' ? '停止生成' : 'Stop generating')}
                </button>
              ) : (
                <button type="submit" disabled={!inputValue.trim()}
                  aria-label={currentLanguage === 'zh-CN' ? '发送消息' : 'Send message'}
                  className="absolute bottom-3 right-3 rounded-xl p-2 text-blue-600 disabled:text-gray-400">
                  <Send className="w-4 h-4" />
                </button>
              )}

              {/* 调试开关按钮 */}
              {DEBUG_MODE && (
                <button
                  type="button"
                  onClick={toggleDebugPanel}
                  className="absolute right-[-45px] bottom-0 text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded"
                >
                  {currentLanguage === 'zh-CN' ? '调试' : 'Debug'}
                </button>
              )}
            </form>
            {isEditing && (
              <div className={`mt-2 text-sm flex justify-end transition-colors duration-300 ${
                isDarkMode ? 'text-gray-400' : 'text-gray-600'
              }`}>
                <div>{currentLanguage === 'zh-CN' ? '编辑模式' : 'Edit Mode'}</div>
                <button
                  type="button"
                  onClick={handleCancelEdit}
                  className={`ml-3 px-2 py-1 rounded transition-colors ${
                    isDarkMode ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'
                  }`}
                >
                  {currentLanguage === 'zh-CN' ? '取消' : 'Cancel'}
                </button>
              </div>
            )}
          </div>
        </div>
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
                {isLoading 
                  ? (currentLanguage === 'zh-CN' ? '加载中' : 'Loading')
                  : (currentLanguage === 'zh-CN' ? '空闲' : 'Idle')
                }
              </span>
              <span className={`ml-2 px-2 py-1 rounded text-xs ${
                streamingComplete ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
              }`}>
                {streamingComplete 
                  ? (currentLanguage === 'zh-CN' ? '流式完成' : 'Streaming Complete')
                  : (currentLanguage === 'zh-CN' ? '流式处理中' : 'Streaming')
                }
              </span>
              <span className={`ml-2 px-2 py-1 rounded text-xs ${
                isProcessing ? 'bg-orange-100 text-orange-800' : 'bg-gray-100 text-gray-800'
              }`}>
                {isProcessing 
                  ? (currentLanguage === 'zh-CN' ? '处理中' : 'Processing')
                  : (currentLanguage === 'zh-CN' ? '未处理' : 'Not Processing')
                }
              </span>
            </div>
            {lastError && (
              <div className="text-red-500 mt-2 p-2 bg-red-50 rounded">
                <strong>{currentLanguage === 'zh-CN' ? '错误' : 'Error'}:</strong> {lastError}
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
