import React, { useState } from 'react';
import { Box, Typography, Button, AppBar, Toolbar } from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import { useAuth } from '../contexts/AuthContext';
import FlowSelect from './FlowSelect';
import { useTranslation } from 'react-i18next';
import LanguageSelector from './LanguageSelector';
import VersionInfo from './VersionInfo';

/**
 * SelectPage组件
 * 
 * 作为流程图选择页面的容器，当用户没有流程图时显示
 * 只允许用户选择流程图和登出
 */
const SelectPage: React.FC = () => {
  const { t } = useTranslation();
  const { logout, isAuthenticated } = useAuth();
  const [flowSelectOpen, setFlowSelectOpen] = useState(true);

  // 确保流程图选择对话框始终打开
  React.useEffect(() => {
    if (!flowSelectOpen) {
      setFlowSelectOpen(true);
    }
  }, [flowSelectOpen]);

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
          {t('selectPage.instruction', '请选择一个现有流程图或创建新的流程图开始使用。')}
        </Typography>
        <Button
          variant="contained"
          color="primary"
          size="large"
          onClick={() => setFlowSelectOpen(true)}
        >
          {t('selectPage.selectFlow', '选择流程图')}
        </Button>
      </Box>

      {/* 版本信息 */}
      <Box sx={{ position: 'fixed', right: '10px', bottom: '10px' }}>
        <VersionInfo />
      </Box>

      {/* 流程图选择对话框 */}
      <FlowSelect
        open={flowSelectOpen}
        onClose={() => {}} // 空函数，防止对话框关闭
      />
    </Box>
  );
};

export default SelectPage; 