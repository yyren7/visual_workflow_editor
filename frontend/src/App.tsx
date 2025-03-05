// visual_workflow_editor/frontend/src/App.tsx
import React from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import { Container, Box } from '@mui/material';
import FlowEditorWrapper from './components/FlowEditor';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import i18n from './i18n';
import { SnackbarProvider } from 'notistack';
// 导入组件
import Register from './components/Register';
import Login from './components/Login';
import Submit from './components/Submit';
import ProtectedRoute from './components/ProtectedRoute';
import NavBar from './components/NavBar';
// 导入认证上下文
import { AuthProvider, useAuth } from './contexts/AuthContext';

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
  },
});

/**
 * App Component
 *
 * This is the main application component that sets up routing and the overall layout.
 */
// 分离路由逻辑以便使用useAuth
const AppRoutes: React.FC = () => {
  // 使用直接访问i18n而非useTranslation
  const t = (key: string) => i18n.t(key);
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      {/* 根路径根据登录状态重定向 */}
      <Route path="/" element={isAuthenticated ? <Navigate to="/flow" replace /> : <Navigate to="/login" replace />} />

      {/* 公开路由 - 登录、注册和提交，已登录用户重定向到 /flow */}
      <Route path="/register" element={isAuthenticated ? <Navigate to="/flow" replace /> : <Register />} />
      <Route path="/login" element={isAuthenticated ? <Navigate to="/flow" replace /> : <Login />} />
      <Route path="/submit" element={<Submit />} />

      {/* 受保护的路由 - 需要登录 */}
      <Route path="/flow" element={
        <ProtectedRoute>
          <FlowEditorWrapper />
        </ProtectedRoute>
      } />
      <Route path="/flow/:flowId" element={
        <ProtectedRoute>
          <FlowEditorWrapper />
        </ProtectedRoute>
      } />

      {/* 所有其他路由重定向到登录页面 */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
};

const App: React.FC = () => {
  // 使用i18n直接访问
  const t = (key: string) => i18n.t(key);

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <SnackbarProvider maxSnack={3}>
        <Router>
          <AuthProvider>
            <NavBar />
            <Container maxWidth="xl" sx={{ mt: 2 }}>
              <AppRoutes />
            </Container>
          </AuthProvider>
        </Router>
      </SnackbarProvider>
    </ThemeProvider>
  );
};

export default App;