import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useState } from 'react'
import AuthModal from '@/components/ui/AuthModal'
import ModernAccountModal from '@/components/ui/ModernAccountModal'
import { useTheme } from '@/context/ThemeContext'

export default function Header() {
  const { user } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showAccountModal, setShowAccountModal] = useState(false);

  // 检测当前主题
  const { isDarkMode } = useTheme();

  const getDisplayName = (currentUser: NonNullable<typeof user>) => {
    return currentUser.nickname || `用户${currentUser.id.toString().padStart(6, '0')}`;
  };

  return (
    <header className={`shadow w-full transition-colors duration-300 ${
      isDarkMode ? 'bg-[#343541]' : 'bg-white'
    }`}>
      <div className="w-full flex justify-between items-center px-6 h-16">
        <Link to="/" className={`text-xl font-bold transition-colors ${
          isDarkMode ? 'text-white' : 'text-gray-900'
        }`}>
          Lumidoc WebUI
        </Link>
        <div className="flex items-center">
          {user ? (
            <button
              className={`px-4 py-2 rounded transition-colors ${
                isDarkMode
                  ? 'bg-gray-700 text-white hover:bg-gray-600'
                  : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
              }`}
              onClick={() => setShowAccountModal(true)}
            >
              {getDisplayName(user)}
            </button>
          ) : (
            <button
              className={`px-4 py-2 rounded transition-colors ${
                isDarkMode
                  ? 'bg-gray-700 text-white hover:bg-gray-600'
                  : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
              }`}
              onClick={() => setShowAuthModal(true)}
            >
              登录/注册
            </button>
          )}
        </div>
      </div>
      <AuthModal open={showAuthModal} onClose={() => setShowAuthModal(false)} />
      <ModernAccountModal open={showAccountModal} onClose={() => setShowAccountModal(false)} />
    </header>
  )
}
