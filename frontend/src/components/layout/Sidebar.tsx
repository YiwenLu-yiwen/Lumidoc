import { Link, useLocation, useParams } from 'react-router-dom'
import { FileText, MessageSquare, Network, BookOpen, ChevronsLeft, ChevronsRight } from 'lucide-react'
import { useState } from 'react'

export default function Sidebar() {
  const { projectId } = useParams()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  const navigation = [
    { name: '文件管理', href: projectId ? `/project/${projectId}/files` : '#', icon: FileText },
    { name: '知识图谱', href: projectId ? `/project/${projectId}/graph` : '#', icon: Network },
    { name: '聊天', href: projectId ? `/project/${projectId}/chat` : '#', icon: MessageSquare },
    { name: '出题', href: projectId ? `/project/${projectId}/questions` : '#', icon: BookOpen },
  ]

  return (
    <div className={`transition-all duration-200 ${collapsed ? 'w-16' : 'w-64'} bg-[#18181b] text-gray-200 shadow h-full flex flex-col`}>
      <div className="flex items-center justify-end p-2">
        <button
          className="text-gray-500 hover:text-white focus:outline-none"
          onClick={() => setCollapsed(v => !v)}
        >
          {collapsed ? <ChevronsRight className="w-6 h-6" /> : <ChevronsLeft className="w-6 h-6" />}
        </button>
      </div>
      <nav className="mt-2 px-2 flex-1">
        <div className="space-y-1">
          {navigation.map(item => {
            const isActive = location.pathname === item.href
            const isDisabled = !projectId || item.href === '#'
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`group flex items-center px-2 py-2 text-base font-medium rounded-md transition-all duration-200 ${
                  isActive
                    ? 'bg-[#26262b] text-white'
                    : isDisabled
                      ? 'text-gray-600 cursor-not-allowed'
                      : 'text-gray-300 hover:bg-[#232325] hover:text-white'
                }`}
                tabIndex={isDisabled ? -1 : 0}
                aria-disabled={isDisabled}
                onClick={e => {
                  if (isDisabled) e.preventDefault()
                }}
              >
                <item.icon
                  className={`mr-3 h-6 w-6 ${
                    isActive
                      ? 'text-white'
                      : isDisabled
                        ? 'text-gray-600'
                        : 'text-gray-400 group-hover:text-white'
                  }`}
                />
                {!collapsed && item.name}
              </Link>
            )
          })}
        </div>
      </nav>
    </div>
  )
} 