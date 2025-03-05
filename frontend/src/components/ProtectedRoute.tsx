import React from 'react';
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
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  // 使用AuthContext获取认证状态和加载状态
  const { isAuthenticated, isLoading } = useAuth();
  
  // 如果正在加载，显示加载状态
  if (isLoading) {
    return (
      <Box sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh'
      }}>
        <CircularProgress size={40} />
        <Typography sx={{ mt: 2 }}>
          验证中...
        </Typography>
      </Box>
    );
  }
  
  // 如果未认证，重定向到登录页面
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // 否则渲染子组件
  return <>{children}</>;
};

export default ProtectedRoute;