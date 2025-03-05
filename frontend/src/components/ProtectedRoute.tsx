import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * 受保护路由组件
 * 如果用户已登录，渲染子组件
 * 如果用户未登录，重定向到登录页面
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  // 使用AuthContext获取认证状态
  const { isAuthenticated } = useAuth();
  
  // 如果未认证，重定向到登录页面
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // 否则渲染子组件
  return <>{children}</>;
};

export default ProtectedRoute;