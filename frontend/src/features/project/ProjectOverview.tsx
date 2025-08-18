import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectApi } from '@/api/project';
import { Calendar, Clock } from 'lucide-react';
import { customToast } from '@/App';
import { useAuth, ProjectAccessLevel } from '@/context/AuthContext';
import { detectAutoTheme, detectBrowserLanguage, getTranslation } from '@/utils/language';

export default function ProjectOverview() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { updateUserProjectAccess } = useAuth();
  const navigate = useNavigate();
  const [loadAttempts, setLoadAttempts] = useState(0);
  
  // 获取当前主题和语言
  const isDarkMode = detectAutoTheme() === 'dark';
  const currentLanguage = detectBrowserLanguage();
  
  // 翻译函数
  const t = (key: keyof typeof import('@/utils/language').translations['zh-CN']) => {
    return getTranslation(currentLanguage, key);
  };

  useEffect(() => {
    const loadProject = async () => {
      if (!projectId) {
        setError(t('projectIdNotExist'));
        setLoading(false);
        return;
      }
      
      try {
        setLoading(true);
        setError(null);
        
        // 记录加载开始
        console.log(`[ProjectOverview] 开始加载项目(${projectId})详情，尝试次数: ${loadAttempts + 1}...`);
        
        // 加载项目前，确保用户对此项目有权限记录
        try {
          const storedPermissions = localStorage.getItem('stp_project_permissions');
          const permissions = storedPermissions ? JSON.parse(storedPermissions) : {};
          
          // 如果在本地缓存中没有此项目的权限记录，添加基本查看权限
          if (!permissions[projectId]) {
            console.log(`[ProjectOverview] 项目(${projectId})在本地权限中不存在，添加查看权限`);
            updateUserProjectAccess(projectId, ProjectAccessLevel.VIEWER);
            
            // 更新本地存储
            permissions[projectId] = ProjectAccessLevel.VIEWER;
            localStorage.setItem('stp_project_permissions', JSON.stringify(permissions));
          } else {
            console.log(`[ProjectOverview] 项目(${projectId})已有权限: ${permissions[projectId]}`);
          }
        } catch (e) {
          console.error('[ProjectOverview] 检查项目权限失败:', e);
        }
        
        // 加载项目详情
        try {
          const projectData = await projectApi.getProject(projectId);
          
          if (!projectData || !projectData.id) {
            throw new Error('项目数据无效');
          }
          
          console.log(`[ProjectOverview] 成功加载项目(${projectId})详情:`, projectData);
          setProject(projectData);
          setLoadAttempts(0); // 重置尝试次数
        } catch (apiError) {
          console.error(`[ProjectOverview] 获取项目(${projectId})失败:`, apiError);
          
          // 尝试次数增加
          const newAttempts = loadAttempts + 1;
          setLoadAttempts(newAttempts);
          
          // 如果重试次数过多，返回项目列表页面
          if (newAttempts >= 3) {
            console.error(`[ProjectOverview] 项目(${projectId})加载失败次数过多，返回项目列表`);
            setError(t('cannotLoadProject'));
            customToast.error(t('projectLoadFailed'));
            
            // 延迟返回，避免连续导航
            setTimeout(() => {
              navigate('/', { replace: true });
            }, 1500);
          } else {
            setError(t('cannotLoadProject'));
            customToast.error(t('loadProjectFailed'));
          }
        }
      } catch (error) {
        console.error('[ProjectOverview] 加载项目详情未知错误:', error);
        setError(t('unknownError'));
        customToast.error(t('unknownErrorRefresh'));
      } finally {
        setLoading(false);
      }
    };

    loadProject();
  }, [projectId, updateUserProjectAccess, loadAttempts, navigate]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mb-4"></div>
          <p className={`${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>{t('loadingProjectInfo')}</p>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className={`${isDarkMode ? 'bg-[#343541]' : 'bg-white'} rounded-lg p-6 text-center border ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
        <p className={`${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>{error || t('cannotLoadProject')}</p>
        <div className="flex justify-center mt-4 space-x-4">
          <button 
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white text-sm"
            onClick={() => window.location.reload()}
          >
            {t('retry')}
          </button>
          <button 
            className={`px-4 py-2 ${isDarkMode ? 'bg-gray-600 hover:bg-gray-700' : 'bg-gray-500 hover:bg-gray-600'} rounded text-white text-sm`}
            onClick={() => navigate('/', { replace: true })}
          >
            {t('returnToProjectList')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className={`${isDarkMode ? 'bg-[#343541]' : 'bg-white'} rounded-lg p-6 border ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
        <h1 className={`text-2xl font-bold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{project.name}</h1>
        <p className={`${isDarkMode ? 'text-gray-300' : 'text-gray-600'} mb-4`}>{project.description || t('noProjectDescription')}</p>
        
        <div className={`flex items-center space-x-4 text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
          <div className="flex items-center">
            <Calendar className="h-4 w-4 mr-1" />
            <span>{t('createdAt')}: {new Date(project.created_at).toLocaleString()}</span>
          </div>
          {project.updated_at && (
            <div className="flex items-center">
              <Clock className="h-4 w-4 mr-1" />
              <span>{t('updatedAt')}: {new Date(project.updated_at).toLocaleString()}</span>
            </div>
          )}
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className={`${isDarkMode ? 'bg-[#343541]' : 'bg-white'} rounded-lg p-6 border ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <h2 className={`text-xl font-semibold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{t('projectStats')}</h2>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className={`${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{t('projectId')}</span>
              <span className={`${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{project.id}</span>
            </div>
            <div className="flex justify-between">
              <span className={`${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{t('status')}</span>
              <span className={`${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{project.status || t('active')}</span>
            </div>
          </div>
        </div>
        
        <div className={`${isDarkMode ? 'bg-[#343541]' : 'bg-white'} rounded-lg p-6 border ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <h2 className={`text-xl font-semibold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{t('quickActions')}</h2>
          <div className="flex flex-wrap gap-2">
            <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white text-sm">
              {t('addFile')}
            </button>
            <button className={`px-4 py-2 ${isDarkMode ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-600 hover:bg-gray-700'} rounded text-white text-sm`}>
              {t('createAnalysis')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
} 