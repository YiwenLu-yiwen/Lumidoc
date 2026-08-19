import { useParams, Outlet, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import ProjectSidebar from './ProjectSidebar';
import Header from '@/components/layout/Header';
import { projectApi } from '@/api/project';
import { toast } from 'sonner';

export default function ProjectLayout() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  // 检查项目是否存在
  useEffect(() => {
    if (!projectId) return;

    const checkProject = async () => {
      try {
        await projectApi.getProject(projectId);
      } catch (err: unknown) {
        console.error('项目不存在或已被删除:', err);
        toast.error('项目不存在或已被删除，即将返回首页');
        // 跳转到首页
        setTimeout(() => navigate('/'), 1500);
      }
    };

    checkProject();
  }, [projectId, navigate]);

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      <Header />
      <div className="flex-1 flex">
        {projectId && <ProjectSidebar projectId={projectId} />}
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
