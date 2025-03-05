// visual_workflow_editor/frontend/src/index.tsx
import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { I18nextProvider } from 'react-i18next';
import i18n from './i18n';
import { Box, CircularProgress, Typography } from '@mui/material';

// 简单的加载指示器组件
const LoadingIndicator = () => (
  <Box sx={{ 
    display: 'flex', 
    flexDirection: 'column',
    alignItems: 'center', 
    justifyContent: 'center', 
    height: '100vh' 
  }}>
    <CircularProgress size={50} />
    <Typography sx={{ mt: 2 }}>
      {i18n.language === 'zh' ? '加载中...' : 'Loading...'}
    </Typography>
  </Box>
);

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('Failed to find the root element');

// 初始化 i18n 后再渲染应用
const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <Suspense fallback={<LoadingIndicator />}>
      <I18nextProvider i18n={i18n}>
        <App />
      </I18nextProvider>
    </Suspense>
  </React.StrictMode>
);