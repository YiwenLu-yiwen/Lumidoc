import { apiClient } from './client';
import { ApiResponse as BaseApiResponse } from '../types/api';
import { isAxiosError } from 'axios';

export interface RagProgress {
  status: string;
  progress: number;
  error?: string;
}

export interface RagQueryResponse {
  success: boolean;
  result: string;
}

export interface RagFilesResponse {
  success: boolean;
  files: RagFile[];
  error?: string;  // 添加可选的错误消息字段
  authError?: boolean;  // 添加可选的认证错误标识字段
}

export interface RagFileInfo {
  filename?: string;
  name?: string;
  originalName?: string;
  displayName?: string;
}

export type RagFile = string | RagFileInfo;

// 添加文件状态类型定义
export type RagFileStatus = 'pending' | 'processing' | 'processed' | 'failed';

// 添加文件状态响应接口
export interface RagFileStatusResponse {
  success: boolean;
  statuses: Record<string, {
    status: RagFileStatus;
    file_path?: string;
    file_name?: string;
    created_at?: string;
    updated_at?: string;
    error?: string;
    chunks_count?: number;
    doc_id?: string;
  }>;
  error?: string;
}

export interface RagDeleteResponse {
  success: boolean;
  message: string;
  deleted_relations?: number;
  cleaned_entities?: number;
}

// 扩展ApiResponse接口，添加RAG构建结果相关字段
export interface RagBuildResponse extends BaseApiResponse {
  success: boolean;
  message: string;
  file_count?: number;
  processed_count?: number;
  processed_files?: string[];
  failed_files?: Array<{
    file_hash: string;
    error: string;
  }>;
  project_id?: string;
}

// 添加请求去重机制
const pendingRequests = new Map<string, Promise<RagBuildResponse>>();

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
};

const getApiErrorDetail = (error: unknown): string | undefined => {
  if (isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail;
  }
  return undefined;
};

