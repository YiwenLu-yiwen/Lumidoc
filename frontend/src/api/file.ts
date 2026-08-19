import { apiClient } from './client';
import { ApiResponse } from '../types/api';

interface BatchDeleteResult {
  deleted: unknown[];
  failed: unknown[];
}

interface FileProcessResponse {
  success: boolean;
  message?: string;
}

interface RawFileInfo {
  file_id?: string | number;
  filename?: string;
  display_name?: string;
  path?: string;
  size?: number;
  file_type?: string;
  content_type?: string;
  created_at?: string;
  updated_at?: string;
  metadata?: string;
  status?: string;
  file_hash?: string;
  name?: string;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '未知错误';
}

// 统一通过Gateway访问文件服务
const gatewayURL = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
console.log('[File API] 通过Gateway访问文件服务:', gatewayURL);

// 从后端响应数据转换为前端使用的FileInfo对象
const convertToFileInfo = (file: RawFileInfo): FileInfo => {
  // 确保文件名正确解码
  const filename = file.filename || '';
  let displayName = '';
  
  try {
    // 尝试解码文件名，如果已经是解码状态则保持不变
    displayName = file.display_name || decodeURIComponent(filename);
    
    // 检查文件名是否为空或undefined
    if (!displayName || displayName === 'undefined' || displayName === 'null') {
      // 尝试从路径中提取文件名
      if (file.path) {
        const pathParts = file.path.split('/');
        const lastPart = pathParts[pathParts.length - 1];
        displayName = lastPart || filename;
      } else {
        displayName = filename || '未命名文件';
      }
    }
    
    console.log(`[File API] 文件名处理完成`);
  } catch (e) {
    // 如果解码失败，使用原始文件名
    console.warn('[File API] 文件名解码失败:', e);
    displayName = filename || '未命名文件';
  }
  
  return {
    file_id: file.file_id ? String(file.file_id) : '',
    filename: filename,
    path: file.path || '',
    size: file.size || 0,
    file_type: file.file_type || 'application/octet-stream',
    content_type: file.content_type || file.file_type || 'application/octet-stream',
    created_at: file.created_at || new Date().toISOString(),
    updated_at: file.updated_at || new Date().toISOString(),
    metadata: file.metadata || '',
    display_name: displayName,
    status: file.status || 'pending',
    file_hash: file.file_hash || '',
    name: file.name || '',
  };
};

export interface FileInfo {
  file_id: string;          // 字符串类型的文件ID
  filename: string;         // 文件名
  name?: string;           // 添加name字段
  path: string;             // 文件路径
  size: number;             // 文件大小
  file_type: string;        // 文件类型
  content_type: string;     // 文件内容类型
  created_at: string;       // 创建时间
  updated_at: string;       // 更新时间
  metadata: string;         // 元数据
  display_name?: string;    // 解码后用于显示的文件名
  status?: string;          // 文件处理状态
  file_hash: string;        // 文件哈希值
  rag_status?: string;      // RAG处理状态
  is_in_rag?: boolean;      // 是否在RAG中
  doc_id?: string;          // 文档ID
  rag_processed_at?: string; // RAG处理时间
  rag_error_message?: string; // RAG错误信息
}

export interface FileUploadResponse {
  file_path: string;
  task_id: string;
  success: boolean;
  message: string;
  exists?: boolean;  // 文件是否已存在
  filename?: string; // 文件名
  file_id?: string;  // 文件ID
  size?: number;     // 文件大小
  content_type?: string; // 文件类型
  upload_time?: string;  // 上传时间
}

export interface FileProcessingStatus {
  status: string;
  progress: number;
  message?: string;
  task_id: string;
  result?: unknown;
}

