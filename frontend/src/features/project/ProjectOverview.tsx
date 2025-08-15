import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectApi } from '@/api/project';
import { Calendar, Clock } from 'lucide-react';
import { customToast } from '@/App';
import { useAuth, ProjectAccessLevel } from '@/context/AuthContext';

export default function ProjectOverview() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { updateUserProjectAccess } = useAuth();
  const navigate = useNavigate();
  const [loadAttempts, setLoadAttempts] = useState(0);

  useEffect(() => {
    const loadProject = async () => {
      if (!projectId) {
        setError('项目ID不存在');
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
            setError('无法加载项目信息，返回项目列表');
            customToast.error('项目加载失败，返回项目列表');
            
            // 延迟返回，避免连续导航
            setTimeout(() => {
              navigate('/', { replace: true });
            }, 1500);
          } else {
            setError('无法加载项目信息');
            customToast.error('加载项目信息失败，请稍后再试');
          }
        }
      } catch (error) {
        console.error('[ProjectOverview] 加载项目详情未知错误:', error);
        setError('未知错误，请刷新页面重试');
        customToast.error('发生未知错误，请刷新页面');
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
          <p className="text-gray-400">加载项目信息...</p>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 text-center">
        <p className="text-gray-400">{error || '无法加载项目信息'}</p>
        <div className="flex justify-center mt-4 space-x-4">
          <button 
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white text-sm"
            onClick={() => window.location.reload()}
          >
            重试
          </button>
          <button 
            className="px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded text-white text-sm"
            onClick={() => navigate('/', { replace: true })}
          >
            返回项目列表
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg p-6">
        <h1 className="text-2xl font-bold mb-2 text-white">{project.name}</h1>
        <p className="text-gray-300 mb-4">{project.description || '无项目描述'}</p>
        
        <div className="flex items-center space-x-4 text-sm text-gray-400">
          <div className="flex items-center">
            <Calendar className="h-4 w-4 mr-1" />
            <span>创建于: {new Date(project.created_at).toLocaleString()}</span>
          </div>
          {project.updated_at && (
            <div className="flex items-center">
              <Clock className="h-4 w-4 mr-1" />
              <span>更新于: {new Date(project.updated_at).toLocaleString()}</span>
            </div>
          )}
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4 text-white">项目统计</h2>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-400">项目ID</span>
              <span className="text-white">{project.id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">状态</span>
              <span className="text-white">{project.status || '活跃'}</span>
            </div>
          </div>
        </div>
        
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4 text-white">快捷操作</h2>
          <div className="flex flex-wrap gap-2">
            <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white text-sm">
              添加文件
            </button>
            <button className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white text-sm">
              创建分析
            </button>
          </div>
        </div>
      </div>
    </div>
  );
} 