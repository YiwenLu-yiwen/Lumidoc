import { NavLink, useLocation } from 'react-router-dom';
import { FileText, Home, MessageSquare, Network, BrainCircuit } from 'lucide-react';

interface ProjectSidebarProps {
  projectId: string;
}

export default function ProjectSidebar({ projectId }: ProjectSidebarProps) {
  const location = useLocation();
  const currentPath = location.pathname;
  
  const navItems = [
    {
      name: '概览',
      path: `/project/${projectId}`,
      icon: Home,
      exact: true
    },
    {
      name: '文件',
      path: `/project/${projectId}/files`,
      icon: FileText
    },
    {
      name: '图谱',
      path: `/project/${projectId}/graph`,
      icon: Network
    },
    {
      name: '聊天',
      path: `/project/${projectId}/chat`,
      icon: MessageSquare
    },
    {
      name: '问题生成',
      path: `/project/${projectId}/questions`,
      icon: BrainCircuit
    }
  ];

  // 检查当前路由是否匹配菜单项
  const isActive = (itemPath: string, exact: boolean = false) => {
    if (exact) {
      return currentPath === itemPath;
    }
    // 确保"/project/123"不会匹配"/project/123/files"等子路由
    const exactOverviewPath = `/project/${projectId}`;
    if (itemPath === exactOverviewPath) {
      return currentPath === exactOverviewPath;
    }
    return currentPath.startsWith(itemPath);
  };

  return (
    <div className="w-56 bg-gray-800 border-r border-gray-700 h-full flex flex-col">
      <div className="p-4 border-b border-gray-700">
        <h2 className="text-lg font-semibold text-white truncate">项目导航</h2>
      </div>
      <nav className="flex-1 overflow-y-auto">
        <ul className="py-2">
          {navItems.map((item) => {
            const active = isActive(item.path, item.exact);
            
            return (
              <li key={item.path} className="px-2 py-1">
                <NavLink 
                  to={item.path} 
                  className={`
                    flex items-center px-3 py-2 rounded-md text-sm transition-colors
                    ${active 
                      ? 'bg-blue-600 text-white hover:bg-blue-700 hover:text-white' 
                      : 'text-gray-300 hover:text-white hover:bg-gray-700'}
                  `}
                >
                  <item.icon className={`mr-3 h-4 w-4 ${active ? 'text-white' : 'text-gray-400'}`} />
                  <span>{item.name}</span>
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="p-4 border-t border-gray-700">
        <div className="text-xs text-gray-500">项目ID: {projectId}</div>
      </div>
    </div>
  );
} 