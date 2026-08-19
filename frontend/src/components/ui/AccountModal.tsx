import { Plus, Folder, Loader2, AlertCircle, Trash2 } from 'lucide-react';
import React, { useEffect, useState, useRef } from 'react';
import { useAuth, type User } from '@/context/AuthContext';
import { projectApi, type Project } from '@/api/project';
import { useNavigate, useLocation } from 'react-router-dom';
import { useProjects } from '@/context/ProjectContext';
import { ConfirmDialog } from './ConfirmDialog';

interface Props {
  open: boolean;
  onClose: () => void;
}

const tabs = [
  { key: 'profile', label: '个人信息' },
  { key: 'settings', label: '账号设置' },
  { key: 'projects', label: '项目管理' },
  { key: 'security', label: '安全设置' },
];

// 添加默认头像组件
function DefaultAvatar({ username, size = 24 }: { username: string, size?: number }) {
  const getInitials = (name: string) => {
    return name ? name.charAt(0).toUpperCase() : '?';
  };

  const getRandomColor = (name: string) => {
    const colors = [
      '#FF6B6B', // 红色
      '#4ECDC4', // 青色
      '#45B7D1', // 蓝色
      '#96CEB4', // 绿色
      '#FFEEAD', // 黄色
      '#D4A5A5', // 粉色
      '#9B59B6', // 紫色
      '#3498DB', // 深蓝色
    ];
    const index = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return colors[index % colors.length];
  };

  return (
    <div
      className="rounded-full flex items-center justify-center text-white font-medium"
      style={{
        width: size,
        height: size,
        backgroundColor: getRandomColor(username),
        fontSize: `${size * 0.4}px`,
      }}
    >
      {getInitials(username)}
    </div>
  );
}

function ProfileTab({ user }: { user: User | null }) {
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="w-24 h-24 rounded-full bg-gray-800 flex items-center justify-center overflow-hidden">
        <DefaultAvatar username={user?.username || ''} size={96} />
      </div>
      <div className="text-xl font-semibold">{user?.username}</div>
      <div className="text-gray-400 text-sm">ID: {user?.id}</div>
      <div className="text-gray-400 text-sm">邮箱：<span className="text-gray-500">（未绑定）</span></div>
      <button className="mt-4 px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium">修改密码</button>
    </div>
  );
}

function SettingsTab() {
  return <div className="text-gray-300">账号设置内容（可扩展）</div>;
}


function SecurityTab() {
  return <div className="text-gray-300">安全设置内容（可扩展）</div>;
}

