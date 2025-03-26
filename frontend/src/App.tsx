// visual_workflow_editor/frontend/src/App.tsx
import React from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import { Container, Box, CircularProgress, Typography } from '@mui/material';
import FlowEditorWrapper from './components/FlowEditor';
import FlowLoader from './components/FlowLoader';
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
import SelectPage from './components/SelectPage';
// 导入认证上下文
import { AuthProvider, useAuth } from './contexts/AuthContext';
// 导入流程图上下文
import { FlowProvider } from './contexts/FlowContext';

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
  const { isAuthenticated, isLoading } = useAuth();

  // 当认证状态正在加载时，显示加载内容
  if (isLoading) {
    return (
      <Box sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '80vh'
      }}>
        <CircularProgress size={40} />
        <Typography sx={{ mt: 2 }}>
          加载中...
        </Typography>
      </Box>
    );
  }

  return (
    <Routes>
      {/* 根路径根据登录状态重定向 - 避免中间跳转 */}
      <Route path="/" element={isAuthenticated ? <Navigate to="/select" replace /> : <Navigate to="/login" replace />} />

      {/* 公开路由 - 登录、注册和提交，已登录用户重定向到 /select */}
      <Route path="/register" element={isAuthenticated ? <Navigate to="/select" replace /> : <Register />} />
      <Route path="/login" element={isAuthenticated ? <Navigate to="/select" replace /> : <Login />} />
      <Route path="/submit" element={<Submit />} />

      {/* 流程图选择页面 - 需要登录 */}
      <Route
        path="/select"
        element={
          <ProtectedRoute>
            <SelectPage />
          </ProtectedRoute>
        }
      />

      {/* 流程图编辑页面 - 需要登录且需要指定流程图ID */}
      <Route
        path="/flow"
        element={
          <ProtectedRoute>
            <FlowLoader />
          </ProtectedRoute>
        }
      />
      <Route
        path="/flow/:flowId"
        element={
          <ProtectedRoute>
            <FlowLoader />
          </ProtectedRoute>
        }
      />

      {/* 所有其他路由重定向 - 根据登录状态决定去向 */}
      <Route path="*" element={isAuthenticated ? <Navigate to="/select" replace /> : <Navigate to="/login" replace />} />
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
            <FlowProvider>
              <Container
                maxWidth={false}
                disableGutters
                sx={{
                  mt: 0,
                  p: 0,
                  height: '100vh',
                  width: '100vw',
                  overflow: 'hidden'
                }}
              >
                <AppRoutes />
              </Container>
            </FlowProvider>
          </AuthProvider>
        </Router>
      </SnackbarProvider>
    </ThemeProvider>
  );
};

export default App;