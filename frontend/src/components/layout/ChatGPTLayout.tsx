import React, { useState } from 'react'
import { Outlet, useNavigate, useParams } from 'react-router-dom'
import { 
  MessageSquare,
  FileText,
  BarChart3,
  HelpCircle,
  Settings,
  Menu,
  X,
  Plus,
  ChevronLeft,
  Home
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'

interface SidebarItemProps {
  icon: React.ReactNode
  label: string
  active?: boolean
  onClick?: () => void
}

const SidebarItem: React.FC<SidebarItemProps> = ({ icon, label, active, onClick }) => {
  return (
    <Button
      variant={active ? "secondary" : "ghost"}
      className={cn(
        "w-full justify-start gap-3 px-3 py-2.5 h-auto font-normal",
        active ? "bg-accent text-accent-foreground" : "hover:bg-accent/50"
      )}
      onClick={onClick}
    >
      {icon}
      <span className="truncate">{label}</span>
    </Button>
  )
}

const ChatGPTLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const navigate = useNavigate()
  const { projectId } = useParams()
  const [currentPath, setCurrentPath] = useState(window.location.pathname)

  const navigationItems = [
    {
      icon: <MessageSquare size={18} />,
      label: '智能对话',
      path: `/project/${projectId}/chat`,
      id: 'chat'
    },
    {
      icon: <FileText size={18} />,
      label: '文件管理',
      path: `/project/${projectId}/files`,
      id: 'files'
    },
    {
      icon: <BarChart3 size={18} />,
      label: '知识图谱',
      path: `/project/${projectId}/graph`,
      id: 'graph'
    },
    {
      icon: <HelpCircle size={18} />,
      label: '问题管理',
      path: `/project/${projectId}/questions`,
      id: 'questions'
    }
  ]

  const handleNavigation = (path: string) => {
    navigate(path)
    setCurrentPath(path)
  }

  const isActive = (path: string) => {
    return currentPath.includes(path) || window.location.pathname.includes(path)
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className={cn(
        "transition-all duration-300 ease-in-out border-r border-border",
        sidebarOpen ? "w-80" : "w-0"
      )}>
        {sidebarOpen && (
          <div className="flex flex-col h-full bg-card">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                  <span className="text-primary-foreground font-bold text-sm">Lumidoc</span>
                </div>
                <span className="font-semibold text-lg">智能平台</span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarOpen(false)}
                className="hover:bg-accent/50"
              >
                <X size={18} />
              </Button>
            </div>

            <ScrollArea className="flex-1 px-3 py-4">
              {/* New Chat Button */}
              <Button
                onClick={() => handleNavigation(`/project/${projectId}/chat`)}
                className="w-full mb-4 gap-2"
                size="sm"
              >
                <Plus size={16} />
                新建对话
              </Button>

              <Separator className="my-4" />

              {/* Navigation */}
              <div className="space-y-1">
                <div className="px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  功能导航
                </div>
                {navigationItems.map((item) => (
                  <SidebarItem
                    key={item.id}
                    icon={item.icon}
                    label={item.label}
                    active={isActive(item.path)}
                    onClick={() => handleNavigation(item.path)}
                  />
                ))}
              </div>

              <Separator className="my-4" />

              {/* Project Info */}
              <div className="px-2">
                <Card>
                  <CardContent className="p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center">
                        <span className="text-white text-xs font-bold">P</span>
                      </div>
                      <span className="font-medium text-sm">当前项目</span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      项目ID: {projectId}
                    </p>
                  </CardContent>
                </Card>
              </div>
            </ScrollArea>

            {/* Footer */}
            <div className="p-4 border-t border-border">
              <div className="flex items-center gap-3 mb-3">
                <Avatar className="w-8 h-8">
                  <AvatarImage src="" />
                  <AvatarFallback className="bg-primary text-primary-foreground text-sm">
                    用
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">用户</p>
                  <p className="text-xs text-muted-foreground">在线</p>
                </div>
                <Button variant="ghost" size="icon" className="hover:bg-accent/50">
                  <Settings size={16} />
                </Button>
              </div>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/')}
                className="w-full gap-2"
              >
                <Home size={14} />
                返回首页
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <div className="flex items-center gap-2 p-3 border-b border-border bg-card/50">
          {!sidebarOpen && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(true)}
              className="hover:bg-accent/50"
            >
              <Menu size={18} />
            </Button>
          )}
          
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/')}
              className="gap-1 px-2"
            >
              <ChevronLeft size={14} />
              项目列表
            </Button>
            <span>/</span>
            <span className="font-medium text-foreground">
              {projectId}
            </span>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-hidden bg-background">
          <Outlet />
        </div>
      </div>
    </div>
  )
}

export default ChatGPTLayout