import React, { useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Box, CircularProgress, Typography } from '@mui/material';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * 受保护路由组件
 * 如果用户已登录，渲染子组件
 * 如果用户未登录，重定向到登录页面
 * 如果正在加载，显示加载状态而不进行重定向
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  // 使用AuthContext获取认证状态和加载状态
  const { isAuthenticated, isLoading } = useAuth();
  
  // 记录组件的加载状态
  useEffect(() => {
    console.log('ProtectedRoute 状态:', { isLoading, isAuthenticated });
  }, [isLoading, isAuthenticated]);
  
  // 如果正在加载，显示加载状态 - 不进行任何重定向
  if (isLoading) {
    return (
      <Box sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        bgcolor: '#1e1e1e',
        color: '#eee'
      }}>
        <CircularProgress size={40} color="primary" />
        <Typography sx={{ mt: 2 }}>
          验证身份中...
        </Typography>
      </Box>
    );
  }
  
  // 只有在确定未认证时才重定向到登录页面
  if (!isAuthenticated) {
    console.log('未认证，重定向到登录页面');
    return <Navigate to="/login" replace />;
  }
  
  // 认证成功，渲染子组件
  return <>{children}</>;
};

export default ProtectedRoute;