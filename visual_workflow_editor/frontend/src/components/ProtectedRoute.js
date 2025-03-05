import React from 'react';
import { Navigate } from 'react-router-dom';
import PropTypes from 'prop-types';

/**
 * 受保护路由组件
 * 如果用户已登录，渲染子组件
 * 如果用户未登录，重定向到登录页面
 */
const ProtectedRoute = ({ children }) => {
  // 检查localStorage中是否存在token
  const isAuthenticated = localStorage.getItem('access_token') !== null;
  
  // 如果未认证，重定向到登录页面
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // 否则渲染子组件
  return children;
};

ProtectedRoute.propTypes = {
  children: PropTypes.node.isRequired,
};

export default ProtectedRoute;