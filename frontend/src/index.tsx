// visual_workflow_editor/frontend/src/index.tsx
import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import App from './App';
import { I18nextProvider } from 'react-i18next';
import i18n from './i18n';
import './index.css';
import './styles/performance-optimizations.css';
import { Box, CircularProgress, Typography } from '@mui/material';
import { store } from './store/store';

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

// Render without StrictMode for debugging draggable issue
const root = ReactDOM.createRoot(rootElement);
root.render(
  <Provider store={store}>
    <Suspense fallback={<LoadingIndicator />}>
      <I18nextProvider i18n={i18n}>
        <App />
      </I18nextProvider>
    </Suspense>
  </Provider>
);