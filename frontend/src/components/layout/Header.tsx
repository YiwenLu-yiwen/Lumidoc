import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useState } from 'react'
import AuthModal from '@/components/ui/AuthModal'
import AccountModal from '@/components/ui/AccountModal'

export default function Header() {
  const { user } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showAccountModal, setShowAccountModal] = useState(false);

  const getDisplayName = (user: any) => {
    if (!user) return "登录/注册";
    return user.nickname || `用户${user.id.toString().padStart(6, '0')}`;
  };

  return (
    <header className="bg-[#232325] shadow w-full">
      <div className="w-full flex justify-between items-center px-6 h-16">
        <Link to="/" className="text-xl font-bold text-white">
          Lumidoc WebUI
        </Link>
        <div className="flex items-center">
          {user ? (
            <button
              className="px-4 py-2 bg-[#18181b] text-white rounded hover:bg-[#26262b]"
              onClick={() => setShowAccountModal(true)}
            >
              {getDisplayName(user)}
            </button>
          ) : (
            <button
              className="px-4 py-2 bg-[#18181b] text-white rounded hover:bg-[#26262b]"
              onClick={() => setShowAuthModal(true)}
            >
              登录/注册
            </button>
          )}
        </div>
      </div>
      <AuthModal open={showAuthModal} onClose={() => setShowAuthModal(false)} />
      <AccountModal open={showAccountModal} onClose={() => setShowAccountModal(false)} />
    </header>
  )
} 