export default function AccountModal({ open, onClose }: Props) {
  const { user, logout } = useAuth();
  const { projects, refreshProjects } = useProjects();
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [createError, setCreateError] = useState('');
  const [activeTab, setActiveTab] = useState('profile');
  const navigate = useNavigate();
  const location = useLocation();
  const modalRef = useRef<HTMLDivElement>(null);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteIsCurrent, setDeleteIsCurrent] = useState(false);

  // 当前项目id（从url获取）
  const currentProjectId = location.pathname.match(/project\/([\w-]+)/)?.[1];

  useEffect(() => {
    if (open && user && activeTab === 'projects') {
      setLoading(true);
      refreshProjects().finally(() => setLoading(false));
    }
  }, [open, user, activeTab, refreshProjects]);

  // ESC关闭弹窗
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // 点击弹窗外部关闭
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open, onClose]);

  // 项目管理相关
  const handleSwitchProject = (projectId: string) => {
    onClose();
    navigate(`/project/${projectId}`);
  };
  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      setCreateError('项目名称不能为空');
      return;
    }
    setCreateError('');
    setLoading(true);
    try {
      await projectApi.createProject({ name: newProjectName });
      setNewProjectName('');
      setCreating(false);
      await refreshProjects();
    } catch {
      setCreateError('创建失败');
    } finally {
      setLoading(false);
    }
  };
  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleCreateProject();
    if (e.key === 'Escape') { setCreating(false); setNewProjectName(''); setCreateError(''); }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50">
      <div className="relative bg-[#232325] text-white rounded-lg shadow-lg w-full max-w-2xl p-0">
        {/* 右上角 X */}
        <button
          className="absolute top-3 right-3 text-gray-400 hover:text-white focus:outline-none"
          style={{ fontSize: 20, lineHeight: 1 }}
          onClick={onClose}
          aria-label="关闭"
        >✕</button>
        {/* Tab 切换栏 */}
        <div className="flex border-b border-gray-700">
          {tabs.map(tab => (
            <button
              key={tab.key}
              className={`px-6 py-3 font-medium transition-colors duration-150 ${activeTab === tab.key ? 'border-b-2 border-blue-500 text-white' : 'text-gray-400 hover:text-white'}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {/* Tab 内容 */}
        <div className="p-8 min-h-[320px]">
          {activeTab === 'profile' && <ProfileTab user={user} />}
          {activeTab === 'settings' && <SettingsTab />}
          {activeTab === 'projects' && (
            <div>
              <h3 className="text-lg font-medium mb-2">项目管理</h3>
              <div className="mb-2">
                {!creating ? (
                  <button
                    className="flex items-center w-full px-4 py-2 rounded-lg hover:bg-[#343541] text-[#ececf1] mb-2 transition font-medium group"
                    onClick={() => setCreating(true)}
                  >
                    <Plus className="w-5 h-5 mr-2 text-blue-400 group-hover:text-blue-300" /> 新建项目
                  </button>
                ) : (
                  <div className="flex items-center w-full mb-2 gap-2 animate-fade-in">
                    <input
                      className="flex-1 px-3 py-2 rounded-lg bg-[#343541] border border-[#2a2b32] text-[#ececf1] placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="输入项目名称"
                      value={newProjectName}
                      onChange={e => { setNewProjectName(e.target.value); setCreateError(''); }}
                      maxLength={32}
                      autoFocus
                      onKeyDown={handleInputKeyDown}
                    />
                    <button
                      className="px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium"
                      onClick={handleCreateProject}
                      disabled={loading}
                    >{loading ? <Loader2 className="w-4 h-4 animate-spin" /> : '创建'}</button>
                    <button
                      className="px-2 py-2 text-gray-400 hover:text-white"
                      onClick={() => { setCreating(false); setNewProjectName(''); setCreateError(''); }}
                    >取消</button>
                  </div>
                )}
                {createError && (
                  <div className="flex items-center text-red-400 text-sm mb-2 mt-1">
                    <AlertCircle className="w-4 h-4 mr-1" /> {createError}
                  </div>
                )}
              </div>
              <div className="border-t border-[#2a2b32] my-2" />
              {loading ? (
                <div className="flex items-center justify-center py-6 text-gray-400">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" /> 加载中...
                </div>
              ) : (
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {projects.map(project => (
                    <div key={project.id} className="flex items-center group">
                      <button
                        className={`flex items-center w-full px-4 py-2 rounded-lg border border-transparent mb-1 text-[#ececf1] transition font-medium group text-left truncate ${project.id === currentProjectId ? 'bg-[#40414f] border-blue-500 shadow-inner' : 'hover:bg-[#343541]'}`}
                        onClick={() => handleSwitchProject(project.id)}
                        title={project.name}
                      >
                        <Folder className={`w-5 h-5 mr-2 ${project.id === currentProjectId ? 'text-blue-400' : 'text-gray-400 group-hover:text-blue-300'}`} />
                        <span className="truncate flex-1">{project.name}</span>
                        {project.id === currentProjectId && <span className="ml-2 w-2 h-2 bg-blue-400 rounded-full inline-block" />}
                      </button>
                      <button
                        className="ml-2 p-1 text-red-400 hover:text-red-300 opacity-80 hover:opacity-100 transition"
                        title="删除项目"
                        onClick={async (e) => {
                          e.stopPropagation();
                          const isCurrentProject = project.id === currentProjectId;
                          setProjectToDelete(project);
                          setDeleteIsCurrent(isCurrentProject);
                          setConfirmDeleteOpen(true);
                        }}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                  {projects.length === 0 && <div className="text-gray-400 text-sm">暂无项目</div>}
                </div>
              )}
            </div>
          )}
          {activeTab === 'security' && <SecurityTab />}
        </div>
        <div className="border-t border-gray-700 px-8 py-4 flex justify-between items-center">
          <button
            className="text-red-400 hover:text-red-600 font-medium flex items-center gap-1"
            onClick={logout}
          >
            <span className="text-lg">⎋</span> 退出登录
          </button>
        </div>
      </div>
      {/* 删除确认弹窗 */}
      <ConfirmDialog
        open={confirmDeleteOpen}
        title="删除项目"
        description={deleteIsCurrent ? '确定要删除当前项目吗？删除后您将被重定向到项目列表页面。此操作不可恢复！' : '确定要删除该项目吗？此操作不可恢复！'}
        confirmText="删除"
        cancelText="取消"
        loading={deleteLoading}
        onCancel={() => {
          setConfirmDeleteOpen(false);
          setProjectToDelete(null);
        }}
        onConfirm={async () => {
          if (!projectToDelete) return;
          setDeleteLoading(true);
          try {
            await projectApi.deleteProject(projectToDelete.id);
            await refreshProjects();
            if (deleteIsCurrent) {
              onClose();
              navigate('/');
            }
          } catch {
            alert('删除失败');
          } finally {
            setDeleteLoading(false);
            setConfirmDeleteOpen(false);
            setProjectToDelete(null);
          }
        }}
      />
    </div>
  );
}
