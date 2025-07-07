import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Button, AppBar, Toolbar, CircularProgress } from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import { useAuth } from '../contexts/AuthContext';
import FlowSelect from './FlowSelect';
import { useTranslation } from 'react-i18next';
import LanguageSelector from './LanguageSelector';
import VersionInfo from './VersionInfo';
import { useFlowData } from './FlowSelect/useFlowData';

/**
 * SelectPage组件
 * 
 * 作为流程图选择页面的容器，当用户没有流程图时显示
 * 只允许用户选择流程图和登出
 */
const SelectPage: React.FC = () => {
  const { t } = useTranslation();
  const { logout, isAuthenticated } = useAuth();
  const [flowSelectOpen, setFlowSelectOpen] = useState(false);
  const { flows, loading } = useFlowData();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading) {
      if (flows && flows.length > 0) {
        // 如果有流程图，重定向到最新的一个
        navigate(`/flow/${flows[0].id}`);
      } else {
        // 如果没有流程图，打开选择对话框
        setFlowSelectOpen(true);
      }
    }
  }, [loading, flows, navigate]);

  if (loading) {
    return (
      <Box sx={{
        height: '100vh',
        width: '100vw',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: '#1e1e1e',
      }}>
        <AppBar position="static" sx={{ bgcolor: '#1e1e1e', borderBottom: '1px solid #333' }}>
          <Toolbar sx={{ justifyContent: 'space-between' }}>
            <Typography variant="h6" component="div">
              {t('selectPage.title', '流程图编辑器')}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <LanguageSelector />
              {isAuthenticated && (
                <Button color="inherit" startIcon={<LogoutIcon />} onClick={logout}>
                  {t('nav.logout', '登出')}
                </Button>
              )}
            </Box>
          </Toolbar>
        </AppBar>
        <Box sx={{
          flexGrow: 1,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        }}>
          <CircularProgress />
          <Typography sx={{ ml: 2, color: 'white' }}>{t('flowSelect.loading', '加载流程列表中...')}</Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{
      height: '100vh',
      width: '100vw',
      display: 'flex',
      flexDirection: 'column',
      bgcolor: '#1e1e1e',
      color: 'white',
      overflow: 'hidden'
    }}>
      {/* 顶部导航栏，只包含登出功能 */}
      <AppBar position="static" sx={{ bgcolor: '#1e1e1e', borderBottom: '1px solid #333' }}>
        <Toolbar sx={{ justifyContent: 'space-between' }}>
          <Typography variant="h6" component="div">
            {t('selectPage.title', '流程图编辑器')}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <LanguageSelector />
            {isAuthenticated && (
              <Button
                color="inherit"
                startIcon={<LogoutIcon />}
                onClick={logout}
              >
                {t('nav.logout', '登出')}
              </Button>
            )}
          </Box>
        </Toolbar>
      </AppBar>

      {/* 主要内容区域 */}
      <Box sx={{
        flexGrow: 1,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        p: 3
      }}>
        <Typography variant="h4" gutterBottom>
          {t('selectPage.welcome', '欢迎使用流程图编辑器')}
        </Typography>
        <Typography variant="body1" sx={{ mb: 4, maxWidth: '600px', textAlign: 'center' }}>
          {t('selectPage.instruction', '您还没有任何流程图，请创建一个开始使用。')}
        </Typography>
        <Button
          variant="contained"
          color="primary"
          size="large"
          onClick={() => setFlowSelectOpen(true)}
        >
          {t('selectPage.createFlow', '创建新流程图')}
        </Button>
      </Box>

      {/* 版本信息 */}
      <Box sx={{ position: 'fixed', right: '10px', bottom: '10px' }}>
        <VersionInfo />
      </Box>

      {/* 流程图选择对话框 */}
      <FlowSelect
        open={flowSelectOpen}
        onClose={() => setFlowSelectOpen(false)}
      />
    </Box>
  );
};

export default SelectPage; 