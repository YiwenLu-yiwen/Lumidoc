import { useState, useRef, ChangeEvent } from 'react';
import { fileApi } from '../../../api/file';
import { toast } from 'sonner';

interface FileUploaderProps {
  projectId?: string;
}


interface UploadProgress {
  fileIndex: number;
  fileName: string;
  percentage: number;
  loaded: number;
  total: number;
  speed: number;
  remainingTime: number;
}

// 格式化文件大小
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

// 格式化上传速度
const formatSpeed = (bytesPerSecond: number): string => {
  return formatFileSize(bytesPerSecond) + '/s';
};

// 格式化剩余时间
const formatTime = (seconds: number): string => {
  if (!isFinite(seconds) || seconds < 0) return '--';
  if (seconds < 60) return `${Math.round(seconds)}秒`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`;
  return `${Math.round(seconds / 3600)}小时`;
};

const FileUploader: React.FC<FileUploaderProps> = ({ projectId }) => {
  const [files, setFiles] = useState<FileList | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResults, setUploadResults] = useState<{
    success: boolean;
    failures: string[];
    total: number;
    completed: number;
  } | null>(null);
  const [currentUploadProgress, setCurrentUploadProgress] = useState<UploadProgress | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);


  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFiles(e.target.files);
    // 清除之前的上传结果
    setUploadResults(null);
  };


  const handleUpload = async () => {
    if (!files || files.length === 0 || !projectId) {
      toast.error('请选择要上传的文件');
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setUploadResults(null);

    try {
      // 使用fileApi上传文件，带进度回调
      console.log(`准备上传文件到项目${projectId}，文件数量: ${files.length}`);
      const result = await fileApi.uploadFiles(projectId, Array.from(files), (progress) => {
        // 更新当前文件上传进度
        setCurrentUploadProgress(progress);
        // 计算总体进度 (考虑多文件的情况)
        const overallProgress = ((progress.fileIndex + progress.percentage / 100) / files.length) * 100;
        setUploadProgress(Math.round(overallProgress));
      });
      
      if (result.success) {
        // 处理上传结果
        const fileResults = result.files || [];
        const successFiles = fileResults.filter(f => f.success || f.file_id);
        const failedFiles = fileResults.filter(f => !f.success && !f.file_id);
        
        // 检查是否有文件已存在
        const existingFiles = fileResults.filter(f => f.exists).map(f => f.filename || '未知文件');
        
        // 设置上传结果以便显示
        setUploadResults({
          success: successFiles.length > 0,
          failures: failedFiles.map(f => f.filename || '未知文件'),
          total: fileResults.length,
          completed: successFiles.length
        });
        
        if (existingFiles.length > 0) {
          // 如果有文件已存在，显示特定消息
          toast.success(`${existingFiles.length}个文件已存在，无需重复上传`);
        }
        
        if (successFiles.length > 0 && successFiles.length !== existingFiles.length) {
          // 如果有新文件成功上传
          toast.success(`成功上传${successFiles.length - existingFiles.length}个文件`);
        }
        
        if (failedFiles.length > 0) {
          // 如果有文件上传失败
          toast.error(`${failedFiles.length}个文件上传失败`);
          // 显示详细错误信息
          failedFiles.forEach(file => {
            if (file.message) {
              console.error(`文件"${file.filename}"上传失败: ${file.message}`);
            }
          });
        }
        
        // 文件上传完成，无需跟踪处理进度
        console.log(`${successFiles.length}个文件上传完成`);
      } else {
        console.error('文件上传失败:', result);
        const errorMessage = result.files && result.files[0] && result.files[0].message 
          ? result.files[0].message 
          : '文件上传失败，请检查网络连接和服务器状态';
        throw new Error(errorMessage);
      }
    } catch (error) {
      console.error('上传失败:', error);
      toast.error(error instanceof Error ? error.message : '上传失败');
      setUploadResults({
        success: false,
        failures: Array.from(files).map(f => f.name),
        total: files.length,
        completed: 0
      });
    } finally {
      setUploading(false);
      setUploadProgress(100); // 完成进度
      // 清理当前上传进度
      setTimeout(() => {
        setCurrentUploadProgress(null);
      }, 2000); // 2秒后清理，让用户看到最终状态
      // 不再自动清空文件输入框，让用户看到上传结果
    }
  };
  
  // 清除所有文件选择和结果
  const handleClear = () => {
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setFiles(null);
    setUploadResults(null);
    setUploadProgress(0);
    setCurrentUploadProgress(null);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFiles(e.dataTransfer.files);
      // 清除之前的上传结果
      setUploadResults(null);
    }
  };

  return (
    <div className="p-6 bg-gray-900 rounded-lg border border-gray-700">
      <h2 className="text-xl font-semibold mb-4">上传文件</h2>
      
      {/* 拖拽区域 */}
      <div 
        className="border-2 border-dashed border-gray-600 rounded-lg p-8 text-center mb-4 hover:border-blue-500 transition-colors cursor-pointer"
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="flex flex-col items-center justify-center">
          <svg className="w-12 h-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-lg text-gray-300 mb-2">拖放文件到这里或点击选择</p>
          <p className="text-sm text-gray-500">支持 PDF, PPT, PPTX, DOC, DOCX, TXT, IMAGE 等格式</p>
          
          {files && files.length > 0 && (
            <div className="mt-4 text-left w-full">
              <p className="text-gray-300 font-medium">已选择 {files.length} 个文件 (总大小: {formatFileSize(Array.from(files).reduce((total, file) => total + file.size, 0))})</p>
            </div>
          )}
        </div>
      </div>
      
      {/* 隐藏的文件输入 */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
        multiple
        accept=".pdf,.ppt,.pptx,.doc,.docx,.txt,.jpg,.jpeg,.png,.md,.html,.htm,.xml"
      />
      
      {/* 上传进度条和详细信息 */}
      {(uploading || uploadProgress > 0) && (
        <div className="mb-4">
          {/* 当前文件上传信息 */}
          {currentUploadProgress && (
            <div className="mb-3 p-3 bg-gray-800 rounded-md">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-gray-300 truncate max-w-xs">
                  正在上传文件...
                </span>
                <span className="text-sm text-blue-400">
                  {currentUploadProgress.percentage}%
                </span>
              </div>
              
              {/* 详细进度条 */}
              <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                  style={{ width: `${currentUploadProgress.percentage}%` }}
                ></div>
              </div>
              
              {/* 详细信息行 */}
              <div className="flex justify-between text-xs text-gray-400">
                <span>
                  {formatFileSize(currentUploadProgress.loaded)} / {formatFileSize(currentUploadProgress.total)}
                </span>
                <div className="flex space-x-4">
                  <span>
                    速度: {formatSpeed(currentUploadProgress.speed)}
                  </span>
                  <span>
                    剩余: {formatTime(currentUploadProgress.remainingTime)}
                  </span>
                </div>
              </div>
            </div>
          )}
          
          {/* 总体进度条 */}
          {files && files.length > 1 && (
            <div className="mb-2">
              <div className="flex justify-between text-sm text-gray-300 mb-1">
                <span>总体进度</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div 
                  className="bg-green-600 h-2 rounded-full transition-all duration-300" 
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>
      )}
      
      
      {/* 上传结果信息 */}
      {uploadResults && !uploading && (
        <div className={`p-3 rounded-md mb-4 ${
          uploadResults.success ? 'bg-green-900 bg-opacity-30' : 'bg-red-900 bg-opacity-30'
        }`}>
          <p className={uploadResults.success ? 'text-green-400' : 'text-red-400'}>
            {uploadResults.success 
              ? `成功上传 ${uploadResults.completed}/${uploadResults.total} 个文件` 
              : `上传失败: ${uploadResults.failures.length}/${uploadResults.total} 个文件出错`
            }
          </p>
        </div>
      )}
      
      {/* 上传按钮 */}
      <div className="flex justify-end space-x-2">
        {(files && files.length > 0) && (
          <button
            onClick={handleClear}
            className="px-6 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
          >
            清除
          </button>
        )}
        <button
          onClick={handleUpload}
          className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          disabled={uploading || !files || files.length === 0}
        >
          {uploading ? '上传中...' : '上传文件'}
        </button>
      </div>
    </div>
  );
};

export default FileUploader; 