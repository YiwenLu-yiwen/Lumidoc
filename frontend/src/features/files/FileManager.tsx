import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { FilesList, FileUploader } from './components';
import { Tab, PageHeader } from '../../components/layout';
import { Spinner } from '../../components/ui';
import useAuthState from '../../hooks/useAuthState';

// 存储标签状态的本地存储键名
const TAB_STORAGE_KEY = 'stp_file_manager_active_tab';

const FileManager = () => {
  // 使用认证状态钩子，确保用户已登录
  const { isLoading, isAuthorized } = useAuthState(true, true);
  const { projectId } = useParams();
  
  // 从本地存储获取初始标签状态或使用默认值
  const getInitialTab = () => {
    try {
      const savedTab = localStorage.getItem(TAB_STORAGE_KEY);
      return savedTab || 'uploaded';
    } catch (e) {
      console.error('读取标签状态失败:', e);
      return 'uploaded';
    }
  };
  
  // 设置当前激活的标签页
  const [activeTab, setActiveTab] = useState(getInitialTab);
  
  // 当标签页变化时，保存到本地存储
  useEffect(() => {
    try {
      localStorage.setItem(TAB_STORAGE_KEY, activeTab);
    } catch (e) {
      console.error('保存标签状态失败:', e);
    }
  }, [activeTab]);
  
  // 监听自定义事件，用于在导入文件后切换到RAG标签页
  useEffect(() => {
    const handleSwitchToRagTab = () => {
      console.log('[FileManager] 收到切换到RAG标签页的事件');
      setActiveTab('rag');
    };
    
    // 监听刷新RAG文件列表的事件
    const handleRefreshRagFiles = () => {
      console.log('[FileManager] 收到刷新RAG文件列表的事件');
      // 这里不需要做什么，因为FilesList组件会自己处理刷新
      // 只是记录日志确认事件被接收到
    };
    
    // 添加事件监听器
    document.addEventListener('switchToRagTab', handleSwitchToRagTab);
    document.addEventListener('refreshRagFiles', handleRefreshRagFiles);
    
    // 清理函数
    return () => {
      document.removeEventListener('switchToRagTab', handleSwitchToRagTab);
      document.removeEventListener('refreshRagFiles', handleRefreshRagFiles);
    };
  }, []);
  
  // 处理标签页变化
  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
  };
  
  if (isLoading) {
    return <div className="flex justify-center items-center h-full"><Spinner /></div>;
  }
  
  if (!isAuthorized || !projectId) {
    return <div className="text-center p-4">请先登录并选择项目</div>;
  }
  
  return (
    <div className="w-full h-full flex flex-col">
      <PageHeader title="文件管理" />
      
      <div className="flex border-b">
        <Tab 
          id="uploaded"
          label="已上传文件"
          isActive={activeTab === 'uploaded'} 
          onClick={() => handleTabChange('uploaded')}
        />
        <Tab 
          id="rag"
          label="知识库文件"
          isActive={activeTab === 'rag'} 
          onClick={() => handleTabChange('rag')}
        />
        <Tab 
          id="upload"
          label="上传文件"
          isActive={activeTab === 'upload'} 
          onClick={() => handleTabChange('upload')}
        />
      </div>
      
      <div className="flex-grow overflow-auto p-4">
        {activeTab === 'uploaded' && (
          <FilesList 
            fileType="regular" 
            projectId={projectId} 
            onTabChange={handleTabChange}
          />
        )}
        {activeTab === 'rag' && (
          <FilesList 
            fileType="rag" 
            projectId={projectId} 
          />
        )}
        {activeTab === 'upload' && (
          <FileUploader projectId={projectId} />
        )}
      </div>
    </div>
  );
};

export default FileManager; 