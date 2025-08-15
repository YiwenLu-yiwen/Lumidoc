import React, { useState, useEffect } from 'react';
import { Loader2, FileText, CheckCircle, AlertCircle } from 'lucide-react';

interface FileItem {
  id: string;
  filename: string;
  file_type: string;
  status: string;
  processed_at?: string;
  file_size?: number;
}

interface FileSelectorProps {
  projectId: string;
  onFilesSelected?: (fileIds: string[]) => void;
}

export const FileSelector: React.FC<FileSelectorProps> = ({ 
  projectId, 
  onFilesSelected 
}) => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [message, setMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);

  // 获取项目文件列表
  useEffect(() => {
    fetchFiles();
  }, [projectId]);

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  const fetchFiles = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/files/projects/${projectId}`);
      const data = await response.json();
      
      if (data.success) {
        setFiles(data.files || []);
      } else {
        showMessage('error', data.message || '获取文件失败');
      }
    } catch (error) {
      showMessage('error', '网络错误，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (fileId: string, checked: boolean) => {
    const newSelected = new Set(selectedFiles);
    if (checked) {
      newSelected.add(fileId);
    } else {
      newSelected.delete(fileId);
    }
    setSelectedFiles(newSelected);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const processedFiles = files.filter(file => file.status === 'completed');
      setSelectedFiles(new Set(processedFiles.map(f => f.id)));
    } else {
      setSelectedFiles(new Set());
    }
  };

  const handleSubmitToLightRAG = async () => {
    if (selectedFiles.size === 0) {
      showMessage('error', '请至少选择一个文件进行处理');
      return;
    }

    try {
      setProcessing(true);
      
      const response = await fetch(`/api/rag/projects/${projectId}/files/select`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          file_ids: Array.from(selectedFiles)
        })
      });

      const data = await response.json();

      if (data.success) {
        showMessage('success', `成功处理 ${data.processed_files} 个文件，插入 ${data.inserted_count} 个文档到LightRAG`);
        
        // 清空选择
        setSelectedFiles(new Set());
        
        // 通知父组件
        if (onFilesSelected) {
          onFilesSelected(Array.from(selectedFiles));
        }
      } else {
        showMessage('error', data.message || '文件处理失败');
      }
    } catch (error) {
      showMessage('error', '网络错误，请重试');
    } finally {
      setProcessing(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const baseStyle = "inline-flex items-center px-2 py-1 rounded-full text-xs font-medium";
    
    switch (status) {
      case 'completed':
        return (
          <span className={`${baseStyle} bg-green-100 text-green-800`}>
            <CheckCircle className="w-3 h-3 mr-1" />
            已处理
          </span>
        );
      case 'processing':
        return (
          <span className={`${baseStyle} bg-blue-100 text-blue-800`}>
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            处理中
          </span>
        );
      case 'failed':
        return (
          <span className={`${baseStyle} bg-red-100 text-red-800`}>
            <AlertCircle className="w-3 h-3 mr-1" />
            失败
          </span>
        );
      default:
        return (
          <span className={`${baseStyle} bg-gray-100 text-gray-800`}>
            待处理
          </span>
        );
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  const processedFiles = files.filter(file => file.status === 'completed');
  const allProcessedSelected = processedFiles.length > 0 && 
    processedFiles.every(file => selectedFiles.has(file.id));

  if (loading) {
    return (
      <div className="bg-white rounded-lg border shadow-sm p-6">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          <span>加载文件列表...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border shadow-sm">
      <div className="p-6 border-b">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">选择文件进入LightRAG</h3>
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={allProcessedSelected}
              onChange={(e) => handleSelectAll(e.target.checked)}
              disabled={processedFiles.length === 0}
              className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
            />
            <span className="text-sm text-gray-600">全选已处理文件</span>
          </div>
        </div>
      </div>
      
      <div className="p-6">
        {/* 消息提示 */}
        {message && (
          <div className={`mb-4 p-4 rounded-md ${
            message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
          }`}>
            {message.text}
          </div>
        )}
        
        {files.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>暂无文件</p>
          </div>
        ) : (
          <div className="space-y-3">
            {files.map((file) => (
              <div
                key={file.id}
                className={`flex items-center space-x-3 p-3 border rounded-lg ${
                  file.status === 'completed' ? 'bg-gray-50' : 'bg-gray-100 opacity-60'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedFiles.has(file.id)}
                  onChange={(e) => handleFileSelect(file.id, e.target.checked)}
                  disabled={file.status !== 'completed'}
                  className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                />
                
                <FileText className="w-5 h-5 text-blue-500 flex-shrink-0" />
                
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{file.filename}</p>
                  <p className="text-sm text-gray-500">
                    {file.file_type} {file.file_size && `• ${formatFileSize(file.file_size)}`}
                    {file.processed_at && ` • 处理时间: ${new Date(file.processed_at).toLocaleString()}`}
                  </p>
                </div>
                
                <div className="flex-shrink-0">
                  {getStatusBadge(file.status)}
                </div>
              </div>
            ))}
            
            {selectedFiles.size > 0 && (
              <div className="pt-4 border-t">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">
                    已选择 {selectedFiles.size} 个文件
                  </span>
                  <button
                    onClick={handleSubmitToLightRAG}
                    disabled={processing}
                    className="ml-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                  >
                    {processing ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        处理中...
                      </>
                    ) : (
                      '提交到LightRAG'
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}; 