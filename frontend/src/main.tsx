import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/app.css'
import App from './App.tsx'

// 导入安全日志工具，自动处理生产环境日志禁用
import './utils/logger'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
