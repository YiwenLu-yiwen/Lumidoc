import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Plus, 
  Folder, 
  Trash2, 
  Edit2, 
  Check, 
  X, 
  Search,
  Users,
  MoreHorizontal,
  FolderOpen,
  Archive,
  Star,
  Clock
} from 'lucide-react'
import { projectApi, Project } from '@/api/project'
import { useAuth, ProjectAccessLevel } from '@/context/AuthContext'
import AuthModal from '@/components/ui/AuthModal'
import { useProjects } from '@/context/ProjectContext'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getTranslation, detectBrowserLanguage } from '@/utils/language'
import { useTheme } from '@/context/ThemeContext'

export default function ProjectSelect() {
  const [projectName, setProjectName] = useState('')
  const { projects, loading: projectsLoading, error: projectsError, refreshProjects } = useProjects()
  const [loading, setLoading] = useState(false)
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null)
  const [editingProjectName, setEditingProjectName] = useState('')
  const [error, setError] = useState('')
  const [showProjects, setShowProjects] = useState(true)
  const [showAuth, setShowAuth] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const navigate = useNavigate()
  const { user, updateUserProjectAccess } = useAuth()
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [projectToDelete, setProjectToDelete] = useState<string | null>(null)

  // 主题和语言检测
  const { isDarkMode } = useTheme()
  const currentLanguage = detectBrowserLanguage()
  const t = (key: keyof typeof import('@/utils/language').translations['zh-CN']) => 
    getTranslation(currentLanguage, key)

  const isProjectNameExists = (name: string, excludeId?: string) => {
    return projects.some(project => 
      project.name.toLowerCase() === name.toLowerCase() && 
      project.id !== excludeId
    )
  }

  const handleCreateProject = async () => {
    if (!projectName.trim()) {
      setError('项目名称不能为空')
      return
    }
    if (isProjectNameExists(projectName)) {
      setError('项目名称已存在')
      return
    }
    try {
      setLoading(true)
      setError('')
      console.log('Creating project:', { name: projectName })
      const response = await projectApi.createProject({ name: projectName })
      console.log('Project created successfully:', response)
      
      // 创建项目后，立即更新用户对该项目的权限
      if (response && response.id) {
        console.log(`为用户设置新创建项目(${response.id})的OWNER权限`)
        
        // 设置为OWNER权限
        updateUserProjectAccess(response.id, ProjectAccessLevel.OWNER)
        
        // 更新本地存储的项目权限
        try {
          const storedPermissions = localStorage.getItem('stp_project_permissions')
          const permissions = storedPermissions ? JSON.parse(storedPermissions) : {}
          
          // 添加新项目的权限
          permissions[response.id] = ProjectAccessLevel.OWNER
          
          // 保存回本地存储
          localStorage.setItem('stp_project_permissions', JSON.stringify(permissions))
          console.log(`已更新本地存储的项目权限，添加项目: ${response.id}`)
          
          // 完全同步本地存储的项目权限到项目详情缓存
          try {
            const projectsJson = localStorage.getItem('stp_projects') || '[]'
            const projects = JSON.parse(projectsJson)
            
            // 确保新项目添加到缓存
            const projectExists = projects.some((p: any) => p.id === response.id)
            if (!projectExists) {
              projects.push({
                id: response.id,
                name: projectName,
                creator_id: user?.id,
                created_at: new Date().toISOString()
              })
              localStorage.setItem('stp_projects', JSON.stringify(projects))
              console.log(`已更新本地项目缓存，添加项目: ${response.id}`)
            }
          } catch (e) {
            console.error('更新本地项目缓存失败:', e)
          }
        } catch (e) {
          console.error('更新本地项目权限失败:', e)
        }
        
        // 清空项目名称输入框
        setProjectName('')
        
        // 更新项目列表并等待完成
        await refreshProjects()
        
        // 创建成功提示
        try {
          const toast = document.createElement('div')
          toast.className = 'fixed bottom-4 right-4 bg-green-600 text-white px-4 py-2 rounded shadow-lg'
          toast.textContent = `项目"${projectName}"创建成功！`
          document.body.appendChild(toast)
          setTimeout(() => {
            document.body.removeChild(toast)
            // 只有在toast消失后才进行导航
            const projectPageUrl = `/project/${response.id}`
            console.log(`即将导航到项目页面: ${projectPageUrl}`)
            navigate(projectPageUrl)
          }, 2000)
        } catch (e) {
          console.error('显示提示失败:', e)
          // 延时导航到项目页面，确保权限更新完成
          setTimeout(() => {
            const projectPageUrl = `/project/${response.id}`
            console.log(`即将导航到项目页面: ${projectPageUrl}`)
            navigate(projectPageUrl)
          }, 2000)
        }
      }
    } catch (error: any) {
      console.error('Failed to create project:', error)
      const errorMessage = error.response?.data?.detail || error.message || '创建项目失败'
      console.error('Error details:', errorMessage)
      setError(`创建项目失败: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectProject = (projectId: string) => {
    try {
      // 检查是否已经在导航中，避免重复导航
      const navigatingStatus = sessionStorage.getItem('navigating_to_project');
      if (navigatingStatus === projectId) {
        console.log(`[ProjectSelect] 正在导航到项目: ${projectId}，避免重复导航`);
        return;
      }
      
      // 设置导航状态
      sessionStorage.setItem('navigating_to_project', projectId);
      
      // 确保此项目有权限记录
      const storedPermissions = localStorage.getItem('stp_project_permissions');
      const permissions = storedPermissions ? JSON.parse(storedPermissions) : {};
      
      // 如果权限缓存中没有此项目，添加基本权限
      if (!permissions[projectId]) {
        console.log(`[ProjectSelect] 为项目(${projectId})添加默认查看权限`);
        permissions[projectId] = ProjectAccessLevel.VIEWER;
        localStorage.setItem('stp_project_permissions', JSON.stringify(permissions));
        
        // 同时更新用户对象的权限
        updateUserProjectAccess(projectId, ProjectAccessLevel.VIEWER);
      }
      
      // 添加项目访问记录，避免重复验证
      sessionStorage.setItem(`visited_project_${projectId}`, 'true');
      
      // 使用带替换的导航，防止返回循环
      console.log(`[ProjectSelect] 导航到项目: ${projectId}`);
      navigate(`/project/${projectId}`, { replace: false });
      
      // 清除导航状态（延迟执行，确保导航完成）
      setTimeout(() => {
        sessionStorage.removeItem('navigating_to_project');
      }, 2000);
    } catch (error) {
      console.error(`[ProjectSelect] 导航到项目(${projectId})失败:`, error);
      // 清除导航状态，避免卡死
      sessionStorage.removeItem('navigating_to_project');
    }
  }

  const handleDeleteClick = (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setProjectToDelete(projectId)
    setDeleteDialogOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!projectToDelete) return
    try {
      await projectApi.deleteProject(projectToDelete)
      await refreshProjects()
      setDeleteDialogOpen(false)
      setProjectToDelete(null)
    } catch (error) {
      console.error('Failed to delete project:', error)
    }
  }

  const handleStartEdit = (project: Project, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingProjectId(project.id)
    setEditingProjectName(project.name)
    setError('')
  }

  const handleCancelEdit = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation && e.stopPropagation();
    setEditingProjectId(null)
    setEditingProjectName('')
    setError('')
  }

  const handleSaveEdit = async (projectId: string, e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation && e.stopPropagation();
    if (!editingProjectName.trim()) {
      setError('项目名称不能为空')
      return
    }
    if (isProjectNameExists(editingProjectName, projectId)) {
      setError('项目名称已存在')
      return
    }
    try {
      setError('')
      await projectApi.updateProject(projectId, { name: editingProjectName })
      await refreshProjects()
      setEditingProjectId(null)
      setEditingProjectName('')
    } catch (error) {
      console.error('Failed to update project:', error)
      setError('更新项目失败')
    }
  }

  // 过滤项目
  const filteredProjects = projects.filter(project =>
    project.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <div className={`h-full overflow-y-auto transition-colors duration-300 ${
      isDarkMode ? 'bg-[#212121] text-gray-100' : 'bg-white text-gray-900'
    }`}>
      <div className="max-w-7xl mx-auto p-6 space-y-8">
        {/* 页面标题和操作 */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className={`text-3xl font-bold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              {t('projectManagement')}
            </h1>
            <p className={`text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {t('createAndManageWorkspaces')}
            </p>
          </div>
        </div>

        {user ? (
          <>
            {/* 搜索和筛选 */}
            <div className={`p-6 rounded-2xl border ${
              isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
            }`}>
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <Input
                    placeholder={currentLanguage === 'zh-CN' ? '搜索项目...' : 'Search projects...'}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>
            </div>

            {/* 创建新项目区域 */}
            <div className={`p-6 rounded-2xl border-2 border-dashed transition-colors ${
              isDarkMode 
                ? 'border-gray-600 bg-gray-800/50 hover:border-blue-500' 
                : 'border-gray-300 bg-gray-50 hover:border-blue-400'
            }`}>
              <div className="text-center">
                <FolderOpen className={`w-12 h-12 mx-auto mb-4 ${
                  isDarkMode ? 'text-gray-400' : 'text-gray-500'
                }`} />
                <h3 className={`text-lg font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  {currentLanguage === 'zh-CN' ? '创建新项目' : 'Create New Project'}
                </h3>
                <p className={`text-sm mb-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                  {currentLanguage === 'zh-CN' 
                    ? '开始一个新的智能项目工作空间'
                    : 'Start a new intelligent project workspace'
                  }
                </p>
                <div className="max-w-md mx-auto space-y-3">
                  <Input
                    placeholder={currentLanguage === 'zh-CN' ? '输入项目名称' : 'Enter project name'}
                    value={projectName}
                    onChange={(e) => {
                      setProjectName(e.target.value)
                      setError('')
                    }}
                  />
                  {error && (
                    <p className="text-sm text-red-500">{error}</p>
                  )}
                  <Button
                    onClick={handleCreateProject}
                    disabled={loading || !projectName.trim()}
                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0"
                  >
                    {loading 
                      ? (currentLanguage === 'zh-CN' ? '创建中...' : 'Creating...')
                      : (currentLanguage === 'zh-CN' ? '创建项目' : 'Create Project')
                    }
                  </Button>
                </div>
              </div>
            </div>

            {/* 项目列表 */}
            <div className={`rounded-2xl border ${
              isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
            }`}>
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <h2 className={`text-xl font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                    {currentLanguage === 'zh-CN' ? '我的项目' : 'My Projects'}
                  </h2>
                  <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    {currentLanguage === 'zh-CN' 
                      ? `共 ${filteredProjects.length} 个项目`
                      : `${filteredProjects.length} projects total`
                    }
                  </span>
                </div>
              </div>

              <div className="p-6">
                {projectsLoading ? (
                  <div className="text-center py-12">
                    <div className={`inline-block animate-spin rounded-full h-8 w-8 border-b-2 ${
                      isDarkMode ? 'border-blue-400' : 'border-blue-600'
                    }`}></div>
                    <p className={`mt-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                      {currentLanguage === 'zh-CN' ? '加载项目中...' : 'Loading projects...'}
                    </p>
                  </div>
                ) : projectsError ? (
                  <div className={`text-center py-12 ${
                    isDarkMode ? 'bg-red-900/20 border border-red-800' : 'bg-red-50 border border-red-200'
                  } rounded-lg`}>
                    <p className={`mb-4 ${isDarkMode ? 'text-red-300' : 'text-red-700'}`}>
                      {currentLanguage === 'zh-CN' 
                        ? `加载项目失败：${projectsError}`
                        : `Failed to load projects: ${projectsError}`
                      }
                    </p>
                    <Button
                      onClick={refreshProjects}
                      variant="outline"
                      size="sm"
                    >
                      {currentLanguage === 'zh-CN' ? '重新加载' : 'Reload'}
                    </Button>
                  </div>
                ) : filteredProjects.length === 0 ? (
                  <div className="text-center py-12">
                    <Archive className={`w-16 h-16 mx-auto mb-4 ${
                      isDarkMode ? 'text-gray-600' : 'text-gray-400'
                    }`} />
                    <h3 className={`text-lg font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                      {searchQuery 
                        ? (currentLanguage === 'zh-CN' ? '未找到匹配的项目' : 'No matching projects found')
                        : (currentLanguage === 'zh-CN' ? '暂无项目' : 'No projects')
                      }
                    </h3>
                    <p className={`${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                      {searchQuery 
                        ? (currentLanguage === 'zh-CN' ? '尝试调整搜索条件' : 'Try adjusting your search criteria')
                        : (currentLanguage === 'zh-CN' ? '创建您的第一个项目开始使用' : 'Create your first project to get started')
                      }
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredProjects.map((project) => (
                      <div
                        key={project.id}
                        className={`group relative p-6 rounded-xl border transition-all duration-200 cursor-pointer ${
                          editingProjectId === project.id
                            ? isDarkMode
                              ? 'border-blue-500 bg-blue-900/20'
                              : 'border-blue-500 bg-blue-50'
                            : isDarkMode
                              ? 'border-gray-700 hover:border-gray-600 hover:bg-gray-750'
                              : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                        }`}
                        onClick={() => !editingProjectId && handleSelectProject(project.id)}
                      >
                        {editingProjectId === project.id ? (
                          <div className="space-y-4" onClick={(e) => e.stopPropagation()}>
                            <Input
                              value={editingProjectName}
                              onChange={(e) => setEditingProjectName(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  handleSaveEdit(project.id, e);
                                } else if (e.key === 'Escape') {
                                  handleCancelEdit(e);
                                }
                              }}
                              autoFocus
                            />
                            <div className="flex space-x-2">
                              <Button
                                onClick={(e) => handleSaveEdit(project.id, e)}
                                size="sm"
                                className="flex-1"
                              >
                                <Check className="w-4 h-4 mr-2" />
                                {currentLanguage === 'zh-CN' ? '保存' : 'Save'}
                              </Button>
                              <Button
                                onClick={handleCancelEdit}
                                variant="outline"
                                size="sm"
                                className="flex-1"
                              >
                                <X className="w-4 h-4 mr-2" />
                                {currentLanguage === 'zh-CN' ? '取消' : 'Cancel'}
                              </Button>
                            </div>
                            {error && (
                              <p className="text-sm text-red-500">{error}</p>
                            )}
                          </div>
                        ) : (
                          <>
                            {/* 项目图标和标题 */}
                            <div className="flex items-start justify-between mb-4">
                              <div className="flex items-center space-x-3">
                                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                                  isDarkMode ? 'bg-blue-600' : 'bg-blue-500'
                                }`}>
                                  <Folder className="w-6 h-6 text-white" />
                                </div>
                                <div>
                                  <h3 className={`font-semibold text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{project.name}</h3>
                                  <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                                    {currentLanguage === 'zh-CN' ? '项目ID' : 'Project ID'}: {String(project.id).slice(0, 8)}...
                                  </p>
                                </div>
                              </div>
                              
                              {/* 操作按钮 */}
                              <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center space-x-1">
                                <button
                                  onClick={(e) => handleStartEdit(project, e)}
                                  className={`p-2 rounded-lg transition-colors ${
                                    isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-200'
                                  }`}
                                >
                                  <Edit2 className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={(e) => handleDeleteClick(project.id, e)}
                                  className={`p-2 rounded-lg transition-colors ${
                                    isDarkMode ? 'hover:bg-red-900/30 text-red-400' : 'hover:bg-red-50 text-red-600'
                                  }`}
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                            </div>

                            {/* 项目信息 */}
                            <div className="space-y-3">
                              <div className="flex items-center space-x-4 text-sm">
                                <div className="flex items-center space-x-1">
                                  <Clock className="w-4 h-4 text-gray-400" />
                                  <span className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>
                                    {formatDate(project.created_at)}
                                  </span>
                                </div>
                                <div className="flex items-center space-x-1">
                                  <Users className="w-4 h-4 text-gray-400" />
                                  <span className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>
                                    {currentLanguage === 'zh-CN' ? '个人项目' : 'Personal Project'}
                                  </span>
                                </div>
                              </div>
                              
                              <div className={`text-sm p-3 rounded-lg ${
                                isDarkMode ? 'bg-gray-700' : 'bg-gray-100'
                              }`}>
                                <p className={isDarkMode ? 'text-gray-300' : 'text-gray-700'}>
                                  {currentLanguage === 'zh-CN' 
                                    ? '点击进入项目工作空间，开始智能对话和文档处理'
                                    : 'Click to enter project workspace and start intelligent conversations and document processing'
                                  }
                                </p>
                              </div>
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          /* 未登录状态 */
          <div className={`text-center py-20 ${
            isDarkMode ? 'bg-gray-800' : 'bg-gray-50'
          } rounded-2xl`}>
            <Users className={`w-16 h-16 mx-auto mb-4 ${
              isDarkMode ? 'text-gray-600' : 'text-gray-400'
            }`} />
            <h2 className={`text-2xl font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              {currentLanguage === 'zh-CN' ? '需要登录' : 'Login Required'}
            </h2>
            <p className={`text-lg mb-6 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {currentLanguage === 'zh-CN' 
                ? '请登录或注册账号后访问项目管理功能'
                : 'Please login or register to access project management features'
              }
            </p>
            <Button
              onClick={() => setShowAuth(true)}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0"
            >
              {currentLanguage === 'zh-CN' ? '登录/注册' : 'Login/Register'}
            </Button>
          </div>
        )}
      </div>

      {/* 认证模态框 */}
      <AuthModal 
        open={showAuth} 
        onClose={() => setShowAuth(false)} 
      />

      {/* 删除确认对话框 */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className={`sm:max-w-md ${
          isDarkMode ? 'bg-gray-800 text-white' : 'bg-white text-gray-900'
        }`}>
          <DialogHeader>
            <DialogTitle className={isDarkMode ? 'text-white' : 'text-gray-900'}>
              {currentLanguage === 'zh-CN' ? '确认删除项目' : 'Confirm Delete Project'}
            </DialogTitle>
            <DialogDescription className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>
              {currentLanguage === 'zh-CN' 
                ? '此操作无法撤销，项目及其所有相关资源将被永久删除。'
                : 'This action cannot be undone. The project and all its related resources will be permanently deleted.'
              }
            </DialogDescription>
          </DialogHeader>
          <div className="pt-2 pb-4">
            <p className={isDarkMode ? 'text-gray-300' : 'text-gray-700'}>
              {currentLanguage === 'zh-CN' 
                ? '您确定要删除这个项目吗？'
                : 'Are you sure you want to delete this project?'
              }
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              className={isDarkMode ? 'border-gray-600 text-gray-300 hover:text-white' : ''}
            >
              {currentLanguage === 'zh-CN' ? '取消' : 'Cancel'}
            </Button>
            <Button
              variant="default"
              onClick={handleConfirmDelete}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {currentLanguage === 'zh-CN' ? '确认删除' : 'Confirm Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
} 