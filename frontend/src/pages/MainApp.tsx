import { Outlet } from 'react-router-dom';
import MainLayout from '@/components/layout/MainLayout';

export function MainApp() {
  return (
    <MainLayout>
      {/* 使用 Outlet 来渲染子路由组件 */}
      <Outlet />
    </MainLayout>
  );
}