// visual_workflow_editor/frontend/src/App.tsx
import React from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import { Container, Box } from '@mui/material';
import FlowEditorWrapper from './components/FlowEditor';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { SnackbarProvider } from 'notistack';
// 导入组件
import Register from './components/Register';
import Login from './components/Login';
import Submit from './components/Submit';
import ProtectedRoute from './components/ProtectedRoute';
import NavBar from './components/NavBar';

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
const App: React.FC = () => {
  const { t } = useTranslation();
  const isAuthenticated = localStorage.getItem('access_token') !== null; // 获取登录状态

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <SnackbarProvider maxSnack={3}>
        <Router>
          <NavBar />
          <Container maxWidth="xl" sx={{ mt: 2 }}>
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
          </Container>
        </Router>
      </SnackbarProvider>
    </ThemeProvider>
  );
};

export default App;