export const ragApi = {
  // 构建RAG索引
  buildRag: async (projectId: string, selectedFiles: string[]): Promise<RagBuildResponse> => {
    // 创建请求键，用于去重
    const requestKey = `buildRag:${projectId}:${[...selectedFiles].sort().join(',')}`;

    // 检查是否有相同的请求正在进行
    if (pendingRequests.has(requestKey)) {
      console.log(`[RagApi] 检测到重复请求，等待现有请求完成: ${requestKey}`);
      return await pendingRequests.get(requestKey)!;
    }

    // 创建新的请求Promise
    const requestPromise = (async (): Promise<RagBuildResponse> => {
      try {
        console.log(`[RagApi] 构建RAG索引, 项目ID: ${projectId}, 选择的文件: ${selectedFiles.join(', ')}`);

        // 确保文件列表非空
      if (!selectedFiles || selectedFiles.length === 0) {
        console.error('[RagApi] 文件列表为空');
        return {
          success: false,
          message: '请选择需要导入的文件',
          file_count: 0,
          processed_count: 0,
          processed_files: [],
          failed_files: [],
          project_id: projectId
        };
      }

      // 调用LightRAG服务的官方build端点
      // 支持多种可能的API路径，以增加兼容性
      const apiPaths = [
        `/api/lightrag/lightrag/build/${projectId}`,  // 添加对双重前缀的支持
        `/api/lightrag/rag/build/${projectId}`,
        `/lightrag/rag/build/${projectId}`,
      ];

      let lastError: unknown = null;
      for (const apiPath of apiPaths) {
        try {
          console.log(`[RagApi] 尝试API路径: ${apiPath}`);
          const response = await apiClient.post<RagBuildResponse>(
            apiPath,
            { selected_files: selectedFiles }
          );

          console.log(`[RagApi] RAG构建响应:`, response.data);
          return response.data;
        } catch (e: unknown) {
          console.warn(`[RagApi] API路径 ${apiPath} 请求失败:`, e);
          lastError = e;
        }
      }

      // 所有API路径都失败
      throw lastError || new Error("所有API路径都请求失败");
    } catch (error: unknown) {
      console.error('[RagApi] RAG构建出错:', error);

        return {
          success: false,
          message: getErrorMessage(error, '导入知识库失败'),
          file_count: selectedFiles?.length || 0,
          processed_count: 0,
          processed_files: [],
          failed_files: selectedFiles?.map(file => ({
            file_hash: file,
            error: '服务调用失败'
          })) || [],
          project_id: projectId
        };
      }
    })();

    // 存储请求Promise
    pendingRequests.set(requestKey, requestPromise);

    try {
      const result = await requestPromise;
      return result;
    } finally {
      // 清理完成的请求
      pendingRequests.delete(requestKey);
    }
  },

  // 获取RAG构建进度
  getRagProgress: async (projectId: string): Promise<RagProgress> => {
    const response = await apiClient.get<RagProgress>(`/rag/progress/${projectId}`);
    return response.data;
  },

  // 获取RAG已索引的文件列表
  getRagFiles: async (projectId: string): Promise<RagFilesResponse> => {
    try {
      console.log(`[RagApi] 获取RAG文件列表, 项目ID: ${projectId}`);

      // 检查用户登录状态
      const token = localStorage.getItem('lumidoc_token');
      if (!token) {
        console.warn('[RagApi] 用户未登录，无法获取RAG文件列表');
        return {
          success: false,
          files: [],
          error: '用户未登录，请先登录后再使用知识库功能'
        };
      }

      // 支持多个可能的API路径
      const apiPaths = [
        `/api/lightrag/lightrag/files/${projectId}`, // 添加对双重前缀的支持
        `/api/lightrag/rag/files/${projectId}`,
        `/lightrag/rag/files/${projectId}`,
        `/rag/files/${projectId}`
      ];

      let lastError: unknown = null;
      for (const apiPath of apiPaths) {
        try {
          console.log(`[RagApi] 尝试API路径: ${apiPath}`);
          const response = await apiClient.get<RagFilesResponse | RagFile[]>(apiPath);

          // 检查响应是否有效
          let files: RagFile[] = [];
          let isValid = false;

          if (response.data) {
            // 情况1：lightrag服务格式 {success: boolean, files: Array}
            if (typeof response.data === 'object' && !Array.isArray(response.data) && response.data.files) {
              files = response.data.files;
              isValid = response.data.success !== false;
            }
            // 情况2：直接返回数组格式
            else if (Array.isArray(response.data)) {
              files = response.data;
              isValid = true;
            }
            // 情况3：其他对象格式的兼容处理
            else if (typeof response.data === 'object' && response.data.success !== false) {
              files = [];
              isValid = true;
            }
          }

          if (isValid) {
            console.log(`[RagApi] 成功获取到${files.length}个文件`);
            return { success: true, files: files };
          }

          console.warn(`[RagApi] API路径 ${apiPath} 响应无效:`, response.data);
          lastError = { message: 'RAG服务响应格式无效' };
        } catch (e: unknown) {
          console.warn(`[RagApi] API路径 ${apiPath} 请求失败:`, e);
          lastError = e;
        }
      }

      // 所有API路径都失败
      throw lastError || new Error('所有API路径都请求失败');

    } catch (e: unknown) {
      console.error('[RagApi] 获取RAG文件列表失败:', e);

      // 检查是否是认证错误
      if (isAxiosError(e) && e.response?.status === 401) {
        return {
          success: false,
          files: [],
          error: '认证失败，请重新登录后再试'
        };
      }

      return {
        success: false,
        files: [],
        error: getErrorMessage(e, '获取知识库文件列表失败')
      };
    }
  },

  // 从知识库删除文件
  deleteRagFile: async (projectId: string, fileName: string): Promise<RagDeleteResponse> => {
    try {
      console.log(`[RagApi] 从知识库删除文件, 项目ID: ${projectId}, 文件名: ${fileName}`);

      // 尝试多种API路径，因为后端可能有不同的端点
      const apiPaths = [
        `/api/lightrag/lightrag/file/${projectId}/${encodeURIComponent(fileName)}`,  // LightRAG删除端点
        `/api/lightrag/rag/file/${projectId}/${encodeURIComponent(fileName)}`,        // 备用端点
        `/lightrag/rag/file/${projectId}/${encodeURIComponent(fileName)}`,           // 直接端点
        `/rag/file/${projectId}/${encodeURIComponent(fileName)}`,                    // 原端点
        `/rag/delete/${projectId}/${encodeURIComponent(fileName)}`,                  // 备用删除端点
      ];

      let lastError: unknown = null;

      for (const path of apiPaths) {
        try {
          console.log(`[RagApi] 尝试删除API路径: ${path}`);
          const response = await apiClient.delete<RagDeleteResponse>(path);

          if (response.data && response.data.success) {
            console.log(`[RagApi] 文件删除成功:`, response.data);
            return response.data;
          }

          console.warn(`[RagApi] API路径 ${path} 删除失败:`, response.data);
          lastError = response.data;
        } catch (e: unknown) {
          console.warn(`[RagApi] API路径 ${path} 请求失败:`, e);
          lastError = e;
        }
      }

      // 如果所有路径都失败，返回错误
      return {
        success: false,
        message: getApiErrorDetail(lastError) || getErrorMessage(lastError, '删除文件失败，所有API路径都无效')
      };

    } catch (error: unknown) {
      console.error('[RagApi] 删除RAG文件出错:', error);
      return {
        success: false,
        message: getErrorMessage(error, '删除文件失败')
      };
    }
  },

  // 查询RAG
  queryRag: async (projectId: string, query: string, mode?: string): Promise<RagQueryResponse> => {
    try {
      console.log(`[RagApi] 查询RAG, 项目ID: ${projectId}, 查询内容: ${query}`);

      // 支持多个可能的API路径
      const apiPaths = [
        `/api/lightrag/rag/search`,          // 企业级LightRAG搜索端点
        `/lightrag/rag/search`,              // 直接LightRAG搜索端点
        `/rag/search`,                       // 简化搜索端点
        `/rag/query`                         // 兼容旧端点
      ];

      let lastError: unknown = null;
      for (const apiPath of apiPaths) {
        try {
          console.log(`[RagApi] 尝试RAG搜索API路径: ${apiPath}`);
          const response = await apiClient.post<RagQueryResponse>(apiPath, {
            query,
            project_id: projectId,
            mode: mode || 'hybrid'
          });

          if (response.data && response.data.success) {
            console.log(`[RagApi] RAG搜索成功:`, response.data);
            return response.data;
          }

          console.warn(`[RagApi] API路径 ${apiPath} 搜索响应无效:`, response.data);
          lastError = { message: 'RAG搜索服务响应格式无效' };
        } catch (e: unknown) {
          console.warn(`[RagApi] API路径 ${apiPath} 搜索请求失败:`, e);
          lastError = e;
        }
      }

      // 所有API路径都失败
      throw lastError || new Error('所有RAG搜索API路径都请求失败');

    } catch (error: unknown) {
      console.error('[RagApi] RAG查询失败:', error);
      return {
        success: false,
        result: `搜索失败：${getErrorMessage(error, '知识库服务不可用')}`
      };
    }
  },

  // 获取文件处理状态
  getRagFileStatus: async (projectId: string): Promise<RagFileStatusResponse> => {
    try {
      console.log(`[RagApi] 获取RAG文件状态, 项目ID: ${projectId}`);

      // 支持多个可能的API路径
      const apiPaths = [
        `/api/lightrag/lightrag/status/${projectId}`, // 添加对双重前缀的支持
        `/api/lightrag/rag/status/${projectId}`,
        `/lightrag/rag/status/${projectId}`,
        `/rag/status/${projectId}`
      ];

      let lastError: unknown = null;
      for (const apiPath of apiPaths) {
        try {
          console.log(`[RagApi] 尝试获取文件状态API路径: ${apiPath}`);
          const response = await apiClient.get<RagFileStatusResponse>(apiPath);

          if (response.data && response.data.success) {
            console.log(`[RagApi] 成功获取文件状态:`, response.data);
            return response.data;
          }

          console.warn(`[RagApi] API路径 ${apiPath} 响应无效:`, response.data);
          lastError = { message: 'RAG服务状态响应格式无效' };
        } catch (e: unknown) {
          console.warn(`[RagApi] API路径 ${apiPath} 请求失败:`, e);
          lastError = e;
        }
      }

      // 所有API路径都失败
      throw lastError || new Error('所有状态API路径都请求失败');

    } catch (e: unknown) {
      console.error('[RagApi] 获取RAG文件状态失败:', e);

      return {
        success: false,
        statuses: {},
        error: getErrorMessage(e, '获取知识库文件状态失败')
      };
    }
  }
};
