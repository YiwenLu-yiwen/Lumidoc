import { apiClient } from './client'
import { ProjectCreate, ProjectUpdate, ProjectResponse, ApiResponse } from '../types/api'
import { ProjectAccessLevel } from '../context/AuthContext'

export interface Project {
  id: string
  name: string
  description?: string
  created_at: string
  updated_at: string
  status: string
}

// 项目权限响应接口
export interface ProjectPermissionResponse {
  project_id: string;
  access_level: ProjectAccessLevel;
}

export const projectApi = {
  createProject: async (project: ProjectCreate): Promise<ProjectResponse> => {
    const response = await apiClient.post<ProjectResponse>(`/api/projects/`, project)
    return response.data
  },

  listProjects: async (): Promise<ProjectResponse[]> => {
    const response = await apiClient.get<ProjectResponse[]>(`/api/projects/`)
    return response.data
  },

  getProject: async (projectId: string): Promise<ProjectResponse> => {
    try {
      const response = await apiClient.get<ProjectResponse>(`/api/projects/${projectId}/`);
      
      if (!response.data || !response.data.id) {
        console.error('[项目API] 获取项目响应格式不正确或项目不存在');
        throw new Error('项目不存在或无法访问');
      }
      
      // 项目存在，确保用户有此项目的权限记录
      const storedPermissions = localStorage.getItem('stp_project_permissions');
      try {
        const permissions = storedPermissions ? JSON.parse(storedPermissions) : {};
        
        // 如果项目存在但没有权限记录，添加查看权限
        if (!permissions[projectId]) {
          console.log(`[项目API] 为项目 ${projectId} 自动添加查看权限`);
          permissions[projectId] = ProjectAccessLevel.VIEWER;
          localStorage.setItem('stp_project_permissions', JSON.stringify(permissions));
        }
      } catch (e) {
        console.error('[项目API] 更新项目权限缓存失败:', e);
      }
      
      return response.data;
    } catch (error) {
      console.error('[项目API] 获取项目失败:', error);
      throw error;
    }
  },

  updateProject: async (projectId: string, update: ProjectUpdate): Promise<ProjectResponse> => {
    const response = await apiClient.put<ProjectResponse>(`/api/projects/${projectId}/`, update)
    return response.data
  },

  deleteProject: async (projectId: string): Promise<ApiResponse> => {
    const response = await apiClient.delete<ApiResponse>(`/api/projects/${projectId}/`)
    return response.data
  },
  
  // 获取当前用户的项目权限
  getUserProjectPermissions: async (): Promise<Record<string, ProjectAccessLevel>> => {
    try {
      console.log('[项目API] 正在获取用户项目权限...');
      
      // 检查是否有权限请求进行中，避免重复请求
      if ((window as any).__fetchingPermissions) {
        console.log('[项目API] 已有权限请求正在进行，返回缓存数据');
        return getStoredPermissions();
      }
      
      // 检查是否在短时间内已请求过权限
      const lastPermissionFetch = localStorage.getItem('stp_last_permission_fetch');
      if (lastPermissionFetch) {
        const lastFetchTime = parseInt(lastPermissionFetch, 10);
        const now = Date.now();
        // 如果10秒内已请求过，直接使用缓存
        if (now - lastFetchTime < 10000) {
          console.log('[项目API] 10秒内已请求过权限，直接使用缓存');
          return getStoredPermissions();
        }
      }
      
      // 设置请求标记
      (window as any).__fetchingPermissions = true;
      
      // 记录请求时间
      localStorage.setItem('stp_last_permission_fetch', Date.now().toString());
      
      // 优先返回缓存，异步更新
      const storedPermissions = getStoredPermissions();
      if (Object.keys(storedPermissions).length > 0) {
        console.log('[项目API] 返回缓存权限，后台更新');
        
        // 后台异步更新
        fetchPermissionsFromAPI().catch(e => 
          console.error('[项目API] 后台更新权限失败:', e)
        ).finally(() => {
          // 请求完成，清除标记
          (window as any).__fetchingPermissions = false;
        });
        
        return storedPermissions;
      }
      
      // 如果没有缓存，等待API返回
      try {
        const permissions = await fetchPermissionsFromAPI();
        return permissions;
      } finally {
        // 清除请求标记
        (window as any).__fetchingPermissions = false;
      }
    } catch (error) {
      console.error('[项目API] 获取用户项目权限失败:', error);
      // 清除请求标记
      (window as any).__fetchingPermissions = false;
      return getStoredPermissions();
    }
    
    // 从API获取权限的函数
    async function fetchPermissionsFromAPI(): Promise<Record<string, ProjectAccessLevel>> {
      try {
        console.log('[项目API] 尝试从API获取项目权限，等待响应...');
        
        // 使用极短的超时时间，避免长时间等待
        const response = await apiClient.get<ProjectPermissionResponse[]>('/api/user_permissions/projects', {
          timeout: 3000 // 进一步减少超时时间到3秒
        });
        
        if (!response.data || !Array.isArray(response.data)) {
          console.error('[项目API] 获取权限响应格式不正确:', response.data);
          return getStoredPermissions();
        }
        
        // 将响应转换为 { project_id: access_level } 格式的对象
        const permissions: Record<string, ProjectAccessLevel> = {};
        response.data.forEach(item => {
          if (item && item.project_id && item.access_level) {
            permissions[item.project_id] = item.access_level as ProjectAccessLevel;
          }
        });
        
        console.log('[项目API] 获取到用户项目权限:', permissions);
        
        // 保存权限到本地存储以便离线恢复
        localStorage.setItem('stp_project_permissions', JSON.stringify(permissions));
        
        return permissions;
      } catch (error) {
        console.error('[项目API] 从API获取权限失败:', error);
        // 错误时直接使用本地存储的权限，不影响用户体验
        return getStoredPermissions();
      }
    }
    
    // 从本地存储获取权限的辅助函数
    function getStoredPermissions(): Record<string, ProjectAccessLevel> {
      const storedPermissions = localStorage.getItem('stp_project_permissions');
      if (storedPermissions) {
        try {
          const permissions = JSON.parse(storedPermissions);
          console.log('[项目API] 从本地存储恢复项目权限:', permissions);
          return permissions;
        } catch (e) {
          console.error('[项目API] 解析本地存储的权限数据失败:', e);
        }
      }
      return {};
    }
  }
} 