export const fileApi = {
  // 上传文件（带进度回调）
  uploadFiles: async (
    projectId: string, 
    files: File[], 
    onProgress?: (progress: { 
      fileIndex: number, 
      fileName: string, 
      percentage: number, 
      loaded: number, 
      total: number,
      speed: number,
      remainingTime: number 
    }) => void
  ): Promise<{success: boolean, files: FileUploadResponse[]}> => {
    try {
      console.log(`[File API] 准备上传${files.length}个文件到项目${projectId}`);
      
      // 处理单文件和多文件上传
      if (files.length === 1) {
        // 单文件上传
        const formData = new FormData();
        formData.append('file', files[0]); // 使用固定的'file'字段名
        formData.append('process', 'true');
        
        console.log(`[File API] 单文件上传, 大小: ${files[0].size}字节`);
        
        // 使用XMLHttpRequest进行上传，支持进度跟踪
        const response = await new Promise<Response>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          const startTime = Date.now();
          
          // 上传进度事件
          xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable && onProgress) {
              const now = Date.now();
              const elapsed = (now - startTime) / 1000; // 秒
              const speed = elapsed > 0 ? event.loaded / elapsed : 0; // 字节/秒
              const remainingBytes = event.total - event.loaded;
              const remainingTime = speed > 0 ? remainingBytes / speed : 0; // 秒
              
              onProgress({
                fileIndex: 0,
                fileName: `文件1`,
                percentage: Math.round((event.loaded / event.total) * 100),
                loaded: event.loaded,
                total: event.total,
                speed: speed,
                remainingTime: remainingTime
              });
            }
          });
          
          xhr.addEventListener('load', () => {
            resolve(new Response(xhr.response, { status: xhr.status, statusText: xhr.statusText }));
          });
          
          xhr.addEventListener('error', () => {
            reject(new Error('上传请求失败'));
          });
          
          xhr.open('POST', `${gatewayURL}/api/file/upload/${projectId}`);
          xhr.setRequestHeader('Authorization', `Bearer ${localStorage.getItem('lumidoc_token')}`);
          xhr.send(formData);
        });
        
        if (!response.ok) {
          const errorText = await response.text();
          console.error(`[File API] 上传响应错误(${response.status}): ${errorText}`);
          throw new Error(`上传失败: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('[File API] 单文件上传响应:', data);
        
        // 封装成标准的多文件响应格式
        return {
          success: Boolean(data.success),
          files: [data]
        };
      } else {
        // 多文件上传 - 逐个上传文件并收集结果
        console.log(`[File API] 开始逐个上传${files.length}个文件`);
        
        const results = [];
        for (let index = 0; index < files.length; index++) {
          const file = files[index];
          try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('process', 'true');
            
            console.log(`[File API] 上传文件${index + 1}, 大小: ${file.size}字节`);
            
            // 使用XMLHttpRequest进行上传，支持进度跟踪
            const response = await new Promise<Response>((resolve, reject) => {
              const xhr = new XMLHttpRequest();
              const startTime = Date.now();
              
              // 上传进度事件
              xhr.upload.addEventListener('progress', (event) => {
                if (event.lengthComputable && onProgress) {
                  const now = Date.now();
                  const elapsed = (now - startTime) / 1000; // 秒
                  const speed = elapsed > 0 ? event.loaded / elapsed : 0; // 字节/秒
                  const remainingBytes = event.total - event.loaded;
                  const remainingTime = speed > 0 ? remainingBytes / speed : 0; // 秒
                  
                  onProgress({
                    fileIndex: index,
                    fileName: `文件${index + 1}`,
                    percentage: Math.round((event.loaded / event.total) * 100),
                    loaded: event.loaded,
                    total: event.total,
                    speed: speed,
                    remainingTime: remainingTime
                  });
                }
              });
              
              xhr.addEventListener('load', () => {
                resolve(new Response(xhr.response, { status: xhr.status, statusText: xhr.statusText }));
              });
              
              xhr.addEventListener('error', () => {
                reject(new Error('上传请求失败'));
              });
              
              xhr.open('POST', `${gatewayURL}/api/file/upload/${projectId}`);
              xhr.setRequestHeader('Authorization', `Bearer ${localStorage.getItem('lumidoc_token')}`);
              xhr.send(formData);
            });
            
            if (!response.ok) {
              const errorText = await response.text();
              console.error(`[File API] 文件${index + 1}上传响应错误(${response.status}): ${errorText}`);
              // 添加失败记录但继续上传其他文件
              results.push({
                success: false,
                message: `上传失败: ${response.status} ${response.statusText}`,
                filename: `文件${index + 1}`
              });
              continue;
            }
            
            const data = await response.json();
            console.log(`[File API] 文件${index + 1}上传响应:`, data);
            results.push(data);
          } catch (fileError) {
            console.error(`[File API] 文件${index + 1}上传错误:`, fileError);
            results.push({
              success: false,
              message: fileError instanceof Error ? fileError.message : '上传过程出错',
              filename: `文件${index + 1}`
            });
          }
        }
        
        // 计算总体成功状态
        const hasSuccess = results.some(r => r.success);
        
        return {
          success: hasSuccess,
          files: results
        };
      }
    } catch (error) {
      console.error('[File API] 文件上传错误:', error);
      throw error;
    }
  },
  
  // 获取文件列表
  listFiles: async (projectId: string): Promise<FileInfo[]> => {
    try {
      console.log(`[File API] 请求获取项目${projectId}的文件列表`);
      // 尝试使用axios
      try {
        const response = await apiClient.get(`/api/file/list/${projectId}`);
        
        // 检查响应数据结构
        if (!Array.isArray(response.data)) {
          console.error('[File API] 文件列表响应格式错误:', response.data);
          throw new Error('响应数据格式不正确');
        }
        
        // 输出响应数据统计，避免暴露文件名
        console.log(`[File API] 收到${response.data.length}个文件的响应数据`);
        
        // 将响应数据转换为标准的FileInfo对象
        const fileInfoList = response.data.map(convertToFileInfo);
        
        // 记录获取到的文件数量
        console.log(`[File API] 成功获取${fileInfoList.length}个文件`);
        
        // 记录转换完成
        console.log(`[File API] 文件数据转换完成`);
        
        // 返回数据
        return fileInfoList;
      } catch (axiosError) {
        console.error('[File API] Axios获取失败，尝试使用fetch API:', axiosError);
        
        // 使用fetch API作为备选方案
        const token = localStorage.getItem('lumidoc_token');
        const headers: Record<string, string> = {
          'Accept': 'application/json',
          'Cache-Control': 'no-cache, no-store'
        };
        
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        
        const response = await fetch(`${gatewayURL}/api/file/list/${projectId}`, {
          method: 'GET',
          headers
        });
        
        if (!response.ok) {
          throw new Error(`Fetch请求失败: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // 将响应数据转换为标准的FileInfo对象
        const fileInfoList = Array.isArray(data) ? data.map(convertToFileInfo) : [];
        
        console.log(`[File API] Fetch成功获取${fileInfoList.length}个文件`);
        return fileInfoList;
      }
    } catch (error) {
      console.error('[File API] 获取文件列表失败:', error);
      // 重新抛出错误，保持原有行为
      throw error;
    }
  },
  
  // 获取文件处理状态
  getFileProcessingStatus: async (_projectId: string, taskId: string): Promise<FileProcessingStatus> => {
    const response = await apiClient.get<FileProcessingStatus>(`/fileproc/status/${taskId}`);
    return response.data;
  },
  
  // 处理已上传的文件
  processFile: async (_projectId: string, filePath: string): Promise<FileProcessResponse> => {
    const response = await apiClient.post<FileProcessResponse>(`/api/file/process/${filePath}`, null, {
      params: { project_id: _projectId }
    });
    return response.data;
  },
  
  // 删除文件
  deleteFile: async (projectId: string, filePath: string): Promise<ApiResponse> => {
    try {
      console.log(`[File API] 删除文件: ${filePath}, 项目ID: ${projectId}`);
      
      // 确保路径正确编码 - 使用encodeURIComponent处理整个路径
      const encodedPath = encodeURIComponent(filePath);
      console.log(`[File API] 编码后的路径: ${encodedPath}`);
      
      // 构建完整的请求URL
      const requestUrl = `${gatewayURL}/api/file/${projectId}/${encodedPath}`;
      console.log(`[File API] 删除请求URL: ${requestUrl}`);
      
      // 获取身份验证令牌
      const token = localStorage.getItem('lumidoc_token');
      const headers = {
        'Authorization': token ? `Bearer ${token}` : '',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      };
      
      // 使用fetch API直接发送请求，避免axios的URL编码问题
      const response = await fetch(requestUrl, {
        method: 'DELETE',
        headers
      });
      
      console.log(`[File API] 删除请求状态: ${response.status} ${response.statusText}`);
      
      // 尝试解析响应 - 即使不是200也尝试解析
      let data;
      try {
        data = await response.json();
        console.log('[File API] 删除响应数据:', data);
      } catch (e) {
        // 如果无法解析JSON，创建一个基于状态码的响应
        console.error('[File API] 解析删除响应失败:', e);
        
        // 如果是404错误，表示文件不存在，视为删除成功
        if (response.status === 404) {
          return {
            success: true,
            message: "文件不存在或已被删除"
          };
        }
        
        // 其他HTTP错误
        if (!response.ok) {
          return {
            success: false,
            message: `服务器错误: ${response.status} ${response.statusText}`
          };
        }
        
        // 无法解析但请求成功
        return {
          success: true,
          message: "操作可能已完成，但无法解析响应"
        };
      }
      
      // 处理服务器返回的数据
      if (data) {
        if (data.success === false) {
          console.log("[File API] 服务器报告删除失败", data);
        } else {
          console.log("[File API] 删除操作完成", data);
        }
        return data;
      }
      
      // 如果没有数据但请求成功，返回基本成功信息
      if (response.ok) {
        return {
          success: true,
          message: "操作已完成"
        };
      }
      
      // 默认返回失败
      return {
        success: false,
        message: `删除请求失败: ${response.statusText}`
      };
    } catch (error: unknown) {
      console.error('[File API] 删除文件失败:', error);
      
      // 返回错误信息
      return {
        success: false,
        message: `删除文件出错: ${getErrorMessage(error)}`
      };
    }
  },
  
  // 批量删除文件
  batchDeleteFiles: async (projectId: string, fileHashes: string[]): Promise<ApiResponse<BatchDeleteResult>> => {
    try {
      console.log(`[File API] 批量删除文件，项目ID: ${projectId}，文件数量: ${fileHashes.length}`);
      
      // 修复API请求路径，使用正确的端点
      const requestUrl = `${gatewayURL}/api/file/batch-delete`;
      
      // 获取身份验证令牌
      const token = localStorage.getItem('lumidoc_token');
      const headers = {
        'Authorization': token ? `Bearer ${token}` : '',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      };
      
      // 发送批量删除请求
      const response = await fetch(requestUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          project_id: projectId,
          file_hashes: fileHashes
        })
      });
      
      console.log(`[File API] 批量删除请求状态: ${response.status} ${response.statusText}`);
      
      // 解析响应
      const data = await response.json();
      console.log('[File API] 批量删除响应数据:', data);
      
      return data;
    } catch (error: unknown) {
      console.error('[File API] 批量删除文件失败:', error);
      
      return {
        success: false,
        message: `批量删除文件出错: ${getErrorMessage(error)}`
      };
    }
  }
};
