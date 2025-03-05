// visual_workflow_editor/frontend/src/components/NavBar.tsx
import React, { useState, useEffect } from 'react';
import { 
  AppBar, 
  Toolbar, 
  Typography, 
  IconButton, 
  Button,
  Box,
  Menu,
  MenuItem,
  Divider
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import LanguageSelector from './LanguageSelector';

const NavBar: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  
  useEffect(() => {
    // 检查用户是否已登录
    const checkAuth = () => {
      const token = localStorage.getItem('access_token');
      setIsAuthenticated(!!token);
    };
    
    checkAuth();
    
    // 添加事件监听器以监听localStorage的变化
    window.addEventListener('storage', checkAuth);
    
    // 创建自定义事件监听器，监听登录状态变化
    const handleLoginChange = () => checkAuth();
    window.addEventListener('loginChange', handleLoginChange);
    
    return () => {
      window.removeEventListener('storage', checkAuth);
      window.removeEventListener('loginChange', handleLoginChange);
    };
  }, []);
  
  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  
  const handleMenuClose = () => {
    setAnchorEl(null);
  };
  
  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setIsAuthenticated(false);
    
    // 触发登录状态变化事件
    window.dispatchEvent(new Event('loginChange'));
    
    handleMenuClose();
    
    // 使用原生window.location替代React Router导航
    // 这避免了与React Router的导航组件和条件渲染之间的冲突
    window.location.href = '/login';
  };
  
  return (
    <AppBar position="static">
      <Toolbar>
        <IconButton
          size="large"
          edge="start"
          color="inherit"
          aria-label="menu"
          sx={{ mr: 2 }}
        >
          <MenuIcon />
        </IconButton>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          {t('nav.flowEditor')}
        </Typography>
        
        <LanguageSelector />
        
        {isAuthenticated ? (
          <>
            <IconButton
              color="inherit"
              onClick={handleMenuOpen}
              aria-controls="user-menu"
              aria-haspopup="true"
            >
              <AccountCircleIcon />
            </IconButton>
            <Menu
              id="user-menu"
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'right',
              }}
              transformOrigin={{
                vertical: 'top',
                horizontal: 'right',
              }}
            >
              <MenuItem onClick={() => {
                handleMenuClose();
                navigate('/flow');
              }}>
                {t('nav.flowEditor')}
              </MenuItem>
              <Divider />
              <MenuItem onClick={handleLogout}>{t('nav.logout')}</MenuItem>
            </Menu>
          </>
        ) : (
          <Box sx={{ display: 'flex' }}>
            <Button 
              color="inherit" 
              onClick={() => navigate('/login')}
              sx={{ mr: 1 }}
            >
              {t('nav.login')}
            </Button>
            <Button 
              color="inherit" 
              onClick={() => navigate('/register')}
            >
              {t('nav.register')}
            </Button>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default NavBar;